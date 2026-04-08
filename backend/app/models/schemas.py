from pydantic import BaseModel
from typing import Optional


class AnalyzeResponse(BaseModel):
    bpm: float
    confidence: float
    waveform: list[float]       # ~300 points downsampled for display
    waveform_fps: int = 5       # points per second (for x-axis rendering)
    processing_time_ms: int
    video_url: Optional[str] = None
    message: str = "success"


class HealthResponse(BaseModel):
    status: str
    model: str
    version: str = "0.1.0"
