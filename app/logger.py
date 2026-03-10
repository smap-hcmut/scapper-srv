import sys
from contextvars import ContextVar
from typing import Optional
from loguru import logger
from contextlib import contextmanager

# Trace ID context variable
_trace_id_var: ContextVar[Optional[str]] = ContextVar("trace_id", default=None)

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
    
    if not debug:
        # Production: Use JSON serialization
        logger.add(
            sys.stdout,
            serialize=True,
            level=level,
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
        )
    
    logger.info(f"Logging initialized at {level} level (JSON={not debug})")
    
    logger.info(f"Logging initialized at {level} level")
