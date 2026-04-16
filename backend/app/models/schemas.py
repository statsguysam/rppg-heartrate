from pydantic import BaseModel
from typing import Optional


class AnalyzeResponse(BaseModel):
    bpm: float
    confidence: float
    waveform: list[float]       # ~300 points downsampled for display
    waveform_fps: int = 5       # points per second (for x-axis rendering)
    processing_time_ms: int
    video_url: Optional[str] = None
    # BP estimate from pulse-wave morphology. Null when the BVP signal
    # is too noisy for reliable BP extraction.
    sbp: Optional[float] = None
    dbp: Optional[float] = None
    bp_confidence: Optional[float] = None
    # HRV (time-domain). Null when <30 clean IBIs detected.
    rmssd_ms: Optional[float] = None
    sdnn_ms: Optional[float] = None
    pnn50: Optional[float] = None
    hrv_confidence: Optional[float] = None
    # Respiration (breaths/min) via BW/AM/FM fusion.
    respiration_bpm: Optional[float] = None
    respiration_confidence: Optional[float] = None
    # Stress — Baevsky SI + CVSD time-domain blend (LF/HF requires ≥2 min RR,
    # not reliable from 60 s per ESC Task Force 1996). score: 0–100,
    # label: Low|Normal|Elevated|High.
    stress_score: Optional[int] = None
    stress_label: Optional[str] = None
    stress_baevsky_si: Optional[float] = None
    stress_confidence: Optional[float] = None
    message: str = "success"


class HealthResponse(BaseModel):
    status: str
    model: str
    version: str = "0.1.0"
