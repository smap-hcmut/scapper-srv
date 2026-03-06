"""TikTok action handlers — each calls the main API via SDK."""

from __future__ import annotations

import re
from typing import Any

from loguru import logger
from tinlikesub import TinLikeSubClient

# Extract aweme_id from TikTok video URL
# e.g. https://www.tiktok.com/@user/video/7612600015135034644 → 7612600015135034644
_VIDEO_ID_RE = re.compile(r"/video/(\d+)")


def _extract_aweme_id(video_url: str) -> str:
    """Extract aweme_id from a TikTok video URL."""
    m = _VIDEO_ID_RE.search(video_url)
    if not m:
        raise ValueError(f"Cannot extract aweme_id from URL: {video_url}")
    return m.group(1)


async def handle_search(client: TinLikeSubClient, params: dict) -> Any:
    keywords = params.get("keywords", [])
    logger.info(f"[TikTok] search: keywords={keywords}")
    return await client.tiktok.search(keywords=keywords)


async def handle_post_detail(client: TinLikeSubClient, params: dict) -> Any:
    # Accept "urls" (list) or "url" (single, backward compat)
    urls = params.get("urls") or [params["url"]]
    logger.info(f"[TikTok] post_detail: {len(urls)} url(s)")
    return await client.tiktok.get_post_detail(urls=urls)


async def handle_comments(client: TinLikeSubClient, params: dict) -> Any:
    # Accept arrays (preferred) or single values (backward compat)
    video_urls = params.get("video_urls")
    if video_urls:
        aweme_ids = [_extract_aweme_id(u) for u in video_urls]
    elif params.get("video_url"):
        aweme_ids = [_extract_aweme_id(params["video_url"])]
    elif params.get("aweme_ids"):
        aweme_ids = params["aweme_ids"]
    else:
        aweme_ids = [params["aweme_id"]]

    cursor = params.get("cursor", 0)
    count = params.get("count", 50)
    threshold = params.get("threshold")
    logger.info(f"[TikTok] comments: {len(aweme_ids)} id(s) cursor={cursor} count={count}")
    return await client.tiktok.get_comments(
        aweme_ids=aweme_ids, cursor=cursor, count=count, threshold=threshold,
    )


async def handle_summary(client: TinLikeSubClient, params: dict) -> Any:
    # Accept arrays (preferred) or single values (backward compat)
    video_urls = params.get("video_urls")
    if video_urls:
        item_ids = [_extract_aweme_id(u) for u in video_urls]
    elif params.get("video_url"):
        item_ids = [_extract_aweme_id(params["video_url"])]
    elif params.get("item_ids"):
        item_ids = params["item_ids"]
    else:
        item_ids = [params["item_id"]]
    logger.info(f"[TikTok] summary: {len(item_ids)} id(s)")
    return await client.tiktok.get_summary(item_ids=item_ids)


async def handle_comment_replies(client: TinLikeSubClient, params: dict) -> Any:
    # Accept video_url (preferred) or item_id
    video_url = params.get("video_url")
    if video_url:
        item_id = _extract_aweme_id(video_url)
    else:
        item_id = params["item_id"]
    comment_id = params["comment_id"]
    cursor = params.get("cursor", 0)
    count = params.get("count", 50)
    logger.info(f"[TikTok] comment_replies: item_id={item_id} comment_id={comment_id}")
    return await client.tiktok.get_comment_replies(
        item_id=item_id, comment_id=comment_id, cursor=cursor, count=count,
    )


async def handle_cookie_check(client: TinLikeSubClient, params: dict) -> Any:
    logger.info("[TikTok] cookie_check")
    return await client.tiktok.check_cookie()


async def handle_full_flow(client: TinLikeSubClient, params: dict) -> Any:
    """Composite: search → post_detail → comments for each result."""
    keyword = params.get("keyword", "")
    limit = params.get("limit", 3)
    threshold = params.get("threshold", 0.5)
    comment_count = params.get("comment_count", 200)

    logger.info(f"[TikTok] full_flow: keyword={keyword} limit={limit}")

    # Step 1: Search
    search_results = await client.tiktok.search(keywords=[keyword])
    all_posts: list[dict] = []
    for group in search_results if isinstance(search_results, list) else [search_results]:
        if isinstance(group, dict) and "posts" in group:
            all_posts.extend(group["posts"])
        elif isinstance(group, dict):
            all_posts.append(group)
    all_posts = all_posts[:limit]

    # Step 2: For each post → detail + comments
    results = []
    for post in all_posts:
        entry: dict[str, Any] = {"post": post, "detail": None, "comments": None}

        video_url = post.get("url") or post.get("share_url")
        if video_url:
            try:
                detail_list = await client.tiktok.get_post_detail(urls=[video_url])
                entry["detail"] = detail_list[0] if detail_list else None
            except Exception as e:
                entry["detail"] = {"error": str(e)}

        aweme_id = post.get("aweme_id") or post.get("video_id") or post.get("id")
        if aweme_id:
            try:
                comments_list = await client.tiktok.get_comments(
                    aweme_ids=[str(aweme_id)], count=comment_count, threshold=threshold,
                )
                entry["comments"] = comments_list[0] if comments_list else None
            except Exception as e:
                entry["comments"] = {"error": str(e)}

        results.append(entry)

    return {"keyword": keyword, "total_posts": len(results), "posts": results}


HANDLERS = {
    "search": handle_search,
    "post_detail": handle_post_detail,
    "comments": handle_comments,
    "summary": handle_summary,
    "comment_replies": handle_comment_replies,
    "cookie_check": handle_cookie_check,
    "full_flow": handle_full_flow,
}
