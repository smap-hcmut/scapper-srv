"""Logging setup for production-friendly worker output."""

from __future__ import annotations

import sys

from loguru import logger

from app.config import Settings


def configure_logging(settings: Settings) -> None:
    level = (settings.LOG_LEVEL or ("DEBUG" if settings.DEBUG else "WARNING")).upper()
    serialize = settings.LOGGER_ENCODING.lower() == "json"

    logger.remove()
    logger.add(
        sys.stderr,
        level=level,
        serialize=serialize,
        backtrace=settings.DEBUG,
        diagnose=settings.DEBUG,
    )
