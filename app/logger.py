import logging
import sys
import os
import json
import email.utils
import uuid
from datetime import timezone, timedelta
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

def generate_trace_id() -> str:
    return str(uuid.uuid4())

def ensure_trace_id() -> str:
    trace_id = _trace_id_var.get()
    if trace_id:
        return trace_id
    trace_id = generate_trace_id()
    _trace_id_var.set(trace_id)
    return trace_id

def set_trace_id(trace_id: str) -> None:
    _trace_id_var.set(trace_id)

@contextmanager
def trace_context(trace_id: Optional[str] = None):
    token = _trace_id_var.set(trace_id or generate_trace_id())
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

    service_name = os.getenv("CONTAINER_NAME", "scapper-srv")

    ict_tz = timezone(timedelta(hours=7))

    def enrich_record(record):
        record["extra"]["trace_id"] = ensure_trace_id()
        return record

    logger.configure(patcher=enrich_record)

    def custom_json_sink(message):
        record = message.record
        dt = record["time"].astimezone(ict_tz)
        trace_id = record["extra"].get("trace_id") or ensure_trace_id()
        log_dict = {
            "timestamp": email.utils.format_datetime(dt),
            "trace_id": trace_id,
            "level": record["level"].name.lower(),
            "caller": f"{record['file'].name}:{record['line']}",
            "message": record["message"],
            "service": service_name,
        }
        # Include extra fields
        for key, value in record["extra"].items():
            if key != "trace_id" and key not in log_dict:
                log_dict[key] = value
        
        print(json.dumps(log_dict), flush=True)

    if not debug:
        # Production: Use custom JSON sink for standardized flattened output
        logger.add(
            custom_json_sink,
            filter=should_filter,
            level=level,
        )
    else:
        # Development: Use human-readable format
        def formatter(record):
            record["extra"]["trace_id"] = ensure_trace_id()
            fmt = "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{extra[trace_id]: <36}</cyan> | <level>{message}</level>\n"
            return fmt

        logger.add(
            sys.stdout,
            level=level,
            format=formatter,
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
