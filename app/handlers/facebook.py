"""Facebook action handlers — each calls the main API via SDK."""

from __future__ import annotations

from typing import Any

from loguru import logger
from tinlikesub import TinLikeSubClient


async def handle_search(client: TinLikeSubClient, params: dict) -> Any:
    """Alias for search_graphql — the legacy v1 Graph-search SDK method was
    removed in tinlikesub 0.3.0 (no v2 JobKind backed it). Output shape is
    preserved as ``list[dict]`` so downstream services don't need to change.
    """
    keyword = params.get("keyword", "")
    count = params.get("limit", params.get("count", 20))
    cursor = params.get("cursor")
    logger.info(f"[Facebook] search: keyword={keyword} count={count}")
    envelope = await client.facebook.search_graphql(
        keyword=keyword, count=count, cursor=cursor,
    )
    logger.debug(
        f"[Facebook] search envelope: end_cursor={envelope.get('end_cursor')} "
        f"has_next={envelope.get('has_next')}"
    )
    return envelope.get("posts", [])


async def handle_posts(client: TinLikeSubClient, params: dict) -> Any:
    """Same migration story as handle_search — routes through GraphQL/v2.
    Returns ``list[dict]`` for backward compat with downstream consumers.
    """
    keyword = params.get("keyword", "")
    count = params.get("page_size", params.get("count", 20))
    cursor = params.get("cursor")
    logger.info(f"[Facebook] posts: keyword={keyword} count={count}")
    envelope = await client.facebook.search_graphql(
        keyword=keyword, count=count, cursor=cursor,
    )
    logger.debug(
        f"[Facebook] posts envelope: end_cursor={envelope.get('end_cursor')} "
        f"has_next={envelope.get('has_next')}"
    )
    return envelope.get("posts", [])


async def handle_post_detail(client: TinLikeSubClient, params: dict) -> Any:
    # Accept "parse_ids" (list) or "parse_id" (single, backward compat)
    parse_ids = params.get("parse_ids") or [params["parse_id"]]
    logger.info(f"[Facebook] post_detail: {len(parse_ids)} id(s)")
    return await client.facebook.get_post_detail(parse_ids=parse_ids)


async def handle_comments(client: TinLikeSubClient, params: dict) -> Any:
    """Alias for comments_graphql — the legacy Graph-API SDK method was
    removed in tinlikesub 0.3.0 (no v2 JobKind backed it). Output shape is
    preserved as ``list[dict]`` so downstream services don't need to change.
    """
    post_id = params["post_id"]
    count = params.get("limit", params.get("count", 100))
    cursor = params.get("cursor")
    sort = params.get("sort", "hot")
    logger.info(f"[Facebook] comments: post_id={post_id} count={count}")
    envelope = await client.facebook.get_comments_graphql(
        post_id=post_id, count=count, cursor=cursor, sort=sort,
    )
    logger.debug(
        f"[Facebook] comments envelope: total={envelope.get('total_count')} "
        f"end_cursor={envelope.get('end_cursor')} has_next={envelope.get('has_next')}"
    )
    return envelope.get("comments", [])


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


async def handle_search_graphql(client: TinLikeSubClient, params: dict) -> Any:
    keyword = params.get("keyword", "")
    cursor = params.get("cursor")
    count = params.get("count", 5)
    logger.info(f"[Facebook] search_graphql: keyword={keyword} count={count}")
    return await client.facebook.search_graphql(
        keyword=keyword, cursor=cursor, count=count,
    )


async def handle_search_graphql_batch(client: TinLikeSubClient, params: dict) -> Any:
    keywords = params["keywords"]
    count = params.get("count", 5)
    logger.info(f"[Facebook] search_graphql_batch: {len(keywords)} keywords count={count}")
    return await client.facebook.search_graphql_batch(
        keywords=keywords, count=count,
    )


async def handle_full_flow(client: TinLikeSubClient, params: dict) -> Any:
    """search keyword → get posts → get comments (graphql) for each post."""
    keyword = params.get("keyword", "")
    limit = params.get("limit", 5)
    comment_count = params.get("comment_count", 50)
    comment_sort = params.get("comment_sort", "hot")

    logger.info(f"[Facebook] full_flow: keyword={keyword} limit={limit}")

    # Step 1: Search via GraphQL
    search_result = await client.facebook.search_graphql(
        keyword=keyword, count=limit,
    )
    posts: list[dict] = search_result.get("posts", [])

    # Step 2: For each post → comments (graphql)
    results = []
    for post in posts:
        post_id = post.get("post_id")
        entry: dict[str, Any] = {"post": post, "comments": None}

        if post_id:
            try:
                entry["comments"] = await client.facebook.get_comments_graphql(
                    post_id=post_id, count=comment_count, sort=comment_sort,
                )
            except Exception as e:
                entry["comments"] = {"error": str(e)}

        results.append(entry)

    return {"keyword": keyword, "total_posts": len(results), "posts": results}


HANDLERS = {
    "search": handle_search,
    "posts": handle_posts,
    "post_detail": handle_post_detail,
    "comments": handle_comments,
    "comments_graphql": handle_comments_graphql,
    "comments_graphql_batch": handle_comments_graphql_batch,
    "search_graphql": handle_search_graphql,
    "search_graphql_batch": handle_search_graphql_batch,
    "full_flow": handle_full_flow,
}
