# RabbitMQ - `scapper-srv <-> ingest-srv` Runtime Contract

**Status:** Canonical  
**Ngày cập nhật:** 2026-03-08  
**Scope:** RabbitMQ queue names, request envelope, completion envelope, delivery semantics  
**Companion shared-runtime doc:** `/mnt/f/SMAP_v2/ingest-srv/documents/plan/scapper_ingest_shared_runtime_contract_proposal.md`  
**Historical companion docs:**  
- `/mnt/f/SMAP_v2/ingest-srv/documents/plan/ingest_scapper_minio_completion_uap_proposal.md`
- `/mnt/f/SMAP_v2/scapper-srv/documents/scapper_ingest_minio_completion_proposal.md`

Durable: Yes | Delivery: Persistent (`delivery_mode = 2`) | Content-Type: `application/json`

---

## 1. Document Boundary

File này là source of truth cho RabbitMQ wire contract giữa `ingest-srv` và `scapper-srv`:

- tên queue và hướng publish/consume
- request envelope `ingest-srv -> scapper-srv`
- completion envelope `scapper-srv -> ingest-srv`
- payload shape của từng action crawler

File này **không** sở hữu:

- MinIO lifecycle chi tiết, replay policy, lineage policy mức nghiệp vụ
- scheduler/runtime support flags của ingest
- parser/UAP publish pipeline

Các phần đó thuộc companion doc:

- `/mnt/f/SMAP_v2/ingest-srv/documents/plan/scapper_ingest_shared_runtime_contract_proposal.md`

`output/*.json` và API `GET /api/v1/tasks/{task_id}/result` vẫn được giữ cho debug/local workflow, nhưng **không** còn là production handoff contract.

---

## 2. Queue Topology

| Queue | Producer | Consumer | Mục đích |
|-------|----------|----------|----------|
| `tiktok_tasks` | `ingest-srv` | `scapper-srv` | Request queue cho TikTok crawl actions |
| `facebook_tasks` | `ingest-srv` | `scapper-srv` | Request queue cho Facebook crawl actions |
| `youtube_tasks` | `ingest-srv` | `scapper-srv` | Request queue cho YouTube crawl actions |
| `ingest_task_completions` | `scapper-srv` | `ingest-srv` | Completion queue trả kết quả crawl sau khi raw đã được upload lên MinIO |

### Publish semantics

- publish qua default exchange
- `routing_key = queue name`
- queue phải durable
- message phải persistent
- producer/consumer phải coi `task_id` là idempotency key chính

---

## 3. Request Envelope: `ingest-srv -> scapper-srv`

### Shape

```json
{
  "task_id": "string (uuid-v4)",
  "action": "string",
  "params": {},
  "created_at": "string (ISO-8601)"
}
```

| Field | Bắt buộc | Mô tả |
|-------|----------|-------|
| `task_id` | **Có** | UUID v4 do `ingest-srv` generate; correlation key xuyên suốt request/completion |
| `action` | **Có** | Tên action crawler tương ứng queue/platform |
| `params` | **Có** | Object tham số theo action contract bên dưới |
| `created_at` | Không | ISO-8601 timestamp tại thời điểm publish |

### Rules

- một lần publish logic dùng đúng một `task_id`
- `scapper-srv` không được tự generate lại `task_id`
- `params` phải khớp action contract của queue tương ứng
- lineage như `source_id`, `project_id`, `target_id`, `scheduled_job_id` là source of truth ở `ingest-srv`, không bắt buộc đi trực tiếp trong request envelope chuẩn

---

## 4. Completion Envelope: `scapper-srv -> ingest-srv`

`scapper-srv` phải publish completion message vào queue `ingest_task_completions` **chỉ sau khi** raw artifact đã upload thành công lên MinIO.

### Shape

```json
{
  "task_id": "uuid-v4",
  "queue": "tiktok_tasks|facebook_tasks|youtube_tasks",
  "platform": "tiktok|facebook|youtube",
  "action": "string",
  "status": "success|error",
  "completed_at": "2026-03-08T00:00:15Z",
  "storage_bucket": "ingest-raw",
  "storage_path": "crawl-raw/tiktok/full_flow/2026/03/08/uuid.json",
  "batch_id": "raw-tiktok-full_flow-uuid",
  "checksum": "sha256:...",
  "item_count": 2,
  "error": null,
  "metadata": {
    "crawler_version": "string",
    "duration_ms": 15234,
    "content_type": "application/json",
    "size_bytes": 1048576,
    "logical_run_id": "uuid-v4",
    "source_id": "optional echo",
    "target_id": "optional echo",
    "scheduled_job_id": "optional echo",
    "external_task_id": "optional echo"
  }
}
```

### Rules

- completion message **không** mang `result` raw đầy đủ; raw authoritative payload nằm ở MinIO
- `task_id` là correlation key duy nhất ingest dùng để lookup `external_tasks.task_id`
- `status=success` bắt buộc có:
  - `storage_bucket`
  - `storage_path`
  - `batch_id`
- `status=error`:
  - phải có `error`
  - có thể omit MinIO fields nếu chưa upload raw
- duplicate completion cùng `task_id` phải được coi là duplicate delivery
- retry completion publish phải reuse cùng:
  - `task_id`
  - `storage_bucket`
  - `storage_path`
  - `batch_id`

### Recommended conventions

- completion queue publish:
  - queue: `ingest_task_completions`
  - routing key: `ingest_task_completions`
- `batch_id` format khuyến nghị:
  - `raw-{platform}-{action}-{task_id}`
- `storage_path` format khuyến nghị:
  - `crawl-raw/{platform}/{action}/{yyyy}/{mm}/{dd}/{task_id}.json`

---

## 5. Action Label Notes

Các label như `(not yet)` trong tài liệu bên dưới được giữ lại để bảo toàn giá trị lịch sử của doc cũ.

Diễn giải chuẩn:

- payload shape vẫn là contract đã chốt ở mức tài liệu
- nhưng ingest scheduler/runtime **không được** tự suy ra action đó đã bật production rollout
- rollout thực tế phải đi qua runtime support flag hoặc quyết định enable riêng ở `ingest-srv`

Nói ngắn gọn:

- doc này chốt **shape**
- ingest runtime chốt **enablement**

---

## 6. Queues And Action Payloads

### 6.1 `tiktok_tasks`

#### `search`

| Param | Bắt buộc | Type | Default | Mô tả |
|-------|----------|------|---------|-------|
| `keywords` | **Có** | `string[]` | — | Danh sách từ khóa |

```json
{"task_id":"test-0001","action":"search","params":{"keywords":["review iphone","unbox"]},"created_at":"2026-03-04T00:00:00"}
```

#### `post_detail`

| Param | Bắt buộc | Type | Default | Mô tả |
|-------|----------|------|---------|-------|
| `urls` | **Có** | `string[]` | — | Danh sách URL video TikTok (batch, max 5 parallel) |

> Backward compat: `"url": "..."` (single string) vẫn hoạt động.

```json
{"task_id":"test-0002","action":"post_detail","params":{"urls":["https://www.tiktok.com/@user/video/1234567890","https://www.tiktok.com/@user/video/9876543210"]},"created_at":"2026-03-04T00:00:00"}
```

#### `comments`

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

#### `summary`

Lấy thông tin tóm tắt video (title, description, keywords) - batch.

| Param | Bắt buộc | Type | Default | Mô tả |
|-------|----------|------|---------|-------|
| `video_urls` | **Có*** | `string[]` | — | Danh sách URL video TikTok |
| `item_ids` | **Có*** | `string[]` | — | Danh sách ID video. *Một trong hai bắt buộc, ưu tiên `video_urls`* |

> Backward compat: `"video_url": "..."` hoặc `"item_id": "..."` (single string) vẫn hoạt động.

```json
{"task_id":"test-0010","action":"summary","params":{"video_urls":["https://www.tiktok.com/@user/video/7612600015135034644"]},"created_at":"2026-03-04T00:00:00"}
```

#### `comment_replies`

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

#### `cookie_check`

Kiểm tra trạng thái cookie.

| Param | Bắt buộc | Type | Default | Mô tả |
|-------|----------|------|---------|-------|
| _(không có)_ | — | — | — | `params` để `{}` |

```json
{"task_id":"test-0004","action":"cookie_check","params":{},"created_at":"2026-03-04T00:00:00"}
```

#### `full_flow`

Tự động: tìm kiếm -> lấy chi tiết -> lấy comments cho mỗi kết quả.

> Canonical ingest integration: grouped TikTok keyword targets may be fanned out by `ingest-srv` thành nhiều `full_flow` tasks, mỗi task mang đúng một `params.keyword`.

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

### 6.2 `facebook_tasks`

#### `search (not yet)`

| Param | Bắt buộc | Type | Default | Mô tả |
|-------|----------|------|---------|-------|
| `keyword` | Không | `string` | `""` | Từ khóa |
| `limit` | Không | `int` | `20` | Số kết quả tối đa |

```json
{"task_id":"test-0006","action":"search","params":{"keyword":"iphone 16","limit":10},"created_at":"2026-03-04T00:00:00"}
```

#### `posts (not yet)`

| Param | Bắt buộc | Type | Default | Mô tả |
|-------|----------|------|---------|-------|
| `keyword` | Không | `string` | `""` | Từ khóa lọc |
| `page_size` | Không | `int` | `20` | Số bài mỗi trang |

```json
{"task_id":"test-0007","action":"posts","params":{"keyword":"samsung galaxy","page_size":20},"created_at":"2026-03-04T00:00:00"}
```

#### `post_detail`

Lấy chi tiết bài viết (batch).

| Param | Bắt buộc | Type | Default | Mô tả |
|-------|----------|------|---------|-------|
| `parse_ids` | **Có** | `string[]` | — | Danh sách post parse_id |

> Backward compat: `"parse_id": "..."` (single string) vẫn hoạt động.

```json
{"task_id":"test-0012","action":"post_detail","params":{"parse_ids":["pfbid02ABC123","pfbid02XYZ456"]},"created_at":"2026-03-04T00:00:00"}
```

#### `comments (not yet)`

Lấy comments của bài viết.

| Param | Bắt buộc | Type | Default | Mô tả |
|-------|----------|------|---------|-------|
| `post_id` | **Có** | `string` | — | Post ID |
| `limit` | Không | `int` | `100` | Số comment tối đa |

```json
{"task_id":"test-0013","action":"comments","params":{"post_id":"123456789012345","limit":100},"created_at":"2026-03-04T00:00:00"}
```

#### `comments_graphql`

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

#### `comments_graphql_batch`

Lấy comments cho nhiều bài viết cùng lúc.

| Param | Bắt buộc | Type | Default | Mô tả |
|-------|----------|------|---------|-------|
| `post_ids` | **Có** | `string[]` | — | Danh sách post IDs |
| `count` | Không | `int` | `50` | Số comment mỗi bài |
| `sort` | Không | `string` | `"hot"` | `"hot"` hoặc `"newest"` |

```json
{"task_id":"test-0015","action":"comments_graphql_batch","params":{"post_ids":["123456789012345","987654321098765"],"count":50,"sort":"hot"},"created_at":"2026-03-04T00:00:00"}
```

---

### 6.3 `youtube_tasks`

#### `search (not yet)`

| Param | Bắt buộc | Type | Default | Mô tả |
|-------|----------|------|---------|-------|
| `keyword` | Không | `string` | `""` | Từ khóa |
| `limit` | Không | `int` | `20` | Số kết quả tối đa |

```json
{"task_id":"test-0008","action":"search","params":{"keyword":"review iphone","limit":10},"created_at":"2026-03-04T00:00:00"}
```

#### `videos (not yet)`

| Param | Bắt buộc | Type | Default | Mô tả |
|-------|----------|------|---------|-------|
| `keyword` | Không | `string` | `""` | Từ khóa lọc |
| `page` | Không | `int` | `1` | Trang |
| `page_size` | Không | `int` | `20` | Số video mỗi trang |

```json
{"task_id":"test-0009","action":"videos","params":{"keyword":"samsung","page":1,"page_size":20},"created_at":"2026-03-04T00:00:00"}
```

#### `video_detail`

Lấy chi tiết video.

| Param | Bắt buộc | Type | Default | Mô tả |
|-------|----------|------|---------|-------|
| `video_id` | **Có** | `string` | — | YouTube video ID |

```json
{"task_id":"test-0016","action":"video_detail","params":{"video_id":"dQw4w9WgXcQ"},"created_at":"2026-03-04T00:00:00"}
```

#### `transcript`

Lấy transcript/phụ đề video.

| Param | Bắt buộc | Type | Default | Mô tả |
|-------|----------|------|---------|-------|
| `video_id` | **Có** | `string` | — | YouTube video ID |

```json
{"task_id":"test-0017","action":"transcript","params":{"video_id":"dQw4w9WgXcQ"},"created_at":"2026-03-04T00:00:00"}
```

#### `comments (not yet)`

Lấy comments của video.

| Param | Bắt buộc | Type | Default | Mô tả |
|-------|----------|------|---------|-------|
| `video_id` | **Có** | `string` | — | YouTube video ID |

```json
{"task_id":"test-0018","action":"comments","params":{"video_id":"dQw4w9WgXcQ"},"created_at":"2026-03-04T00:00:00"}
```

---

## 7. API Endpoints (port 8105)

Phần này được giữ cho local/dev workflow của `scapper-srv`.

### Gửi task

```
POST /api/v1/tasks/{platform}
```

Body:

```json
{ "action": "full_flow", "params": { "keyword": "review" } }
```

Response:

```json
{
  "message": "Task submitted",
  "task_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "action": "full_flow",
  "queue": "tiktok_tasks"
}
```

### Lấy kết quả debug

```
GET /api/v1/tasks/{task_id}/result
```

### Danh sách tasks debug

```
GET /api/v1/tasks?limit=20
```

---

## 8. Local Debug Output

Filename: `{queue}_{action}_{task_id[:8]}_{timestamp}.json`

Ví dụ: `tiktok_full_flow_a1b2c3d4_20260304_150000.json`

```json
{
  "task_id": "a1b2c3d4-...",
  "queue": "tiktok_tasks",
  "action": "full_flow",
  "params": {},
  "created_at": "2026-03-04T00:00:00",
  "completed_at": "2026-03-04T00:01:30",
  "status": "success",
  "result": {},
  "error": null
}
```

`status`: `"success"` hoặc `"error"`.

Ghi chú:

- đây là local debug artifact
- không phải completion contract cho `ingest-srv`
- production handoff authoritative là:
  - MinIO raw artifact
  - RabbitMQ completion message ở `ingest_task_completions`

---

## 9. Reliability Notes

- idempotency key chính: `task_id`
- duplicate completion cùng `task_id` phải safe cho ingest consumer
- raw payload production phải nằm ở MinIO, không đính kèm trực tiếp trong completion message
- completion publish phải xảy ra sau khi upload raw thành công
- DLQ/parking flow là concern của runtime implementation, không đổi wire contract đã chốt ở file này
