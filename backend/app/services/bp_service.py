"""
Blood pressure estimation from rPPG BVP waveform.

Two-stage pipeline:
  1. Extract pulse-wave-morphology features from BVP (HR, rise time, pulse
     width, augmentation index, HRV proxy).
  2. Population-centered linear regression with demographic inputs (age, sex,
     BMI) → uncalibrated SBP/DBP.

Per-user calibration offsets are applied on the client; the backend returns
the raw uncalibrated estimate plus a confidence score. 54 overlapping 7-second
windows over a 60 s scan are median-aggregated for stability.

The regression coefficients below are a *baseline* population model inspired
by the pulse-wave-analysis literature (Elgendi et al. 2019, Schrumpf et al.
2021). Replace `_predict_population` with a trained regressor (e.g. 1D ResNet
on MIMIC-III fine-tuned on rPPG) without touching the rest of the pipeline.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional

import numpy as np
from scipy.signal import find_peaks, resample_poly, welch

logger = logging.getLogger(__name__)

# Target analysis rate. Most PPG→BP models are trained at 125 Hz.
TARGET_FPS = 125
WINDOW_S = 7.0        # 7-second windows — matches MIMIC-III BP literature
WINDOW_STRIDE_S = 1.0 # 1 s stride → 54 windows over a 60 s signal

# Population reference values (adults, globally averaged).
_REF_HR = 70.0
_REF_AGE = 40.0
_REF_BMI = 22.0
_REF_RISE_MS = 120.0
_REF_PW_MS = 300.0

# Baseline regression coefficients. Centered on population means so an
# "average adult" with no signal information lands at (120/78).
# Replace these by loading a trained sklearn/torch model if/when available.
_SBP = dict(intercept=120.0, hr=0.30, age=0.35, bmi=0.80, rise_ms=-0.15, sex_male=2.0)
_DBP = dict(intercept=78.0,  hr=0.20, age=0.15, bmi=0.40, pw_ms=-0.03, sex_male=1.5)


@dataclass
class BPResult:
    sbp: float
    dbp: float
    confidence: float      # 0–1 — window agreement × feature quality
    n_windows: int         # how many windows contributed (out of 54)


def _upsample(bvp: np.ndarray, fps: float) -> np.ndarray:
    """Resample BVP to TARGET_FPS using polyphase filtering."""
    if fps <= 0 or len(bvp) == 0:
        return bvp
    up, down = TARGET_FPS, int(round(fps))
    if down == 0:
        return bvp
    from math import gcd
    g = gcd(up, down)
    return resample_poly(bvp, up // g, down // g)


def _window_features(win: np.ndarray, fps: int) -> Optional[dict]:
    """Extract pulse-wave features from a single window. Returns None if unreliable."""
    if len(win) < fps * 3:
        return None

    # Normalize so peak detection thresholds are signal-independent
    w = (win - win.mean()) / (win.std() + 1e-8)

    # Systolic peaks. Minimum distance = 0.4 s (150 BPM ceiling).
    peaks, _ = find_peaks(w, distance=int(fps * 0.4), prominence=0.3)
    if len(peaks) < 4:
        return None

    ibi = np.diff(peaks) / fps  # inter-beat intervals (s)
    hr = 60.0 / ibi.mean() if ibi.mean() > 0 else 0.0
    if hr < 40 or hr > 180:
        return None

    # Systolic upstroke: foot (local minimum before peak) → peak
    rise_times_ms = []
    widths_ms = []
    for p in peaks:
        lo = max(0, p - int(fps * 0.5))
        seg = w[lo:p + 1]
        if len(seg) < 3:
            continue
        foot = lo + int(np.argmin(seg))
        if foot >= p:
            continue
        rise_times_ms.append((p - foot) / fps * 1000.0)

        # Pulse width at 50% amplitude
        amp_half = (w[foot] + w[p]) * 0.5
        hi = min(len(w), p + int(fps * 0.5))
        right_seg = w[p:hi]
        right_cross = np.where(right_seg <= amp_half)[0]
        if len(right_cross) == 0:
            continue
        right = p + int(right_cross[0])
        widths_ms.append((right - foot) / fps * 1000.0)

    if not rise_times_ms or not widths_ms:
        return None

    return {
        "hr": float(hr),
        "rise_ms": float(np.median(rise_times_ms)),
        "pw_ms": float(np.median(widths_ms)),
        "ibi_std": float(np.std(ibi)),
        "n_peaks": int(len(peaks)),
    }


def _predict_population(
    feats: dict,
    age: Optional[int],
    sex: Optional[str],
    bmi: Optional[float],
) -> tuple[float, float]:
    """Apply centered linear regression. Returns (sbp, dbp)."""
    age_c = (age if age is not None else _REF_AGE) - _REF_AGE
    bmi_c = (bmi if bmi is not None else _REF_BMI) - _REF_BMI
    sex_male = 1.0 if (sex and sex.lower().startswith("m")) else 0.0
    hr_c = feats["hr"] - _REF_HR
    rise_c = feats["rise_ms"] - _REF_RISE_MS
    pw_c = feats["pw_ms"] - _REF_PW_MS

    sbp = (
        _SBP["intercept"]
        + _SBP["hr"] * hr_c
        + _SBP["age"] * age_c
        + _SBP["bmi"] * bmi_c
        + _SBP["rise_ms"] * rise_c
        + _SBP["sex_male"] * sex_male
    )
    dbp = (
        _DBP["intercept"]
        + _DBP["hr"] * hr_c
        + _DBP["age"] * age_c
        + _DBP["bmi"] * bmi_c
        + _DBP["pw_ms"] * pw_c
        + _DBP["sex_male"] * sex_male
    )
    return float(sbp), float(dbp)


def estimate_bp(
    bvp: np.ndarray,
    fps: float,
    age: Optional[int] = None,
    sex: Optional[str] = None,
    bmi: Optional[float] = None,
) -> Optional[BPResult]:
    """
    Main entry point. Returns None if BP cannot be estimated reliably.

    Aggregation: median of per-window predictions. Confidence blends inter-
    window agreement (tight distribution → high) with window yield (54/54 → high).
    """
    if len(bvp) == 0 or fps <= 0:
        return None

    sig = _upsample(np.asarray(bvp, dtype=np.float64), fps)
    win_len = int(WINDOW_S * TARGET_FPS)
    stride = int(WINDOW_STRIDE_S * TARGET_FPS)

    if len(sig) < win_len:
        return None

    sbps, dbps = [], []
    n_total = (len(sig) - win_len) // stride + 1
    for start in range(0, len(sig) - win_len + 1, stride):
        win = sig[start:start + win_len]
        feats = _window_features(win, TARGET_FPS)
        if feats is None:
            continue
        s, d = _predict_population(feats, age, sex, bmi)
        if 70 <= s <= 210 and 40 <= d <= 130 and s > d + 15:
            sbps.append(s)
            dbps.append(d)

    if len(sbps) < max(3, n_total // 4):
        logger.info(f"BP estimation rejected: only {len(sbps)}/{n_total} windows viable")
        return None

    sbp = float(np.median(sbps))
    dbp = float(np.median(dbps))

    # Window agreement (low spread → high confidence)
    sbp_mad = float(np.median(np.abs(np.array(sbps) - sbp)))
    agreement = float(np.clip(1.0 - sbp_mad / 15.0, 0.0, 1.0))
    yield_ratio = len(sbps) / n_total
    confidence = round(0.6 * agreement + 0.4 * yield_ratio, 2)

    return BPResult(
        sbp=round(sbp, 1),
        dbp=round(dbp, 1),
        confidence=confidence,
        n_windows=len(sbps),
    )
