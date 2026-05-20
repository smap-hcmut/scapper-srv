"""Configuration via pydantic-settings + .env file."""

from functools import lru_cache

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # App
    MODE: str = "production"
    APP_NAME: str = "Scapper Worker Service"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False
    LOG_LEVEL: str = "WARNING"
    LOGGER_ENCODING: str = "json"

    # RabbitMQ
    RABBITMQ_URL: str = "amqp://admin:21042004@172.16.21.200:5673/"

    # TinLikeSub API (main API this worker calls via SDK)
    API_BASE_URL: str = "https://api.tinlikesub.pro/"
    API_KEY: str = "sk-9wC3UCwGeROwjw-ktWdd4YghZHK2NH2Zkhw6oZpLLjU"
    API_SECRET_KEY: str = ""

    # Worker
    WORKER_PREFETCH_COUNT: int = 1
    TASK_TIMEOUT_SECONDS: float = 600.0
    OUTPUT_DIR: str = "output"

    # MinIO
    MINIO_ENDPOINT: str = "172.16.21.10:9000"
    MINIO_ACCESS_KEY: str = "tantai"
    MINIO_SECRET_KEY: str = "21042004"
    MINIO_USE_SSL: bool = False
    MINIO_BUCKET: str = "ingest-data"

    model_config = {"env_file": ".env", "extra": "ignore"}


@lru_cache()
def get_settings() -> Settings:
    return Settings()
