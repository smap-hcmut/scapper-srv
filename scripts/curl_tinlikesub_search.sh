#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage:
  scripts/curl_tinlikesub_search.sh --keyword "bia tiger" [--count 20] [--cursor 0]

Required env vars:
  API_KEY         TinLikeSub API key
  API_SECRET_KEY  TinLikeSub secret key

Optional env vars:
  API_BASE_URL    Default: https://api.tinlikesub.pro

Example:
  API_KEY=xxx API_SECRET_KEY=yyy scripts/curl_tinlikesub_search.sh --keyword "bia tiger"
EOF
}

KEYWORD=""
COUNT="20"
CURSOR="0"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --keyword)
      KEYWORD="${2:-}"
      shift 2
      ;;
    --count)
      COUNT="${2:-}"
      shift 2
      ;;
    --cursor)
      CURSOR="${2:-}"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      usage
      exit 1
      ;;
  esac
done

if [[ -z "$KEYWORD" ]]; then
  echo "Missing --keyword" >&2
  usage
  exit 1
fi

API_BASE_URL="${API_BASE_URL:-https://api.tinlikesub.pro}"
API_KEY="${API_KEY:-}"
API_SECRET_KEY="${API_SECRET_KEY:-}"

if [[ -z "$API_KEY" || -z "$API_SECRET_KEY" ]]; then
  echo "API_KEY and API_SECRET_KEY are required in environment." >&2
  exit 1
fi

PATH_API="/api/v1/tiktok/posts/search"
BODY=$(printf '{"keywords":["%s"],"cursor":%s,"count":%s}' "$KEYWORD" "$CURSOR" "$COUNT")
TS="$(date +%s)"

SIG="$(
  TS="$TS" PATH_API="$PATH_API" BODY="$BODY" API_SECRET_KEY="$API_SECRET_KEY" \
  uv run python - <<'PY'
import hashlib
import hmac
import os

ts = os.environ["TS"]
path_api = os.environ["PATH_API"]
body = os.environ["BODY"]
secret = os.environ["API_SECRET_KEY"]

body_hash = hashlib.sha256(body.encode("utf-8")).hexdigest()
msg = f"{ts}.POST.{path_api}.{body_hash}"
print(hmac.new(secret.encode("utf-8"), msg.encode("utf-8"), hashlib.sha256).hexdigest())
PY
)"

curl -sS -X POST "${API_BASE_URL}${PATH_API}" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: ${API_KEY}" \
  -H "X-Timestamp: ${TS}" \
  -H "X-Signature: ${SIG}" \
  --data "$BODY"

echo