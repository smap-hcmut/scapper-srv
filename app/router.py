"""FastAPI endpoints — submit tasks, check results."""

from __future__ import annotations

import json
import os

from fastapi import APIRouter, HTTPException

from app.config import get_settings
from app.handlers import QUEUE_HANDLERS, QUEUE_PLATFORMS
from app.publisher import publish_task
from app.schemas import SubmitTaskRequest, SubmitTaskResponse, TaskPayload

router = APIRouter()

# platform name → queue name
_PLATFORM_QUEUES = {v: k for k, v in QUEUE_PLATFORMS.items()}


@router.post("/tasks/{platform}", response_model=SubmitTaskResponse)
async def submit_task(platform: str, request: SubmitTaskRequest):
    """Submit a task to the appropriate platform queue.

    Platform: tiktok, facebook, youtube
    """
    queue_name = _PLATFORM_QUEUES.get(platform)
    if not queue_name:
        raise HTTPException(status_code=404, detail=f"Unknown platform: {platform}")

    valid_actions = QUEUE_HANDLERS.get(queue_name, {})
    if request.action not in valid_actions:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid action '{request.action}' for {platform}. "
            f"Valid: {list(valid_actions.keys())}",
        )

    payload = TaskPayload(action=request.action, params=request.params)
    await publish_task(queue_name, payload.model_dump())

    return SubmitTaskResponse(
        message="Task đã được gửi vào queue, worker sẽ xử lý",
        task_id=payload.task_id,
        action=payload.action,
        queue=queue_name,
        payload=payload,
    )


@router.get("/tasks/{task_id}/result")
async def get_task_result(task_id: str):
    """Check if a task result exists and return it."""
    settings = get_settings()
    output_dir = settings.OUTPUT_DIR
    if not os.path.isdir(output_dir):
        raise HTTPException(status_code=404, detail="No results available yet")

    prefix = task_id[:8]
    for filename in os.listdir(output_dir):
        if prefix in filename and filename.endswith(".json"):
            filepath = os.path.join(output_dir, filename)
            with open(filepath, "r", encoding="utf-8") as f:
                return json.load(f)

    raise HTTPException(
        status_code=404,
        detail=f"Result not found for task_id={task_id}. Task may still be processing.",
    )


@router.get("/tasks")
async def list_recent_tasks(limit: int = 20):
    """List recent task result files."""
    settings = get_settings()
    output_dir = settings.OUTPUT_DIR
    if not os.path.isdir(output_dir):
        return []

    files = sorted(
        [f for f in os.listdir(output_dir) if f.endswith(".json")],
        reverse=True,
    )[:limit]

    results = []
    for filename in files:
        filepath = os.path.join(output_dir, filename)
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
            results.append({
                "filename": filename,
                "task_id": data.get("task_id"),
                "action": data.get("action"),
                "queue": data.get("queue"),
                "status": data.get("status"),
                "completed_at": data.get("completed_at"),
            })
        except Exception:
            results.append({"filename": filename, "error": "Failed to parse"})

    return results
