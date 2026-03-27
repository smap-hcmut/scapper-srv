# TikTok Subtitle Download

Case da test thanh cong:

- Nguon input: `tiktok_post_detail_3bbd2171_20260323_192558.json`
- Field tai duoc: `result[0].subtitle_url`
- Field `result[0].downloads.subtitle` hien tai tra `401 Unauthorized`

## Cach tai subtitle ra file

Chay lenh sau tu root repo `SMAP`:

```bash
subtitle_url=$(jq -r '.result[0].subtitle_url // empty' \
  scapper-srv/output/tiktok_post_detail_3bbd2171_20260323_192558.json)

dest="scapper-srv/output/tiktok_subtitle_direct_$(date +%Y%m%d_%H%M%S).vtt"

curl -L --fail --silent --show-error \
  -o "$dest" \
  "$subtitle_url"

echo "saved to: $dest"
```

## Kiem tra file vua tai

```bash
file "$dest"
sed -n '1,20p' "$dest"
```

Ky vong:

- `file` bao `UTF-8 text`
- Noi dung dau file bat dau bang `WEBVTT`

## Lenh da test thanh cong

```bash
direct_url=$(jq -r '.result[0].subtitle_url // empty' \
  /Users/phongdang/Documents/GitHub/SMAP/scapper-srv/output/tiktok_post_detail_3bbd2171_20260323_192558.json)

dest="/Users/phongdang/Documents/GitHub/SMAP/scapper-srv/output/tiktok_subtitle_direct_$(date +%Y%m%d_%H%M%S)"
headers="$dest.headers"

curl -L --fail --silent --show-error \
  --dump-header "$headers" \
  -o "$dest" \
  "$direct_url"

file "$dest"
xxd -l 64 "$dest"
sed -n '1,20p' "$dest"
```

Ghi chu:

- HTTP header co the bao `content-type: video/mp4`
- Nhung payload thuc te van la subtitle text dang `WEBVTT`
