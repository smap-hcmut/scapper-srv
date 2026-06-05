"""RabbitMQ consumer — dispatches tasks to SDK-based handlers."""

from __future__ import annotations

import asyncio
import hashlib
import io
import json
import os
import re
from datetime import datetime, timezone
from typing import Any

import aio_pika
from aio_pika.abc import AbstractIncomingMessage
from loguru import logger
from minio import Minio
from tinlikesub import TinLikeSubClient

from app.publisher import publish_task
from app.config import get_settings
from app.handlers import QUEUE_HANDLERS, QUEUE_PLATFORMS
from app.schemas import TaskResult


INGEST_TASK_COMPLETIONS_QUEUE = "ingest_task_completions"
INGEST_DRYRUN_COMPLETIONS_QUEUE = "ingest_dryrun_completions"
INGEST_TASK_DEAD_LETTER_QUEUE = "ingest_task_dead_letter"
RUNTIME_KIND_DRYRUN = "dryrun"

WORKER_ACTION_LIMITS: dict[str, dict[str, int]] = {
    "full_flow": {
        "limit": 5,
        "comment_count": 8,
    },
    "user_full_flow": {
        "count": 5,
        "comment_count": 8,
    },
    "page_full_flow": {
        "count": 2,
        "comment_count": 8,
    },
    "search": {
        "count": 5,
        "limit": 5,
    },
    "posts": {
        "count": 5,
        "page_size": 16,
    },
    "comments": {
        "count": 30,
        "limit": 30,
        "page_size": 30,
    },
    "comments_graphql_batch": {
        "count": 20,
    },
    "comments_graphql": {
        "count": 20,
    },
    "comment_replies": {
        "count": 20,
    },
    "video_detail": {},
    "post_detail": {},
    "transcript": {},
}


def _coerce_int(value: object, default: int) -> int:
    try:
        as_int = int(value)
    except (TypeError, ValueError):
        return default
    return default if as_int < 0 else as_int


class Worker:
    """Async RabbitMQ consumer that processes tasks via the TinLikeSub SDK."""

    def __init__(self, queues: list[str] | None = None):
        self.settings = get_settings()
        self._connection: aio_pika.abc.AbstractRobustConnection | None = None
        self._channel: aio_pika.abc.AbstractChannel | None = None
        self._client: TinLikeSubClient | None = None
        self._minio: Minio | None = None
        self._queues: dict[str, aio_pika.abc.AbstractQueue] = {}
        self._consumer_callbacks: dict[str, Any] = {}
        self._consumer_tags: dict[str, str] = {}

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
            timeout=self.settings.TINLIKESUB_TIMEOUT_SECONDS,
            secret_key=self.settings.API_SECRET_KEY,
        )
        self._minio = Minio(
            self.settings.MINIO_ENDPOINT,
            access_key=self.settings.MINIO_ACCESS_KEY,
            secret_key=self.settings.MINIO_SECRET_KEY,
            secure=self.settings.MINIO_USE_SSL,
        )

        self._connection = await aio_pika.connect_robust(self.settings.RABBITMQ_URL)
        self._channel = await self._connection.channel()
        await self._channel.set_qos(prefetch_count=self.settings.WORKER_PREFETCH_COUNT)

        for queue_name in self._queue_names:
            callback = self._consumer_callbacks.get(queue_name)
            if callback is None:
                callback = self._build_consumer_callback(queue_name)
                self._consumer_callbacks[queue_name] = callback

            await self._attach_consumer(queue_name, callback)
            logger.info(f"Consuming from queue: {queue_name}")

        logger.info(f"Worker started. Queues: {self._queue_names}")

    async def stop(self) -> None:
        """Gracefully shut down."""
        self._queues.clear()
        self._consumer_callbacks.clear()
        self._consumer_tags.clear()
        if self._client:
            await self._client.close()
            self._client = None
        if self._channel and not self._channel.is_closed:
            await self._channel.close()
        if self._connection and not self._connection.is_closed:
            await self._connection.close()
        logger.info("Worker stopped.")

    async def health_status(self) -> dict[str, Any]:
        queue_statuses = []
        healthy = self._connection is not None and not self._connection.is_closed

        for queue_name in self._queue_names:
            consumer_tag = self._consumer_tags.get(queue_name)
            consumer_count = None
            recovered = False

            try:
                queue = await self._declare_queue(queue_name, passive=True)
                consumer_count = getattr(queue.declaration_result, "consumer_count", None)
                is_active = bool(consumer_tag) and (consumer_count or 0) > 0

                if not is_active:
                    recovered = await self._restore_consumer(queue_name)
                    if recovered:
                        queue = await self._declare_queue(queue_name, passive=True)
                        consumer_tag = self._consumer_tags.get(queue_name)
                        consumer_count = getattr(queue.declaration_result, "consumer_count", None)
                        is_active = bool(consumer_tag) and (consumer_count or 0) > 0
            except Exception as exc:
                is_active = False
                healthy = False
                queue_statuses.append(
                    {
                        "queue": queue_name,
                        "consumer_tag": consumer_tag,
                        "consumer_count": consumer_count,
                        "active": is_active,
                        "recovered": recovered,
                        "error": str(exc),
                    }
                )
                continue

            if not is_active:
                healthy = False

            queue_statuses.append(
                {
                    "queue": queue_name,
                    "consumer_tag": consumer_tag,
                    "consumer_count": consumer_count,
                    "active": is_active,
                    "recovered": recovered,
                }
            )

        return {
            "healthy": healthy,
            "connection_open": self._connection is not None and not self._connection.is_closed,
            "channel_open": self._channel is not None and not self._channel.is_closed,
            "queues": queue_statuses,
        }

    async def _declare_queue(
        self,
        queue_name: str,
        *,
        passive: bool = False,
    ) -> aio_pika.abc.AbstractQueue:
        if self._channel is None or self._channel.is_closed:
            raise RuntimeError("channel is closed")

        queue = await self._channel.declare_queue(
            queue_name,
            durable=True,
            passive=passive,
        )
        if not passive:
            self._queues[queue_name] = queue
        return queue

    def _build_consumer_callback(self, queue_name: str):
        async def consume(message: AbstractIncomingMessage) -> None:
            await self._on_message(message, queue_name)

        return consume

    async def _attach_consumer(self, queue_name: str, callback: Any) -> None:
        queue = await self._declare_queue(queue_name)
        self._consumer_tags[queue_name] = await queue.consume(callback)

    async def _restore_consumer(self, queue_name: str) -> bool:
        callback = self._consumer_callbacks.get(queue_name)
        if callback is None:
            return False

        try:
            await self._attach_consumer(queue_name, callback)
            logger.warning(f"Reattached consumer for queue: {queue_name}")
            return True
        except Exception as exc:
            logger.warning(f"Failed to reattach consumer for queue {queue_name}: {exc}")
            return False

    async def _on_message(
        self, message: AbstractIncomingMessage, queue_name: str
    ) -> None:
        """Process a single message from a queue."""
        retry_count = self._get_retry_count(message)

        try:
            body = json.loads(message.body.decode())
        except Exception as exc:
            logger.exception(f"[{queue_name}] Invalid message payload: {exc}")
            await message.ack()
            return

        task_id = str(body.get("task_id", "unknown"))
        action = str(body.get("action", "unknown"))
        params = self._sanitize_task_params(action, dict(body.get("params", {}) or {}))
        created_at = str(body.get("created_at", ""))

        logger.info(f"[{queue_name}] Received: action={action} task_id={task_id[:8]} retry={retry_count}")

        handlers = QUEUE_HANDLERS.get(queue_name, {})
        handler = handlers.get(action)

        if handler is None:
            error_msg = f"Unknown action '{action}' for queue '{queue_name}'"
            logger.error(error_msg)
            result = TaskResult(
                task_id=task_id,
                queue=queue_name,
                action=action,
                params=params,
                created_at=created_at,
                completed_at=datetime.now(timezone.utc).isoformat(),
                status="error",
                error=error_msg,
            )
            await self._finalize_message(message, result)
            return

        start_time = datetime.now(timezone.utc)
        try:
            crawl_result = await asyncio.wait_for(
                handler(self._client, params),
                timeout=self.settings.TASK_TIMEOUT_SECONDS,
            )
            result = TaskResult(
                task_id=task_id,
                queue=queue_name,
                action=action,
                params=params,
                created_at=created_at,
                completed_at=start_time.isoformat(),
                status="success",
                result=crawl_result,
            )
            await self._finalize_message(message, result)
            logger.info(f"[{queue_name}] Completed: action={action} task_id={task_id[:8]}")
        except asyncio.TimeoutError:
            error_message = (
                f"task timed out after {self.settings.TASK_TIMEOUT_SECONDS:.0f}s"
            )
            logger.warning(
                f"[{queue_name}] Timeout processing message: "
                f"action={action} task_id={task_id[:8]} retry={retry_count} error={error_message}"
            )
            if await self._should_retry(message, queue_name, body, retry_count, error_message):
                await message.ack()
                return

            result = TaskResult(
                task_id=task_id,
                queue=queue_name,
                action=action,
                params=params,
                created_at=created_at,
                completed_at=datetime.now(timezone.utc).isoformat(),
                status="error",
                error=error_message,
            )
            await self._finalize_message(message, result)
        except Exception as e:
            error_message = self._format_processing_error(e)
            logger.exception(f"[{queue_name}] Error processing message: {error_message}")
            if not self._is_provider_queue_timeout(error_message) and await self._should_retry(message, queue_name, body, retry_count, error_message):
                await message.ack()
                return

            result = TaskResult(
                task_id=task_id,
                queue=queue_name,
                action=action,
                params=params,
                created_at=created_at,
                completed_at=datetime.now(timezone.utc).isoformat(),
                status="error",
                error=error_message,
            )
            await self._finalize_message(message, result)

    @staticmethod
    def _is_provider_queue_timeout(error_message: str) -> bool:
        normalized = error_message.lower()
        return "did not finish within" in normalized and "last_status=queued" in normalized

    async def _finalize_message(self, message: AbstractIncomingMessage, result: TaskResult) -> None:
        self._save_result(result)
        await self._publish_completion(result)
        await message.ack()

    def _sanitize_task_params(self, action: str, params: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(params, dict):
            return {}

        if action not in WORKER_ACTION_LIMITS:
            return params

        normalized = dict(params)
        caps = WORKER_ACTION_LIMITS[action]

        for key, cap in caps.items():
            if key in normalized:
                current = _coerce_int(normalized[key], default=_coerce_int(caps[key], default=0))
                limited = min(max(current, 1), cap)
                if current != limited:
                    logger.warning(
                        f"[{action}] sanitize param clamped: {key}={current} -> {limited} "
                        f"(cap={cap})"
                    )
                normalized[key] = limited

        if "comment_sort" in normalized and str(normalized["comment_sort"]) not in {"hot", "top", "newest"}:
            normalized["comment_sort"] = "hot"

        if action == "page_full_flow":
            normalized["count"] = min(_coerce_int(normalized.get("count", 2), 2), 2)

        if action == "full_flow" and "threshold" in normalized:
            try:
                threshold = float(normalized["threshold"])
                if threshold < 0 or threshold > 1:
                    normalized["threshold"] = 0.3
            except (TypeError, ValueError):
                normalized["threshold"] = 0.3

        return normalized

    async def _should_retry(
        self,
        message: AbstractIncomingMessage,
        queue_name: str,
        body: dict[str, Any],
        retry_count: int,
        error_message: str,
    ) -> bool:
        if retry_count >= self.settings.WORKER_MAX_RETRIES:
            await self._publish_dead_letter(
                queue_name,
                body,
                retry_count,
                error_message,
            )
            return False

        next_retry_count = retry_count + 1
        if self.settings.WORKER_RETRY_DELAY_SECONDS > 0:
            await asyncio.sleep(self.settings.WORKER_RETRY_DELAY_SECONDS)

        headers = self._with_retry_headers(message.headers, next_retry_count)
        try:
            from app.publisher import publish_task_with_retry
            await publish_task_with_retry(queue_name, body, headers=headers)
            logger.warning(
                f"[{queue_name}] Retrying task_id={str(body.get('task_id', 'unknown'))[:8]} "
                f"retry={next_retry_count}/{self.settings.WORKER_MAX_RETRIES}"
            )
            return True
        except Exception as exc:
            logger.error(
                f"[{queue_name}] Failed to enqueue retry for task_id={str(body.get('task_id', 'unknown'))[:8]}: {exc}"
            )
            return False

    async def _publish_dead_letter(
        self,
        queue_name: str,
        body: dict[str, Any],
        retry_count: int,
        error_message: str,
    ) -> None:
        dead_letter_payload = {
            "source_queue": queue_name,
            "task_id": str(body.get("task_id", "unknown")),
            "action": str(body.get("action", "unknown")),
            "params": body.get("params", {}),
            "created_at": str(body.get("created_at", "")),
            "failed_at": datetime.now(timezone.utc).isoformat(),
            "retry_count": retry_count,
            "error": error_message,
            "error_type": "processing",
            "original_payload": body,
        }
        from app.publisher import publish_task_with_retry
        await publish_task_with_retry(INGEST_TASK_DEAD_LETTER_QUEUE, dead_letter_payload)

    @staticmethod
    def _with_retry_headers(headers: dict[str, object] | None, retry_count: int) -> dict[str, object]:
        retry_headers = dict(headers or {})
        retry_headers["x-retry-count"] = retry_count
        return retry_headers

    @staticmethod
    def _get_retry_count(message: AbstractIncomingMessage) -> int:
        try:
            headers = message.headers or {}
            if not isinstance(headers, dict):
                return 0
            raw_retry = headers.get("x-retry-count")
            if raw_retry is None:
                return 0
            return max(0, int(raw_retry))
        except Exception:
            return 0

    def _format_processing_error(self, error: Exception) -> str:
        message = str(error).strip() or error.__class__.__name__
        if "<!DOCTYPE html" not in message and "<html" not in message.lower():
            return message

        title_match = re.search(r"<title>(.*?)</title>", message, flags=re.IGNORECASE | re.DOTALL)
        if title_match:
            title = re.sub(r"\s+", " ", title_match.group(1)).strip()
            if title:
                return f"upstream returned HTML error page: {title}"

        return "upstream returned unexpected HTML response"

    def _save_result(self, result: TaskResult) -> None:
        """Save task result to output/ as JSON file."""
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        queue_short = result.queue.replace("_tasks", "")
        filename = f"{queue_short}_{result.action}_{result.task_id[:8]}_{timestamp}.json"
        filepath = os.path.join(self.settings.OUTPUT_DIR, filename)

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(result.model_dump(), f, ensure_ascii=False, indent=2, default=str)

        logger.info(f"Result saved: {filepath}")

    async def _publish_completion(self, result: TaskResult) -> None:
        payload = {
            "task_id": result.task_id,
            "queue": result.queue,
            "platform": QUEUE_PLATFORMS.get(result.queue, result.queue.replace("_tasks", "")),
            "action": result.action,
            "status": result.status,
            "completed_at": result.completed_at,
            "error": result.error,
            "metadata": self._build_completion_metadata(result),
        }

        if result.status == "success":
            artifact = await self._upload_result_artifact(result)
            payload.update(artifact)

        completion_queue = self._completion_queue(result)
        await publish_task(completion_queue, payload)

    def _completion_queue(self, result: TaskResult) -> str:
        runtime_kind = str(result.params.get("runtime_kind", "")).strip().lower()
        if runtime_kind == RUNTIME_KIND_DRYRUN:
            return INGEST_DRYRUN_COMPLETIONS_QUEUE
        return INGEST_TASK_COMPLETIONS_QUEUE

    async def _upload_result_artifact(self, result: TaskResult) -> dict[str, Any]:
        if self._minio is None:
            raise RuntimeError("MinIO client is not initialized")

        raw_bytes = self._serialize_result(result)
        checksum = f"sha256:{hashlib.sha256(raw_bytes).hexdigest()}"
        storage_path = self._build_storage_path(result)

        await asyncio.to_thread(
            self._minio.put_object,
            self.settings.MINIO_BUCKET,
            storage_path,
            io.BytesIO(raw_bytes),
            len(raw_bytes),
            content_type="application/json",
            metadata={
                "task_id": result.task_id,
                "platform": QUEUE_PLATFORMS.get(result.queue, "unknown"),
                "action": result.action,
                "batch_id": self._build_batch_id(result),
            },
        )

        return {
            "storage_bucket": self.settings.MINIO_BUCKET,
            "storage_path": storage_path,
            "batch_id": self._build_batch_id(result),
            "checksum": checksum,
            "item_count": self._derive_item_count(result.result),
        }

    def _serialize_result(self, result: TaskResult) -> bytes:
        return json.dumps(
            result.model_dump(),
            ensure_ascii=False,
            indent=2,
            default=str,
        ).encode("utf-8")

    def _build_storage_path(self, result: TaskResult) -> str:
        completed_at = self._parse_timestamp(result.completed_at)
        platform = QUEUE_PLATFORMS.get(result.queue, result.queue.replace("_tasks", ""))
        return (
            f"crawl-raw/{platform}/{result.action}/"
            f"{completed_at:%Y/%m/%d}/{result.task_id}.json"
        )

    def _build_batch_id(self, result: TaskResult) -> str:
        platform = QUEUE_PLATFORMS.get(result.queue, result.queue.replace("_tasks", ""))
        return f"raw-{platform}-{result.action}-{result.task_id}"

    def _build_completion_metadata(self, result: TaskResult) -> dict[str, Any]:
        completed_at = self._parse_timestamp(result.completed_at)
        created_at = self._parse_timestamp(result.created_at)
        metadata: dict[str, Any] = {
            "crawler_version": self.settings.APP_VERSION,
            "content_type": "application/json",
        }
        if created_at is not None:
            metadata["duration_ms"] = max(0, int((completed_at - created_at).total_seconds() * 1000))
        if result.status == "success":
            metadata["size_bytes"] = len(self._serialize_result(result))
        return metadata

    def _parse_timestamp(self, value: str) -> datetime:
        normalized = (value or "").strip()
        if normalized.endswith("Z"):
            normalized = normalized[:-1] + "+00:00"
        if normalized:
            try:
                return datetime.fromisoformat(normalized)
            except ValueError:
                pass
        return datetime.now(timezone.utc)

    def _derive_item_count(self, payload: Any) -> int | None:
        if isinstance(payload, list):
            return len(payload)
        if not isinstance(payload, dict):
            return None

        for key in ("total_posts", "total_videos", "total"):
            value = payload.get(key)
            if isinstance(value, int) and value >= 0:
                return value

        for key in ("posts", "videos", "comments"):
            value = payload.get(key)
            if isinstance(value, list):
                return len(value)

        return None
