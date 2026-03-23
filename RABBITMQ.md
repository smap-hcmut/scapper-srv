# RabbitMQ — Multi-Platform Tasks

Durable: Yes | Delivery: Persistent (`delivery_mode = 2`)

---

## Queues

| Queue | Platform | Actions |
|-------|----------|---------|
| `tiktok_tasks` | TikTok | `search`, `post_detail`, `comments`, `summary`, `comment_replies`, `cookie_check`, `full_flow` |
| `facebook_tasks` | Facebook | `search`, `posts`, `post_detail`, `comments`, `comments_graphql`, `comments_graphql_batch`, `search_graphql`, `search_graphql_batch`, `full_flow` |
| `youtube_tasks` | YouTube | `search`, `videos`, `video_detail`, `transcript`, `comments`, `full_flow` |

---

## Payload Format

```json
{
  "task_id": "string (uuid-v4)",
  "action": "string",
  "params": { ... },
  "created_at": "string (ISO-8601)"
}
```

| Field | Bắt buộc | Mô tả |
|-------|----------|-------|
| `task_id` | **Có** | UUID v4, dùng để track kết quả |
| `action` | **Có** | Tên action (xem bảng trên) |
| `params` | **Có** | Object tham số (có thể `{}`) |
| `created_at` | Không | ISO-8601 timestamp |

---

## tiktok_tasks

### `search`

| Param | Bắt buộc | Type | Default | Mô tả |
|-------|----------|------|---------|-------|
| `keywords` | **Có** | `string[]` | — | Danh sách từ khóa |

```json
{"task_id":"test-0001","action":"search","params":{"keywords":["review iphone","unbox"]},"created_at":"2026-03-04T00:00:00"}
```

### `post_detail`

| Param | Bắt buộc | Type | Default | Mô tả |
|-------|----------|------|---------|-------|
| `urls` | **Có** | `string[]` | — | Danh sách URL video TikTok (batch, max 5 parallel) |

> Backward compat: `"url": "..."` (single string) vẫn hoạt động.

```json
{"task_id":"test-0002","action":"post_detail","params":{"urls":["https://www.tiktok.com/@user/video/1234567890","https://www.tiktok.com/@user/video/9876543210"]},"created_at":"2026-03-04T00:00:00"}
```

### `comments`

Lấy danh sách comments của video (batch).

| Param | Bắt buộc | Type | Default | Mô tả |
|-------|----------|------|---------|-------|
| `video_urls` | **Có*** | `string[]` | — | Danh sách URL video TikTok |
| `aweme_ids` | **Có*** | `string[]` | — | Danh sách ID video. *Một trong hai bắt buộc, ưu tiên `video_urls`* |
| `cursor` | Không | `int` | `0` | Vị trí phân trang |
| `count` | Không | `int` | `50` | Số comment cần lấy per post |
| `threshold` | Không | `float` | `null` | Ngưỡng tự lấy replies |

> Backward compat: `"video_url": "..."` hoặc `"aweme_id": "..."` (single string) vẫn hoạt động.

```json
{"task_id":"test-0003","action":"comments","params":{"video_urls":["https://www.tiktok.com/@user/video/7612600015135034644"],"count":50,"threshold":0.5},"created_at":"2026-03-04T00:00:00"}
```

### `summary`

Lấy thông tin tóm tắt video (title, description, keywords) — batch.

| Param | Bắt buộc | Type | Default | Mô tả |
|-------|----------|------|---------|-------|
| `video_urls` | **Có*** | `string[]` | — | Danh sách URL video TikTok |
| `item_ids` | **Có*** | `string[]` | — | Danh sách ID video. *Một trong hai bắt buộc, ưu tiên `video_urls`* |

> Backward compat: `"video_url": "..."` hoặc `"item_id": "..."` (single string) vẫn hoạt động.

```json
{"task_id":"test-0010","action":"summary","params":{"video_urls":["https://www.tiktok.com/@user/video/7612600015135034644"]},"created_at":"2026-03-04T00:00:00"}
```

### `comment_replies`

Lấy replies của một comment.

| Param | Bắt buộc | Type | Default | Mô tả |
|-------|----------|------|---------|-------|
| `video_url` | **Có*** | `string` | — | URL video TikTok |
| `item_id` | **Có*** | `string` | — | ID video. *Một trong hai bắt buộc, ưu tiên `video_url`* |
| `comment_id` | **Có** | `string` | — | ID comment |
| `cursor` | Không | `int` | `0` | Vị trí phân trang |
| `count` | Không | `int` | `50` | Số replies cần lấy |

```json
{"task_id":"test-0011","action":"comment_replies","params":{"video_url":"https://www.tiktok.com/@user/video/7612600015135034644","comment_id":"7612345678901234567"},"created_at":"2026-03-04T00:00:00"}
```

### `cookie_check`

Kiểm tra trạng thái cookie.

| Param | Bắt buộc | Type | Default | Mô tả |
|-------|----------|------|---------|-------|
| _(không có)_ | — | — | — | `params` để `{}` |

```json
{"task_id":"test-0004","action":"cookie_check","params":{},"created_at":"2026-03-04T00:00:00"}
```

### `full_flow`

Tự động: tìm kiếm → lấy chi tiết → lấy comments cho mỗi kết quả.

| Param | Bắt buộc | Type | Default | Mô tả |
|-------|----------|------|---------|-------|
| `keyword` | Không | `string` | `""` | Từ khóa |
| `limit` | Không | `int` | `3` | Số post tối đa |
| `threshold` | Không | `float` | `0.5` | Ngưỡng tự lấy replies |
| `comment_count` | Không | `int` | `200` | Số comment mỗi post |

```json
{"task_id":"test-0005","action":"full_flow","params":{"keyword":"review iphone","limit":3,"threshold":0.5,"comment_count":200},"created_at":"2026-03-04T00:00:00"}
```

---

## facebook_tasks

### `search (not yet)`

| Param | Bắt buộc | Type | Default | Mô tả |
|-------|----------|------|---------|-------|
| `keyword` | Không | `string` | `""` | Từ khóa |
| `limit` | Không | `int` | `20` | Số kết quả tối đa |

```json
{"task_id":"test-0006","action":"search","params":{"keyword":"iphone 16","limit":10},"created_at":"2026-03-04T00:00:00"}
```

### `posts (not yet)`

| Param | Bắt buộc | Type | Default | Mô tả |
|-------|----------|------|---------|-------|
| `keyword` | Không | `string` | `""` | Từ khóa lọc |
| `page_size` | Không | `int` | `20` | Số bài mỗi trang |

```json
{"task_id":"test-0007","action":"posts","params":{"keyword":"samsung galaxy","page_size":20},"created_at":"2026-03-04T00:00:00"}
```

### `post_detail`

Lấy chi tiết bài viết (batch).

| Param | Bắt buộc | Type | Default | Mô tả |
|-------|----------|------|---------|-------|
| `parse_ids` | **Có** | `string[]` | — | Danh sách post parse_id |

> Backward compat: `"parse_id": "..."` (single string) vẫn hoạt động.

```json
{"task_id":"test-0012","action":"post_detail","params":{"parse_ids":["pfbid02ABC123","pfbid02XYZ456"]},"created_at":"2026-03-04T00:00:00"}
```

### `comments (not yet)`

Lấy comments của bài viết.

| Param | Bắt buộc | Type | Default | Mô tả |
|-------|----------|------|---------|-------|
| `post_id` | **Có** | `string` | — | Post ID |
| `limit` | Không | `int` | `100` | Số comment tối đa |

```json
{"task_id":"test-0013","action":"comments","params":{"post_id":"123456789012345","limit":100},"created_at":"2026-03-04T00:00:00"}
```

### `comments_graphql`

Lấy comments với sắp xếp hot/newest.

| Param | Bắt buộc | Type | Default | Mô tả |
|-------|----------|------|---------|-------|
| `post_id` | **Có** | `string` | — | Post ID |
| `cursor` | Không | `string` | `null` | Cursor phân trang (từ `end_cursor` response trước) |
| `count` | Không | `int` | `50` | Số comment cần lấy |
| `sort` | Không | `string` | `"hot"` | `"hot"` hoặc `"newest"` |

```json
{"task_id":"test-0014","action":"comments_graphql","params":{"post_id":"123456789012345","count":50,"sort":"newest"},"created_at":"2026-03-04T00:00:00"}
```

### `comments_graphql_batch`

Lấy comments cho nhiều bài viết cùng lúc.

| Param | Bắt buộc | Type | Default | Mô tả |
|-------|----------|------|---------|-------|
| `post_ids` | **Có** | `string[]` | — | Danh sách post IDs |
| `count` | Không | `int` | `50` | Số comment mỗi bài |
| `sort` | Không | `string` | `"hot"` | `"hot"` hoặc `"newest"` |

```json
{"task_id":"test-0015","action":"comments_graphql_batch","params":{"post_ids":["123456789012345","987654321098765"],"count":50,"sort":"hot"},"created_at":"2026-03-04T00:00:00"}
```

### `search_graphql`

Tìm kiếm bài viết Facebook.

| Param | Bắt buộc | Type | Default | Mô tả |
|-------|----------|------|---------|-------|
| `keyword` | **Có** | `string` | — | Từ khóa tìm kiếm |
| `cursor` | Không | `string` | `null` | Cursor phân trang (từ `end_cursor` response trước) |
| `count` | Không | `int` | `5` | Số bài viết cần lấy |

```json
{"task_id":"test-0020","action":"search_graphql","params":{"keyword":"thỏ ơi","count":10},"created_at":"2026-03-04T00:00:00"}
```

### `search_graphql_batch`

Tìm kiếm nhiều từ khóa song song.

| Param | Bắt buộc | Type | Default | Mô tả |
|-------|----------|------|---------|-------|
| `keywords` | **Có** | `string[]` | — | Danh sách từ khóa |
| `count` | Không | `int` | `5` | Số bài viết mỗi keyword |

```json
{"task_id":"test-0021","action":"search_graphql_batch","params":{"keywords":["thỏ ơi","trấn thành"],"count":5},"created_at":"2026-03-04T00:00:00"}
```

### `full_flow`

Tự động: tìm kiếm → lấy comments cho mỗi bài viết.

| Param | Bắt buộc | Type | Default | Mô tả |
|-------|----------|------|---------|-------|
| `keyword` | Không | `string` | `""` | Từ khóa |
| `limit` | Không | `int` | `5` | Số bài viết tối đa |
| `comment_count` | Không | `int` | `50` | Số comment mỗi bài |
| `comment_sort` | Không | `string` | `"hot"` | `"hot"` hoặc `"newest"` |

```json
{"task_id":"test-0022","action":"full_flow","params":{"keyword":"thỏ ơi","limit":5,"comment_count":50,"comment_sort":"hot"},"created_at":"2026-03-04T00:00:00"}
```

---

## youtube_tasks

### `search`

Tìm kiếm video YouTube.

| Param | Bắt buộc | Type | Default | Mô tả |
|-------|----------|------|---------|-------|
| `keywords` | **Có** | `string[]` | — | Danh sách từ khóa (parallel) |
| `limit` | Không | `int` | `20` | Số video tối đa mỗi keyword |
| `sort_by` | Không | `string` | `null` | `"relevance"`, `"date"`, `"views"`, `"rating"` |
| `upload_date` | Không | `string` | `null` | `"hour"`, `"today"`, `"week"`, `"month"`, `"year"` |
| `video_type` | Không | `string` | `null` | `"video"`, `"channel"`, `"playlist"` |
| `duration` | Không | `string` | `null` | `"short"` (<4p), `"medium"` (4-20p), `"long"` (>20p) |

```json
{"task_id":"test-0008","action":"search","params":{"keywords":["review iphone","unbox samsung"],"limit":20,"sort_by":"views"},"created_at":"2026-03-04T00:00:00"}
```

### `videos (not yet)`

| Param | Bắt buộc | Type | Default | Mô tả |
|-------|----------|------|---------|-------|
| `keyword` | Không | `string` | `""` | Từ khóa lọc |
| `page` | Không | `int` | `1` | Trang |
| `page_size` | Không | `int` | `20` | Số video mỗi trang |

```json
{"task_id":"test-0009","action":"videos","params":{"keyword":"samsung","page":1,"page_size":20},"created_at":"2026-03-04T00:00:00"}
```

### `video_detail`

Lấy chi tiết video.

| Param | Bắt buộc | Type | Default | Mô tả |
|-------|----------|------|---------|-------|
| `video_id` | **Có** | `string` | — | YouTube video ID |

```json
{"task_id":"test-0016","action":"video_detail","params":{"video_id":"dQw4w9WgXcQ"},"created_at":"2026-03-04T00:00:00"}
```

### `transcript`

Lấy transcript/phụ đề video.

| Param | Bắt buộc | Type | Default | Mô tả |
|-------|----------|------|---------|-------|
| `video_id` | **Có** | `string` | — | YouTube video ID |

```json
{"task_id":"test-0017","action":"transcript","params":{"video_id":"dQw4w9WgXcQ"},"created_at":"2026-03-04T00:00:00"}
```

### `comments`

Lấy comments của video.

| Param | Bắt buộc | Type | Default | Mô tả |
|-------|----------|------|---------|-------|
| `video_id` | **Có** | `string` | — | YouTube video ID |
| `limit` | Không | `int` | `100` | Số comment tối đa |

```json
{"task_id":"test-0018","action":"comments","params":{"video_id":"dQw4w9WgXcQ","limit":100},"created_at":"2026-03-04T00:00:00"}
```

### `full_flow`

Tự động: tìm kiếm → lấy chi tiết + comments cho mỗi video.

| Param | Bắt buộc | Type | Default | Mô tả |
|-------|----------|------|---------|-------|
| `keyword` | Không | `string` | `""` | Từ khóa |
| `limit` | Không | `int` | `5` | Số video tối đa |
| `comment_count` | Không | `int` | `100` | Số comment mỗi video |
| `sort_by` | Không | `string` | `null` | `"relevance"`, `"date"`, `"views"`, `"rating"` |
| `upload_date` | Không | `string` | `null` | `"hour"`, `"today"`, `"week"`, `"month"`, `"year"` |
| `video_type` | Không | `string` | `null` | `"video"`, `"channel"`, `"playlist"` |
| `duration` | Không | `string` | `null` | `"short"`, `"medium"`, `"long"` |

```json
{"task_id":"test-0019","action":"full_flow","params":{"keyword":"review iphone","limit":5,"comment_count":100,"sort_by":"views"},"created_at":"2026-03-04T00:00:00"}
```

---

## API Endpoints (port 8105)

### Gửi task

```
POST /api/v1/tasks/{platform}
```

Body:
```json
{ "action": "search", "params": { "keywords": ["review"] } }
```

Response:
```json
{
  "message": "Task submitted",
  "task_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "action": "search",
  "queue": "tiktok_tasks"
}
```

### Lấy kết quả

```
GET /api/v1/tasks/{task_id}/result
```

### Danh sách tasks

```
GET /api/v1/tasks?limit=20
```

---

## Output

Filename: `{queue}_{action}_{task_id[:8]}_{timestamp}.json`

Ví dụ: `tiktok_search_a1b2c3d4_20260304_150000.json`

```json
{
  "task_id": "a1b2c3d4-...",
  "queue": "tiktok_tasks",
  "action": "full_flow",
  "params": { ... },
  "created_at": "2026-03-04T00:00:00",
  "completed_at": "2026-03-04T00:01:30",
  "status": "success",
  "result": { ... },
  "error": null
}
```

`status`: `"success"` hoặc `"error"`. Khi lỗi: `"result": null`, `"error": "message"`.
