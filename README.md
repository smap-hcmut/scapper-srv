# Scapper Worker Service

Async task worker xử lý các tác vụ crawl dữ liệu từ TikTok, Facebook và YouTube thông qua RabbitMQ.

## Setup

### Prerequisites

- Python 3.10+
- RabbitMQ server
- TinLikeSub SDK (`tinlikesub`)

### Install

```bash
cd scapper-srv

# Install SDK (file .whl được cung cấp riêng)
pip install tinlikesub-0.1.1-py3-none-any.whl

# Install dependencies
pip install -r requirements.txt

# Copy env
cp .env.example .env
```

### Configuration (.env)

```env
# RabbitMQ
RABBITMQ_URL=amqp://guest:guest@localhost:5672/

# TinLikeSub API
API_BASE_URL=https://api.tinlikesub.pro
API_KEY=your-api-key
API_SECRET_KEY=your-secret-key

# Worker
WORKER_PREFETCH_COUNT=1
OUTPUT_DIR=output
```

> **API_KEY** và **API_SECRET_KEY** sẽ được cung cấp riêng cho từng khách hàng.

### Run

```bash
# API + Worker
uvicorn app.main:app --host 0.0.0.0 --port 8105

# Worker only
python worker.py                     # Tất cả platforms
python worker.py tiktok              # Chỉ TikTok
python worker.py facebook youtube    # Chọn platforms
```

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/v1/tasks/{platform}` | Submit task |
| `GET` | `/api/v1/tasks/{task_id}/result` | Lấy kết quả |
| `GET` | `/api/v1/tasks?limit=20` | Danh sách tasks |
| `GET` | `/health` | Health check |

Chi tiết payload từng action xem [RABBITMQ.md](RABBITMQ.md).

## Output

Kết quả lưu tại `output/` với format: `{platform}_{action}_{task_id}_{timestamp}.json`

```json
{
  "task_id": "a1b2c3d4-...",
  "action": "search",
  "status": "success",
  "result": { ... },
  "error": null
}
```
