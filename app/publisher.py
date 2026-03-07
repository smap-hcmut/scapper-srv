"""Publish task messages to RabbitMQ queues."""

import json

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
    channel = await get_channel()
    await channel.declare_queue(queue_name, durable=True)
    message = Message(
        body=json.dumps(payload, ensure_ascii=False).encode(),
        delivery_mode=DeliveryMode.PERSISTENT,
        content_type="application/json",
    )
    await channel.default_exchange.publish(message, routing_key=queue_name)
    logger.info(
        f"Published to {queue_name}: action={payload.get('action')} "
        f"task_id={payload.get('task_id', '')[:8]}"
    )


async def publish_completion(payload: dict) -> None:
    """Publish a completion message to ingest_task_completions queue."""
    queue_name = "ingest_task_completions"
    channel = await get_channel()
    await channel.declare_queue(queue_name, durable=True)
    message = Message(
        body=json.dumps(payload, ensure_ascii=False).encode(),
        delivery_mode=DeliveryMode.PERSISTENT,
        content_type="application/json",
    )
    await channel.default_exchange.publish(message, routing_key=queue_name)
    logger.info(
        f"Published completion to {queue_name}: task_id={payload.get('task_id', '')[:8]} "
        f"status={payload.get('status')}"
    )


async def close_publisher() -> None:
    """Close publisher connection (called on shutdown)."""
    global _connection, _channel
    if _channel and not _channel.is_closed:
        await _channel.close()
    if _connection and not _connection.is_closed:
        await _connection.close()
    _connection = None
    _channel = None
