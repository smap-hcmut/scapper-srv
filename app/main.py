"""FastAPI app with RabbitMQ worker running in lifespan."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger

from app.config import get_settings
from app.publisher import close_publisher
from app.router import router
from app.worker import Worker

settings = get_settings()

_worker: Worker | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _worker

    # Startup: start the RabbitMQ consumer
    _worker = Worker()
    try:
        await _worker.start()
        logger.info("Worker started inside FastAPI lifespan")
    except Exception as e:
        logger.error(
            f"Failed to start worker: {e}. "
            "API endpoints will work but worker won't consume tasks."
        )
        _worker = None

    yield

    # Shutdown
    if _worker:
        await _worker.stop()
    await close_publisher()
    logger.info("Shutdown complete.")


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="Scapper Worker Service — RabbitMQ consumer + task submission API",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router, prefix="/api/v1")


@app.get("/")
async def root():
    return {
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "docs": "/docs",
    }


@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "worker_active": _worker is not None,
        "rabbitmq_url": (
            settings.RABBITMQ_URL.split("@")[-1]
            if "@" in settings.RABBITMQ_URL
            else settings.RABBITMQ_URL
        ),
        "api_base_url": settings.API_BASE_URL,
    }
