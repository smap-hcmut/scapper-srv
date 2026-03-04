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


async def handle_post_detail(client: TinLikeSubClient, params: dict) -> Any:
    parse_id = params["parse_id"]
    logger.info(f"[Facebook] post_detail: parse_id={parse_id}")
    return await client.facebook.get_post_detail(parse_id=parse_id)


async def handle_comments(client: TinLikeSubClient, params: dict) -> Any:
    post_id = params["post_id"]
    limit = params.get("limit", 100)
    logger.info(f"[Facebook] comments: post_id={post_id} limit={limit}")
    return await client.facebook.get_comments(post_id=post_id, limit=limit)


async def handle_comments_graphql(client: TinLikeSubClient, params: dict) -> Any:
    post_id = params["post_id"]
    cursor = params.get("cursor")
    count = params.get("count", 50)
    sort = params.get("sort", "hot")
    logger.info(f"[Facebook] comments_graphql: post_id={post_id} sort={sort} count={count}")
    return await client.facebook.get_comments_graphql(
        post_id=post_id, cursor=cursor, count=count, sort=sort,
    )


async def handle_comments_graphql_batch(client: TinLikeSubClient, params: dict) -> Any:
    post_ids = params["post_ids"]
    count = params.get("count", 50)
    sort = params.get("sort", "hot")
    logger.info(f"[Facebook] comments_graphql_batch: {len(post_ids)} posts sort={sort}")
    return await client.facebook.get_comments_graphql_batch(
        post_ids=post_ids, count=count, sort=sort,
    )


HANDLERS = {
    "search": handle_search,
    "posts": handle_posts,
    "post_detail": handle_post_detail,
    "comments": handle_comments,
    "comments_graphql": handle_comments_graphql,
    "comments_graphql_batch": handle_comments_graphql_batch,
}
