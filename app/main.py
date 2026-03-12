"""FastAPI app with RabbitMQ worker running in lifespan."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger

from app.config import get_settings
from app.publisher import close_publisher
from app.router import router
from app.worker import Worker
from app.logger import setup_logging, trace_context

settings = get_settings()

# Initialize logging as early as possible
setup_logging(debug=settings.DEBUG)

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

@app.middleware("http")
async def add_tracing(request, call_next):
    trace_id = request.headers.get("X-Trace-Id")
    with trace_context(trace_id=trace_id):
        response = await call_next(request)
        if trace_id:
            response.headers["X-Trace-Id"] = trace_id
        return response


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
