"""Pydantic models for task payloads, API requests/responses, and result output."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field


class TaskPayload(BaseModel):
    """Message payload published to RabbitMQ — matches RABBITMQ.md spec."""

    task_id: str = Field(default_factory=lambda: str(uuid4()))
    action: str
    params: dict[str, Any] = Field(default_factory=dict)
    created_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


class SubmitTaskRequest(BaseModel):
    """API request body to submit a task."""

    action: str
    params: dict[str, Any] = Field(default_factory=dict)


class SubmitTaskResponse(BaseModel):
    """API response after task submission."""

    message: str
    task_id: str
    action: str
    queue: str
    payload: TaskPayload


class TaskResult(BaseModel):
    """JSON structure saved to output/ files or MinIO raw artifact."""

    task_id: str
    queue: str
    action: str
    params: dict[str, Any]
    created_at: str
    completed_at: str
    status: str = "success"
    result: Any = None
    error: str | None = None
    
    # Metadata for ingest-srv
    item_count: int = 0
    storage_bucket: str | None = None
    storage_path: str | None = None
    batch_id: str | None = None
    checksum: str | None = None


class CompletionEnvelope(BaseModel):
    """Message payload published to ingest_task_completions queue."""

    task_id: str
    queue: str
    platform: str
    action: str
    status: str
    completed_at: str
    storage_bucket: str | None = None
    storage_path: str | None = None
    batch_id: str | None = None
    checksum: str | None = None
    item_count: int = 0
    error: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
