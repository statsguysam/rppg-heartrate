import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers import health, analyze
from app.services import rppg_service
from app.config import settings

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s – %(message)s")
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: warm up the model so first request is fast
    logger.info(f"Loading {settings.model_name} model…")
    rppg_service.load_model()
    logger.info("Model ready. Server accepting requests.")
    yield
    # Shutdown: nothing to clean up


app = FastAPI(
    title="rPPG Heart Rate API",
    description="Estimate heart rate from a 1-minute facial video using PhysMamba.",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   # tighten for production
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(analyze.router)
