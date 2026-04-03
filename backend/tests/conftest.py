"""
Pytest fixtures that generate synthetic MP4 test videos using OpenCV.
No real face video required — face detection is satisfied by drawing an
oval skin-coloured blob that the Haar cascade will accept.
"""
import os
import math
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

import cv2
import numpy as np
import pytest
from fastapi.testclient import TestClient

# ── Make sure the app package is importable ──────────────────────────────────
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.main import app


# ── TestClient fixture ────────────────────────────────────────────────────────

@pytest.fixture(scope="session")
def client():
    """
    Synchronous TestClient.  We patch rppg_service.load_model so that the
    real PhysMamba weights are NOT loaded during test runs (fast + offline).
    Inference itself is also patched per-test where needed.
    """
    with patch("app.services.rppg_service.load_model", return_value=None):
        with TestClient(app, raise_server_exceptions=True) as c:
            yield c


# ── Video generation helpers ──────────────────────────────────────────────────

def _write_synthetic_video(path: str, duration_s: float, fps: int = 30,
                            draw_face: bool = True) -> None:
    """
    Write a synthetic MP4 to *path*.
    If draw_face=True, draws a skin-toned ellipse that the Haar cascade
    can detect.  The green channel is modulated with a 1.2 Hz sine wave
    to simulate a plausible rPPG signal.
    """
    w, h = 640, 480
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    out = cv2.VideoWriter(path, fourcc, fps, (w, h))

    n_frames = int(duration_s * fps)
    cx, cy = w // 2, h // 2
    rx, ry = 120, 160          # face ellipse radii

    for i in range(n_frames):
        t = i / fps
        frame = np.full((h, w, 3), 30, dtype=np.uint8)   # dark background

        if draw_face:
            # Skin-tone colour with subtle green-channel pulse (1.2 Hz ≈ 72 BPM)
            pulse = int(8 * math.sin(2 * math.pi * 1.2 * t))
            skin_bgr = (100, 140 + pulse, 180)
            cv2.ellipse(frame, (cx, cy), (rx, ry), 0, 0, 360, skin_bgr, -1)
            # Eyes — make it look more face-like for Haar
            cv2.circle(frame, (cx - 40, cy - 30), 15, (20, 20, 20), -1)
            cv2.circle(frame, (cx + 40, cy - 30), 15, (20, 20, 20), -1)

        out.write(frame)

    out.release()


@pytest.fixture(scope="session")
def valid_video_path(tmp_path_factory) -> Path:
    """60-second synthetic face video."""
    p = tmp_path_factory.mktemp("videos") / "valid_60s.mp4"
    _write_synthetic_video(str(p), duration_s=60.0, draw_face=True)
    return p


@pytest.fixture(scope="session")
def short_video_path(tmp_path_factory) -> Path:
    """30-second video — too short, should be rejected."""
    p = tmp_path_factory.mktemp("videos") / "short_30s.mp4"
    _write_synthetic_video(str(p), duration_s=30.0, draw_face=True)
    return p


@pytest.fixture(scope="session")
def no_face_video_path(tmp_path_factory) -> Path:
    """60-second video with no face content."""
    p = tmp_path_factory.mktemp("videos") / "noface_60s.mp4"
    _write_synthetic_video(str(p), duration_s=60.0, draw_face=False)
    return p


@pytest.fixture(scope="session")
def corrupt_file_path(tmp_path_factory) -> Path:
    """Not a video — just random bytes."""
    p = tmp_path_factory.mktemp("videos") / "corrupt.mp4"
    p.write_bytes(os.urandom(1024))
    return p


# ── Shared rPPG mock result ────────────────────────────────────────────────────

MOCK_ANALYZE_RESULT = {
    "bpm": 72.0,
    "confidence": 0.85,
    "waveform": [float(math.sin(2 * math.pi * i / 25)) for i in range(300)],
    "waveform_fps": 5,
}
