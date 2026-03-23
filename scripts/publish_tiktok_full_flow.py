from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

# Add root dir to sys.path for direct script execution
ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.publisher import close_publisher, publish_task
from app.schemas import TaskPayload


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Publish a TikTok full_flow task to RabbitMQ.",
    )
    parser.add_argument(
        "--keyword",
        required=True,
        help="Search keyword for TikTok full_flow (example: 'bia tiger').",
    )
    parser.add_argument("--limit", type=int, default=3, help="Number of posts to process.")
    parser.add_argument(
        "--comment-count",
        type=int,
        default=100,
        help="Number of comments to fetch per post.",
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=0.5,
        help="Reply-fetch threshold for comments.",
    )
    parser.add_argument(
        "--runtime-kind",
        default="dryrun",
        help="Optional runtime_kind passed through params metadata.",
    )
    parser.add_argument(
        "--queue",
        default="tiktok_tasks",
        help="RabbitMQ queue name (default: tiktok_tasks).",
    )
    return parser.parse_args()


async def main() -> None:
    args = parse_args()
    payload = TaskPayload(
        action="full_flow",
        params={
            "keyword": args.keyword,
            "limit": args.limit,
            "comment_count": args.comment_count,
            "threshold": args.threshold,
            "runtime_kind": args.runtime_kind,
        },
    ).model_dump()

    print("Publishing task:")
    print(payload)
    await publish_task(args.queue, payload)
    await close_publisher()
    print("Done.")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass