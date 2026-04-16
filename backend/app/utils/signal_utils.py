import numpy as np
from scipy.signal import resample


def downsample_waveform(arr: np.ndarray, from_fps: float, to_fps: int = 5) -> np.ndarray:
    """Downsample a waveform from `from_fps` to `to_fps` points/second."""
    if from_fps <= 0 or len(arr) == 0:
        return arr
    duration_s = len(arr) / from_fps
    target_len = max(1, int(duration_s * to_fps))
    return resample(arr, target_len)


def normalize_signal(arr: np.ndarray) -> np.ndarray:
    """Normalize signal to [-1, 1] range."""
    min_val, max_val = arr.min(), arr.max()
    if max_val - min_val < 1e-9:
        return np.zeros_like(arr)
    return 2.0 * (arr - min_val) / (max_val - min_val) - 1.0


def validate_bpm(bpm: float) -> float:
    """Clamp BPM to a physiologically plausible range and raise if wildly off."""
    if bpm < 30 or bpm > 220:
        raise ValueError(
            f"Estimated BPM {bpm:.1f} is outside physiological range (30–220). "
            "Ensure the face is clearly visible and the video is well-lit."
        )
    return round(bpm, 1)


def welch_hr(waveform: np.ndarray, fps: float) -> float | None:
    """
    Estimate HR via Welch PSD peak in 0.7–4 Hz band. Returns BPM, or None
    if signal is too short / noisy to give a clear peak. Used as an
    independent cross-check against the primary model output.
    """
    from scipy.signal import welch

    if fps <= 0 or len(waveform) < fps * 5:
        return None

    nperseg = max(64, min(int(fps * 10), len(waveform) // 2))
    freqs, psd = welch(waveform, fs=fps, nperseg=nperseg, noverlap=nperseg // 2)
    mask = (freqs >= 0.7) & (freqs <= 4.0)
    if not mask.any():
        return None
    band_psd = psd[mask]
    band_freqs = freqs[mask]
    if band_psd.max() <= 0:
        return None
    peak_freq = float(band_freqs[int(np.argmax(band_psd))])
    return round(peak_freq * 60.0, 1)


def estimate_confidence(waveform: np.ndarray, fps: float) -> float:
    """
    Multi-factor confidence score [0, 1].
    Combines spectral SNR (power in HR band vs total) and peak sharpness
    (how isolated the dominant frequency is vs its neighbours).
    More signal (longer recording) → more reliable estimate.
    """
    from scipy.signal import welch

    if len(waveform) < fps * 5:
        return 0.0

    # Use Welch for more stable PSD estimate
    nperseg = max(64, min(int(fps * 10), len(waveform) // 2))
    freqs, psd = welch(waveform, fs=fps, nperseg=nperseg, noverlap=nperseg // 2)

    hr_mask = (freqs >= 0.7) & (freqs <= 4.0)
    total_power = psd.sum()
    hr_power = psd[hr_mask].sum()

    if total_power < 1e-12:
        return 0.0

    # Factor 1: spectral concentration in HR band
    snr_ratio = hr_power / total_power
    snr_score = float(np.clip((snr_ratio - 0.15) / 0.5, 0.0, 1.0))

    # Factor 2: peak sharpness — peak power vs mean HR-band power
    hr_psd = psd[hr_mask]
    peak_val = hr_psd.max()
    mean_val = hr_psd.mean() + 1e-12
    sharpness = float(np.clip((peak_val / mean_val - 1.5) / 8.0, 0.0, 1.0))

    # Combine: SNR weighted more heavily, sharpness as secondary signal
    confidence = float(np.clip(0.7 * snr_score + 0.3 * sharpness, 0.0, 1.0))
    return round(confidence, 2)
