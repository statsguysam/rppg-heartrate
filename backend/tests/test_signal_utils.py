"""Unit tests for app/utils/signal_utils.py"""
import math
import numpy as np
import pytest

from app.utils.signal_utils import (
    downsample_waveform,
    normalize_signal,
    validate_bpm,
    estimate_confidence,
)


# ── normalize_signal ──────────────────────────────────────────────────────────

class TestNormalizeSignal:
    def test_output_range_is_minus1_to_1(self):
        arr = np.array([0.0, 5.0, 10.0, 3.0])
        out = normalize_signal(arr)
        assert out.min() == pytest.approx(-1.0)
        assert out.max() == pytest.approx(1.0)

    def test_flat_signal_returns_zeros(self):
        arr = np.full(100, 3.14)
        out = normalize_signal(arr)
        np.testing.assert_array_equal(out, np.zeros(100))

    def test_preserves_shape(self):
        arr = np.random.randn(500)
        assert normalize_signal(arr).shape == (500,)

    def test_single_element(self):
        arr = np.array([42.0])
        out = normalize_signal(arr)
        assert out[0] == pytest.approx(0.0)


# ── downsample_waveform ───────────────────────────────────────────────────────

class TestDownsampleWaveform:
    def test_output_length_correct(self):
        # 30 fps × 60 s = 1800 samples → 5 fps × 60 s = 300 samples
        arr = np.random.randn(1800)
        out = downsample_waveform(arr, from_fps=30.0, to_fps=5)
        assert len(out) == 300

    def test_already_at_target_fps(self):
        arr = np.random.randn(300)
        out = downsample_waveform(arr, from_fps=5.0, to_fps=5)
        assert len(out) == 300

    def test_empty_array_returns_empty(self):
        arr = np.array([])
        out = downsample_waveform(arr, from_fps=30.0, to_fps=5)
        assert len(out) == 0

    def test_zero_fps_returns_original(self):
        arr = np.random.randn(100)
        out = downsample_waveform(arr, from_fps=0, to_fps=5)
        np.testing.assert_array_equal(out, arr)


# ── validate_bpm ──────────────────────────────────────────────────────────────

class TestValidateBpm:
    @pytest.mark.parametrize("bpm", [40.0, 60.0, 72.5, 100.0, 180.0, 220.0])
    def test_valid_bpm_returns_value(self, bpm):
        assert validate_bpm(bpm) == pytest.approx(bpm, abs=0.1)

    @pytest.mark.parametrize("bpm", [0.0, 29.9, 220.1, 999.0, -10.0])
    def test_invalid_bpm_raises(self, bpm):
        with pytest.raises(ValueError, match="physiological"):
            validate_bpm(bpm)

    def test_rounds_to_one_decimal(self):
        result = validate_bpm(72.456789)
        assert result == pytest.approx(72.5, abs=0.01)


# ── estimate_confidence ───────────────────────────────────────────────────────

class TestEstimateConfidence:
    def _pure_sine(self, freq_hz: float, fps: float, duration_s: float) -> np.ndarray:
        """Clean sine wave at exactly freq_hz — should yield high confidence."""
        t = np.arange(int(duration_s * fps)) / fps
        return np.sin(2 * math.pi * freq_hz * t)

    def test_clean_hr_signal_high_confidence(self):
        # 1.2 Hz = 72 BPM — squarely inside the valid HR band
        signal = self._pure_sine(1.2, fps=30.0, duration_s=60.0)
        conf = estimate_confidence(signal, fps=30.0)
        assert conf > 0.7, f"Expected high confidence, got {conf}"

    def test_noise_signal_low_confidence(self):
        rng = np.random.default_rng(42)
        noise = rng.standard_normal(1800)
        conf = estimate_confidence(noise, fps=30.0)
        assert conf < 0.6, f"Expected low confidence for noise, got {conf}"

    def test_empty_signal_returns_zero(self):
        assert estimate_confidence(np.array([]), fps=30.0) == 0.0

    def test_short_signal_returns_zero(self):
        # < 5 seconds at 30 fps
        short = np.random.randn(100)
        assert estimate_confidence(short, fps=30.0) == 0.0

    def test_confidence_between_0_and_1(self):
        rng = np.random.default_rng(0)
        for _ in range(10):
            signal = rng.standard_normal(900)
            conf = estimate_confidence(signal, fps=30.0)
            assert 0.0 <= conf <= 1.0
