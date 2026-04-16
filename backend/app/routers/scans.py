import logging
import os
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
import httpx

logger = logging.getLogger(__name__)
router = APIRouter()

SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY = os.getenv("SUPABASE_ANON_KEY", "")


class ScanRecord(BaseModel):
    bpm: float
    confidence: float
    sbp: Optional[float] = None
    dbp: Optional[float] = None
    bp_confidence: Optional[float] = None
    rmssd_ms: Optional[float] = None
    sdnn_ms: Optional[float] = None
    pnn50: Optional[float] = None
    hrv_confidence: Optional[float] = None
    respiration_bpm: Optional[float] = None
    respiration_confidence: Optional[float] = None
    stress_score: Optional[int] = None
    stress_label: Optional[str] = None
    stress_baevsky_si: Optional[float] = None
    stress_confidence: Optional[float] = None
    age: Optional[int] = None
    sex: Optional[str] = None
    activity: Optional[str] = None
    stress: Optional[str] = None
    caffeine: Optional[str] = None
    medications: Optional[str] = None
    video_url: Optional[str] = None
    comment: Optional[str] = None
    device_id: Optional[str] = None  # anonymous device identifier


@router.post("/scans", status_code=201)
async def save_scan(record: ScanRecord):
    """Save a scan result to Supabase. Silently succeeds even if Supabase is not configured."""
    if not SUPABASE_URL or not SUPABASE_KEY:
        return {"saved": False, "reason": "database not configured"}

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(
                f"{SUPABASE_URL}/rest/v1/scans",
                headers={
                    "apikey": SUPABASE_KEY,
                    "Authorization": f"Bearer {SUPABASE_KEY}",
                    "Content-Type": "application/json",
                    "Prefer": "return=minimal",
                },
                json=record.model_dump(exclude_none=True),
            )
            resp.raise_for_status()
            return {"saved": True}
    except Exception as e:
        logger.warning(f"Failed to save scan to Supabase: {e}")
        return {"saved": False, "reason": str(e)}
