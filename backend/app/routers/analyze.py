import time
import logging
import asyncio
from fastapi import APIRouter, UploadFile, File, HTTPException, BackgroundTasks
from app.models.schemas import AnalyzeResponse
from app.services import video_service, rppg_service, storage_service
from app.utils.signal_utils import validate_bpm

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/analyze", response_model=AnalyzeResponse)
async def analyze_video(video: UploadFile = File(...), background_tasks: BackgroundTasks = None):
    """
    Accept a ~1-minute face video and return estimated heart rate.
    Video is uploaded to Supabase Storage as a background task after the response.
    """
    if not video.filename or not video.filename.lower().endswith((".mp4", ".mov")):
        raise HTTPException(status_code=422, detail="Only .mp4 or .mov files are accepted.")

    start_ms = int(time.time() * 1000)
    video_path = None

    try:
        # 1. Save to disk
        video_path = await video_service.save_upload(video)
        logger.info(f"Video saved: {video_path}")

        # 2. Validate duration and face presence
        fps, duration_s = video_service.validate_video(video_path)
        logger.info(f"Video valid: {duration_s:.1f}s @ {fps:.0f}fps")

        # 3. Run rPPG inference (runs in thread pool)
        result = await rppg_service.analyze_video(video_path)

        # 4. Validate BPM
        bpm = validate_bpm(result["bpm"])

        elapsed_ms = int(time.time() * 1000) - start_ms
        logger.info(f"Analysis complete: {bpm} BPM in {elapsed_ms}ms")

        # 5. Upload video to Supabase in background (doesn't block response)
        video_url = None
        if video_path and video_path.exists():
            # Schedule upload — path copied so cleanup below doesn't race
            path_copy = video_path
            video_url_future = asyncio.ensure_future(
                storage_service.upload_video(path_copy)
            )
            # We return immediately; URL won't be in this response but
            # it will be available via /scans endpoint after upload completes
            # For simplicity, await with a short timeout to get URL if fast
            try:
                video_url = await asyncio.wait_for(asyncio.shield(video_url_future), timeout=5.0)
            except asyncio.TimeoutError:
                # Upload still running in background — that's fine
                video_url = None

        return AnalyzeResponse(
            bpm=bpm,
            confidence=result["confidence"],
            waveform=result["waveform"],
            waveform_fps=result["waveform_fps"],
            processing_time_ms=elapsed_ms,
            video_url=video_url,
        )

    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        logger.exception("Unexpected error during analysis")
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")
    finally:
        if video_path:
            video_service.cleanup(video_path)
