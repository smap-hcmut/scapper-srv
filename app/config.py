"""Configuration via pydantic-settings + .env file."""

from functools import lru_cache

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # App
    APP_NAME: str = "Scapper Worker Service"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False

    # RabbitMQ
    RABBITMQ_URL: str = "amqp://guest:guest@localhost:5672/"

    # TinLikeSub API (main API this worker calls via SDK)
    API_BASE_URL: str = "http://localhost:8104"
    API_KEY: str = ""
    API_SECRET_KEY: str = ""

    # Worker
    WORKER_PREFETCH_COUNT: int = 1
    OUTPUT_DIR: str = "output"

    model_config = {"env_file": ".env", "extra": "ignore"}


@lru_cache()
def get_settings() -> Settings:
    return Settings()
