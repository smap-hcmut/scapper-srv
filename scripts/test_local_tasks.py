from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))


@dataclass(frozen=True)
class Scenario:
    platform: str
    queue: str
    action: str
    feature: str
    params: dict[str, Any]
    suites: tuple[str, ...] = ("all",)


def env(name: str, default: str) -> str:
    return os.getenv(name, default)


def env_int(name: str, default: int) -> int:
    value = os.getenv(name)
    return int(value) if value else default


DEFAULT_KEYWORD = env("SMAP_TEST_KEYWORD", "vinfast")
TIKTOK_VIDEO_URL = env(
    "SMAP_TEST_TIKTOK_VIDEO_URL",
    "https://www.tiktok.com/@vinfast.official/video/7358420765906521352",
)
TIKTOK_AWEME_ID = env("SMAP_TEST_TIKTOK_AWEME_ID", "7358420765906521352")
TIKTOK_COMMENT_ID = env("SMAP_TEST_TIKTOK_COMMENT_ID", "7358421111111111111")
TIKTOK_USERNAME = env("SMAP_TEST_TIKTOK_USERNAME", "vinfast.official")

FACEBOOK_PARSE_ID = env(
    "SMAP_TEST_FACEBOOK_PARSE_ID",
    "100069153349307_pfbid0m6dmZhdGq59QT1DQY7m6Cp8cNDc1eiAT29prRfnJegdwwz1VLYj9ovStdyarETm4l",
)
FACEBOOK_POST_ID = env("SMAP_TEST_FACEBOOK_POST_ID", FACEBOOK_PARSE_ID)
FACEBOOK_PAGE_ID = env("SMAP_TEST_FACEBOOK_PAGE_ID", "100066224874581")

YOUTUBE_VIDEO_ID = env("SMAP_TEST_YOUTUBE_VIDEO_ID", "dQw4w9WgXcQ")
YOUTUBE_CHANNEL_KEYWORD = env("SMAP_TEST_YOUTUBE_CHANNEL_KEYWORD", DEFAULT_KEYWORD)


SCENARIOS: list[Scenario] = [
    Scenario(
        "tiktok",
        "tiktok_tasks",
        "search",
        "TikTok keyword search, optional pagination/search_id/region.",
        {"keywords": [DEFAULT_KEYWORD], "count": 5, "region": "VN"},
        ("smoke", "search", "all"),
    ),
    Scenario(
        "tiktok",
        "tiktok_tasks",
        "post_detail",
        "Fetch TikTok post detail by one or many video URLs.",
        {"urls": [TIKTOK_VIDEO_URL]},
        ("post", "all"),
    ),
    Scenario(
        "tiktok",
        "tiktok_tasks",
        "comments",
        "Fetch TikTok comments by video_url, aweme_id, or list of IDs.",
        {"aweme_ids": [TIKTOK_AWEME_ID], "count": 20, "cursor": 0, "threshold": 0},
        ("post", "all"),
    ),
    Scenario(
        "tiktok",
        "tiktok_tasks",
        "summary",
        "Fetch TikTok summary metrics for one or many item IDs.",
        {"item_ids": [TIKTOK_AWEME_ID]},
        ("post", "all"),
    ),
    Scenario(
        "tiktok",
        "tiktok_tasks",
        "comment_replies",
        "Fetch replies for a specific TikTok comment.",
        {
            "item_id": TIKTOK_AWEME_ID,
            "comment_id": TIKTOK_COMMENT_ID,
            "count": 20,
            "cursor": 0,
        },
        ("post", "all"),
    ),
    Scenario(
        "tiktok",
        "tiktok_tasks",
        "user_posts",
        "Fetch posts from a TikTok user by username or sec_uid.",
        {"username": TIKTOK_USERNAME, "count": 10},
        ("profile", "all"),
    ),
    Scenario(
        "tiktok",
        "tiktok_tasks",
        "cookie_check",
        "Check upstream TikTok cookie/session status.",
        {},
        ("health", "all"),
    ),
    Scenario(
        "tiktok",
        "tiktok_tasks",
        "full_flow",
        "Composite flow: search -> post detail -> comments.",
        {"keyword": DEFAULT_KEYWORD, "limit": 2, "comment_count": 20, "threshold": 0},
        ("smoke", "flow", "all"),
    ),
    Scenario(
        "facebook",
        "facebook_tasks",
        "search",
        "Facebook search alias that returns a backward-compatible posts list.",
        {"keyword": DEFAULT_KEYWORD, "limit": 5},
        ("smoke", "search", "all"),
    ),
    Scenario(
        "facebook",
        "facebook_tasks",
        "posts",
        "Facebook posts alias through GraphQL search.",
        {"keyword": DEFAULT_KEYWORD, "page_size": 5},
        ("search", "all"),
    ),
    Scenario(
        "facebook",
        "facebook_tasks",
        "post_detail",
        "Fetch Facebook post detail by parse_id or parse_ids.",
        {"parse_ids": [FACEBOOK_PARSE_ID]},
        ("post", "all"),
    ),
    Scenario(
        "facebook",
        "facebook_tasks",
        "comments",
        "Fetch Facebook comments as a backward-compatible comments list.",
        {"post_id": FACEBOOK_POST_ID, "count": 20, "sort": "hot"},
        ("post", "all"),
    ),
    Scenario(
        "facebook",
        "facebook_tasks",
        "comments_graphql",
        "Fetch Facebook comments GraphQL envelope for one post.",
        {"post_id": FACEBOOK_POST_ID, "count": 20, "sort": "hot"},
        ("post", "all"),
    ),
    Scenario(
        "facebook",
        "facebook_tasks",
        "comments_graphql_batch",
        "Fetch Facebook comments for multiple posts.",
        {"post_ids": [FACEBOOK_POST_ID], "count": 20, "sort": "hot"},
        ("post", "all"),
    ),
    Scenario(
        "facebook",
        "facebook_tasks",
        "search_graphql",
        "Facebook GraphQL search envelope.",
        {"keyword": DEFAULT_KEYWORD, "count": 5},
        ("search", "all"),
    ),
    Scenario(
        "facebook",
        "facebook_tasks",
        "search_graphql_batch",
        "Facebook GraphQL search for multiple keywords.",
        {"keywords": [DEFAULT_KEYWORD, "xe dien"], "count": 5},
        ("search", "all"),
    ),
    Scenario(
        "facebook",
        "facebook_tasks",
        "page_posts",
        "Fetch posts from a Facebook profile/page by numeric page_id.",
        {"page_id": FACEBOOK_PAGE_ID, "count": 5},
        ("profile", "all"),
    ),
    Scenario(
        "facebook",
        "facebook_tasks",
        "full_flow",
        "Composite flow: search -> comments for each post.",
        {"keyword": DEFAULT_KEYWORD, "limit": 2, "comment_count": 20},
        ("smoke", "flow", "all"),
    ),
    Scenario(
        "youtube",
        "youtube_tasks",
        "search",
        "YouTube keyword search with optional filters.",
        {"keywords": [DEFAULT_KEYWORD], "limit": 5},
        ("smoke", "search", "all"),
    ),
    Scenario(
        "youtube",
        "youtube_tasks",
        "search",
        "YouTube channel/profile discovery via search filter. The service has no channel timeline action yet.",
        {"keywords": [YOUTUBE_CHANNEL_KEYWORD], "limit": 5, "video_type": "channel"},
        ("profile", "all"),
    ),
    Scenario(
        "youtube",
        "youtube_tasks",
        "videos",
        "YouTube video search/list endpoint.",
        {"keyword": DEFAULT_KEYWORD, "page": 1, "page_size": 5},
        ("search", "all"),
    ),
    Scenario(
        "youtube",
        "youtube_tasks",
        "video_detail",
        "Fetch YouTube video detail by video_id.",
        {"video_id": YOUTUBE_VIDEO_ID},
        ("post", "all"),
    ),
    Scenario(
        "youtube",
        "youtube_tasks",
        "transcript",
        "Fetch YouTube transcript by video_id.",
        {"video_id": YOUTUBE_VIDEO_ID},
        ("post", "all"),
    ),
    Scenario(
        "youtube",
        "youtube_tasks",
        "comments",
        "Fetch YouTube comments by video_id.",
        {"video_id": YOUTUBE_VIDEO_ID, "limit": 20},
        ("post", "all"),
    ),
    Scenario(
        "youtube",
        "youtube_tasks",
        "full_flow",
        "Composite flow: search -> video detail -> comments.",
        {"keyword": DEFAULT_KEYWORD, "limit": 2, "comment_count": 20},
        ("smoke", "flow", "all"),
    ),
]


def select_scenarios(args: argparse.Namespace) -> list[Scenario]:
    scenarios = SCENARIOS
    if args.suite != "all":
        scenarios = [s for s in scenarios if args.suite in s.suites]
    if args.platform:
        platforms = set(args.platform)
        scenarios = [s for s in scenarios if s.platform in platforms]
    if args.action:
        actions = set(args.action)
        scenarios = [s for s in scenarios if s.action in actions]
    return scenarios


def print_catalog(scenarios: list[Scenario]) -> None:
    current_platform = None
    for scenario in scenarios:
        if scenario.platform != current_platform:
            current_platform = scenario.platform
            print(f"\n{current_platform.upper()} ({scenario.queue})")
        print(f"  - {scenario.action}: {scenario.feature}")
        print(f"    params: {json.dumps(scenario.params, ensure_ascii=False)}")


def build_payload(scenario: Scenario, runtime_kind: str | None) -> dict[str, Any]:
    params = dict(scenario.params)
    if runtime_kind:
        params["runtime_kind"] = runtime_kind
    return {
        "task_id": str(uuid4()),
        "action": scenario.action,
        "params": params,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }


async def wait_for_completions(
    task_ids: set[str],
    *,
    queue_name: str,
    rabbitmq_url: str,
    timeout_seconds: int,
) -> dict[str, dict[str, Any]]:
    import aio_pika

    completions: dict[str, dict[str, Any]] = {}
    connection = await aio_pika.connect_robust(rabbitmq_url)
    try:
        channel = await connection.channel()
        queue = await channel.declare_queue(queue_name, durable=True)
        deadline = asyncio.get_running_loop().time() + timeout_seconds

        while task_ids - completions.keys():
            remaining = deadline - asyncio.get_running_loop().time()
            if remaining <= 0:
                break

            message = await queue.get(timeout=min(remaining, 5), fail=False)
            if message is None:
                continue

            async with message.process(requeue=False):
                try:
                    payload = json.loads(message.body.decode())
                except Exception:
                    continue
                task_id = str(payload.get("task_id", ""))
                if task_id in task_ids:
                    completions[task_id] = payload
                    status = payload.get("status")
                    action = payload.get("action")
                    print(f"[completion] {task_id[:8]} {action} status={status}")
    finally:
        await connection.close()

    return completions


async def publish_scenarios(args: argparse.Namespace) -> int:
    if not args.dry_run:
        from app.publisher import close_publisher, publish_task

    scenarios = select_scenarios(args)
    if not scenarios:
        print("No scenarios matched the selected filters.", file=sys.stderr)
        return 2

    published: list[tuple[Scenario, dict[str, Any]]] = []
    print(f"Publishing {len(scenarios)} scenario(s)")
    print(f"RabbitMQ: {os.getenv('RABBITMQ_URL', 'from app/.env or defaults')}")
    print(f"Output dir expected from worker env: {os.getenv('OUTPUT_DIR', 'output')}")
    print()

    for scenario in scenarios:
        payload = build_payload(scenario, args.runtime_kind)
        payload["task_id"] = f"local-{scenario.platform}-{scenario.action}-{uuid4()}"
        payload["created_at"] = datetime.now(timezone.utc).isoformat()
        published.append((scenario, payload))
        print(f"[task] {payload['task_id'][:18]} -> {scenario.queue}/{scenario.action}")
        if args.print_payloads or args.dry_run:
            print(json.dumps(payload, ensure_ascii=False, indent=2))
        if not args.dry_run:
            await publish_task(scenario.queue, payload)

    if args.dry_run:
        return 0

    await close_publisher()

    if args.wait:
        queue_name = (
            "ingest_dryrun_completions"
            if args.runtime_kind == "dryrun"
            else "ingest_task_completions"
        )
        task_ids = {payload["task_id"] for _, payload in published}
        completions = await wait_for_completions(
            task_ids,
            queue_name=queue_name,
            rabbitmq_url=os.getenv("RABBITMQ_URL", "amqp://admin:21042004@localhost:5672/"),
            timeout_seconds=args.timeout,
        )
        missing = task_ids - completions.keys()
        if missing:
            print(f"\nTimed out waiting for {len(missing)} completion(s):")
            for task_id in sorted(missing):
                print(f"  - {task_id}")
            return 1

    print("\nDone. Check worker logs and output JSON files.")
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Publish local scapper-srv test tasks and list supported task types.",
    )
    parser.add_argument("--list", action="store_true", help="List supported task types.")
    parser.add_argument(
        "--suite",
        choices=("smoke", "search", "post", "profile", "flow", "health", "all"),
        default="smoke",
        help=(
            "smoke publishes safer keyword/composite tests; search/post/profile/flow "
            "target capability groups; all publishes every scenario."
        ),
    )
    parser.add_argument(
        "--platform",
        action="append",
        choices=("tiktok", "facebook", "youtube"),
        help="Filter by platform. Can be repeated.",
    )
    parser.add_argument(
        "--action",
        action="append",
        help="Filter by action name. Can be repeated.",
    )
    parser.add_argument(
        "--runtime-kind",
        default="dryrun",
        help="Value copied into params.runtime_kind for completion queue routing.",
    )
    parser.add_argument(
        "--wait",
        action="store_true",
        help="Wait for matching completion messages after publishing.",
    )
    parser.add_argument("--timeout", type=int, default=900, help="Wait timeout in seconds.")
    parser.add_argument("--dry-run", action="store_true", help="Print tasks without publishing.")
    parser.add_argument(
        "--print-payloads",
        action="store_true",
        help="Print JSON payloads as they are published.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    scenarios = select_scenarios(args)
    if args.list:
        print_catalog(scenarios)
        return 0

    try:
        return asyncio.run(publish_scenarios(args))
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
