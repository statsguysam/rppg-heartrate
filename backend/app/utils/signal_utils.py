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


def estimate_confidence(waveform: np.ndarray, fps: float) -> float:
    """
    Rough SNR-based confidence score [0, 1].
    Computes the ratio of power at the dominant HR frequency to total power.
    """
    if len(waveform) < fps * 5:
        return 0.0

    freqs = np.fft.rfftfreq(len(waveform), d=1.0 / fps)
    power = np.abs(np.fft.rfft(waveform)) ** 2

    # Valid HR band: 0.7–4 Hz (42–240 BPM)
    hr_mask = (freqs >= 0.7) & (freqs <= 4.0)
    total_power = power.sum()
    hr_power = power[hr_mask].sum()

    if total_power < 1e-12:
        return 0.0

    snr_ratio = hr_power / total_power
    # Scale: SNR > 0.6 → high confidence; SNR < 0.2 → low confidence
    confidence = float(np.clip((snr_ratio - 0.15) / 0.5, 0.0, 1.0))
    return round(confidence, 2)
