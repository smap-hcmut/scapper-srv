import logging
import sys
from contextvars import ContextVar
from typing import Optional
from loguru import logger
from contextlib import contextmanager

# Trace ID context variable
_trace_id_var: ContextVar[Optional[str]] = ContextVar("trace_id", default=None)

class InterceptHandler(logging.Handler):
    def emit(self, record):
        # Get corresponding Loguru level if it exists
        try:
            level = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno

        # Find caller from where originated the logged message
        frame, depth = logging.currentframe(), 2
        while frame.f_code.co_filename == logging.__file__:
            frame = frame.f_back
            depth += 1

        logger.opt(depth=depth, exception=record.exc_info).log(level, record.getMessage())

def get_trace_id() -> Optional[str]:
    return _trace_id_var.get()

def set_trace_id(trace_id: str) -> None:
    _trace_id_var.set(trace_id)

@contextmanager
def trace_context(trace_id: Optional[str] = None):
    token = _trace_id_var.set(trace_id)
    try:
        yield
    finally:
        _trace_id_var.reset(token)

def setup_logging(debug: bool = False):
    """Setup loguru with custom formatter or JSON for production."""
    logger.remove()

    level = "DEBUG" if debug else "INFO"
    
    def should_filter(record):
        # Filter out Kubernetes health check spam
        message = record["message"]
        if "/scraper/health" in message:
            return False
        return True

    if not debug:
        # Production: Use JSON serialization
        logger.add(
            sys.stdout,
            serialize=True,
            level=level,
            filter=should_filter,
        )
    else:
        # Development: Use human-readable format
        def formatter(record):
            trace_id = _trace_id_var.get()
            record["extra"]["trace_id"] = trace_id if trace_id else "-"
            fmt = "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{extra[trace_id]: <36}</cyan> | <level>{message}</level>\n"
            return fmt

        logger.add(
            sys.stdout,
            format=formatter,
            level=level,
            colorize=True,
            backtrace=True,
            diagnose=True,
            filter=should_filter,
        )
    
    # Intercept all logs from standard logging
    logging.basicConfig(handlers=[InterceptHandler()], level=0, force=True)
    for name in ["uvicorn", "uvicorn.access", "uvicorn.error", "fastapi"]:
        _logger = logging.getLogger(name)
        _logger.handlers = [InterceptHandler()]
        _logger.propagate = False

    logger.info(f"Logging initialized at {level} level (JSON={not debug})")
