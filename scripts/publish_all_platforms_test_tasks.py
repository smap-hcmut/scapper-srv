from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path
from datetime import datetime, timezone

# Add root dir to sys.path
ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.publisher import close_publisher, publish_task
from app.schemas import TaskPayload

# --- Test Task Definition ---
# For platforms without "full_flow", we send multiple tasks to get a complete data set.

TEST_SCENARIOS = [
    # 1. TIKTOK - Fully integrated flow
    {
        "platform": "tiktok",
        "queue": "tiktok_tasks",
        "action": "full_flow",
        "params": {
            "keyword": "vinfast vf8 review",
            "limit": 50,
            "comment_count": 1000,
            "threshold": 0  # 0 means fetch replies for ANY comment that has them
        }
    },
    # # 2. FACEBOOK - Post Detail
    # {
    #     "platform": "facebook",
    #     "queue": "facebook_tasks",
    #     "action": "post_detail",
    #     "params": {
    #         "parse_ids": ["100069153349307_pfbid0m6dmZhdGq59QT1DQY7m6Cp8cNDc1eiAT29prRfnJegdwwz1VLYj9ovStdyarETm4l"]
    #     }
    # },
    # # 3. FACEBOOK - Comments (Graph API)
    # {
    #     "platform": "facebook",
    #     "queue": "facebook_tasks",
    #     "action": "comments_graphql_batch",
    #     "params": {
    #         "post_ids": ["100069153349307_pfbid0m6dmZhdGq59QT1DQY7m6Cp8cNDc1eiAT29prRfnJegdwwz1VLYj9ovStdyarETm4l"],
    #         "count": 30
    #     }
    # },
    # # 4. YOUTUBE - Video Detail
    # {
    #     "platform": "youtube",
    #     "queue": "youtube_tasks",
    #     "action": "video_detail",
    #     "params": {
    #         "video_id": "dQw4w9WgXcQ"
    #     }
    # },
    # # 5. YOUTUBE - Comments
    # {
    #     "platform": "youtube",
    #     "queue": "youtube_tasks",
    #     "action": "comments",
    #     "params": {
    #         "video_id": "dQw4w9WgXcQ"
    #     }
    # }
]

async def run_comprehensive_tests():
    print(f"--- SMAP Scapper Comprehensive Data Test ---")
    print(f"Goal: Ensure both Post Detail and Comments are captured across all platforms.\n")

    tasks = []
    
    for scenario in TEST_SCENARIOS:
        payload = TaskPayload(
            action=scenario["action"],
            params=scenario["params"]
        ).model_dump()
        
        print(f"[+] Queuing {scenario['platform'].upper()} - {scenario['action']}")
        tasks.append(publish_task(scenario["queue"], payload))

    print(f"\nPublishing {len(tasks)} tasks to RabbitMQ...")
    
    try:
        await asyncio.gather(*tasks)
        print("\n[SUCCESS] All comprehensive test tasks have been published.")
        print("Expected results in MinIO bucket 'ingest-data':")
        print("  - tiktok/full_flow/ (Combined post + comments)")
        print("  - facebook/post_detail/ (Post content)")
        print("  - facebook/comments_graphql_batch/ (Post comments)")
        print("  - youtube/video_detail/ (Video content)")
        print("  - youtube/comments/ (Video comments)")
    except Exception as e:
        print(f"\n[ERROR] Failed to publish: {e}")
    finally:
        await close_publisher()

if __name__ == "__main__":
    try:
        asyncio.run(run_comprehensive_tests())
    except KeyboardInterrupt:
        pass
