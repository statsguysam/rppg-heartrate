FROM python:3.11-slim

WORKDIR /app

# System deps: OpenCV + ffmpeg for H.264 compression and keyframe re-encoding
RUN apt-get update && apt-get install -y \
    libgl1 libglib2.0-0 ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# JAX CPU — must be installed before open-rppg
RUN pip install --no-cache-dir "jax[cpu]"

COPY backend/requirements-cloud.txt .
RUN pip install --no-cache-dir -r requirements-cloud.txt

COPY backend/app/ ./app/

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--timeout-keep-alive", "180"]
