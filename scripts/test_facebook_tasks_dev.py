from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


BASE_URL = os.environ.get("API_BASE", "http://127.0.0.1:8105")
OUT_DIR = Path(os.environ.get("FB_OUT_DIR", "output/facebook_task_tests"))


def _request(method: str, path: str, body: dict[str, Any] | None = None) -> dict[str, Any]:
    data = None
    headers = {"Content-Type": "application/json"}
    if body is not None:
        data = json.dumps(body).encode("utf-8")
    req = Request(f"{BASE_URL}{path}", data=data, headers=headers, method=method)
    try:
        with urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="ignore")
        raise RuntimeError(f"HTTP {exc.code} {path}: {detail}") from exc
    except URLError as exc:
        raise RuntimeError(f"Network error {path}: {exc}") from exc


def submit_fb(action: str, params: dict[str, Any]) -> str:
    payload = {"action": action, "params": params}
    resp = _request("POST", "/api/v1/tasks/facebook", payload)
    return resp["task_id"]


def poll_result(task_id: str, timeout_sec: int = 180) -> dict[str, Any]:
    deadline = time.time() + timeout_sec
    while time.time() < deadline:
        try:
            return _request("GET", f"/api/v1/tasks/{task_id}/result")
        except RuntimeError as exc:
            if "HTTP 404" not in str(exc):
                raise
        time.sleep(1)
    raise TimeoutError(f"Timeout waiting task result: {task_id}")


def save_result(action: str, task_id: str, result: dict[str, Any]) -> Path:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = OUT_DIR / f"facebook_{action}_{task_id}.json"
    out_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return out_path


def pick_post_ids(result_obj: dict[str, Any]) -> list[str]:
    result = result_obj.get("result")
    if not isinstance(result, dict):
        return []
    posts = result.get("posts")
    if not isinstance(posts, list):
        return []

    values: list[str] = []
    for post in posts:
        if not isinstance(post, dict):
            continue
        for key in ("post_id", "id", "parse_id"):
            value = post.get(key)
            if isinstance(value, str) and value.strip():
                values.append(value)
                break
    return values


def pick_parse_ids(result_obj: dict[str, Any]) -> list[str]:
    result = result_obj.get("result")
    if not isinstance(result, dict):
        return []
    posts = result.get("posts")
    if not isinstance(posts, list):
        return []

    values: list[str] = []
    for post in posts:
        if not isinstance(post, dict):
            continue
        value = post.get("parse_id")
        if isinstance(value, str) and value.strip():
            values.append(value)
    return values


def run_and_capture(action: str, params: dict[str, Any]) -> dict[str, Any]:
    task_id = submit_fb(action, params)
    result = poll_result(task_id)
    out_path = save_result(action, task_id, result)
    status = result.get("status")
    print(f"[OK] {action}: task_id={task_id} status={status} -> {out_path}")
    return result


def main() -> int:
    keyword = os.environ.get("FB_KEYWORD", "vinfast")
    fallback_parse_id = os.environ.get(
        "FB_PARSE_ID",
        "100069153349307_pfbid0m6dmZhdGq59QT1DQY7m6Cp8cNDc1eiAT29prRfnJegdwwz1VLYj9ovStdyarETm4l",
    )
    fallback_post_id = os.environ.get("FB_POST_ID", fallback_parse_id)

    print(f"Testing Facebook tasks via {BASE_URL}, keyword={keyword}")

    # Group A: no dependency on prior ids
    search_res = run_and_capture("search", {"keyword": keyword, "limit": 5})
    posts_res = run_and_capture("posts", {"keyword": keyword, "page_size": 5})
    sg_res = run_and_capture("search_graphql", {"keyword": keyword, "count": 5})
    sgb_res = run_and_capture(
        "search_graphql_batch",
        {"keywords": [keyword, "iphone 16"], "count": 3},
    )
    ff_res = run_and_capture(
        "full_flow",
        {"keyword": keyword, "limit": 3, "comment_count": 30, "comment_sort": "hot"},
    )

    post_ids = pick_post_ids(sg_res) or pick_post_ids(search_res) or pick_post_ids(posts_res)
    parse_ids = pick_parse_ids(sg_res) or pick_parse_ids(search_res) or pick_parse_ids(posts_res)

    post_id = post_ids[0] if post_ids else fallback_post_id
    parse_id = parse_ids[0] if parse_ids else fallback_parse_id

    if not post_ids:
        print(f"[WARN] Could not infer post_id from search results. Using fallback: {post_id}")
    if not parse_ids:
        print(f"[WARN] Could not infer parse_id from search results. Using fallback: {parse_id}")

    # Group B: requires ids
    pd_res = run_and_capture("post_detail", {"parse_ids": [parse_id]})
    cmt_res = run_and_capture("comments", {"post_id": post_id, "limit": 30})
    cg_res = run_and_capture("comments_graphql", {"post_id": post_id, "count": 30, "sort": "hot"})
    cgb_res = run_and_capture(
        "comments_graphql_batch",
        {"post_ids": [post_id], "count": 30, "sort": "hot"},
    )

    summary = {
        "keyword": keyword,
        "actions_tested": [
            "search",
            "posts",
            "search_graphql",
            "search_graphql_batch",
            "full_flow",
            "post_detail",
            "comments",
            "comments_graphql",
            "comments_graphql_batch",
        ],
        "used_post_id": post_id,
        "used_parse_id": parse_id,
        "statuses": {
            "search": search_res.get("status"),
            "posts": posts_res.get("status"),
            "search_graphql": sg_res.get("status"),
            "search_graphql_batch": sgb_res.get("status"),
            "full_flow": ff_res.get("status"),
            "post_detail": pd_res.get("status"),
            "comments": cmt_res.get("status"),
            "comments_graphql": cg_res.get("status"),
            "comments_graphql_batch": cgb_res.get("status"),
        },
    }
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    summary_path = OUT_DIR / "facebook_task_test_summary.json"
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[DONE] Summary -> {summary_path}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # noqa: BLE001
        print(f"[ERROR] {exc}", file=sys.stderr)
        raise