"""
rPPG service wrapping open-rppg (PhysMamba model).

open-rppg is imported lazily and the model is warmed up at app startup
via the lifespan handler in main.py. All inference happens synchronously
in a thread pool executor to avoid blocking the async event loop.
"""
from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import Any

import numpy as np

from app.utils.signal_utils import (
    downsample_waveform,
    normalize_signal,
    validate_bpm,
    estimate_confidence,
    welch_hr,
)
from app.services import bp_service, hrv_service, respiration_service, stress_service

logger = logging.getLogger(__name__)

# Module-level singleton — set during startup lifespan
_model: Any = None
_model_fps: float = 30.0  # rPPG-Toolbox default training FPS


def load_model() -> None:
    """Load PhysMamba model weights. Called once at startup."""
    global _model
    try:
        import rppg  # open-rppg package

        _model = rppg.Model("PhysMamba.pure")
        logger.info("PhysMamba model loaded successfully via open-rppg.")
    except Exception as e:
        logger.warning(f"open-rppg not available or model load failed ({e}). Falling back to CHROM baseline.")
        _model = None


def _run_inference(video_path: str) -> dict:
    """Run rPPG inference synchronously. Called in a thread pool."""
    if _model is not None:
        return _run_physmamba(video_path)
    else:
        return _run_chrom_fallback(video_path)


def _trim_video(video_path: str, max_seconds: float = 65.0) -> str:
    """
    If video is longer than max_seconds, write a trimmed copy and return its path.
    65s captures the full ~60s scan with margin; full-length video improves rPPG accuracy.
    """
    import cv2, tempfile, os
    cap = cv2.VideoCapture(video_path)
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    cap.release()

    max_frames = int(fps * max_seconds)
    if total_frames <= max_frames:
        return video_path  # already short enough

    cap = cv2.VideoCapture(video_path)
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    tmp = tempfile.NamedTemporaryFile(suffix=".mp4", delete=False)
    tmp.close()
    w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    out = cv2.VideoWriter(tmp.name, fourcc, fps, (w, h))
    written = 0
    while written < max_frames:
        ret, frame = cap.read()
        if not ret:
            break
        out.write(frame)
        written += 1
    cap.release()
    out.release()
    return tmp.name


def _reencode_keyframes(video_path: str) -> str:
    """
    Re-encode video to all-keyframes (intra-only) so PhysMamba can use every frame.
    Phone H.264 video typically has only ~3% key frames; PhysMamba skips the rest.
    Returns path to re-encoded file (temp); caller must delete if different from input.
    """
    import subprocess, tempfile, os
    tmp = tempfile.NamedTemporaryFile(suffix=".mp4", delete=False)
    tmp.close()
    try:
        result = subprocess.run(
            [
                "ffmpeg", "-y",
                "-i", video_path,
                "-vcodec", "libx264",
                "-x264-params", "keyint=1:scenecut=0",  # every frame is a keyframe
                "-crf", "18",          # near-lossless for signal quality
                "-preset", "fast",
                "-an",                 # drop audio — not needed for rPPG
                tmp.name,
            ],
            capture_output=True,
            timeout=120,
        )
        if result.returncode != 0:
            logger.warning(f"ffmpeg keyframe re-encode failed: {result.stderr[-200:].decode(errors='replace')}")
            os.unlink(tmp.name)
            return video_path  # fallback to original
        logger.info(f"Re-encoded to all-keyframes: {tmp.name}")
        return tmp.name
    except (FileNotFoundError, subprocess.TimeoutExpired) as e:
        logger.warning(f"ffmpeg not available for keyframe re-encode ({e}), using original.")
        try:
            os.unlink(tmp.name)
        except Exception:
            pass
        return video_path


def _run_physmamba(video_path: str) -> dict:
    """
    Inference via open-rppg PhysMamba model.
    Re-encodes to all-keyframes first so PhysMamba uses every frame (not just ~3%).
    process_video handles rotation metadata and face detection internally.
    """
    reencoded = _reencode_keyframes(video_path)
    try:
        result = _model.process_video(reencoded)
    finally:
        if reencoded != video_path:
            import os
            try:
                os.unlink(reencoded)
            except Exception:
                pass

    if result is None or result.get("hr") is None:
        raise RuntimeError(
            "PhysMamba could not detect a heart rate. "
            "Ensure the face is clearly visible and well-lit throughout the scan."
        )

    bpm = float(result["hr"])

    # Retrieve BVP waveform (populated in model state after process_video)
    try:
        bvp_arr, _ = _model.bvp()
        raw_signal = np.array(bvp_arr, dtype=np.float32) if len(bvp_arr) else np.array([])
        # pre-filter = raw BVP before internal bandpass — use same signal, model already normalises
        raw_prefilter = raw_signal.copy()
    except Exception:
        raw_signal = np.array([])
        raw_prefilter = np.array([])

    return {"bpm": bpm, "raw_signal": raw_signal, "raw_prefilter": raw_prefilter, "fps": _model.fps}


def _run_chrom_fallback(video_path: str) -> dict:
    """
    CHROM baseline — runs without any ML model.
    Used when open-rppg is not installed (dev/test mode).
    """
    import cv2
    from scipy.signal import butter, filtfilt
    from scipy.fft import fft, fftfreq

    trimmed = _trim_video(video_path)
    try:
        return _run_chrom_on_file(trimmed)
    finally:
        if trimmed != video_path:
            import os
            os.unlink(trimmed)


def _run_chrom_on_file(video_path: str) -> dict:
    import cv2
    from scipy.signal import butter, filtfilt
    from scipy.fft import fft, fftfreq

    cap = cv2.VideoCapture(video_path)
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))

    # Use center crop as face ROI — faster than per-frame face detection,
    # valid since app instructs user to keep face in the oval guide
    cy, cx = height // 2, width // 2
    rh, rw = height // 3, width // 3
    y1, y2 = cy - rh // 2, cy + rh // 2
    x1, x2 = cx - rw // 2, cx + rw // 2

    # Sample every 3rd frame — 10fps is sufficient for rPPG (HR 0.7–4Hz)
    step = 3
    rgb_means = []
    frame_idx = 0
    while cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            break
        if frame_idx % step == 0:
            roi = frame[y1:y2, x1:x2]
            rgb_means.append(roi.reshape(-1, 3).mean(axis=0)[::-1])  # BGR→RGB
        frame_idx += 1
    cap.release()

    effective_fps = fps / step
    if len(rgb_means) < effective_fps * 10:
        raise RuntimeError("Insufficient face frames for CHROM analysis.")

    rgb = np.array(rgb_means, dtype=np.float32)
    # Normalize
    norm = rgb / (rgb.mean(axis=0) + 1e-6)
    X = 3 * norm[:, 0] - 2 * norm[:, 1]
    Y = 1.5 * norm[:, 0] + norm[:, 1] - 1.5 * norm[:, 2]
    # Combine channels (raw, pre-filter) — used for honest confidence scoring
    raw_signal_prefilter = 3 * norm[:, 0] - 2 * norm[:, 1]  # X channel proxy

    # Bandpass 0.7–4 Hz
    b, a = butter(3, [0.7, 4.0], btype="bandpass", fs=effective_fps)
    Xf = filtfilt(b, a, X)
    Yf = filtfilt(b, a, Y)
    alpha = Xf.std() / (Yf.std() + 1e-6)
    signal = Xf - alpha * Yf

    # HR via Welch PSD — more robust than single FFT, especially with full 60s signal
    from scipy.signal import welch
    window_s = min(15.0, len(signal) / effective_fps * 0.5)
    nperseg = max(64, int(window_s * effective_fps))
    freqs_w, psd = welch(signal, fs=effective_fps, nperseg=nperseg, noverlap=nperseg // 2)
    valid_w = (freqs_w >= 0.7) & (freqs_w <= 4.0)
    peak_freq = freqs_w[valid_w][np.argmax(psd[valid_w])]
    bpm = float(peak_freq * 60)

    return {"bpm": bpm, "raw_signal": signal, "raw_prefilter": raw_signal_prefilter, "fps": effective_fps}


async def analyze_video(
    video_path: Path,
    age: int | None = None,
    sex: str | None = None,
    bmi: float | None = None,
) -> dict:
    """
    Async entry point: runs inference in a thread pool, then post-processes.
    Returns dict with keys: bpm, confidence, waveform, waveform_fps, sbp,
    dbp, bp_confidence. BP fields are None if estimation fails.
    """
    loop = asyncio.get_event_loop()
    raw = await loop.run_in_executor(None, _run_inference, str(video_path))

    bpm = validate_bpm(raw["bpm"])
    signal: np.ndarray = raw.get("raw_signal", np.array([]))
    # Use pre-filter signal for confidence — post-filter signal is always "clean"
    confidence_signal: np.ndarray = raw.get("raw_prefilter", signal)
    fps: float = raw.get("fps", _model_fps)

    if len(signal) > 0:
        confidence = estimate_confidence(confidence_signal, fps)
        # Independent HR cross-check from the BVP waveform. If the Welch
        # peak agrees with the model's HR → strong boost (both sources
        # agree). Big disagreement → knock confidence down, the primary
        # estimate may be tracking noise.
        welch_bpm = welch_hr(signal, fps)
        if welch_bpm is not None:
            delta = abs(welch_bpm - bpm)
            if delta <= 3.0:
                confidence = min(1.0, confidence + 0.10)
            elif delta <= 5.0:
                confidence = min(1.0, confidence + 0.05)
            elif delta >= 10.0:
                confidence = max(0.0, confidence - 0.15)
            elif delta >= 6.0:
                confidence = max(0.0, confidence - 0.05)
            logger.info(f"HR cross-check: model={bpm:.1f} welch={welch_bpm:.1f} Δ={delta:.1f} → conf={confidence:.2f}")
        confidence = round(confidence, 2)
        downsampled = downsample_waveform(signal, fps, to_fps=5)
        waveform = normalize_signal(downsampled).tolist()
    else:
        confidence = 0.5
        waveform = []

    # Blood pressure — best-effort. Never blocks the HR response.
    sbp = dbp = bp_confidence = None
    try:
        bp = bp_service.estimate_bp(signal, fps, age=age, sex=sex, bmi=bmi)
        if bp is not None:
            sbp, dbp, bp_confidence = bp.sbp, bp.dbp, bp.confidence
            logger.info(f"BP estimate: {sbp}/{dbp} mmHg (conf={bp_confidence}, n={bp.n_windows})")
    except Exception as e:
        logger.warning(f"BP estimation failed: {e}")

    # HRV → Stress → Respiration. Each is best-effort and null-safe.
    rmssd_ms = sdnn_ms = pnn50 = hrv_confidence = None
    stress_score = stress_lf_hf = stress_confidence = None
    stress_label = None
    respiration_bpm = respiration_confidence = None
    try:
        hrv = hrv_service.extract_hrv(signal, fps)
        if hrv is not None:
            rmssd_ms = hrv.rmssd_ms
            sdnn_ms = hrv.sdnn_ms
            pnn50 = hrv.pnn50
            hrv_confidence = hrv.confidence
            logger.info(
                f"HRV: RMSSD={rmssd_ms}ms SDNN={sdnn_ms}ms pNN50={pnn50} "
                f"(n={hrv.n_beats}, conf={hrv_confidence})"
            )
            # Stress reuses the cleaned IBI list — avoids re-detecting beats.
            try:
                stress = stress_service.estimate_stress(hrv.ibis_ms)
                if stress is not None:
                    stress_score = stress.score
                    stress_label = stress.label
                    stress_lf_hf = stress.lf_hf_ratio
                    stress_confidence = stress.confidence
            except Exception as e:
                logger.warning(f"Stress estimation failed: {e}")
    except Exception as e:
        logger.warning(f"HRV estimation failed: {e}")

    try:
        resp = respiration_service.estimate_respiration(signal, fps)
        if resp is not None:
            respiration_bpm = resp.rate_bpm
            respiration_confidence = resp.confidence
    except Exception as e:
        logger.warning(f"Respiration estimation failed: {e}")

    return {
        "bpm": bpm,
        "confidence": confidence,
        "waveform": waveform,
        "waveform_fps": 5,
        "sbp": sbp,
        "dbp": dbp,
        "bp_confidence": bp_confidence,
        "rmssd_ms": rmssd_ms,
        "sdnn_ms": sdnn_ms,
        "pnn50": pnn50,
        "hrv_confidence": hrv_confidence,
        "respiration_bpm": respiration_bpm,
        "respiration_confidence": respiration_confidence,
        "stress_score": stress_score,
        "stress_label": stress_label,
        "stress_lf_hf": stress_lf_hf,
        "stress_confidence": stress_confidence,
    }
