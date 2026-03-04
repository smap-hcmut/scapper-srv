"""Facebook action handlers — each calls the main API via SDK."""

from __future__ import annotations

from typing import Any

from loguru import logger
from tinlikesub import TinLikeSubClient


async def handle_search(client: TinLikeSubClient, params: dict) -> Any:
    keyword = params.get("keyword", "")
    limit = params.get("limit", 20)
    logger.info(f"[Facebook] search: keyword={keyword} limit={limit}")
    return await client.facebook.search(keyword=keyword, limit=limit)


async def handle_posts(client: TinLikeSubClient, params: dict) -> Any:
    keyword = params.get("keyword", "")
    page_size = params.get("page_size", 20)
    logger.info(f"[Facebook] posts: keyword={keyword}")
    return await client.facebook.search(keyword=keyword, limit=page_size)


HANDLERS = {
    "search": handle_search,
    "posts": handle_posts,
}
