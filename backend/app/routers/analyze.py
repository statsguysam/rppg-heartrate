import time
import logging
from typing import Optional
from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from app.models.schemas import AnalyzeResponse
from app.services import video_service, rppg_service, storage_service
from app.utils.signal_utils import validate_bpm

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/analyze", response_model=AnalyzeResponse)
async def analyze_video(
    video: UploadFile = File(...),
    age: Optional[int] = Form(None),
    sex: Optional[str] = Form(None),
    bmi: Optional[float] = Form(None),
):
    """
    Accept a ~1-minute face video and return estimated heart rate + BP.
    Demographics (age/sex/BMI) are optional and improve BP accuracy.
    Video is uploaded to Supabase Storage before cleanup.
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
        result = await rppg_service.analyze_video(video_path, age=age, sex=sex, bmi=bmi)

        # 4. Validate BPM
        bpm = validate_bpm(result["bpm"])

        elapsed_ms = int(time.time() * 1000) - start_ms
        logger.info(f"Analysis complete: {bpm} BPM in {elapsed_ms}ms")

        # 5. Upload video to Supabase Storage BEFORE cleanup (best-effort, never blocks result)
        try:
            video_url = await storage_service.upload_video(video_path)
            if video_url:
                logger.info(f"Video uploaded: {video_url}")
        except Exception as e:
            logger.warning(f"Video upload skipped: {e}")
            video_url = None

        return AnalyzeResponse(
            bpm=bpm,
            confidence=result["confidence"],
            waveform=result["waveform"],
            waveform_fps=result["waveform_fps"],
            processing_time_ms=elapsed_ms,
            video_url=video_url,
            sbp=result.get("sbp"),
            dbp=result.get("dbp"),
            bp_confidence=result.get("bp_confidence"),
            rmssd_ms=result.get("rmssd_ms"),
            sdnn_ms=result.get("sdnn_ms"),
            pnn50=result.get("pnn50"),
            hrv_confidence=result.get("hrv_confidence"),
            respiration_bpm=result.get("respiration_bpm"),
            respiration_confidence=result.get("respiration_confidence"),
            stress_score=result.get("stress_score"),
            stress_label=result.get("stress_label"),
            stress_lf_hf=result.get("stress_lf_hf"),
            stress_confidence=result.get("stress_confidence"),
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
