import os
from fastapi import APIRouter
from app.models.schemas import HealthResponse
from app.config import settings
from app.services import storage_service

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
async def health_check():
    return HealthResponse(status="ok", model=settings.model_name)


@router.get("/debug-storage")
async def debug_storage():
    """Test Supabase Storage connectivity from Render."""
    import tempfile, os
    tmp = tempfile.NamedTemporaryFile(suffix=".mp4", delete=False)
    tmp.write(b"debug-test-data")
    tmp.close()
    from pathlib import Path
    url = await storage_service.upload_video(Path(tmp.name))
    os.unlink(tmp.name)
    return {
        "supabase_url_set": bool(os.getenv("SUPABASE_URL")),
        "supabase_key_set": bool(os.getenv("SUPABASE_ANON_KEY")),
        "upload_result": url,
    }
