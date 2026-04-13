"""Configuration via pydantic-settings + .env file."""

from functools import lru_cache

from pydantic_settings import BaseSettings


from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # App
    APP_NAME: str = "Scapper Worker Service"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = Field(default=False)
    MODE: str = Field(default="dev")  # dev | production

    # RabbitMQ
    RABBITMQ_URL: str = Field(default="amqp://admin:21042004@172.16.21.200:5672/")

    # MinIO (used in production mode)
    MINIO_ENDPOINT: str = Field(default="172.16.21.10:9000")
    MINIO_ACCESS_KEY: str = Field(default="tantai")
    MINIO_SECRET_KEY: str = Field(default="21042004")
    MINIO_BUCKET: str = Field(default="ingest-data")
    MINIO_USE_SSL: bool = Field(default=False)
    MINIO_REGION: str = Field(default="us-east-1")

    # TinLikeSub API
    API_BASE_URL: str = Field(default="http://localhost:8104")
    API_KEY: str = Field(default="")
    API_SECRET_KEY: str = Field(default="")

    # Worker
    WORKER_PREFETCH_COUNT: int = Field(default=1)
    OUTPUT_DIR: str = Field(default="output")

    model_config = {"env_file": ".env", "extra": "ignore", "env_file_encoding": "utf-8"}


@lru_cache()
def get_settings() -> Settings:
    return Settings()
