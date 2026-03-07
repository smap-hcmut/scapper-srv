from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.publisher import close_publisher, publish_task
from app.schemas import TaskPayload


DEFAULT_TIKTOK_URLS = [
    "https://www.tiktok.com/@vutrunews.official/video/7612600015135034644",
    "https://www.tiktok.com/@baohatinh/video/7612490346186018066",
]

DEFAULT_FACEBOOK_PARSE_IDS = [
    "100069153349307_pfbid0m6dmZhdGq59QT1DQY7m6Cp8cNDc1eiAT29prRfnJegdwwz1VLYj9ovStdyarETm4l",
    "1509435412435707_1204092691905831",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Publish a batch post-detail task to scapper RabbitMQ queues.",
    )
    parser.add_argument(
        "--platform",
        choices=["tiktok", "facebook"],
        default="tiktok",
        help="Target platform queue to publish to.",
    )
    parser.add_argument(
        "--value",
        action="append",
        dest="values",
        help="Repeat this flag to pass multiple URLs or parse_ids.",
    )
    return parser.parse_args()


def build_payload(platform: str, values: list[str] | None) -> tuple[str, dict]:
    if platform == "tiktok":
        queue_name = "tiktok_tasks"
        params = {"urls": values or DEFAULT_TIKTOK_URLS}
    else:
        queue_name = "facebook_tasks"
        params = {"parse_ids": values or DEFAULT_FACEBOOK_PARSE_IDS}

    payload = TaskPayload(
        action="post_detail",
        params=params,
    ).model_dump()
    return queue_name, payload


async def run() -> None:
    args = parse_args()
    queue_name, payload = build_payload(args.platform, args.values)

    print("Publishing payload:")
    print(json.dumps(payload, ensure_ascii=False, indent=2))

    try:
        await publish_task(queue_name, payload)
    finally:
        await close_publisher()

    print("")
    print("Published successfully.")
    print(f"queue:   {queue_name}")
    print(f"task_id: {payload['task_id']}")
    print("Expected output file pattern:")
    print(f"  output/{args.platform}_post_detail_{payload['task_id'][:8]}_YYYYMMDD_HHMMSS.json")


if __name__ == "__main__":
    asyncio.run(run())
