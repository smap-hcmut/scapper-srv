from __future__ import annotations

import asyncio
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# Add root dir to sys.path for direct script execution.
ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from tinlikesub import TinLikeSubClient

from app.config import get_settings
from app.handlers.facebook import handle_full_flow as facebook_full_flow
from app.handlers.tiktok import handle_full_flow as tiktok_full_flow
from app.handlers.youtube import handle_full_flow as youtube_full_flow


OUT_DIR = ROOT_DIR / "output" / "validation_uap"

YOUTUBE_KEYWORDS = [
    "iphone 16 review",
    "vinfast vf8",
    "man city arsenal",
    "minecraft movie trailer",
    "tao quan",
]

FACEBOOK_KEYWORDS = [
    "Theanh28 Entertainment",
    "VTV24",
    "VinFast",
    "Arsenal",
    "iPhone 16",
]

TIKTOK_KEYWORDS = [
    "iphone 16",
    "vinfast vf8",
    "man city",
    "tao quan",
    "blackpink",
]


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _timestamp() -> str:
    return _now_utc().strftime("%Y%m%d_%H%M%S")


def _save_json(name: str, payload: Any) -> Path:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    path = OUT_DIR / f"{name}_{_timestamp()}.json"
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def _count_reply_bodies_from_items(items: list[dict[str, Any]], field: str) -> int:
    total = 0
    for item in items:
        nested = item.get(field)
        if isinstance(nested, list):
            total += len([entry for entry in nested if isinstance(entry, dict)])
    return total


def _count_nonzero_reply_count(items: list[dict[str, Any]], field: str) -> int:
    total = 0
    for item in items:
        value = item.get(field)
        if isinstance(value, (int, float)) and value > 0:
            total += 1
    return total


def _increment(counter: Counter[str], key: str, condition: bool) -> None:
    if condition:
        counter[key] += 1


async def probe_youtube(client: TinLikeSubClient) -> dict[str, Any]:
    raw_runs: list[dict[str, Any]] = []
    field_counter: Counter[str] = Counter()
    total_videos = 0
    reply_count_only_videos = 0

    for keyword in YOUTUBE_KEYWORDS:
        result = await youtube_full_flow(client, {
            "keyword": keyword,
            "limit": 2,
            "comment_count": 30,
        })
        raw_runs.append(result)

        for entry in result.get("videos", []):
            total_videos += 1
            video = entry.get("video") or {}
            detail = entry.get("detail") or {}
            comments = entry.get("comments") or {}
            transcript = entry.get("transcript") or {}
            comment_items = comments.get("comments", []) if isinstance(comments, dict) else []

            _increment(field_counter, "video.title", isinstance(video.get("title"), str) and bool(video.get("title")))
            _increment(field_counter, "video.thumbnail_url", isinstance(video.get("thumbnail_url"), str) and bool(video.get("thumbnail_url")))
            _increment(field_counter, "detail.title", isinstance(detail.get("title"), str) and bool(detail.get("title")))
            _increment(field_counter, "detail.description", isinstance(detail.get("description"), str) and bool(detail.get("description")))
            _increment(field_counter, "detail.keywords", isinstance(detail.get("keywords"), list) and len(detail.get("keywords", [])) > 0)
            _increment(field_counter, "detail.width", isinstance(detail.get("width"), int))
            _increment(field_counter, "detail.height", isinstance(detail.get("height"), int))
            _increment(field_counter, "detail.author_url", isinstance(detail.get("author_url"), str) and bool(detail.get("author_url")))
            _increment(field_counter, "detail.date_published", isinstance(detail.get("date_published"), str) and bool(detail.get("date_published")))
            _increment(field_counter, "detail.upload_date", isinstance(detail.get("upload_date"), str) and bool(detail.get("upload_date")))
            _increment(field_counter, "transcript.full_text", isinstance(transcript.get("full_text"), str) and bool(transcript.get("full_text")))
            _increment(field_counter, "transcript.segments", isinstance(transcript.get("segments"), list) and len(transcript.get("segments", [])) > 0)
            _increment(field_counter, "comments.items", isinstance(comment_items, list) and len(comment_items) > 0)

            comments_with_reply_count = _count_nonzero_reply_count(comment_items, "reply_count")
            reply_body_count = _count_reply_bodies_from_items(comment_items, "replies")
            if comments_with_reply_count > 0 and reply_body_count == 0:
                reply_count_only_videos += 1

    raw_path = _save_json("youtube_hot_keyword_full_flow_coverage_raw", raw_runs)
    return {
        "raw_output_path": str(raw_path),
        "keywords_tested": YOUTUBE_KEYWORDS,
        "total_videos": total_videos,
        "field_coverage": dict(field_counter),
        "reply_support": "count-only" if reply_count_only_videos > 0 else "not available in current raw",
    }


async def probe_facebook(client: TinLikeSubClient) -> dict[str, Any]:
    raw_runs: list[dict[str, Any]] = []
    field_counter: Counter[str] = Counter()
    attachment_type_counter: Counter[str] = Counter()
    total_posts = 0
    video_posts_with_caption = 0
    photo_posts_with_caption = 0
    reply_count_only_posts = 0

    for keyword in FACEBOOK_KEYWORDS:
        result = await facebook_full_flow(client, {
            "keyword": keyword,
            "limit": 3,
            "comment_count": 30,
            "comment_sort": "hot",
        })
        raw_runs.append(result)

        for entry in result.get("posts", []):
            total_posts += 1
            post = entry.get("post") or {}
            comments = entry.get("comments") or {}
            comment_items = comments.get("comments", []) if isinstance(comments, dict) else []

            _increment(field_counter, "post.message", isinstance(post.get("message"), str) and bool(post.get("message")))
            _increment(field_counter, "post.url", isinstance(post.get("url"), str) and bool(post.get("url")))
            _increment(field_counter, "post.author.url", isinstance((post.get("author") or {}).get("url"), str) and bool((post.get("author") or {}).get("url")))
            _increment(field_counter, "post.author.avatar_url", isinstance((post.get("author") or {}).get("avatar_url"), str) and bool((post.get("author") or {}).get("avatar_url")))
            _increment(field_counter, "post.created_time", post.get("created_time") is not None)
            _increment(field_counter, "post.attachments", isinstance(post.get("attachments"), list) and len(post.get("attachments", [])) > 0)
            _increment(field_counter, "comments.items", isinstance(comment_items, list) and len(comment_items) > 0)

            for attachment in post.get("attachments") or []:
                if not isinstance(attachment, dict):
                    continue
                att_type = attachment.get("type")
                if isinstance(att_type, str) and att_type:
                    attachment_type_counter[att_type] += 1
                _increment(field_counter, "attachments.media_url", isinstance(attachment.get("media_url"), str) and bool(attachment.get("media_url")))
                _increment(field_counter, "attachments.width", isinstance(attachment.get("width"), int))
                _increment(field_counter, "attachments.height", isinstance(attachment.get("height"), int))
                has_caption = isinstance(attachment.get("accessibility_caption"), str) and bool(attachment.get("accessibility_caption"))
                _increment(field_counter, "attachments.accessibility_caption", has_caption)
                if att_type == "Video" and has_caption:
                    video_posts_with_caption += 1
                if att_type == "Photo" and has_caption:
                    photo_posts_with_caption += 1

            _increment(field_counter, "comments.author.profile_url", any(
                isinstance((comment.get("author") or {}).get("profile_url"), str)
                and bool((comment.get("author") or {}).get("profile_url"))
                for comment in comment_items if isinstance(comment, dict)
            ))
            comments_with_reply_count = _count_nonzero_reply_count(comment_items, "reply_count")
            reply_body_count = _count_reply_bodies_from_items(comment_items, "replies")
            if comments_with_reply_count > 0 and reply_body_count == 0:
                reply_count_only_posts += 1

    raw_path = _save_json("facebook_hot_keyword_full_flow_coverage_raw", raw_runs)
    return {
        "raw_output_path": str(raw_path),
        "keywords_tested": FACEBOOK_KEYWORDS,
        "total_posts": total_posts,
        "field_coverage": dict(field_counter),
        "attachment_type_counts": dict(attachment_type_counter),
        "video_posts_with_accessibility_caption": video_posts_with_caption,
        "photo_posts_with_accessibility_caption": photo_posts_with_caption,
        "reply_support": "count-only" if reply_count_only_posts > 0 else "not available in current raw",
    }


async def probe_tiktok(client: TinLikeSubClient) -> dict[str, Any]:
    raw_runs: list[dict[str, Any]] = []
    field_counter: Counter[str] = Counter()
    total_posts = 0
    posts_with_any_comments = 0
    reply_count_only_posts = 0

    for keyword in TIKTOK_KEYWORDS:
        result = await tiktok_full_flow(client, {
            "keyword": keyword,
            "limit": 3,
            "comment_count": 80,
            "threshold": 0.3,
        })
        raw_runs.append(result)

        for entry in result.get("posts", []):
            total_posts += 1
            post = entry.get("post") or {}
            detail = entry.get("detail") or {}
            comments = entry.get("comments") or {}
            comment_items = comments.get("comments", []) if isinstance(comments, dict) else []

            _increment(field_counter, "post.description", isinstance(post.get("description"), str) and bool(post.get("description")))
            _increment(field_counter, "post.hashtags", isinstance(post.get("hashtags"), list) and len(post.get("hashtags", [])) > 0)
            _increment(field_counter, "detail.bookmarks_count", isinstance(detail.get("bookmarks_count"), int))
            _increment(field_counter, "detail.music_title", isinstance(detail.get("music_title"), str) and bool(detail.get("music_title")))
            _increment(field_counter, "detail.music_url", isinstance(detail.get("music_url"), str) and bool(detail.get("music_url")))
            _increment(field_counter, "detail.summary.title", isinstance((detail.get("summary") or {}).get("title"), str) and bool((detail.get("summary") or {}).get("title")))
            _increment(field_counter, "detail.summary.desc", isinstance((detail.get("summary") or {}).get("desc"), str) and bool((detail.get("summary") or {}).get("desc")))
            _increment(field_counter, "detail.summary.keywords", isinstance((detail.get("summary") or {}).get("keywords"), list) and len((detail.get("summary") or {}).get("keywords", [])) > 0)
            _increment(field_counter, "detail.subtitle_url", isinstance(detail.get("subtitle_url"), str) and bool(detail.get("subtitle_url")))
            _increment(field_counter, "detail.downloads.subtitle", isinstance((detail.get("downloads") or {}).get("subtitle"), str) and bool((detail.get("downloads") or {}).get("subtitle")))
            _increment(field_counter, "detail.downloads.video", isinstance((detail.get("downloads") or {}).get("video"), str) and bool((detail.get("downloads") or {}).get("video")))
            _increment(field_counter, "detail.video_resources", isinstance(detail.get("video_resources"), list) and len(detail.get("video_resources", [])) > 0)
            _increment(field_counter, "comments.items", isinstance(comment_items, list) and len(comment_items) > 0)

            if isinstance(comment_items, list) and len(comment_items) > 0:
                posts_with_any_comments += 1

            comments_with_reply_count = _count_nonzero_reply_count(comment_items, "reply_count")
            reply_body_count = _count_reply_bodies_from_items(comment_items, "reply_comments")
            if comments_with_reply_count > 0 and reply_body_count == 0:
                reply_count_only_posts += 1

    raw_path = _save_json("tiktok_hot_keyword_full_flow_coverage_raw", raw_runs)
    return {
        "raw_output_path": str(raw_path),
        "keywords_tested": TIKTOK_KEYWORDS,
        "total_posts": total_posts,
        "posts_with_any_comments": posts_with_any_comments,
        "field_coverage": dict(field_counter),
        "reply_support": "count-only" if reply_count_only_posts > 0 else "not available in current raw",
    }


async def main() -> int:
    settings = get_settings()
    client = TinLikeSubClient(
        base_url=settings.API_BASE_URL,
        api_key=settings.API_KEY,
        timeout=120.0,
        secret_key=settings.API_SECRET_KEY,
    )
    try:
        youtube, facebook, tiktok = await asyncio.gather(
            probe_youtube(client),
            probe_facebook(client),
            probe_tiktok(client),
        )
    finally:
        await client.close()

    summary = {
        "generated_at": _now_utc().isoformat(),
        "api_base_url": settings.API_BASE_URL,
        "keyword_strategy": "heuristic mix of tech, sports, entertainment, auto",
        "youtube": youtube,
        "facebook": facebook,
        "tiktok": tiktok,
    }
    summary_path = _save_json("uap_hot_keyword_coverage_summary", summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"summary_path={summary_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
