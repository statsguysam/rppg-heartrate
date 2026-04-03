"""
Unit tests for app/services/video_service.py

validate_video runs real OpenCV logic — tested against synthetic videos
from conftest.py.  save_upload is tested with in-memory bytes.
"""
import io
import os
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.video_service import validate_video, cleanup
from app.config import settings


# ── validate_video ────────────────────────────────────────────────────────────

class TestValidateVideo:
    def test_valid_video_returns_fps_and_duration(self, valid_video_path):
        fps, duration = validate_video(valid_video_path)
        assert 25.0 <= fps <= 35.0          # synthetic video is 30 fps
        assert 55.0 <= duration <= 65.0      # synthetic video is 60 s

    def test_short_video_raises_422(self, short_video_path):
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc:
            validate_video(short_video_path)
        assert exc.value.status_code == 422
        assert "short" in exc.value.detail.lower()

    def test_no_face_raises_422(self, no_face_video_path):
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc:
            validate_video(no_face_video_path)
        assert exc.value.status_code == 422
        assert "face" in exc.value.detail.lower()

    def test_corrupt_file_raises_422(self, corrupt_file_path):
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc:
            validate_video(corrupt_file_path)
        assert exc.value.status_code == 422

    def test_nonexistent_file_raises_422(self, tmp_path):
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc:
            validate_video(tmp_path / "ghost.mp4")
        assert exc.value.status_code == 422


# ── cleanup ───────────────────────────────────────────────────────────────────

class TestCleanup:
    def test_cleanup_removes_existing_file(self, tmp_path):
        f = tmp_path / "test.mp4"
        f.write_bytes(b"data")
        assert f.exists()
        cleanup(f)
        assert not f.exists()

    def test_cleanup_does_not_raise_for_missing_file(self, tmp_path):
        """missing_ok=True — should never raise."""
        cleanup(tmp_path / "nonexistent.mp4")  # no exception


# ── save_upload ───────────────────────────────────────────────────────────────

class TestSaveUpload:
    @pytest.mark.asyncio
    async def test_saves_bytes_to_disk(self, tmp_path):
        from app.services.video_service import save_upload

        payload = b"fake video bytes" * 100
        mock_file = AsyncMock()
        mock_file.read = AsyncMock(side_effect=[payload, b""])

        with patch.object(settings, "upload_dir", str(tmp_path)):
            path = await save_upload(mock_file)

        assert path.exists()
        assert path.read_bytes() == payload
        path.unlink()

    @pytest.mark.asyncio
    async def test_rejects_oversized_file(self, tmp_path):
        from app.services.video_service import save_upload
        from fastapi import HTTPException

        # Write a temp file that exceeds max_video_size_mb
        big_data = b"x" * (1024 * 1024)   # 1 MB per chunk

        mock_file = AsyncMock()
        call_count = [0]

        async def chunked_read(n):
            call_count[0] += 1
            if call_count[0] <= 200:   # 200 MB → over the 150 MB limit
                return big_data
            return b""

        mock_file.read = chunked_read

        with patch.object(settings, "upload_dir", str(tmp_path)):
            with pytest.raises(HTTPException) as exc:
                await save_upload(mock_file)

        assert exc.value.status_code == 413
        # Ensure no leaked temp file
        assert not any(tmp_path.iterdir())
