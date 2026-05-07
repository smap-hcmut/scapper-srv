# scapper-srv — Changelog (kể từ bản SDK 0.1.6)

Tóm tắt nhanh các thay đổi của scapper-srv kể từ bản dùng SDK **0.1.6** đến bản hiện tại (SDK **0.4.0**). Tài liệu này dành cho các service downstream đang publish job qua RabbitMQ.

> **TL;DR**: Tất cả action cũ vẫn hoạt động và **trả về cùng shape như trước**. Có thêm 1 action mới (`facebook.page_posts`). Một vài tham số TikTok mới được mở để hỗ trợ phân trang/region.

---

## 1. Tin vui đầu tiên: không có breaking change

Tất cả tên action cũ và shape response của chúng được **giữ nguyên**. Nếu service của bạn đang chạy ổn với scapper-srv bản 0.1.6, không cần đổi gì.

| Action | Shape response | Thay đổi |
|---|---|---|
| `facebook.search` | `list[dict]` | Không đổi |
| `facebook.posts` | `list[dict]` | Không đổi |
| `facebook.post_detail` | `dict` | Không đổi |
| `facebook.comments` | `list[dict]` | Không đổi |
| `facebook.comments_graphql` | envelope `dict` | Không đổi |
| `facebook.comments_graphql_batch` | `list[dict]` | Không đổi |
| `facebook.search_graphql` | envelope `dict` | Không đổi |
| `facebook.search_graphql_batch` | `list[dict]` | Không đổi |
| `facebook.full_flow` | `dict` | Không đổi |
| `tiktok.*` | (như cũ) | Không đổi |

---

## 2. Có gì MỚI

### 2.1. Facebook — action `page_posts`

Lấy danh sách bài viết trên timeline của 1 profile/page theo **numeric page_id**.

**Request params:**
```json
{
  "action": "page_posts",
  "page_id": "100066224874581",
  "count": 20,
  "cursor": null
}
```

- `page_id` (bắt buộc): id số của profile/page (không phải username/vanity URL).
- `count` (mặc định 10): số post muốn lấy mỗi job. Server có thể cap ~50–60/job, nếu xin nhiều hơn sẽ trả về kèm `has_next=true` để bạn gọi tiếp với `cursor`.
- `cursor` (tuỳ chọn): cursor lấy từ response trước để tiếp tục phân trang.
- `limit` được chấp nhận như alias cho `count` (backward-compat).

**Response shape (envelope):**
```json
{
  "page_id": "100066224874581",
  "post_count": 20,
  "has_next": true,
  "end_cursor": "...",
  "posts": [ ... ]
}
```

### 2.2. TikTok — `search` mở rộng tham số

Action `tiktok.search` vẫn hoạt động như cũ nếu chỉ truyền `keywords`. Có thêm các tham số tuỳ chọn:

| Param | Ý nghĩa |
|---|---|
| `cursor` | Phân trang (mặc định 0) |
| `count` | Số kết quả mỗi page (mặc định 20) |
| `search_id` | Pin search session qua nhiều page để dedup |
| `region` | Lọc theo region |
| `target` | Nếu set, kích hoạt **auto-paginate**: scapper sẽ tự lặp tới khi đủ `target` kết quả. Đi kèm `page_size` (mặc định 16). |

Service cũ chỉ truyền `keywords` không cần đổi gì — defaults giữ nguyên hành vi 0.1.6.

---

## 3. Có gì THAY ĐỔI bên trong (không ảnh hưởng caller)

Đây là phần internal, ghi lại để team biết khi debug:

- **Facebook search/comments** đã được migrate sang đường GraphQL (v2 jobs) ở phía SDK. Handler tự unwrap envelope để **trả về đúng `list[dict]` như trước** cho các action `search`, `posts`, `comments` → **caller không cần biết**.
- Vendored SDK wheel trong repo nâng từ `tinlikesub-0.1.6` lên `tinlikesub-0.4.0`. Dockerfile cài SDK trực tiếp từ source khi build, wheel chỉ phục vụ dev-install local.

---

## 4. Migration checklist cho service consumer

Nếu bạn đang dùng scapper-srv bản 0.1.6:

- [x] Không phải đổi action name nào.
- [x] Không phải đổi response parser nào.
- [ ] _(Tuỳ chọn)_ Nếu cần lấy posts từ timeline 1 profile/page → dùng action mới `facebook.page_posts`.
- [ ] _(Tuỳ chọn)_ Nếu cần phân trang/region/auto-paginate cho TikTok search → dùng các param mới của `tiktok.search`.

---

## 5. Tham chiếu

- Action handler Facebook: [app/handlers/facebook.py](app/handlers/facebook.py)
- Action handler TikTok: [app/handlers/tiktok.py](app/handlers/tiktok.py)
- Hợp đồng message RabbitMQ: [RABBITMQ.md](RABBITMQ.md)
