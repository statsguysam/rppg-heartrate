"""
Respiration rate estimation from rPPG BVP.

Best-in-class "Smart Fusion" approach (Karlen 2013, Charlton 2016, Pimentel
2017). Respiration modulates the BVP through three simultaneous channels:

  • BW (Baseline Wander)      — slow drift of the DC level with breathing
  • AM (Amplitude Modulation) — pulse amplitude expands/contracts
  • FM (Frequency Modulation) — respiratory sinus arrhythmia (RSA): IBIs
                                 lengthen on exhale, shorten on inhale

Each channel gives an independent RR estimate. If at least two channels
agree within 2 breaths/min we return their mean — this is the "smart
fusion" rule that gives significantly better accuracy than any single
channel alone (Karlen's original MAE ≈ 3 bpm at rest).

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


@dataclass
class RespirationResult:
    rate_bpm: float        # breaths per minute
    confidence: float      # 0–1
    agreement_channels: int   # how many of {BW, AM, FM} agreed (2 or 3)


def _upsample(bvp: np.ndarray, fps: float) -> np.ndarray:
    if fps <= 0 or len(bvp) == 0:
        return bvp
    up, down = TARGET_FPS, int(round(fps))
    if down == 0:
        return bvp
    from math import gcd
    g = gcd(up, down)
    return resample_poly(bvp, up // g, down // g)


def _dominant_freq(signal: np.ndarray, fs: float) -> Optional[tuple[float, float]]:
    """
    Welch PSD peak in the respiration band. Returns (freq_Hz, prominence)
    where prominence is peak_psd / mean_band_psd. None if band is silent.
    """
    if len(signal) < fs * 10:
        return None
    nperseg = int(min(len(signal), fs * 30))   # up to 30 s window
    if nperseg < 64:
        return None
    freqs, psd = welch(signal, fs=fs, nperseg=nperseg, noverlap=nperseg // 2)
    mask = (freqs >= RESP_BAND_LOW) & (freqs <= RESP_BAND_HIGH)
    if not mask.any():
        return None
    band_psd = psd[mask]
    band_freqs = freqs[mask]
    if band_psd.max() <= 0:
        return None
    idx = int(np.argmax(band_psd))
    prominence = float(band_psd[idx] / (band_psd.mean() + 1e-12))
    return float(band_freqs[idx]), prominence


def _bw_signal(bvp: np.ndarray) -> np.ndarray:
    """Baseline-wander channel — lowpass at 0.7 Hz removes cardiac content."""
    b, a = butter(3, 0.7, btype="lowpass", fs=TARGET_FPS)
    return filtfilt(b, a, bvp)


def _am_signal(bvp: np.ndarray) -> Optional[np.ndarray]:
    """
    Amplitude-modulation channel — peak-to-peak envelope of each cardiac
    beat. Returns a respiration-band signal resampled back to TARGET_FPS.
    """
    # Bandpass around cardiac range first so peaks are clean.
    b, a = butter(3, [0.7, 4.0], btype="bandpass", fs=TARGET_FPS)
    card = filtfilt(b, a, bvp)
    w = (card - card.mean()) / (card.std() + 1e-8)

    peaks, _ = find_peaks(w, distance=int(TARGET_FPS * 0.4), prominence=0.3)
    if len(peaks) < 10:
        return None

    # Compute peak-to-trough amplitude per beat
    amps = []
    for i in range(len(peaks) - 1):
        lo, hi = peaks[i], peaks[i + 1]
        trough = lo + int(np.argmin(card[lo:hi]))
        amps.append(card[peaks[i]] - card[trough])
    if len(amps) < 8:
        return None

    # Place amplitudes at the beat times, then resample to uniform TARGET_FPS grid
    beat_times = peaks[:-1] / TARGET_FPS
    total_s = len(bvp) / TARGET_FPS
    uniform_t = np.arange(0, total_s, 1.0 / TARGET_FPS)
    am = np.interp(uniform_t, beat_times, amps, left=amps[0], right=amps[-1])
    return am


def _fm_signal(bvp: np.ndarray) -> Optional[np.ndarray]:
    """
    Frequency-modulation channel — IBI series (RSA). Uniformly resampled
    to TARGET_FPS for Welch analysis.
    """
    b, a = butter(3, [0.7, 4.0], btype="bandpass", fs=TARGET_FPS)
    card = filtfilt(b, a, bvp)
    w = (card - card.mean()) / (card.std() + 1e-8)

    peaks, _ = find_peaks(w, distance=int(TARGET_FPS * 0.4), prominence=0.3)
    if len(peaks) < 10:
        return None

    ibis = np.diff(peaks) / TARGET_FPS    # seconds
    beat_times = peaks[1:] / TARGET_FPS

    total_s = len(bvp) / TARGET_FPS
    uniform_t = np.arange(0, total_s, 1.0 / TARGET_FPS)
    fm = np.interp(uniform_t, beat_times, ibis, left=ibis[0], right=ibis[-1])
    return fm


def estimate_respiration(bvp: np.ndarray, fps: float) -> Optional[RespirationResult]:
    """Returns None if respiration rate cannot be reliably extracted."""
    if len(bvp) == 0 or fps <= 0:
        return None
    sig = _upsample(np.asarray(bvp, dtype=np.float64), fps)
    if len(sig) < TARGET_FPS * 30:     # <30 s — insufficient for resp band
        return None

    channels: list[tuple[str, float, float]] = []  # (name, bpm, prominence)

    bw = _bw_signal(sig)
    res = _dominant_freq(bw, TARGET_FPS)
    if res is not None:
        f, p = res
        channels.append(("BW", f * 60.0, p))

    am = _am_signal(sig)
    if am is not None:
        res = _dominant_freq(am, TARGET_FPS)
        if res is not None:
            f, p = res
            channels.append(("AM", f * 60.0, p))

    fm = _fm_signal(sig)
    if fm is not None:
        res = _dominant_freq(fm, TARGET_FPS)
        if res is not None:
            f, p = res
            channels.append(("FM", f * 60.0, p))

    if len(channels) < 2:
        logger.info(f"Respiration rejected: only {len(channels)} viable channels")
        return None

    rates = np.array([c[1] for c in channels])
    proms = np.array([c[2] for c in channels])

    # Smart-fusion agreement check: find the largest cluster of channels
    # within FUSION_AGREEMENT_BPM of each other.
    best_cluster_idx: list[int] = []
    for i in range(len(rates)):
        cluster = [j for j in range(len(rates)) if abs(rates[j] - rates[i]) <= FUSION_AGREEMENT_BPM]
        if len(cluster) > len(best_cluster_idx):
            best_cluster_idx = cluster

    if len(best_cluster_idx) < 2:
        logger.info(f"Respiration rejected: channels disagree (rates={rates.tolist()})")
        return None

    cluster_rates = rates[best_cluster_idx]
    cluster_proms = proms[best_cluster_idx]
    # Prominence-weighted mean inside the agreeing cluster.
    rate = float(np.sum(cluster_rates * cluster_proms) / np.sum(cluster_proms))

    # Confidence: agreement (2/3 → 0.7, 3/3 → 1.0) × prominence saturation
    agreement_score = len(best_cluster_idx) / 3.0   # 0.67 or 1.00
    prom_score = float(np.clip((np.mean(cluster_proms) - 2.0) / 6.0, 0.0, 1.0))
    confidence = round(0.6 * agreement_score + 0.4 * prom_score, 2)

    logger.info(
        f"Respiration: channels={[(c[0], round(c[1],1)) for c in channels]} → "
        f"{round(rate, 1)} bpm (agreement {len(best_cluster_idx)}/3, conf {confidence})"
    )

    return RespirationResult(
        rate_bpm=round(rate, 1),
        confidence=confidence,
        agreement_channels=len(best_cluster_idx),
    )
