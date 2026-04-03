"""
Tests for POST /analyze

Strategy
--------
- The rppg_service.analyze_video coroutine is mocked in all tests to avoid
  loading the real PhysMamba model weights (which require GPU / large memory).
- video_service.validate_video runs for real so we test face-detection and
  duration logic against synthetically-generated videos from conftest.py.
"""
import io
from unittest.mock import AsyncMock, patch

import math
import pytest

MOCK_ANALYZE_RESULT = {
    "bpm": 72.0,
    "confidence": 0.85,
    "waveform": [float(math.sin(2 * math.pi * i / 25)) for i in range(300)],
    "waveform_fps": 5,
}


# ── Helpers ───────────────────────────────────────────────────────────────────

def _upload(client, path, filename="face.mp4", content_type="video/mp4"):
    """POST the file at *path* to /analyze, return response."""
    with open(path, "rb") as f:
        data = f.read()
    return client.post(
        "/analyze",
        files={"video": (filename, io.BytesIO(data), content_type)},
    )


def _mock_analyze():
    """Context-manager that patches analyze_video with a fast async mock."""
    return patch(
        "app.routers.analyze.rppg_service.analyze_video",
        new_callable=AsyncMock,
        return_value=MOCK_ANALYZE_RESULT,
    )


# ── Happy path ────────────────────────────────────────────────────────────────

def test_analyze_valid_video_returns_200(client, valid_video_path):
    with _mock_analyze():
        resp = _upload(client, valid_video_path)
    assert resp.status_code == 200, resp.text


def test_analyze_response_schema(client, valid_video_path):
    with _mock_analyze():
        data = _upload(client, valid_video_path).json()
    assert "bpm" in data
    assert "confidence" in data
    assert "waveform" in data
    assert "waveform_fps" in data
    assert "processing_time_ms" in data
    assert data["message"] == "success"


def test_analyze_bpm_is_float(client, valid_video_path):
    with _mock_analyze():
        data = _upload(client, valid_video_path).json()
    assert isinstance(data["bpm"], float)


def test_analyze_bpm_in_physiological_range(client, valid_video_path):
    with _mock_analyze():
        data = _upload(client, valid_video_path).json()
    assert 30.0 <= data["bpm"] <= 220.0


def test_analyze_confidence_between_0_and_1(client, valid_video_path):
    with _mock_analyze():
        data = _upload(client, valid_video_path).json()
    assert 0.0 <= data["confidence"] <= 1.0


def test_analyze_waveform_is_list_of_floats(client, valid_video_path):
    with _mock_analyze():
        data = _upload(client, valid_video_path).json()
    waveform = data["waveform"]
    assert isinstance(waveform, list)
    assert all(isinstance(v, float) for v in waveform)


def test_analyze_waveform_fps_is_positive_int(client, valid_video_path):
    with _mock_analyze():
        data = _upload(client, valid_video_path).json()
    assert isinstance(data["waveform_fps"], int)
    assert data["waveform_fps"] > 0


def test_analyze_processing_time_positive(client, valid_video_path):
    with _mock_analyze():
        data = _upload(client, valid_video_path).json()
    assert data["processing_time_ms"] > 0


# ── Rejection cases ───────────────────────────────────────────────────────────

def test_analyze_rejects_short_video(client, short_video_path):
    """Videos under 50s must return 422."""
    with _mock_analyze():
        resp = _upload(client, short_video_path)
    assert resp.status_code == 422
    assert "short" in resp.json()["detail"].lower()


def test_analyze_rejects_no_face(client, no_face_video_path):
    """Videos with no detected face must return 422."""
    with _mock_analyze():
        resp = _upload(client, no_face_video_path)
    assert resp.status_code == 422
    detail = resp.json()["detail"].lower()
    assert "face" in detail


def test_analyze_rejects_corrupt_file(client, corrupt_file_path):
    """Non-video binary data must return 422."""
    with _mock_analyze():
        resp = _upload(client, corrupt_file_path)
    assert resp.status_code == 422


def test_analyze_rejects_wrong_extension(client, valid_video_path):
    """Files not ending in .mp4/.mov must return 422 immediately."""
    with _mock_analyze():
        resp = client.post(
            "/analyze",
            files={"video": ("scan.avi", open(valid_video_path, "rb"), "video/avi")},
        )
    assert resp.status_code == 422
    assert "mp4" in resp.json()["detail"].lower() or "mov" in resp.json()["detail"].lower()


def test_analyze_rejects_missing_file(client):
    """Request with no file field must return 422."""
    resp = client.post("/analyze")
    assert resp.status_code == 422


# ── BPM validation edge cases ─────────────────────────────────────────────────

def test_analyze_rejects_bpm_below_30(client, valid_video_path):
    """If the model returns a physiologically impossible BPM, surface a 422."""
    with patch(
        "app.routers.analyze.rppg_service.analyze_video",
        new_callable=AsyncMock,
        return_value={**MOCK_ANALYZE_RESULT, "bpm": 10.0},
    ):
        resp = _upload(client, valid_video_path)
    assert resp.status_code == 422


def test_analyze_rejects_bpm_above_220(client, valid_video_path):
    with patch(
        "app.routers.analyze.rppg_service.analyze_video",
        new_callable=AsyncMock,
        return_value={**MOCK_ANALYZE_RESULT, "bpm": 300.0},
    ):
        resp = _upload(client, valid_video_path)
    assert resp.status_code == 422


# ── Cleanup ───────────────────────────────────────────────────────────────────

def test_temp_file_deleted_after_success(client, valid_video_path, tmp_path):
    """The uploaded temp file must be deleted after a successful response."""
    import app.services.video_service as vs
    saved_paths = []

    original_save = vs.save_upload

    async def tracking_save(file):
        path = await original_save(file)
        saved_paths.append(path)
        return path

    with patch("app.routers.analyze.video_service.save_upload", side_effect=tracking_save):
        with _mock_analyze():
            _upload(client, valid_video_path)

    for p in saved_paths:
        assert not p.exists(), f"Temp file was not cleaned up: {p}"


def test_temp_file_deleted_after_failure(client, short_video_path, tmp_path):
    """The temp file must also be deleted when validation fails."""
    import app.services.video_service as vs
    saved_paths = []

    original_save = vs.save_upload

    async def tracking_save(file):
        path = await original_save(file)
        saved_paths.append(path)
        return path

    with patch("app.routers.analyze.video_service.save_upload", side_effect=tracking_save):
        _upload(client, short_video_path)

    for p in saved_paths:
        assert not p.exists(), f"Temp file leaked after failure: {p}"
