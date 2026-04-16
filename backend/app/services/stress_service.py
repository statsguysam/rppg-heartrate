"""
Stress estimation from HRV.

Combines two complementary indicators, both well-validated in the HRV
literature (Baevsky 2017, Shaffer & Ginsberg 2017, Kim 2018):

  • Baevsky's Stress Index (SI)
      SI = AMo / (2 · Mo · MxDMn)
    where the RR-interval histogram (50-ms bins) gives:
      Mo     — mode (the bin with the most RR values), in seconds
      AMo    — % of RRs in the mode bin (sympathetic tone marker)
      MxDMn  — max − min of RR values, in seconds (total variation range)
    Reference ranges (Baevsky & Chernikova 2017):
      80–150  normal, 150–500 mild-moderate stress, >500 severe sympathetic drive.

  • LF/HF power ratio from the RR tachogram (Welch PSD):
      LF band 0.04–0.15 Hz, HF band 0.15–0.40 Hz
      LF/HF < 1 → parasympathetic/recovery dominant
      LF/HF > 2 → sympathetic/stress dominant (rest of day)

We merge the two into a 0–100 "stress score" and a human-readable band.
Accepts a pre-cleaned IBI list (ms) from hrv_service so we inherit all
ectopic rejection work.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional

import numpy as np
from scipy.signal import welch

logger = logging.getLogger(__name__)

LF_BAND = (0.04, 0.15)
HF_BAND = (0.15, 0.40)
RR_INTERP_FPS = 4.0   # tachogram resample rate — standard for HRV Welch analysis

# numpy≥2.0 renamed trapz → trapezoid; support both.
_trap = getattr(np, "trapezoid", np.trapz)


@dataclass
class StressResult:
    score: int            # 0–100, higher = more stress
    label: str            # "Low" | "Normal" | "Elevated" | "High"
    baevsky_si: float     # raw SI
    lf_hf_ratio: float    # sympathovagal balance
    confidence: float     # 0–1
    n_beats: int


def _baevsky_si(rr_ms: np.ndarray) -> Optional[float]:
    """
    Baevsky Stress Index from an RR series (ms).
    Returns None if the histogram is degenerate (all RRs identical, etc.).
    """
    if len(rr_ms) < 30:
        return None

    rr_s = rr_ms / 1000.0
    bin_width = 0.050   # 50 ms — canonical Baevsky bin width
    # Histogram bounded by the actual range
    lo, hi = float(rr_s.min()), float(rr_s.max())
    if hi - lo < bin_width:
        return None

    edges = np.arange(lo, hi + bin_width, bin_width)
    counts, _ = np.histogram(rr_s, bins=edges)
    if counts.sum() == 0:
        return None

    mode_idx = int(np.argmax(counts))
    mo = float(edges[mode_idx] + bin_width / 2.0)     # mode centre, s
    amo = 100.0 * float(counts[mode_idx]) / float(counts.sum())   # %
    mxdmn = hi - lo                                    # s

    if mo <= 0 or mxdmn <= 0:
        return None

    si = amo / (2.0 * mo * mxdmn)
    return float(si)


def _lf_hf_ratio(rr_ms: np.ndarray) -> Optional[float]:
    """LF/HF from Welch PSD of the uniformly-resampled RR tachogram."""
    if len(rr_ms) < 30:
        return None

    # Build cumulative beat-time axis, then resample RR onto uniform grid.
    t_beats = np.cumsum(rr_ms) / 1000.0
    total_s = float(t_beats[-1])
    if total_s < 40.0:    # LF band resolution needs ≥ 25 s; we require more margin
        return None

    uniform_t = np.arange(0.0, total_s, 1.0 / RR_INTERP_FPS)
    tachogram = np.interp(uniform_t, t_beats, rr_ms)
    tachogram -= tachogram.mean()

    nperseg = int(min(len(tachogram), RR_INTERP_FPS * 40))
    if nperseg < 32:
        return None
    freqs, psd = welch(tachogram, fs=RR_INTERP_FPS, nperseg=nperseg, noverlap=nperseg // 2)

    lf = float(_trap(psd[(freqs >= LF_BAND[0]) & (freqs < LF_BAND[1])],
                            freqs[(freqs >= LF_BAND[0]) & (freqs < LF_BAND[1])]))
    hf = float(_trap(psd[(freqs >= HF_BAND[0]) & (freqs < HF_BAND[1])],
                            freqs[(freqs >= HF_BAND[0]) & (freqs < HF_BAND[1])]))
    if hf <= 1e-9:
        return None
    return lf / hf


def _combine(si: Optional[float], lf_hf: Optional[float]) -> tuple[int, str]:
    """
    Map SI and LF/HF onto a 0–100 score + label.

    SI component: log-scale so that 50→0, 150→50, 500→100.
    LF/HF component: <1 low, 1–2 normal, 2–4 elevated, >4 high (Shaffer 2017).
    Combine 60% SI + 40% LF/HF (SI is geometry-based and typically more stable).
    """
    parts, weights = [], []

    if si is not None:
        # log-mapped SI → 0–100
        si_score = float(np.clip(50.0 * np.log10(max(si, 1.0) / 50.0) / np.log10(10.0), 0.0, 100.0))
        parts.append(si_score)
        weights.append(0.6)

    if lf_hf is not None:
        # LF/HF → 0–100
        if lf_hf < 1.0:
            lfhf_score = 20.0 * lf_hf          # 0 → 0, 1 → 20
        elif lf_hf < 2.0:
            lfhf_score = 20.0 + 30.0 * (lf_hf - 1.0)    # 1 → 20, 2 → 50
        elif lf_hf < 4.0:
            lfhf_score = 50.0 + 25.0 * (lf_hf - 2.0) / 2.0  # 2 → 50, 4 → 75
        else:
            lfhf_score = float(np.clip(75.0 + 5.0 * (lf_hf - 4.0), 75.0, 100.0))
        parts.append(lfhf_score)
        weights.append(0.4)

    score = int(round(float(np.average(parts, weights=weights))))
    if score < 30:
        label = "Low"
    elif score < 55:
        label = "Normal"
    elif score < 75:
        label = "Elevated"
    else:
        label = "High"
    return score, label


def estimate_stress(ibis_ms: list[float]) -> Optional[StressResult]:
    """
    Accepts cleaned IBIs from hrv_service. Returns None if neither SI nor
    LF/HF can be computed.
    """
    if not ibis_ms or len(ibis_ms) < 30:
        return None
    rr = np.asarray(ibis_ms, dtype=np.float64)

    si = _baevsky_si(rr)
    lf_hf = _lf_hf_ratio(rr)
    if si is None and lf_hf is None:
        return None

    score, label = _combine(si, lf_hf)

    # Confidence: both components available → 1.0, one → 0.6.
    if si is not None and lf_hf is not None:
        confidence = 0.9
    else:
        confidence = 0.55

    si_str = f"{si:.1f}" if si is not None else "nan"
    lfhf_str = f"{lf_hf:.2f}" if lf_hf is not None else "nan"
    logger.info(f"Stress: SI={si_str} LF/HF={lfhf_str} → score={score} ({label})")

    return StressResult(
        score=score,
        label=label,
        baevsky_si=round(si, 1) if si is not None else 0.0,
        lf_hf_ratio=round(lf_hf, 2) if lf_hf is not None else 0.0,
        confidence=round(confidence, 2),
        n_beats=len(rr),
    )
