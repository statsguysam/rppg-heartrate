"""
Respiration rate estimation from rPPG BVP — SOTA pipeline.

Architecture follows the RRest benchmark winners (Charlton 2016, 2018) and
the "Smart Fusion" rule (Karlen 2013), with per-channel **Signal Quality
Index (SQI)** gating which is what lets the Capnobase / BIDMC state-of-
the-art stay under ~3 bpm MAE even when individual channels are noisy.

Three respiration-bearing channels are extracted from a cardiac-range BVP:

  • BW (Baseline Wander)      — slow DC drift from breath (lowpass < 0.7 Hz)
  • AM (Amplitude Modulation) — per-beat pulse amplitude varies with breath
  • FM (Frequency Modulation) — respiratory sinus arrhythmia (IBI tachogram)

For each channel we compute a spectral SQI with three components:

  1. prominence_ratio = peak_PSD / median_band_PSD
        Robust against a single outlier bin (Charlton 2018 §2.3). Higher
        means the peak stands out from the noise floor.
  2. concentration    = ∫±0.05 Hz of peak / ∫entire band
        Fraction of band power within ±3 bpm of the peak — a narrow,
        well-defined peak has high concentration.
  3. sharpness        = 1 − half_width_Hz / 0.15
        Full-width-at-half-maximum penalty. Sharp peaks → sharp RR.

Combined SQI = geometric mean of the three, mapped to [0, 1]. Rationale:
geometric mean penalises any single weak component, which is exactly what
we want — a channel with one bad SQI dimension should not pass.

Decision rule (strictest-first):

  • If ≥2 channels pass SQI ≥ 0.40 AND their rates agree within 2 bpm →
    SQI-weighted fusion of the agreeing cluster (smart fusion).
  • Else if the single highest-SQI channel has SQI ≥ 0.55 → single-channel
    fallback (Charlton 2018 shows a well-gated single channel can still
    hit ≤4 bpm MAE when fusion isn't possible).
  • Else → reject (correct behaviour; returning any RR under these
    conditions would be guessing).

Typical operating band: 0.1–0.5 Hz (6–30 breaths/min).
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional

import numpy as np
from scipy.signal import butter, filtfilt, find_peaks, resample_poly, welch

logger = logging.getLogger(__name__)

TARGET_FPS = 125
RESP_BAND_LOW = 0.1       # 6 breaths/min
RESP_BAND_HIGH = 0.5      # 30 breaths/min
FUSION_AGREEMENT_BPM = 2.0

# SQI gates — calibrated against RRest benchmark typical operating points.
SQI_PASS_THRESHOLD = 0.40        # channel must clear this to enter fusion
SQI_SINGLE_CHANNEL_MIN = 0.55    # stricter bar to trust a lone channel

# ±3 bpm (~0.05 Hz) window around the peak for concentration calculation.
CONCENTRATION_HALFWIDTH_HZ = 0.05


@dataclass
class RespirationResult:
    rate_bpm: float        # breaths per minute
    confidence: float      # 0–1
    agreement_channels: int   # 1 (single-channel fallback), 2, or 3


def _upsample(bvp: np.ndarray, fps: float) -> np.ndarray:
    if fps <= 0 or len(bvp) == 0:
        return bvp
    up, down = TARGET_FPS, int(round(fps))
    if down == 0:
        return bvp
    from math import gcd
    g = gcd(up, down)
    return resample_poly(bvp, up // g, down // g)


def _spectral_sqi(signal: np.ndarray, fs: float) -> Optional[tuple[float, float]]:
    """
    Welch PSD → (rate_bpm, SQI∈[0,1]) for the dominant respiration peak.
    Returns None if the band has no usable signal.

    SQI = geometric_mean(prominence_norm, concentration, sharpness).
    """
    if len(signal) < fs * 10:
        return None
    nperseg = int(min(len(signal), fs * 30))   # up to 30 s window → 0.033 Hz bin
    if nperseg < 64:
        return None
    freqs, psd = welch(signal, fs=fs, nperseg=nperseg, noverlap=nperseg // 2)

    band_mask = (freqs >= RESP_BAND_LOW) & (freqs <= RESP_BAND_HIGH)
    if not band_mask.any():
        return None
    band_freqs = freqs[band_mask]
    band_psd = psd[band_mask]
    if band_psd.max() <= 0:
        return None

    peak_idx = int(np.argmax(band_psd))
    peak_psd = float(band_psd[peak_idx])
    peak_freq = float(band_freqs[peak_idx])

    # (1) Prominence ratio — peak vs median noise floor. Robust to a single
    # outlier bin. Normalise: ratio of 3 → SQI 0, ratio of 8 → SQI 1.
    median_band = float(np.median(band_psd))
    prominence_ratio = peak_psd / (median_band + 1e-12)
    prominence_norm = float(np.clip((prominence_ratio - 3.0) / 5.0, 0.0, 1.0))

    # (2) Concentration — fraction of band power inside ±0.05 Hz of peak.
    concentration_mask = np.abs(band_freqs - peak_freq) <= CONCENTRATION_HALFWIDTH_HZ
    concentration = float(band_psd[concentration_mask].sum() / (band_psd.sum() + 1e-12))
    # Normalise: 0.15 → 0, 0.60 → 1. Wider peaks fail here even if prominent.
    concentration_norm = float(np.clip((concentration - 0.15) / 0.45, 0.0, 1.0))

    # (3) Sharpness — full-width-at-half-maximum of the peak.
    half_max = peak_psd / 2.0
    # Walk left and right from peak_idx until we drop below half-max.
    lo_idx = peak_idx
    while lo_idx > 0 and band_psd[lo_idx] >= half_max:
        lo_idx -= 1
    hi_idx = peak_idx
    while hi_idx < len(band_psd) - 1 and band_psd[hi_idx] >= half_max:
        hi_idx += 1
    fwhm = float(band_freqs[hi_idx] - band_freqs[lo_idx])
    sharpness_norm = float(np.clip(1.0 - fwhm / 0.15, 0.0, 1.0))

    # Geometric mean — any weak component pulls the overall SQI down.
    components = np.array([prominence_norm, concentration_norm, sharpness_norm])
    # Floor at 0.01 so one zero doesn't annihilate the product (keeps gradient).
    sqi = float(np.exp(np.log(np.clip(components, 0.01, 1.0)).mean()))

    return peak_freq * 60.0, sqi


def _bw_signal(bvp: np.ndarray) -> np.ndarray:
    """Baseline-wander channel — lowpass at 0.7 Hz removes cardiac content."""
    b, a = butter(3, 0.7, btype="lowpass", fs=TARGET_FPS)
    return filtfilt(b, a, bvp)


def _am_signal(bvp: np.ndarray) -> Optional[np.ndarray]:
    """Per-beat peak-to-trough amplitude, interpolated to TARGET_FPS grid."""
    b, a = butter(3, [0.7, 4.0], btype="bandpass", fs=TARGET_FPS)
    card = filtfilt(b, a, bvp)
    w = (card - card.mean()) / (card.std() + 1e-8)

    peaks, _ = find_peaks(w, distance=int(TARGET_FPS * 0.4), prominence=0.3)
    if len(peaks) < 10:
        return None

    amps = []
    for i in range(len(peaks) - 1):
        lo, hi = peaks[i], peaks[i + 1]
        trough = lo + int(np.argmin(card[lo:hi]))
        amps.append(card[peaks[i]] - card[trough])
    if len(amps) < 8:
        return None

    beat_times = peaks[:-1] / TARGET_FPS
    total_s = len(bvp) / TARGET_FPS
    uniform_t = np.arange(0, total_s, 1.0 / TARGET_FPS)
    return np.interp(uniform_t, beat_times, amps, left=amps[0], right=amps[-1])


def _fm_signal(bvp: np.ndarray) -> Optional[np.ndarray]:
    """IBI tachogram (RSA), interpolated to TARGET_FPS grid."""
    b, a = butter(3, [0.7, 4.0], btype="bandpass", fs=TARGET_FPS)
    card = filtfilt(b, a, bvp)
    w = (card - card.mean()) / (card.std() + 1e-8)

    peaks, _ = find_peaks(w, distance=int(TARGET_FPS * 0.4), prominence=0.3)
    if len(peaks) < 10:
        return None

    ibis = np.diff(peaks) / TARGET_FPS
    beat_times = peaks[1:] / TARGET_FPS
    total_s = len(bvp) / TARGET_FPS
    uniform_t = np.arange(0, total_s, 1.0 / TARGET_FPS)
    return np.interp(uniform_t, beat_times, ibis, left=ibis[0], right=ibis[-1])


def estimate_respiration(bvp: np.ndarray, fps: float) -> Optional[RespirationResult]:
    """SOTA respiration estimator. Returns None when no channel passes SQI."""
    if len(bvp) == 0 or fps <= 0:
        return None
    sig = _upsample(np.asarray(bvp, dtype=np.float64), fps)
    if len(sig) < TARGET_FPS * 30:
        return None

    # (name, rate_bpm, sqi) for every channel that produced an SQI.
    all_channels: list[tuple[str, float, float]] = []

    bw = _bw_signal(sig)
    res = _spectral_sqi(bw, TARGET_FPS)
    if res is not None:
        all_channels.append(("BW", res[0], res[1]))

    am = _am_signal(sig)
    if am is not None:
        res = _spectral_sqi(am, TARGET_FPS)
        if res is not None:
            all_channels.append(("AM", res[0], res[1]))

    fm = _fm_signal(sig)
    if fm is not None:
        res = _spectral_sqi(fm, TARGET_FPS)
        if res is not None:
            all_channels.append(("FM", res[0], res[1]))

    if not all_channels:
        logger.info("Respiration rejected: no channels produced a spectral estimate")
        return None

    diag = [(c[0], round(c[1], 1), round(c[2], 2)) for c in all_channels]

    # SQI gate — only channels that clear the pass threshold compete.
    passing = [c for c in all_channels if c[2] >= SQI_PASS_THRESHOLD]

    # -- Fusion path: largest cluster of passing channels within ±2 bpm.
    if len(passing) >= 2:
        rates = np.array([c[1] for c in passing])
        sqis = np.array([c[2] for c in passing])
        best_cluster: list[int] = []
        for i in range(len(rates)):
            cluster = [j for j in range(len(rates)) if abs(rates[j] - rates[i]) <= FUSION_AGREEMENT_BPM]
            if len(cluster) > len(best_cluster):
                best_cluster = cluster

        if len(best_cluster) >= 2:
            c_rates = rates[best_cluster]
            c_sqis = sqis[best_cluster]
            rate = float(np.sum(c_rates * c_sqis) / np.sum(c_sqis))
            base_conf = 0.75 + 0.10 * (len(best_cluster) - 2)      # 2 → 0.75, 3 → 0.85
            confidence = round(float(np.clip(base_conf + 0.15 * float(np.mean(c_sqis)), 0.0, 0.95)), 2)
            logger.info(
                f"Respiration (fusion {len(best_cluster)}/{len(passing)} passing): "
                f"channels={diag} → {round(rate, 1)} bpm, conf={confidence}"
            )
            return RespirationResult(
                rate_bpm=round(rate, 1),
                confidence=confidence,
                agreement_channels=len(best_cluster),
            )

    # -- Single-channel fallback: best channel must clear a stricter SQI bar.
    best = max(all_channels, key=lambda c: c[2])
    if best[2] >= SQI_SINGLE_CHANNEL_MIN:
        # Scale confidence by how far above the strict bar we are.
        confidence = round(float(np.clip(0.45 + 0.35 * (best[2] - SQI_SINGLE_CHANNEL_MIN) / (1.0 - SQI_SINGLE_CHANNEL_MIN), 0.45, 0.75)), 2)
        logger.info(
            f"Respiration (single-channel {best[0]}, SQI={best[2]:.2f}): "
            f"channels={diag} → {round(best[1], 1)} bpm, conf={confidence}"
        )
        return RespirationResult(
            rate_bpm=round(best[1], 1),
            confidence=confidence,
            agreement_channels=1,
        )

    logger.info(
        f"Respiration rejected: no fusion cluster and best SQI={best[2]:.2f} < {SQI_SINGLE_CHANNEL_MIN}. "
        f"channels={diag}"
    )
    return None
