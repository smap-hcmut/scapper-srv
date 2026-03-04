"""YouTube action handlers — each calls the main API via SDK."""

from __future__ import annotations

from typing import Any

from loguru import logger
from tinlikesub import TinLikeSubClient


async def handle_search(client: TinLikeSubClient, params: dict) -> Any:
    keyword = params.get("keyword", "")
    limit = params.get("limit", 20)
    logger.info(f"[YouTube] search: keyword={keyword} limit={limit}")
    return await client.youtube.search(keyword=keyword, limit=limit)


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
    logger.info(f"[YouTube] comments: video_id={video_id}")
    return await client.youtube.get_comments(video_id=video_id)


HANDLERS = {
    "search": handle_search,
    "videos": handle_videos,
    "video_detail": handle_video_detail,
    "transcript": handle_transcript,
    "comments": handle_comments,
}
