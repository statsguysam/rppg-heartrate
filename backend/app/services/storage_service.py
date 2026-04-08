"""
Async fire-and-forget video upload to Supabase Storage.
Runs after the analysis response is returned so user never waits for it.
"""
import asyncio
import logging
import os
import uuid
from pathlib import Path

import httpx

logger = logging.getLogger(__name__)

SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY = os.getenv("SUPABASE_ANON_KEY", "")
BUCKET = "scan-videos"
MAX_UPLOAD_SECONDS = 20  # trim to 20s before upload — keeps file ~10MB


def _trim_for_upload(video_path: Path) -> Path:
    """Return a trimmed copy of the video (max 20s). Caller must delete the copy."""
    import cv2, tempfile
    cap = cv2.VideoCapture(str(video_path))
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    max_frames = int(fps * MAX_UPLOAD_SECONDS)
    if total_frames <= max_frames:
        cap.release()
        return video_path  # already short enough

    w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    tmp = tempfile.NamedTemporaryFile(suffix=".mp4", delete=False)
    tmp.close()
    out = cv2.VideoWriter(tmp.name, cv2.VideoWriter_fourcc(*"mp4v"), fps, (w, h))
    written = 0
    while written < max_frames:
        ret, frame = cap.read()
        if not ret:
            break
        out.write(frame)
        written += 1
    cap.release()
    out.release()
    return Path(tmp.name)


async def upload_video(video_path: Path) -> str | None:
    """
    Upload video to Supabase Storage. Returns the public URL or None on failure.
    Called as a background task — never raises.
    """
    if not SUPABASE_URL or not SUPABASE_KEY:
        return None

    trimmed_path = None
    try:
        # Trim to 20s to stay under Supabase's 50MB limit
        trimmed_path = _trim_for_upload(video_path)
        upload_path = trimmed_path

        filename = f"{uuid.uuid4()}.mp4"
        url = f"{SUPABASE_URL}/storage/v1/object/{BUCKET}/{filename}"
        file_size = upload_path.stat().st_size if upload_path.exists() else 0
        logger.info(f"Uploading video {filename} ({file_size/1024/1024:.1f}MB) to Supabase...")

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
        if trimmed_path and trimmed_path != video_path:
            try:
                os.unlink(trimmed_path)
            except Exception:
                pass
