from __future__ import annotations

import asyncio
import json
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# Add root dir to sys.path for direct script execution.
ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from tinlikesub import TinLikeSubClient

from app.config import get_settings


OUT_DIR = ROOT_DIR / "output" / "validation_uap"


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _timestamp() -> str:
    return _now_utc().strftime("%Y%m%d_%H%M%S")


def _save_json(name: str, payload: Any) -> Path:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    path = OUT_DIR / f"{name}_{_timestamp()}.json"
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def _extract_nested_videos(search_results: Any, limit: int) -> list[dict[str, Any]]:
    videos: list[dict[str, Any]] = []
    groups = search_results if isinstance(search_results, list) else [search_results]
    for group in groups:
        if isinstance(group, dict) and isinstance(group.get("videos"), list):
            videos.extend(group["videos"])
    return videos[:limit]


def _extract_nested_posts(search_results: Any, limit: int) -> list[dict[str, Any]]:
    posts: list[dict[str, Any]] = []
    groups = search_results if isinstance(search_results, list) else [search_results]
    for group in groups:
        if isinstance(group, dict) and isinstance(group.get("posts"), list):
            posts.extend(group["posts"])
        elif isinstance(group, dict):
            posts.append(group)
    return posts[:limit]


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


def _preview_text(value: Any, limit: int = 180) -> str | None:
    if not isinstance(value, str):
        return None
    collapsed = " ".join(value.split())
    if not collapsed:
        return None
    return collapsed[:limit]


@dataclass
class PlatformValidation:
    raw_output_path: str
    summary: dict[str, Any]


async def validate_youtube(client: TinLikeSubClient) -> PlatformValidation:
    keyword = "iphone 16 review"
    limit = 2
    comment_count = 40

    search_results = await client.youtube.search(keywords=[keyword], limit=limit)
    videos = _extract_nested_videos(search_results, limit)

    entries: list[dict[str, Any]] = []
    for video in videos:
        video_id = video.get("video_id")
        entry: dict[str, Any] = {
            "video": video,
            "detail": None,
            "comments": None,
            "transcript": None,
        }
        if video_id:
            try:
                entry["detail"] = await client.youtube.get_video_detail(video_id=video_id)
            except Exception as exc:  # noqa: BLE001
                entry["detail"] = {"error": str(exc)}
            try:
                entry["comments"] = await client.youtube.get_comments(
                    video_id=video_id,
                    limit=comment_count,
                )
            except Exception as exc:  # noqa: BLE001
                entry["comments"] = {"error": str(exc)}
            try:
                entry["transcript"] = await client.youtube.get_transcript(video_id=video_id)
            except Exception as exc:  # noqa: BLE001
                entry["transcript"] = {"error": str(exc)}
        entries.append(entry)

    payload = {
        "keyword": keyword,
        "total_videos": len(entries),
        "videos": entries,
    }
    output_path = _save_json("youtube_full_flow_with_transcript_validation", payload)

    entry_summaries: list[dict[str, Any]] = []
    reply_count_only_videos = 0
    for entry in entries:
        comments = entry.get("comments")
        transcript = entry.get("transcript")
        comment_items = comments.get("comments", []) if isinstance(comments, dict) else []
        reply_body_count = _count_reply_bodies_from_items(comment_items, "replies")
        comments_with_reply_count = _count_nonzero_reply_count(comment_items, "reply_count")
        if comments_with_reply_count > 0 and reply_body_count == 0:
            reply_count_only_videos += 1

        transcript_text = None
        transcript_segments = None
        if isinstance(transcript, dict):
            transcript_text = transcript.get("full_text")
            segments = transcript.get("segments")
            if isinstance(segments, list):
                transcript_segments = len(segments)

        entry_summaries.append({
            "video_id": entry.get("video", {}).get("video_id"),
            "shape_additive_only": list(entry.keys()) == ["video", "detail", "comments", "transcript"],
            "has_detail": isinstance(entry.get("detail"), dict) and "error" not in entry["detail"],
            "has_comments": isinstance(comments, dict) and "error" not in comments,
            "has_transcript": isinstance(transcript_text, str) and bool(transcript_text.strip()),
            "transcript_text_length": len(transcript_text or ""),
            "transcript_segments": transcript_segments,
            "comments_count": len(comment_items) if isinstance(comment_items, list) else 0,
            "comments_with_reply_count": comments_with_reply_count,
            "reply_body_count": reply_body_count,
        })

    summary = {
        "keyword": keyword,
        "total_videos": len(entries),
        "shape_before": ["video", "detail", "comments"],
        "shape_after": ["video", "detail", "comments", "transcript"],
        "transcript_addition_supported": all(
            item["shape_additive_only"] and item["has_transcript"]
            for item in entry_summaries
        ) if entry_summaries else False,
        "reply_support": (
            "count-only"
            if reply_count_only_videos > 0
            else "not available in current raw"
        ),
        "videos": entry_summaries,
    }
    return PlatformValidation(raw_output_path=str(output_path), summary=summary)


async def validate_facebook(client: TinLikeSubClient) -> PlatformValidation:
    keyword = "Theanh28 Entertainment"
    count = 8
    search_result = await client.facebook.search_graphql(keyword=keyword, count=count)
    posts = search_result.get("posts", []) if isinstance(search_result, dict) else []

    video_post = None
    photo_post = None
    for post in posts:
        attachments = post.get("attachments") or []
        if not isinstance(attachments, list):
            continue
        attachment_types = {item.get("type") for item in attachments if isinstance(item, dict)}
        if "Video" in attachment_types and video_post is None:
            video_post = post
        if "Photo" in attachment_types and photo_post is None:
            photo_post = post
        if video_post and photo_post:
            break

    validation_payload: dict[str, Any] = {
        "keyword": keyword,
        "search_result": search_result,
        "selected_video_post": video_post,
        "selected_photo_post": photo_post,
    }

    if video_post and isinstance(video_post.get("post_id"), str):
        try:
            validation_payload["video_post_comments"] = await client.facebook.get_comments_graphql(
                post_id=video_post["post_id"],
                count=40,
                sort="hot",
            )
        except Exception as exc:  # noqa: BLE001
            validation_payload["video_post_comments"] = {"error": str(exc)}

    output_path = _save_json("facebook_video_caption_validation", validation_payload)

    def attachment_summary(post: dict[str, Any] | None) -> dict[str, Any] | None:
        if not isinstance(post, dict):
            return None
        attachments = post.get("attachments") or []
        summaries = []
        for item in attachments:
            if not isinstance(item, dict):
                continue
            summaries.append({
                "type": item.get("type"),
                "url": item.get("url"),
                "media_url": item.get("media_url"),
                "width": item.get("width"),
                "height": item.get("height"),
                "accessibility_caption_present": isinstance(item.get("accessibility_caption"), str)
                and bool(item.get("accessibility_caption", "").strip()),
                "accessibility_caption_preview": _preview_text(item.get("accessibility_caption")),
            })
        return {
            "post_id": post.get("post_id"),
            "parse_id": post.get("parse_id"),
            "attachments": summaries,
        }

    comments_root = validation_payload.get("video_post_comments")
    comment_items = comments_root.get("comments", []) if isinstance(comments_root, dict) else []
    reply_body_count = _count_reply_bodies_from_items(comment_items, "replies")
    comments_with_reply_count = _count_nonzero_reply_count(comment_items, "reply_count")

    video_summary = attachment_summary(video_post)
    photo_summary = attachment_summary(photo_post)

    video_caption_present = any(
        item.get("accessibility_caption_present")
        for item in (video_summary or {}).get("attachments", [])
    )
    photo_caption_present = any(
        item.get("accessibility_caption_present")
        for item in (photo_summary or {}).get("attachments", [])
    )

    summary = {
        "keyword": keyword,
        "total_posts_scanned": len(posts),
        "video_post_found": video_post is not None,
        "photo_post_found": photo_post is not None,
        "video_post": video_summary,
        "photo_post": photo_summary,
        "video_accessibility_caption_behavior": (
            "present"
            if video_caption_present
            else "not present in tested video sample"
        ),
        "photo_accessibility_caption_behavior": (
            "present"
            if photo_caption_present
            else "not present in tested photo sample"
        ),
        "reply_support": (
            "count-only"
            if comments_with_reply_count > 0 and reply_body_count == 0
            else "not available in current raw"
        ),
        "comments_with_reply_count": comments_with_reply_count,
        "reply_body_count": reply_body_count,
    }
    return PlatformValidation(raw_output_path=str(output_path), summary=summary)


async def _run_tiktok_full_flow(
    client: TinLikeSubClient,
    keyword: str,
    limit: int,
    comment_count: int,
    threshold: float,
) -> dict[str, Any]:
    search_results = await client.tiktok.search(keywords=[keyword])
    posts = _extract_nested_posts(search_results, limit)

    results: list[dict[str, Any]] = []
    for post in posts:
        entry: dict[str, Any] = {"post": post, "detail": None, "comments": None}
        video_url = post.get("url") or post.get("share_url")
        aweme_id = post.get("aweme_id") or post.get("video_id") or post.get("id")

        if video_url:
            try:
                detail_list = await client.tiktok.get_post_detail(urls=[video_url])
                entry["detail"] = detail_list[0] if detail_list else None
            except Exception as exc:  # noqa: BLE001
                entry["detail"] = {"error": str(exc)}

        if aweme_id:
            try:
                comments_list = await client.tiktok.get_comments(
                    aweme_ids=[str(aweme_id)],
                    count=comment_count,
                    threshold=threshold,
                )
                entry["comments"] = comments_list[0] if comments_list else None
            except Exception as exc:  # noqa: BLE001
                entry["comments"] = {"error": str(exc)}

        results.append(entry)

    return {"keyword": keyword, "total_posts": len(results), "posts": results}


async def validate_tiktok(client: TinLikeSubClient) -> PlatformValidation:
    keywords = ["vinfast vf8", "iphone 16", "bia tiger"]
    limit = 3
    comment_count = 120
    threshold = 0.3

    attempts: list[dict[str, Any]] = []
    selected_payload = None
    selected_summary = None

    for keyword in keywords:
        payload = await _run_tiktok_full_flow(
            client=client,
            keyword=keyword,
            limit=limit,
            comment_count=comment_count,
            threshold=threshold,
        )
        post_entries = payload.get("posts", [])
        total_comments = 0
        comments_with_reply_count = 0
        reply_body_count = 0
        sample_comment_ids: list[str] = []

        for entry in post_entries:
            comments_root = entry.get("comments")
            comment_items = comments_root.get("comments", []) if isinstance(comments_root, dict) else []
            total_comments += len(comment_items) if isinstance(comment_items, list) else 0
            comments_with_reply_count += _count_nonzero_reply_count(comment_items, "reply_count")
            reply_body_count += _count_reply_bodies_from_items(comment_items, "reply_comments")
            for item in comment_items[:3]:
                if isinstance(item, dict) and item.get("reply_count"):
                    sample_comment_ids.append(str(item.get("comment_id")))

        summary = {
            "keyword": keyword,
            "threshold": threshold,
            "total_posts": len(post_entries),
            "total_comments": total_comments,
            "comments_with_reply_count": comments_with_reply_count,
            "reply_body_count": reply_body_count,
            "sample_comment_ids_with_reply_count": sample_comment_ids[:5],
            "reply_support": (
                "supported now"
                if reply_body_count > 0
                else "count-only"
                if comments_with_reply_count > 0
                else "not available in current raw"
            ),
        }
        attempts.append(summary)

        if selected_payload is None or reply_body_count > 0:
            selected_payload = payload
            selected_summary = summary
        if reply_body_count > 0:
            break

    output_path = _save_json("tiktok_full_flow_threshold03_validation", selected_payload)

    summary = {
        "threshold": threshold,
        "attempts": attempts,
        "selected_keyword": selected_summary["keyword"] if selected_summary else None,
        "selected_result": selected_summary,
    }
    return PlatformValidation(raw_output_path=str(output_path), summary=summary)


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
            validate_youtube(client),
            validate_facebook(client),
            validate_tiktok(client),
        )
    finally:
        await client.close()

    summary = {
        "generated_at": _now_utc().isoformat(),
        "api_base_url": settings.API_BASE_URL,
        "youtube": asdict(youtube),
        "facebook": asdict(facebook),
        "tiktok": asdict(tiktok),
    }
    summary_path = _save_json("uap_validation_summary", summary)

    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"summary_path={summary_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
