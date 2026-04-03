import os
import uuid
import asyncio
import aiofiles
from pathlib import Path
from fastapi import HTTPException, UploadFile

import cv2

from app.config import settings


async def save_upload(file: UploadFile) -> Path:
    """Stream-write the uploaded file to a temp path. Returns the path."""
    os.makedirs(settings.upload_dir, exist_ok=True)
    dest = Path(settings.upload_dir) / f"{uuid.uuid4()}.mp4"

    async with aiofiles.open(dest, "wb") as out:
        while chunk := await file.read(1024 * 1024):  # 1 MB chunks
            await out.write(chunk)

    # Check file size
    size_mb = dest.stat().st_size / (1024 * 1024)
    if size_mb > settings.max_video_size_mb:
        dest.unlink(missing_ok=True)
        raise HTTPException(
            status_code=413,
            detail=f"Video too large: {size_mb:.1f} MB (max {settings.max_video_size_mb} MB)",
        )

    return dest


def validate_video(path: Path) -> tuple[float, float]:
    """
    Opens video with OpenCV, validates duration and basic face detection.
    Returns (fps, duration_s).
    Raises HTTPException on failure.
    """
    cap = cv2.VideoCapture(str(path))
    if not cap.isOpened():
        raise HTTPException(status_code=422, detail="Could not open video file. Ensure it is a valid MP4.")

    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    frame_count = cap.get(cv2.CAP_PROP_FRAME_COUNT)
    duration_s = frame_count / fps

    if duration_s < settings.min_duration_s:
        cap.release()
        raise HTTPException(
            status_code=422,
            detail=f"Video too short: {duration_s:.1f}s (minimum {settings.min_duration_s}s). Please record for ~1 minute.",
        )
    if duration_s > settings.max_duration_s:
        cap.release()
        raise HTTPException(
            status_code=422,
            detail=f"Video too long: {duration_s:.1f}s (maximum {settings.max_duration_s}s).",
        )

    # Quick face detection on first 10 frames
    face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
    face_found = False
    for _ in range(10):
        ret, frame = cap.read()
        if not ret:
            break
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        faces = face_cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5)
        if len(faces) > 0:
            face_found = True
            break

    cap.release()

    if not face_found:
        raise HTTPException(
            status_code=422,
            detail="No face detected in the first seconds of video. Ensure your face is clearly visible, well-lit, and centered in frame.",
        )

    return fps, duration_s


def cleanup(path: Path) -> None:
    path.unlink(missing_ok=True)
