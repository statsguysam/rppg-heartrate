from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    upload_dir: str = "/tmp/rppg_uploads"
    max_video_size_mb: int = 150
    model_name: str = "PhysMamba"
    host: str = "0.0.0.0"
    port: int = 8000
    # Minimum/maximum allowed video duration in seconds
    min_duration_s: float = 50.0
    max_duration_s: float = 70.0


settings = Settings()
