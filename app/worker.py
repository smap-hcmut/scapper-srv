"""RabbitMQ consumer — dispatches tasks to SDK-based handlers."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Any

import aio_pika
from aio_pika.abc import AbstractIncomingMessage
from loguru import logger
from tinlikesub import TinLikeSubClient

from app.config import get_settings
from app.handlers import QUEUE_HANDLERS, QUEUE_PLATFORMS
from app.logger import trace_context
from app.publisher import publish_completion
from app.schemas import CompletionEnvelope, TaskResult
from app.storage import save_result_data


class Worker:
    """Async RabbitMQ consumer that processes tasks via the TinLikeSub SDK."""

    def __init__(self, queues: list[str] | None = None):
        self.settings = get_settings()
        self._connection: aio_pika.abc.AbstractRobustConnection | None = None
        self._channel: aio_pika.abc.AbstractChannel | None = None
        self._client: TinLikeSubClient | None = None

        # Resolve queue names from platform names or queue names
        if queues:
            platform_to_queue = {v: k for k, v in QUEUE_PLATFORMS.items()}
            self._queue_names = []
            for q in queues:
                if q in QUEUE_HANDLERS:
                    self._queue_names.append(q)
                elif q in platform_to_queue:
                    self._queue_names.append(platform_to_queue[q])
                else:
                    logger.warning(f"Unknown queue/platform: {q}")
        else:
            self._queue_names = list(QUEUE_HANDLERS.keys())

    async def start(self) -> None:
        """Connect to RabbitMQ and start consuming."""
        os.makedirs(self.settings.OUTPUT_DIR, exist_ok=True)

        # SDK client with long timeout for crawl operations
        self._client = TinLikeSubClient(
            base_url=self.settings.API_BASE_URL,
            api_key=self.settings.API_KEY,
            timeout=120.0,
            secret_key=self.settings.API_SECRET_KEY,
        )

        self._connection = await aio_pika.connect_robust(self.settings.RABBITMQ_URL)
        self._channel = await self._connection.channel()
        await self._channel.set_qos(prefetch_count=self.settings.WORKER_PREFETCH_COUNT)

        for queue_name in self._queue_names:
            queue = await self._channel.declare_queue(queue_name, durable=True)
            await queue.consume(
                lambda msg, qn=queue_name: self._on_message(msg, qn),
            )
            logger.info(f"Consuming from queue: {queue_name}")

        logger.info(f"Worker started. Mode: {self.settings.MODE}. Queues: {self._queue_names}")

    async def stop(self) -> None:
        """Gracefully shut down."""
        if self._client:
            await self._client.close()
            self._client = None
        if self._channel and not self._channel.is_closed:
            await self._channel.close()
        if self._connection and not self._connection.is_closed:
            await self._connection.close()
        logger.info("Worker stopped.")

    async def _on_message(
        self, message: AbstractIncomingMessage, queue_name: str
    ) -> None:
        """Process a single message from a queue."""
        body: dict[str, Any] = {}

        # Extract trace_id from headers
        headers = message.headers or {}
        trace_id = headers.get("X-Trace-Id")
        if isinstance(trace_id, bytes):
            trace_id = trace_id.decode(errors="ignore")

        async with message.process():
            with trace_context(trace_id=trace_id):
                try:
                    body = json.loads(message.body.decode())
                    task_id = body.get("task_id", "unknown")
                    action = body.get("action", "unknown")
                    params = body.get("params", {})
                    created_at = body.get("created_at", "")

                    logger.info(f"[{queue_name}] Received: action={action} task_id={task_id[:8]}")

                    # Find handler
                    handlers = QUEUE_HANDLERS.get(queue_name, {})
                    handler = handlers.get(action)

                    if handler is None:
                        error_msg = f"Unknown action '{action}' for queue '{queue_name}'"
                        logger.error(error_msg)
                        await self._handle_result(TaskResult(
                            task_id=task_id,
                            queue=queue_name,
                            action=action,
                            params=params,
                            created_at=created_at,
                            completed_at=datetime.now(timezone.utc).isoformat(),
                            status="error",
                            error=error_msg,
                        ))
                        return

                    # Execute
                    result = await handler(self._client, params)

                    # Count items
                    item_count = 0
                    if isinstance(result, list):
                        item_count = len(result)
                    elif isinstance(result, dict):
                        # For tiktok full_flow or similar
                        item_count = result.get("total_posts") or result.get("item_count") or 1

                    await self._handle_result(TaskResult(
                        task_id=task_id,
                        queue=queue_name,
                        action=action,
                        params=params,
                        created_at=created_at,
                        completed_at=datetime.now(timezone.utc).isoformat(),
                        status="success",
                        result=result,
                        item_count=item_count,
                    ))
                    logger.info(f"[{queue_name}] Completed: action={action} task_id={task_id[:8]}")

                except Exception as e:
                    logger.exception(f"[{queue_name}] Error processing message: {e}")
                    await self._handle_result(TaskResult(
                        task_id=body.get("task_id", "unknown"),
                        queue=queue_name,
                        action=body.get("action", "unknown"),
                        params=body.get("params", {}),
                        created_at=body.get("created_at", ""),
                        completed_at=datetime.now(timezone.utc).isoformat(),
                        status="error",
                        error=str(e),
                    ))

    async def _handle_result(self, result: TaskResult) -> None:
        """Save result to storage and publish completion to ingest-srv."""
        platform = QUEUE_PLATFORMS.get(result.queue, "unknown")

        # 1. Save to Storage (Local or MinIO)
        storage_meta = await save_result_data(
            task_id=result.task_id,
            platform=platform,
            action=result.action,
            result_dict=result.model_dump(),
        )

        # Update result object with storage info
        result.storage_bucket = storage_meta.get("storage_bucket")
        result.storage_path = storage_meta.get("storage_path")
        result.batch_id = storage_meta.get("batch_id")
        result.checksum = storage_meta.get("checksum")

        # 2. Publish Completion Envelope to RabbitMQ
        # Following RABBITMQ.md contract
        completion = CompletionEnvelope(
            task_id=result.task_id,
            queue=result.queue,
            platform=platform,
            action=result.action,
            status=result.status,
            completed_at=result.completed_at,
            storage_bucket=result.storage_bucket,
            storage_path=result.storage_path,
            batch_id=result.batch_id,
            checksum=result.checksum,
            item_count=result.item_count,
            error=result.error,
            metadata={
                "crawler_version": self.settings.APP_VERSION,
                "mode": self.settings.MODE,
            },
        )

        await publish_completion(completion.model_dump())
