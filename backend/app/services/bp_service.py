"""
Blood pressure estimation from rPPG BVP waveform.

Two-stage pipeline:
  1. Per-window pulse-wave-morphology features (HR, rise time, pulse width,
     reflection index, crest-time ratio, IBI variability).
  2. Population-centered regression predicting MAP and PP independently,
     then SBP/DBP = MAP ± scaled PP. MAP/PP reparametrization is more
     physiologically meaningful than predicting SBP/DBP directly: PP
     tracks arterial stiffness (pulse-wave features) and MAP tracks
     cardiac output & peripheral resistance (HR, age).

Windows are signal-quality scored, then aggregated with a quality-weighted
trimmed mean. 54 overlapping 7-second windows over a 60 s scan.

Coefficients are a baseline population model inspired by the pulse-wave
literature (Elgendi 2019, Schrumpf 2021, Mukkamala 2018). Replace
`_predict_population` with a trained regressor without touching the rest.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional

import numpy as np
from scipy.signal import find_peaks, resample_poly

logger = logging.getLogger(__name__)

TARGET_FPS = 125
WINDOW_S = 7.0
WINDOW_STRIDE_S = 1.0

# Population reference values (adults, globally averaged).
_REF_HR = 70.0
_REF_AGE = 40.0
_REF_BMI = 22.0
_REF_RISE_MS = 120.0
_REF_PW_MS = 300.0
_REF_RI = 0.55        # reflection index (diastolic/systolic peak amplitude)
_REF_CT = 0.20        # crest-time ratio (rise / pulse-width)

# Baseline MAP/PP regression. Centered so an "average adult" with no signal
# information lands at (120/78) via MAP=92, PP=42.
_MAP = dict(intercept=92.0, hr=0.18, age=0.30, bmi=0.55, rise_ms=-0.05, sex_male=1.5)
_PP = dict(intercept=42.0, age=0.45, bmi=0.35, pw_ms=-0.04, rise_ms=-0.08, ri=18.0, sex_male=2.0)


@dataclass
class BPResult:
    sbp: float
    dbp: float
    confidence: float      # 0–1 — window agreement × yield × signal quality
    n_windows: int         # how many windows contributed (out of ~54)


def _upsample(bvp: np.ndarray, fps: float) -> np.ndarray:
    if fps <= 0 or len(bvp) == 0:
        return bvp
    up, down = TARGET_FPS, int(round(fps))
    if down == 0:
        return bvp
    from math import gcd
    g = gcd(up, down)
    return resample_poly(bvp, up // g, down // g)


def _window_features(win: np.ndarray, fps: int) -> Optional[dict]:
    """Extract pulse-wave features + signal-quality score. None if unreliable."""
    if len(win) < fps * 3:
        return None

    w = (win - win.mean()) / (win.std() + 1e-8)

    peaks, peak_props = find_peaks(w, distance=int(fps * 0.4), prominence=0.3)
    if len(peaks) < 4:
        return None

    ibi = np.diff(peaks) / fps
    mean_ibi = ibi.mean()
    if mean_ibi <= 0:
        return None
    hr = 60.0 / mean_ibi
    if hr < 40 or hr > 180:
        return None

    rise_times_ms, widths_ms, ri_vals, ct_vals = [], [], [], []
    for i, p in enumerate(peaks):
        lo = max(0, p - int(fps * 0.5))
        seg = w[lo:p + 1]
        if len(seg) < 3:
            continue
        foot = lo + int(np.argmin(seg))
        if foot >= p:
            continue
        rise = (p - foot) / fps * 1000.0
        rise_times_ms.append(rise)

        # Pulse width at 50% amplitude
        amp_half = (w[foot] + w[p]) * 0.5
        hi = min(len(w), p + int(fps * 0.5))
        right_seg = w[p:hi]
        right_cross = np.where(right_seg <= amp_half)[0]
        if len(right_cross) == 0:
            continue
        right = p + int(right_cross[0])
        width = (right - foot) / fps * 1000.0
        widths_ms.append(width)
        if width > 0:
            ct_vals.append(rise / width)

        # Reflection index — diastolic peak (largest maximum after systolic
        # within the beat) amplitude relative to systolic peak amplitude.
        next_p = peaks[i + 1] if i + 1 < len(peaks) else min(len(w), p + int(mean_ibi * fps))
        between = w[p:next_p]
        if len(between) > 5:
            sub_peaks, _ = find_peaks(between)
            if len(sub_peaks) > 0:
                dia = between[sub_peaks].max()
                sys = w[p]
                amp_sys = sys - w[foot]
                amp_dia = dia - w[foot]
                if amp_sys > 1e-6:
                    ri_vals.append(float(np.clip(amp_dia / amp_sys, 0.0, 1.5)))

    if not rise_times_ms or not widths_ms:
        return None

    # Signal quality score: combine peak prominence consistency + IBI stability.
    prominences = peak_props.get("prominences", np.array([0.3]))
    prom_cv = float(np.std(prominences) / (np.mean(prominences) + 1e-6))
    ibi_cv = float(np.std(ibi) / (mean_ibi + 1e-6))
    # Physiologic HRV lives ~3–10% ibi_cv. Only penalise above that.
    sq = float(np.clip(1.0 - 0.6 * min(prom_cv, 1.0) - 0.4 * max(ibi_cv - 0.10, 0.0) * 5.0, 0.0, 1.0))

    return {
        "hr": float(hr),
        "rise_ms": float(np.median(rise_times_ms)),
        "pw_ms": float(np.median(widths_ms)),
        "ri": float(np.median(ri_vals)) if ri_vals else _REF_RI,
        "ct": float(np.median(ct_vals)) if ct_vals else _REF_CT,
        "ibi_std": float(np.std(ibi)),
        "n_peaks": int(len(peaks)),
        "sq": sq,
    }


def _predict_population(
    feats: dict,
    age: Optional[int],
    sex: Optional[str],
    bmi: Optional[float],
) -> tuple[float, float]:
    """
    Centered regression for MAP and PP, then derive SBP = MAP + 2/3·PP,
    DBP = MAP − 1/3·PP (standard haemodynamic reparametrization).
    """
    age_c = (age if age is not None else _REF_AGE) - _REF_AGE
    bmi_c = (bmi if bmi is not None else _REF_BMI) - _REF_BMI
    sex_male = 1.0 if (sex and sex.lower().startswith("m")) else 0.0
    hr_c = feats["hr"] - _REF_HR
    rise_c = feats["rise_ms"] - _REF_RISE_MS
    pw_c = feats["pw_ms"] - _REF_PW_MS
    ri_c = feats["ri"] - _REF_RI

    map_ = (
        _MAP["intercept"]
        + _MAP["hr"] * hr_c
        + _MAP["age"] * age_c
        + _MAP["bmi"] * bmi_c
        + _MAP["rise_ms"] * rise_c
        + _MAP["sex_male"] * sex_male
    )
    pp = (
        _PP["intercept"]
        + _PP["age"] * age_c
        + _PP["bmi"] * bmi_c
        + _PP["pw_ms"] * pw_c
        + _PP["rise_ms"] * rise_c
        + _PP["ri"] * ri_c
        + _PP["sex_male"] * sex_male
    )

    # Physiological gate — PP outside 25–70 mmHg is rarely real in ambulatory adults.
    pp = float(np.clip(pp, 25.0, 70.0))

    sbp = map_ + (2.0 / 3.0) * pp
    dbp = map_ - (1.0 / 3.0) * pp
    return float(sbp), float(dbp)


def _weighted_trimmed_mean(values: np.ndarray, weights: np.ndarray, trim: float = 0.15) -> float:
    """Weighted mean after dropping top and bottom `trim` fraction by value."""
    if len(values) == 0:
        return float("nan")
    order = np.argsort(values)
    n = len(values)
    k = int(n * trim)
    keep = order[k: n - k] if n - 2 * k > 0 else order
    v = values[keep]
    w = weights[keep]
    w_sum = w.sum()
    if w_sum <= 0:
        return float(np.mean(v))
    return float(np.sum(v * w) / w_sum)


def estimate_bp(
    bvp: np.ndarray,
    fps: float,
    age: Optional[int] = None,
    sex: Optional[str] = None,
    bmi: Optional[float] = None,
) -> Optional[BPResult]:
    """
    Returns None if BP cannot be reliably estimated.
    Aggregation: signal-quality-weighted trimmed mean across windows.
    """
    if len(bvp) == 0 or fps <= 0:
        return None

    sig = _upsample(np.asarray(bvp, dtype=np.float64), fps)
    win_len = int(WINDOW_S * TARGET_FPS)
    stride = int(WINDOW_STRIDE_S * TARGET_FPS)

    if len(sig) < win_len:
        return None

    sbps, dbps, sqs = [], [], []
    n_total = (len(sig) - win_len) // stride + 1
    for start in range(0, len(sig) - win_len + 1, stride):
        win = sig[start:start + win_len]
        feats = _window_features(win, TARGET_FPS)
        if feats is None:
            continue
        s, d = _predict_population(feats, age, sex, bmi)
        pp = s - d
        if 70 <= s <= 210 and 40 <= d <= 130 and 25 <= pp <= 75:
            sbps.append(s)
            dbps.append(d)
            sqs.append(feats["sq"])

    if len(sbps) < max(3, n_total // 4):
        logger.info(f"BP estimation rejected: only {len(sbps)}/{n_total} windows viable")
        return None

    sbps_a = np.array(sbps)
    dbps_a = np.array(dbps)
    sqs_a = np.array(sqs)

    sbp = _weighted_trimmed_mean(sbps_a, sqs_a)
    dbp = _weighted_trimmed_mean(dbps_a, sqs_a)

    # Confidence: window agreement (MAD) × yield × mean signal quality.
    sbp_mad = float(np.median(np.abs(sbps_a - sbp)))
    agreement = float(np.clip(1.0 - sbp_mad / 12.0, 0.0, 1.0))
    yield_ratio = len(sbps) / n_total
    sq_mean = float(np.mean(sqs_a))
    confidence = round(0.5 * agreement + 0.3 * yield_ratio + 0.2 * sq_mean, 2)

    return BPResult(
        sbp=round(sbp, 1),
        dbp=round(dbp, 1),
        confidence=confidence,
        n_windows=len(sbps),
    )
