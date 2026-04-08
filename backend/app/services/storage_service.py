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


async def upload_video(video_path: Path) -> str | None:
    """
    Upload video to Supabase Storage. Returns the public URL or None on failure.
    Called as a background task — never raises.
    """
    if not SUPABASE_URL or not SUPABASE_KEY:
        return None

    try:
        filename = f"{uuid.uuid4()}.mp4"
        url = f"{SUPABASE_URL}/storage/v1/object/{BUCKET}/{filename}"
        file_size = video_path.stat().st_size if video_path.exists() else 0
        logger.info(f"Uploading video {filename} ({file_size/1024/1024:.1f}MB) to Supabase...")

        async with httpx.AsyncClient(timeout=120) as client:
            with open(video_path, "rb") as f:
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
