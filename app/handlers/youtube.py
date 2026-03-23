"""YouTube action handlers — each calls the main API via SDK."""

from __future__ import annotations

from typing import Any

from loguru import logger
from tinlikesub import TinLikeSubClient


async def handle_search(client: TinLikeSubClient, params: dict) -> Any:
    keywords = params.get("keywords", [])
    limit = params.get("limit", 20)
    sort_by = params.get("sort_by")
    upload_date = params.get("upload_date")
    video_type = params.get("video_type")
    duration = params.get("duration")
    logger.info(f"[YouTube] search: keywords={keywords} limit={limit}")
    return await client.youtube.search(
        keywords=keywords, limit=limit,
        sort_by=sort_by, upload_date=upload_date,
        video_type=video_type, duration=duration,
    )


async def handle_videos(client: TinLikeSubClient, params: dict) -> Any:
    keyword = params.get("keyword", "")
    page = params.get("page", 1)
    page_size = params.get("page_size", 20)
    logger.info(f"[YouTube] videos: keyword={keyword} page={page}")
    return await client.youtube.get_videos(keyword=keyword, page=page, page_size=page_size)


async def handle_video_detail(client: TinLikeSubClient, params: dict) -> Any:
    video_id = params["video_id"]
    logger.info(f"[YouTube] video_detail: video_id={video_id}")
    return await client.youtube.get_video_detail(video_id=video_id)


async def handle_transcript(client: TinLikeSubClient, params: dict) -> Any:
    video_id = params["video_id"]
    logger.info(f"[YouTube] transcript: video_id={video_id}")
    return await client.youtube.get_transcript(video_id=video_id)


async def handle_comments(client: TinLikeSubClient, params: dict) -> Any:
    video_id = params["video_id"]
    limit = params.get("limit", 100)
    logger.info(f"[YouTube] comments: video_id={video_id} limit={limit}")
    return await client.youtube.get_comments(video_id=video_id, limit=limit)


async def handle_full_flow(client: TinLikeSubClient, params: dict) -> Any:
    """Composite: search → video_detail + comments for each result."""
    keyword = params.get("keyword", "")
    limit = params.get("limit", 5)
    comment_count = params.get("comment_count", 100)
    sort_by = params.get("sort_by")
    upload_date = params.get("upload_date")
    video_type = params.get("video_type")
    duration = params.get("duration")

    logger.info(f"[YouTube] full_flow: keyword={keyword} limit={limit}")

    # Step 1: Search
    search_results = await client.youtube.search(
        keywords=[keyword], limit=limit,
        sort_by=sort_by, upload_date=upload_date,
        video_type=video_type, duration=duration,
    )
    videos: list[dict] = []
    for group in search_results if isinstance(search_results, list) else [search_results]:
        if isinstance(group, dict) and "videos" in group:
            videos.extend(group["videos"])
    videos = videos[:limit]

    # Step 2: For each video → detail + comments
    results = []
    for video in videos:
        vid = video.get("video_id", "")
        entry: dict[str, Any] = {"video": video, "detail": None, "comments": None}

        if vid:
            try:
                entry["detail"] = await client.youtube.get_video_detail(video_id=vid)
            except Exception as e:
                entry["detail"] = {"error": str(e)}

            try:
                entry["comments"] = await client.youtube.get_comments(
                    video_id=vid, limit=comment_count,
                )
            except Exception as e:
                entry["comments"] = {"error": str(e)}

        results.append(entry)

    return {"keyword": keyword, "total_videos": len(results), "videos": results}


HANDLERS = {
    "search": handle_search,
    "videos": handle_videos,
    "video_detail": handle_video_detail,
    "transcript": handle_transcript,
    "comments": handle_comments,
    "full_flow": handle_full_flow,
}
