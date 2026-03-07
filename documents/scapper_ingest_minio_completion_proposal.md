# Scapper Proposal: Production Handoff To `ingest-srv`

**Status:** Companion scapper-side proposal  
**Date:** 2026-03-08  
**Audience:** worker runtime, platform handlers, operations

## 0. Canonical References

This document keeps scapper-side implementation notes and rollout expectations.

Canonical contract now lives in:

- RabbitMQ wire contract: `/mnt/f/SMAP_v2/scapper-srv/RABBITMQ.md`
- Shared runtime boundary, MinIO, idempotency: `/mnt/f/SMAP_v2/ingest-srv/documents/plan/scapper_ingest_shared_runtime_contract_proposal.md`

## 1. Goal

Define the production behavior after `scapper-srv` finishes a crawl task.

Chosen runtime contract:

- execute task from RabbitMQ
- serialize full raw result
- upload raw artifact to MinIO
- publish a small completion envelope to RabbitMQ queue `ingest_task_completions`
- let `ingest-srv` fetch raw from MinIO and handle `raw_batch`, parse, and UAP publishing

Current local `output/*.json` behavior remains useful for dev, but it is not the production source of truth.

## 2. Worker Lifecycle

For each consumed task:

1. receive task from queue
2. extract `task_id`, `action`, `params`, `created_at`
3. execute platform handler
4. serialize full result envelope
5. upload serialized raw to MinIO
6. compute `batch_id`, checksum, item_count
7. publish completion envelope to `ingest_task_completions`
8. optionally write local debug file if debug mode is enabled

Completion publish must happen only after MinIO upload succeeds.

## 3. Completion Envelope Expected By `ingest-srv`

Completion queue:

- queue: `ingest_task_completions`
- routing key: `ingest_task_completions`

```json
{
  "task_id": "uuid-v4",
  "queue": "tiktok_tasks|facebook_tasks|youtube_tasks",
  "platform": "tiktok|facebook|youtube",
  "action": "string",
  "status": "success|error",
  "completed_at": "2026-03-07T00:00:15Z",
  "storage_bucket": "ingest-raw",
  "storage_path": "crawl-raw/tiktok/post_detail/2026/03/07/uuid.json",
  "batch_id": "raw-tiktok-post_detail-uuid",
  "checksum": "sha256:...",
  "item_count": 2,
  "error": null,
  "metadata": {
    "crawler_version": "string",
    "duration_ms": 15234,
    "content_type": "application/json",
    "size_bytes": 1048576,
    "logical_run_id": "uuid-v4"
  }
}
```

If task execution fails:

- `status = error`
- `error` must be populated
- MinIO fields may be absent

## 4. MinIO Upload Contract

### 4.1 Object path

Recommended raw path:

`crawl-raw/{platform}/{action}/{yyyy}/{mm}/{dd}/{task_id}.json`

### 4.2 Metadata

Recommended object metadata:

- `task_id`
- `platform`
- `action`
- `queue`
- `batch_id`
- `checksum`
- `item_count`
- `completed_at`

### 4.3 Overwrite policy

- same `task_id` must not create multiple different objects
- retry should either:
  - overwrite the exact same object path safely, or
  - check object existence and skip re-upload if checksum matches
- production contract assumes object immutability once completion has been published

## 5. Retry and Stability

### 5.1 Task execution retry

Handled at message-processing layer according to worker policy. If task handler raises:

- no success completion is published
- error completion may be published if policy chooses to close the task explicitly

### 5.2 MinIO upload retry

`scapper-srv` should retry upload before giving up on a successful crawl result.

Recommended behavior:

- bounded retry with backoff
- preserve same `task_id`
- preserve same object path

### 5.3 Completion publish retry

If upload succeeded but completion publish failed:

- retry completion publish
- reuse the same `task_id`, `batch_id`, `storage_bucket`, `storage_path`
- do not generate a second raw artifact

## 6. Logging and Traceability

Every stage should log structured fields:

- `task_id`
- `queue`
- `platform`
- `action`
- `status`
- `duration_ms`
- `storage_bucket`
- `storage_path`
- `batch_id`
- `item_count`

Recommended log points:

- task received
- handler started
- handler finished
- raw serialized
- MinIO upload started
- MinIO upload succeeded
- completion publish started
- completion publish succeeded
- retry attempts
- terminal failure

## 7. Local Output Mode

### Dev/debug

`output/*.json` remains allowed for:

- local manual inspection
- debugging handler output
- quick regression checks

### Production

Production handoff must not depend on local files.

Authoritative production handoff is:

- MinIO raw object
- completion envelope message

`GET /api/v1/tasks/{task_id}/result` may remain as a debug convenience, not as the runtime contract for ingest.

## 8. `POST_URL` Production Behavior

`POST_URL` orchestration is owned by `ingest-srv`, not by the worker.

Expected model:

- one logical run may trigger:
  - one `post_detail` task
  - one `comments` task
- each task is completed independently
- each successful task uploads its own raw artifact
- each successful task publishes its own completion envelope

This keeps worker behavior simple and avoids building composite retry semantics into one action prematurely.

## 9. Review Scenarios

The proposal should be validated against:

1. successful keyword crawl -> raw upload -> completion publish
2. successful post-detail task with multiple URLs
3. successful comments task
4. duplicate completion retry with same `task_id`
5. upload succeeds, completion publish retried
6. task fails before upload
7. dev mode still writes `output/*.json`
8. production mode relies only on MinIO + completion envelope
