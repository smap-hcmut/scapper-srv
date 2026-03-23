from __future__ import annotations

import asyncio
import glob
import json
import sys
import time
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.publisher import close_publisher, publish_task
from app.schemas import TaskPayload


POST_ID = "1509435412435707_1204092691905831"
PARSE_ID = "100069153349307_pfbid0m6dmZhdGq59QT1DQY7m6Cp8cNDc1eiAT29prRfnJegdwwz1VLYj9ovStdyarETm4l"
OUT_DIR = Path("output")


TASKS: list[tuple[str, dict]] = [
    ("post_detail", {"parse_ids": [PARSE_ID]}),
    ("comments", {"post_id": POST_ID, "limit": 30}),
    ("comments_graphql", {"post_id": POST_ID, "count": 30, "sort": "hot"}),
    ("comments_graphql_batch", {"post_ids": [POST_ID], "count": 30, "sort": "hot"}),
    ("full_flow", {"keyword": "Theanh28 Entertainment", "limit": 3, "comment_count": 30, "comment_sort": "hot"}),
]


def _result_shape(result: object) -> str:
    if isinstance(result, list):
        return f"list[{len(result)}]"
    if isinstance(result, dict):
        if isinstance(result.get("posts"), list):
            return f"posts[{len(result['posts'])}]"
        if isinstance(result.get("comments"), list):
            return f"comments[{len(result['comments'])}]"
        return f"dict_keys[{len(result.keys())}]"
    return type(result).__name__


async def main() -> None:
    published: list[tuple[str, str]] = []
    try:
        for action, params in TASKS:
            payload = TaskPayload(action=action, params=params).model_dump()
            await publish_task("facebook_tasks", payload)
            published.append((action, payload["task_id"]))
    finally:
        await close_publisher()

    summary: list[dict] = []
    for action, task_id in published:
        prefix = task_id[:8]
        file_path = None
        for _ in range(180):
            matches = sorted(glob.glob(str(OUT_DIR / f"facebook_{action}_{prefix}_*.json")))
            if matches:
                file_path = matches[-1]
                break
            time.sleep(1)

        if file_path is None:
            summary.append({"action": action, "task_id": task_id, "status": "timeout"})
            continue

        data = json.loads(Path(file_path).read_text(encoding="utf-8"))
        summary.append(
            {
                "action": action,
                "task_id": task_id,
                "status": data.get("status"),
                "item_count": data.get("item_count"),
                "result_shape": _result_shape(data.get("result")),
                "has_error": bool(data.get("error")),
                "file": file_path,
            }
        )

    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    asyncio.run(main())