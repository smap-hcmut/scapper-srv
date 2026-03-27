#!/usr/bin/env bash
set -euo pipefail

# End-to-end dev helper:
# 1) Run API (with embedded worker) in MODE=dev using uv
# 2) Submit full_flow tasks via curl for tiktok/facebook/youtube
# 3) Poll results and save each output JSON to output/full_flow/

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUT_DIR="$ROOT_DIR/output/full_flow"
LOG_FILE="$OUT_DIR/dev_api.log"

API_HOST="${API_HOST:-127.0.0.1}"
API_PORT="${API_PORT:-8105}"
API_BASE="http://${API_HOST}:${API_PORT}"

TT_KEYWORD="${TT_KEYWORD:-vinfast vf8 review}"
FB_KEYWORD="${FB_KEYWORD:-iphone 16}"
YT_KEYWORD="${YT_KEYWORD:-iphone 16 review}"

TT_LIMIT="${TT_LIMIT:-3}"
FB_LIMIT="${FB_LIMIT:-3}"
YT_LIMIT="${YT_LIMIT:-3}"

TT_COMMENT_COUNT="${TT_COMMENT_COUNT:-200}"
FB_COMMENT_COUNT="${FB_COMMENT_COUNT:-50}"
YT_COMMENT_COUNT="${YT_COMMENT_COUNT:-100}"

mkdir -p "$OUT_DIR"

cleanup() {
  if [[ -n "${API_PID:-}" ]] && kill -0 "$API_PID" 2>/dev/null; then
    kill "$API_PID" 2>/dev/null || true
    wait "$API_PID" 2>/dev/null || true
  fi
}
trap cleanup EXIT

echo "[1/5] Starting API in dev mode..."
(
  cd "$ROOT_DIR"
  MODE=dev uv run python run_api.py >"$LOG_FILE" 2>&1
) &
API_PID=$!

echo "[2/5] Waiting for API health at ${API_BASE}/health ..."
for _ in $(seq 1 60); do
  if curl -fsS "${API_BASE}/health" >/dev/null 2>&1; then
    break
  fi
  sleep 1
done

if ! curl -fsS "${API_BASE}/health" >/dev/null 2>&1; then
  echo "API did not become healthy. Check log: $LOG_FILE" >&2
  exit 1
fi

submit_task() {
  local platform="$1"
  local body="$2"

  curl -fsS -X POST "${API_BASE}/api/v1/tasks/${platform}" \
    -H "Content-Type: application/json" \
    --data "$body"
}

extract_task_id() {
  uv run python -c 'import json,sys; print(json.load(sys.stdin)["task_id"])'
}

echo "[3/5] Submitting full_flow tasks via curl..."
TT_RESP="$(submit_task "tiktok" "{\"action\":\"full_flow\",\"params\":{\"keyword\":\"${TT_KEYWORD}\",\"limit\":${TT_LIMIT},\"threshold\":0.5,\"comment_count\":${TT_COMMENT_COUNT}}}")"
FB_RESP="$(submit_task "facebook" "{\"action\":\"full_flow\",\"params\":{\"keyword\":\"${FB_KEYWORD}\",\"limit\":${FB_LIMIT},\"comment_count\":${FB_COMMENT_COUNT},\"comment_sort\":\"hot\"}}")"
YT_RESP="$(submit_task "youtube" "{\"action\":\"full_flow\",\"params\":{\"keyword\":\"${YT_KEYWORD}\",\"limit\":${YT_LIMIT},\"comment_count\":${YT_COMMENT_COUNT}}}")"

TT_TASK_ID="$(printf '%s' "$TT_RESP" | extract_task_id)"
FB_TASK_ID="$(printf '%s' "$FB_RESP" | extract_task_id)"
YT_TASK_ID="$(printf '%s' "$YT_RESP" | extract_task_id)"

echo "  - tiktok task_id:   $TT_TASK_ID"
echo "  - facebook task_id: $FB_TASK_ID"
echo "  - youtube task_id:  $YT_TASK_ID"

poll_and_save() {
  local platform="$1"
  local task_id="$2"
  local out_file="$OUT_DIR/${platform}_full_flow_${task_id}.json"

  for _ in $(seq 1 180); do
    if curl -fsS "${API_BASE}/api/v1/tasks/${task_id}/result" -o "$out_file" 2>/dev/null; then
      local status
      status="$(uv run python -c 'import json,sys; print(json.load(open(sys.argv[1], encoding="utf-8")).get("status","unknown"))' "$out_file")"
      echo "  - saved: $out_file (status=${status})"
      return 0
    fi
    sleep 1
  done

  echo "Timed out waiting for result: ${platform} ${task_id}" >&2
  return 1
}

echo "[4/5] Polling task results and writing output files..."
poll_and_save "tiktok" "$TT_TASK_ID"
poll_and_save "facebook" "$FB_TASK_ID"
poll_and_save "youtube" "$YT_TASK_ID"

echo "[5/5] Done. Output files are in: $OUT_DIR"
echo "API log: $LOG_FILE"