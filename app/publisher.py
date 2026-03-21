"""Publish task messages to RabbitMQ queues."""

import json

import aio_pika
from aio_pika import Message, DeliveryMode
from loguru import logger

from app.config import get_settings
from app.logger import ensure_trace_id, get_trace_id

_connection: aio_pika.abc.AbstractRobustConnection | None = None
_channel: aio_pika.abc.AbstractChannel | None = None

INGEST_EXECUTION_COMPLETION_QUEUE = "ingest_task_completions"
INGEST_DRYRUN_COMPLETION_QUEUE = "ingest_dryrun_completions"
RUNTIME_KIND_DRYRUN = "dryrun"


async def get_channel() -> aio_pika.abc.AbstractChannel:
    """Get or create a persistent RabbitMQ channel."""
    global _connection, _channel
    settings = get_settings()
    if _connection is None or _connection.is_closed:
        _connection = await aio_pika.connect_robust(settings.RABBITMQ_URL)
        _channel = await _connection.channel()
    if _channel is None or _channel.is_closed:
        _channel = await _connection.channel()
    return _channel


async def publish_task(queue_name: str, payload: dict) -> None:
    """Publish a task message to a durable queue with persistent delivery."""
    channel = await get_channel()
    await channel.declare_queue(queue_name, durable=True)

    headers = {}
    trace_id = get_trace_id() or ensure_trace_id()
    if trace_id:
        headers["X-Trace-Id"] = trace_id

    message = Message(
        body=json.dumps(payload, ensure_ascii=False).encode(),
        delivery_mode=DeliveryMode.PERSISTENT,
        content_type="application/json",
        headers=headers,
    )
    await channel.default_exchange.publish(message, routing_key=queue_name)
    logger.info(
        f"Published to {queue_name}: action={payload.get('action')} "
        f"task_id={payload.get('task_id', '')[:8]}"
    )


async def publish_completion(payload: dict) -> None:
    """Publish a completion message to the routed ingest completion queue."""
    queue_name = _resolve_completion_queue(payload)
    channel = await get_channel()
    await channel.declare_queue(queue_name, durable=True)
    headers = {}
    trace_id = get_trace_id() or ensure_trace_id()
    if trace_id:
        headers["X-Trace-Id"] = trace_id
    message = Message(
        body=json.dumps(payload, ensure_ascii=False).encode(),
        delivery_mode=DeliveryMode.PERSISTENT,
        content_type="application/json",
        headers=headers,
    )
    await channel.default_exchange.publish(message, routing_key=queue_name)
    logger.info(
        f"Published completion to {queue_name}: task_id={payload.get('task_id', '')[:8]} "
        f"status={payload.get('status')}"
    )


def _resolve_completion_queue(payload: dict) -> str:
    metadata = payload.get("metadata") if isinstance(payload, dict) else None
    if not isinstance(metadata, dict):
        return INGEST_EXECUTION_COMPLETION_QUEUE

    runtime_kind = str(metadata.get("runtime_kind", "")).strip().lower()
    if runtime_kind == RUNTIME_KIND_DRYRUN:
        return INGEST_DRYRUN_COMPLETION_QUEUE

    return INGEST_EXECUTION_COMPLETION_QUEUE


async def close_publisher() -> None:
    """Close publisher connection (called on shutdown)."""
    global _connection, _channel
    if _channel and not _channel.is_closed:
        await _channel.close()
    if _connection and not _connection.is_closed:
        await _connection.close()
    _connection = None
    _channel = None
