from fastapi import APIRouter
from app.models.schemas import HealthResponse
from app.config import settings

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
async def health_check():
    return HealthResponse(status="ok", model=settings.model_name)
