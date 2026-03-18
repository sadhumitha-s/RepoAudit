from pydantic_settings import BaseSettings
from functools import lru_cache
import os


class Settings(BaseSettings):
    supabase_url: str = ""
    supabase_service_role_key: str = ""
    groq_api_key: str = ""
    redis_url: str = "redis://localhost:6379/0"
    allowed_origins: str = "http://localhost:3000"
    clone_base_dir: str = "/tmp/repoaudit_clones"
    max_repo_size_mb: int = 200
    celery_broker_url: str = "redis://localhost:6379/0"
    celery_result_backend: str = "redis://localhost:6379/1"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


@lru_cache
def get_settings() -> Settings:
    return Settings()