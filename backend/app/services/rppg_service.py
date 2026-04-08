"""
rPPG service wrapping open-rppg (PhysMamba model).

open-rppg is imported lazily and the model is warmed up at app startup
via the lifespan handler in main.py. All inference happens synchronously
in a thread pool executor to avoid blocking the async event loop.
"""
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
)

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


def _trim_video(video_path: str, max_seconds: float = 20.0) -> str:
    """
    If video is longer than max_seconds, write a trimmed copy and return its path.
    30s of facial video is sufficient for accurate rPPG; trimming keeps CPU time <30s.
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


def _run_physmamba(video_path: str) -> dict:
    """Inference via open-rppg PhysMamba model."""
    trimmed = _trim_video(video_path)
    try:
        result = _model.process_video(trimmed)
    finally:
        if trimmed != video_path:
            import os
            os.unlink(trimmed)

    # open-rppg returns a dict with at minimum 'hr' (BPM)
    bpm = float(result["hr"])
    raw_signal: np.ndarray = np.array(result.get("ppg", []))

    return {"bpm": bpm, "raw_signal": raw_signal, "fps": _model_fps}


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

    # HR via FFT
    N = len(signal)
    freqs = fftfreq(N, d=1.0 / effective_fps)
    power = np.abs(fft(signal)) ** 2
    valid = (freqs >= 0.7) & (freqs <= 4.0)
    peak_freq = freqs[valid][np.argmax(power[valid])]
    bpm = float(peak_freq * 60)

    return {"bpm": bpm, "raw_signal": signal, "raw_prefilter": raw_signal_prefilter, "fps": effective_fps}


async def analyze_video(video_path: Path) -> dict:
    """
    Async entry point: runs inference in a thread pool, then post-processes.
    Returns dict with keys: bpm, confidence, waveform, waveform_fps.
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
        downsampled = downsample_waveform(signal, fps, to_fps=5)
        waveform = normalize_signal(downsampled).tolist()
    else:
        confidence = 0.5
        waveform = []

    return {
        "bpm": bpm,
        "confidence": confidence,
        "waveform": waveform,
        "waveform_fps": 5,
    }
