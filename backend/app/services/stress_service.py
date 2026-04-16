"""
Stress estimation from short-term HRV — SOTA time-domain pipeline.

Why no LF/HF here: the LF band spans 0.04–0.15 Hz, i.e. periods up to 25 s.
Reliable LF power estimation requires ≥ 2 min of clean RR data (Task Force
of the ESC / NASPE 1996; Malik 1996; Shaffer & Ginsberg 2017). A 60-second
scan yields only ~55 s of RR — LF power from that window is dominated by
edge-effect noise and spectral leakage. Reporting LF/HF from ≤ 1 min data
has been repeatedly shown to be unreliable (Munoz 2015, Pecchia 2018).

Instead we combine two validated **time-domain** short-window markers that
are well-posed at ~1 min:

  • Baevsky's Stress Index (SI) — sympathetic drive
      SI = AMo / (2 · Mo · MxDMn)
    Histogram-based geometry of the RR-interval series, 50 ms bins.
    Reference ranges (Baevsky & Chernikova 2017; Kim 2018):
      SI < 150     rest / parasympathetic dominant
      150–500      mild–moderate sympathetic drive
      > 500        severe sympathetic drive / acute stress

  • CVSD (Coefficient of Variation of Successive Differences) — parasympathetic
    tone. CVSD = RMSSD / meanRR, dimensionless, typically expressed as %.
    Penttilä 2001, Tulppo 1996, Shaffer 2017 have established CVSD as one
    of the most trustworthy short-term vagal markers (it is a normalised
    form of RMSSD, which compensates for inter-subject heart-rate bias).
    Reference ranges at rest (healthy adults):
      CVSD > 5 %   strong parasympathetic tone (low stress)
      3–5 %        normal rest
      1.5–3 %      reduced vagal tone (elevated stress)
      < 1.5 %      marked sympathetic dominance (high stress)

SI reflects sympathetic arousal; CVSD reflects parasympathetic recovery.
The two are complementary: stress is fundamentally a shift in the ratio
between the branches, and measuring both sides is more robust than
measuring either in isolation.

The two scores are blended 50/50 into a 0–100 stress score. A scan with
only SI available (e.g. extremely low beat count for CVSD) falls back
to SI alone at reduced confidence.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional

import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class StressResult:
    score: int            # 0–100, higher = more stress
    label: str            # "Low" | "Normal" | "Elevated" | "High"
    baevsky_si: float     # raw SI — sympathetic drive marker
    cvsd_pct: float       # RMSSD / meanRR × 100 — parasympathetic marker
    confidence: float     # 0–1
    n_beats: int


def _baevsky_si(rr_ms: np.ndarray) -> Optional[float]:
    """Baevsky Stress Index from an RR series (ms)."""
    if len(rr_ms) < 30:
        return None
    rr_s = rr_ms / 1000.0
    bin_width = 0.050   # 50 ms — canonical Baevsky bin width
    lo, hi = float(rr_s.min()), float(rr_s.max())
    if hi - lo < bin_width:
        return None
    edges = np.arange(lo, hi + bin_width, bin_width)
    counts, _ = np.histogram(rr_s, bins=edges)
    if counts.sum() == 0:
        return None

    mode_idx = int(np.argmax(counts))
    mo = float(edges[mode_idx] + bin_width / 2.0)
    amo = 100.0 * float(counts[mode_idx]) / float(counts.sum())
    mxdmn = hi - lo
    if mo <= 0 or mxdmn <= 0:
        return None
    return float(amo / (2.0 * mo * mxdmn))


def _cvsd_pct(rr_ms: np.ndarray) -> Optional[float]:
    """CVSD = RMSSD / meanRR × 100 (%). Normalised parasympathetic marker."""
    if len(rr_ms) < 30:
        return None
    mean_rr = float(np.mean(rr_ms))
    if mean_rr <= 0:
        return None
    diffs = np.diff(rr_ms)
    if len(diffs) == 0:
        return None
    rmssd = float(np.sqrt(np.mean(diffs ** 2)))
    return float(rmssd / mean_rr * 100.0)


def _si_to_score(si: float) -> float:
    """
    SI → stress score (0–100). Log-scale mapping calibrated to Baevsky
    reference ranges: SI=50→0, SI=150→50, SI=500→~85, SI≥1000→100.
    """
    if si <= 0:
        return 0.0
    score = 50.0 * np.log10(max(si, 1.0) / 50.0)
    return float(np.clip(score, 0.0, 100.0))


def _cvsd_to_score(cvsd_pct: float) -> float:
    """
    CVSD → stress score (0–100). Piecewise-linear mapping calibrated to
    the Penttilä 2001 / Shaffer 2017 reference ranges:
      CVSD ≥ 6 %   → 0    (strong vagal tone)
      CVSD = 4 %   → 25
      CVSD = 3 %   → 50
      CVSD = 1.5 % → 80
      CVSD ≤ 0.5 % → 100
    Inverse relationship: high parasympathetic tone ⇒ low stress.
    """
    if cvsd_pct >= 6.0:
        return 0.0
    if cvsd_pct >= 4.0:
        return float(25.0 * (6.0 - cvsd_pct) / 2.0)         # 6→0, 4→25
    if cvsd_pct >= 3.0:
        return float(25.0 + 25.0 * (4.0 - cvsd_pct) / 1.0)  # 4→25, 3→50
    if cvsd_pct >= 1.5:
        return float(50.0 + 30.0 * (3.0 - cvsd_pct) / 1.5)  # 3→50, 1.5→80
    return float(np.clip(80.0 + 20.0 * (1.5 - cvsd_pct) / 1.0, 80.0, 100.0))


def _combine(si: Optional[float], cvsd_pct: Optional[float]) -> tuple[int, str]:
    """Merge SI and CVSD sub-scores into a 0–100 score + band label."""
    parts, weights = [], []
    if si is not None:
        parts.append(_si_to_score(si))
        weights.append(0.5)
    if cvsd_pct is not None:
        parts.append(_cvsd_to_score(cvsd_pct))
        weights.append(0.5)

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
    CVSD can be computed.
    """
    if not ibis_ms or len(ibis_ms) < 30:
        return None
    rr = np.asarray(ibis_ms, dtype=np.float64)

    si = _baevsky_si(rr)
    cvsd = _cvsd_pct(rr)
    if si is None and cvsd is None:
        return None

    score, label = _combine(si, cvsd)

    # Confidence: both markers available → 0.9. One only → 0.55.
    confidence = 0.9 if (si is not None and cvsd is not None) else 0.55

    si_str = f"{si:.1f}" if si is not None else "nan"
    cvsd_str = f"{cvsd:.2f}%" if cvsd is not None else "nan"
    logger.info(f"Stress: SI={si_str} CVSD={cvsd_str} → score={score} ({label})")

    return StressResult(
        score=score,
        label=label,
        baevsky_si=round(si, 1) if si is not None else 0.0,
        cvsd_pct=round(cvsd, 2) if cvsd is not None else 0.0,
        confidence=round(confidence, 2),
        n_beats=len(rr),
    )
