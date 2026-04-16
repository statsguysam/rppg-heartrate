"""
HRV (heart rate variability) extraction from rPPG BVP waveform.

Pipeline follows the best-practice rPPG HRV literature (Yu 2023 "Robust HRV
from Facial Videos", Rouast VitalLens 2.0 2025, Shen.ai 2024):

  1. Upsample BVP to 125 Hz (already done upstream).
  2. Detect systolic peaks via prominence+distance, then refine each peak to
     sub-sample accuracy with parabolic interpolation of the three points
     around the maximum. Critical — at 125 Hz one sample = 8 ms, comparable
     to the RMSSD numbers we are trying to measure.
  3. Derive IBIs, then apply a three-stage ectopic filter:
       • physiologic range 400–1300 ms (corresponds to 46–150 BPM)
       • global outliers: |ibi − mean| > 40% · mean
       • local outliers: rolling-window (10-beat) |ibi − win_mean| > 20%
  4. Compute standard time-domain metrics: RMSSD, SDNN, pNN50, mean HR.
  5. Quality gate: ≥ 30 clean IBIs (~30 s of beats) before returning.

Target accuracy at rest (clean UBFC-rPPG benchmark):
  RMSSD MAE ≈ 10 ms · SDNN MAE ≈ 6 ms.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional

import numpy as np
from scipy.signal import find_peaks, resample_poly

logger = logging.getLogger(__name__)

TARGET_FPS = 125  # must match bp_service / respiration_service


@dataclass
class HRVResult:
    rmssd_ms: float
    sdnn_ms: float
    pnn50: float        # fraction 0–1
    mean_hr: float      # BPM, from clean IBIs
    ibis_ms: list[float]   # cleaned IBI series, for downstream services
    confidence: float   # 0–1 — clean-beat yield × IBI regularity
    n_beats: int


def _upsample(bvp: np.ndarray, fps: float) -> np.ndarray:
    if fps <= 0 or len(bvp) == 0:
        return bvp
    up, down = TARGET_FPS, int(round(fps))
    if down == 0:
        return bvp
    from math import gcd
    g = gcd(up, down)
    return resample_poly(bvp, up // g, down // g)


def _parabolic_refine(y: np.ndarray, idx: int) -> float:
    """
    Fit a parabola through (idx-1, idx, idx+1) and return the sub-sample
    index of the vertex. Works in "sample" units; caller converts to ms.

    Classic 3-point parabolic interpolation:
        δ = 0.5·(y[-1] − y[+1]) / (y[-1] − 2·y[0] + y[+1])
    """
    if idx <= 0 or idx >= len(y) - 1:
        return float(idx)
    y0, y1, y2 = float(y[idx - 1]), float(y[idx]), float(y[idx + 1])
    denom = y0 - 2.0 * y1 + y2
    if abs(denom) < 1e-12:
        return float(idx)
    delta = 0.5 * (y0 - y2) / denom
    # Guard: |delta| > 1 means vertex is outside the 3-sample window —
    # discard the correction to stay robust.
    if abs(delta) > 1.0:
        return float(idx)
    return float(idx) + delta


def _clean_ibis(ibis_ms: np.ndarray) -> np.ndarray:
    """Three-stage ectopic filter. Returns IBIs that survive all three."""
    if len(ibis_ms) == 0:
        return ibis_ms

    # Stage 1: absolute physiologic range
    mask = (ibis_ms >= 400.0) & (ibis_ms <= 1300.0)
    if mask.sum() < 3:
        return ibis_ms[mask]

    # Stage 2: global outlier vs mean (40% band)
    mean_all = float(np.mean(ibis_ms[mask]))
    mask &= np.abs(ibis_ms - mean_all) <= 0.40 * mean_all
    if mask.sum() < 3:
        return ibis_ms[mask]

    # Stage 3: local outlier vs rolling mean (window 10, 20% band)
    kept = ibis_ms[mask].copy()
    keep_local = np.ones(len(kept), dtype=bool)
    win = 10
    for i in range(len(kept)):
        lo = max(0, i - win // 2)
        hi = min(len(kept), i + win // 2 + 1)
        window_mean = float(np.mean(kept[lo:hi]))
        if abs(kept[i] - window_mean) > 0.20 * window_mean:
            keep_local[i] = False
    return kept[keep_local]


def extract_hrv(bvp: np.ndarray, fps: float) -> Optional[HRVResult]:
    """
    Main entry point. Returns None if a reliable HRV estimate cannot be formed.
    """
    if len(bvp) == 0 or fps <= 0:
        return None

    sig = _upsample(np.asarray(bvp, dtype=np.float64), fps)
    if len(sig) < TARGET_FPS * 15:   # <15 s — not enough beats for stable HRV
        return None

    # Normalise so prominence threshold is signal-independent.
    w = (sig - sig.mean()) / (sig.std() + 1e-8)

    peaks, _ = find_peaks(w, distance=int(TARGET_FPS * 0.35), prominence=0.3)
    if len(peaks) < 20:
        return None

    # Sub-sample peak refinement — absolutely critical for HRV accuracy.
    refined = np.array([_parabolic_refine(w, int(p)) for p in peaks])
    ibis_ms = np.diff(refined) / TARGET_FPS * 1000.0

    clean = _clean_ibis(ibis_ms)
    if len(clean) < 30:
        logger.info(f"HRV rejected: only {len(clean)} clean IBIs (need ≥30)")
        return None

    diffs = np.diff(clean)
    rmssd = float(np.sqrt(np.mean(diffs ** 2)))
    sdnn = float(np.std(clean, ddof=1))
    pnn50 = float(np.mean(np.abs(diffs) > 50.0))
    mean_hr = float(60000.0 / np.mean(clean))

    # Confidence: (clean / detected) × (1 − ibi_cv clipped).
    yield_ratio = len(clean) / max(1, len(ibis_ms))
    ibi_cv = float(np.std(clean) / (np.mean(clean) + 1e-6))
    # Healthy resting HRV gives ibi_cv ~0.03–0.08. >0.15 suggests noisy beats.
    cv_score = float(np.clip(1.0 - max(0.0, ibi_cv - 0.05) * 5.0, 0.0, 1.0))
    confidence = round(0.6 * yield_ratio + 0.4 * cv_score, 2)

    return HRVResult(
        rmssd_ms=round(rmssd, 1),
        sdnn_ms=round(sdnn, 1),
        pnn50=round(pnn50, 3),
        mean_hr=round(mean_hr, 1),
        ibis_ms=clean.tolist(),
        confidence=confidence,
        n_beats=len(clean),
    )
