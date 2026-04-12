"""
Async fire-and-forget video upload to Supabase Storage.
Runs after the analysis response is returned so user never waits for it.
Uses ffmpeg H.264 compression to get full 60s video under Supabase's 50MB limit.
"""
import logging
import os
import subprocess
import tempfile
import uuid
from pathlib import Path

import httpx

logger = logging.getLogger(__name__)

SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY = os.getenv("SUPABASE_ANON_KEY", "")
BUCKET = "scan-videos"
MAX_FILE_SIZE_MB = 45


def _compress_for_upload(video_path: Path) -> Path:
    """
    Compress video using ffmpeg H.264 (libx264) to fit under Supabase's 50MB limit.
    Returns path to compressed copy; caller must delete it.
    Falls back to original path if ffmpeg is unavailable.
    """
    tmp = tempfile.NamedTemporaryFile(suffix=".mp4", delete=False)
    tmp.close()
    tmp_path = Path(tmp.name)
    try:
        result = subprocess.run(
            [
                "ffmpeg", "-y",
                "-i", str(video_path),
                "-vcodec", "libx264",
                "-crf", "28",         # quality: 23=good, 28=smaller, 35=low
                "-preset", "fast",
                "-acodec", "aac",
                "-b:a", "64k",
                "-movflags", "+faststart",
                str(tmp_path),
            ],
            capture_output=True,
            timeout=120,
        )
        if result.returncode != 0:
            logger.warning(f"ffmpeg compression failed: {result.stderr[-300:].decode(errors='replace')}")
            tmp_path.unlink(missing_ok=True)
            return video_path  # fallback: try original
        return tmp_path
    except (FileNotFoundError, subprocess.TimeoutExpired) as e:
        logger.warning(f"ffmpeg not available or timed out ({e}), uploading original.")
        tmp_path.unlink(missing_ok=True)
        return video_path


async def upload_video(video_path: Path) -> str | None:
    """
    Upload full 60s video to Supabase Storage after H.264 compression.
    Returns the public URL or None on failure. Never raises.
    """
    if not SUPABASE_URL or not SUPABASE_KEY:
        return None

    compressed_path = None
    try:
        compressed_path = _compress_for_upload(video_path)
        upload_path = compressed_path

        file_size = upload_path.stat().st_size if upload_path.exists() else 0
        file_size_mb = file_size / (1024 * 1024)

        if file_size_mb > MAX_FILE_SIZE_MB:
            logger.warning(f"Compressed video still {file_size_mb:.1f}MB — skipping upload.")
            return None

        filename = f"{uuid.uuid4()}.mp4"
        url = f"{SUPABASE_URL}/storage/v1/object/{BUCKET}/{filename}"
        logger.info(f"Uploading video {filename} ({file_size_mb:.1f}MB) to Supabase...")

        async with httpx.AsyncClient(timeout=120) as client:
            with open(upload_path, "rb") as f:
                video_bytes = f.read()

            resp = await client.post(
                url,
                headers={
                    "apikey": SUPABASE_KEY,
                    "Authorization": f"Bearer {SUPABASE_KEY}",
                    "Content-Type": "video/mp4",
                },
                content=video_bytes,
            )
            logger.info(f"Supabase storage response: {resp.status_code} {resp.text[:200]}")
            resp.raise_for_status()

        public_url = f"{SUPABASE_URL}/storage/v1/object/public/{BUCKET}/{filename}"
        logger.info(f"Video uploaded successfully: {public_url}")
        return public_url

    except Exception as e:
        logger.error(f"Video upload to Supabase failed: {type(e).__name__}: {e}")
        return None
    finally:
        if compressed_path and compressed_path != video_path:
            try:
                os.unlink(compressed_path)
            except Exception:
                pass
