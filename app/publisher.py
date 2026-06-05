"""Publish task messages to RabbitMQ queues."""

import json
import asyncio

import aio_pika
from aio_pika import Message, DeliveryMode
from loguru import logger

from app.config import get_settings

_connection: aio_pika.abc.AbstractRobustConnection | None = None
_channel: aio_pika.abc.AbstractChannel | None = None


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
    await publish_task_with_retry(queue_name, payload, None)


async def publish_task_with_retry(
    queue_name: str, payload: dict, headers: dict[str, object] | None = None
) -> None:
    """Publish with retry/backoff to avoid transient broker issues dropping a task."""
    channel = await get_channel()
    await channel.declare_queue(queue_name, durable=True)

    max_attempts = 3
    delay_base_seconds = 0.5
    last_error: Exception | None = None

    for attempt in range(1, max_attempts + 1):
        try:
            message = Message(
                body=json.dumps(payload, ensure_ascii=False).encode(),
                delivery_mode=DeliveryMode.PERSISTENT,
                content_type="application/json",
                headers=headers or {},
            )
            await channel.default_exchange.publish(message, routing_key=queue_name)
            logger.info(
                f"Published to {queue_name}: action={payload.get('action')} "
                f"task_id={payload.get('task_id', '')[:8]}"
            )
            return
        except Exception as exc:  # pragma: no cover - broker/network issues
            last_error = exc
            if attempt >= max_attempts:
                break
            await asyncio.sleep(delay_base_seconds * attempt)

    logger.error(f"Failed to publish to {queue_name} after {max_attempts} attempts: {last_error}")
    raise last_error or RuntimeError("failed to publish task")


async def close_publisher() -> None:
    """Close publisher connection (called on shutdown)."""
    global _connection, _channel
    if _channel and not _channel.is_closed:
        await _channel.close()
    if _connection and not _connection.is_closed:
        await _connection.close()
    _connection = None
    _channel = None
