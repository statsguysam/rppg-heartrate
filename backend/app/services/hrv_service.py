"""
HRV (heart rate variability) extraction from rPPG BVP waveform.

Pipeline follows the best-practice rPPG HRV literature (Yu 2023 "Robust HRV
from Facial Videos", Rouast VitalLens 2.0 2025, Shen.ai 2024):

  1. Upsample BVP to 125 Hz (already done upstream).
  2. Detect systolic peaks with Elgendi's Two Event-Related Moving Averages
     (TERMA, 2014) — validated on MIT-BIH polysomnographic PPG with 99.9 %
     sensitivity and 99.8 % PPV, which beats any prominence/distance rule
     for noisy PPG morphology. Each detected peak is then refined to
     sub-sample accuracy via 3-point parabolic interpolation. Critical —
     at 125 Hz one sample = 8 ms, comparable to the RMSSD numbers we are
     trying to measure.
  3. Derive IBIs, then apply a three-stage ectopic filter:
       • physiologic range 400–1300 ms (corresponds to 46–150 BPM)
       • global outliers: |ibi − mean| > 40% · mean
       • local outliers: rolling-window (10-beat) |ibi − win_mean| > 20%
  4. Compute standard time-domain metrics: RMSSD, SDNN, pNN50, mean HR.
  5. Quality gates: ≥ 30 clean IBIs AND ≥ 80 % beat-coverage of the scan
     (Shaffer 2017 / Camm 1996) before returning.

Target accuracy at rest (clean UBFC-rPPG benchmark):
  RMSSD MAE ≈ 10 ms · SDNN MAE ≈ 6 ms.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional

import numpy as np
from scipy.signal import resample_poly

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


def _elgendi_terma_peaks(
    signal: np.ndarray, fs: float, hr_prior_bpm: Optional[float] = None
) -> np.ndarray:
    """
    SOTA PPG peak detection — Elgendi 2014 "Systolic Peak Detection in
    Acceleration Photoplethysmograms Measured from Emergency Responders in
    Tropical Conditions" (PLOS ONE), adapted for rPPG by Pilz 2018.

    Two event-related moving averages of the rectified-and-squared signal:
      • MApeak over W1 ≈ 111 ms  (roughly one-third of a systolic upstroke)
      • MAbeat over W2 ≈ 667 ms  (roughly one full beat at 90 bpm)
    A block of interest is a contiguous region where MApeak > MAbeat + α.
    α is a small offset that suppresses noise during asystolic pauses.
    Any block longer than W1 samples is accepted, and the systolic peak is
    the argmax of the original signal inside it.

    Two rPPG-specific adaptations on top of the paper:
      (1) Sign auto-flip. rPPG BVP polarity is unstable across face
          detectors / model variants; some subjects land with inverted
          waveforms (systole = local minimum). We inspect positive- vs
          negative-half energy and flip if diastolic troughs dominate,
          so we always feed upstrokes into the rectifier.
      (2) α = 0.005 · mean(squared) (β tightened from the paper's 0.02).
          Validated for video-derived PPG by Pilz 2018 — rPPG has a
          smaller SNR margin than finger PPG and the paper's β causes
          under-detection in weak-amplitude segments.
    """
    w = (signal - signal.mean()) / (signal.std() + 1e-8)

    # (1) Sign auto-flip — ensure systolic peaks are the local maxima.
    pos_energy = float(np.mean(np.clip(w, 0.0, None) ** 2))
    neg_energy = float(np.mean(np.clip(-w, 0.0, None) ** 2))
    if neg_energy > 1.25 * pos_energy:
        w = -w

    clipped = np.clip(w, 0.0, None)   # keep systolic upstrokes, drop diastolic troughs
    squared = clipped ** 2

    # Window sizing — Elgendi 2014 defaults are W1=111ms, W2=667ms (calibrated
    # at ~90 BPM). For slow HR these are too short: ma_beat smooths less than a
    # full cycle, so the threshold sits too high and TERMA misses systoles.
    # When an HR prior is available, scale to the actual cycle length:
    #   W1 ≈ 15 % of RR  (covers the systolic upstroke)
    #   W2 ≈ one full RR (covers a complete beat — paper's intent)
    # Paper defaults are kept as a floor so fast-HR scans are unaffected.
    if hr_prior_bpm is not None and 30.0 <= float(hr_prior_bpm) <= 200.0:
        rr_prior_s = 60.0 / float(hr_prior_bpm)
        w1_s = max(0.111, 0.15 * rr_prior_s)
        w2_s = max(0.667, rr_prior_s)
    else:
        w1_s, w2_s = 0.111, 0.667
    w1 = max(int(round(w1_s * fs)), 1)
    w2 = max(int(round(w2_s * fs)), w1 + 1)

    kernel1 = np.ones(w1) / w1
    kernel2 = np.ones(w2) / w2
    ma_peak = np.convolve(squared, kernel1, mode="same")
    ma_beat = np.convolve(squared, kernel2, mode="same")

    alpha = 0.005 * float(np.mean(squared))                # (2) tighter β for rPPG
    thr = ma_beat + alpha
    boi = ma_peak > thr                                    # block-of-interest mask

    peaks: list[int] = []
    in_block = False
    start = 0
    for i in range(len(boi)):
        if boi[i] and not in_block:
            in_block = True
            start = i
        elif not boi[i] and in_block:
            in_block = False
            if i - start >= w1:
                peaks.append(start + int(np.argmax(w[start:i])))
    if in_block and (len(boi) - start) >= w1:
        peaks.append(start + int(np.argmax(w[start:])))

    # Adaptive refractory pass — suppresses dicrotic-notch double-picks.
    # Two true systolic peaks can never be closer than ~0.7·RR because
    # the dicrotic wave always falls in the first half of the cardiac cycle.
    # With β tightened for rPPG SNR (α = 0.005·mean²), TERMA otherwise picks
    # up the dicrotic wave as its own block — the ectopic filter then deletes
    # BOTH the S→D and D→S IBIs, halving usable coverage.
    #
    # When the caller passes an HR prior (Welch PSD on the same waveform), we
    # use 0.7 × RR_prior as the refractory window — much more reliable than
    # the median of the raw peak set, which is itself biased short by the
    # very dicrotic detections we are trying to remove.
    # Floor: 300 ms (physiologic ceiling of 200 BPM) so the filter still
    # applies when the prior is missing or out of range.
    if len(peaks) >= 3:
        if hr_prior_bpm is not None and 30.0 <= float(hr_prior_bpm) <= 200.0:
            rr_prior_samples = (60.0 / float(hr_prior_bpm)) * fs
            min_gap = max(int(round(0.30 * fs)), int(round(0.70 * rr_prior_samples)))
        else:
            median_ibi = int(np.median(np.diff(peaks)))
            min_gap = max(int(round(0.30 * fs)), int(0.5 * median_ibi))
        merged = [peaks[0]]
        for p in peaks[1:]:
            if p - merged[-1] < min_gap:
                if w[p] > w[merged[-1]]:
                    merged[-1] = p   # keep the taller of the two — the true systole
            else:
                merged.append(p)
        peaks = merged

    return np.array(peaks, dtype=np.int64)


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


def extract_hrv(
    bvp: np.ndarray, fps: float, hr_prior_bpm: Optional[float] = None
) -> Optional[HRVResult]:
    """
    Main entry point. Returns None if a reliable HRV estimate cannot be formed.

    `hr_prior_bpm` is the heart-rate estimate from the caller (typically
    PhysMamba or Welch on the same waveform). When supplied it is used to
    set TERMA's refractory window, which dramatically reduces dicrotic
    double-picks on noisy rPPG signals.
    """
    if len(bvp) == 0 or fps <= 0:
        return None

    sig = _upsample(np.asarray(bvp, dtype=np.float64), fps)
    if len(sig) < TARGET_FPS * 15:   # <15 s — not enough beats for stable HRV
        return None

    # Elgendi TERMA peak detection — far higher recall than a global
    # prominence threshold on noisy rPPG BVP.
    peaks = _elgendi_terma_peaks(sig, TARGET_FPS, hr_prior_bpm=hr_prior_bpm)
    if len(peaks) < 20:
        logger.info(f"HRV rejected: only {len(peaks)} TERMA peaks detected")
        return None

    # Sub-sample peak refinement — absolutely critical for HRV accuracy.
    # Refine against the normalised waveform (same sign convention as TERMA)
    # so the parabola fit is well-conditioned regardless of BVP amplitude.
    w = (sig - sig.mean()) / (sig.std() + 1e-8)
    if float(np.mean(np.clip(-w, 0.0, None) ** 2)) > 1.25 * float(np.mean(np.clip(w, 0.0, None) ** 2)):
        w = -w
    refined = np.array([_parabolic_refine(w, int(p)) for p in peaks])
    ibis_ms = np.diff(refined) / TARGET_FPS * 1000.0

    clean = _clean_ibis(ibis_ms)
    if len(clean) < 30:
        logger.info(f"HRV rejected: only {len(clean)} clean IBIs of {len(ibis_ms)} raw (need ≥30)")
        return None

    # Beat-coverage gate. Shaffer 2017 / Camm 1996 require ≥ 80 % clean beat
    # coverage for short-term time-domain HRV to be trustworthy. A low
    # coverage means the peak detector missed whole runs of beats and the
    # ectopic filter has been deleting multi-beat gaps — the surviving IBIs
    # are a biased remnant, not the true rhythm. Reject rather than report
    # inflated RMSSD / CVSD (which would make stress look "Low" on a noisy
    # signal).
    total_s = len(sig) / TARGET_FPS
    coverage = float(np.sum(clean) / 1000.0) / max(total_s, 1e-6)
    if coverage < 0.80:
        logger.info(
            f"HRV rejected: beat coverage only {coverage:.0%} "
            f"(n_raw={len(peaks)}, n_clean={len(clean)}, mean_RR={np.mean(clean):.0f}ms, total={total_s:.0f}s)"
        )
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
