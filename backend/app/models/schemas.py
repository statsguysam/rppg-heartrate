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
    message: str = "success"


class HealthResponse(BaseModel):
    status: str
    model: str
    version: str = "0.1.0"
