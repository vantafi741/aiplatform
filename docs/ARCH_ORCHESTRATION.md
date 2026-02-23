# Architecture: Single Source of Truth Orchestrator

## Muc tieu

He thong chi co **mot luong orchestration duy nhat** cho pipeline:

`drive -> summary -> generate -> approval -> publish -> metrics`

Core service:

- `app/services/orchestrator_service.py`
- API `POST /api/pipelines/drive_to_facebook/run` chi goi service nay.

## Why

- Loai bo duplicate logic giua router/service/worker.
- Giam nguy co publish trung (double-run).
- Giu mot noi duy nhat de quan sat log theo thu tu step.

## Luong chuan (mode=full)

1. **ingest**: ingest idempotent tu Google Drive vao `content_assets`.
2. **summarize**: tao/lay cache `asset_summaries` cho asset.
3. **generate**: tao `content_items` tu asset + summary context.
4. **approval**: auto-approve theo policy pipeline (SYSTEM flow).
5. **publish**: goi `facebook_publish_service.publish_post`.
6. **metrics**: fetch metrics va luu `post_metrics`.

## Luong scheduled (mode=scheduled)

- Dung cho scheduler tick/manual tick.
- Khong ingest/generate moi.
- Chi claim `content_items` da `approved + scheduled` va publish + fetch metrics.

## Compatibility wrappers

De tranh breaking change, cac entry-point cu duoc giu dang thin wrapper:

- `drive_to_facebook_pipeline_service.run_drive_to_facebook_for_tenant(...)`
- `scheduled_publish_worker.run_scheduled_publish(...)`
- `pipeline_drive_to_facebook.run_drive_to_facebook_pipeline(...)`

Tat ca deu forward ve `orchestrator_service.run_drive_to_facebook_pipeline(...)`.

## API Response (pipeline run)

`POST /api/pipelines/drive_to_facebook/run` tra ve:

- `ingested`
- `summarized`
- `generated`
- `approved`
- `published`
- `metrics_fetched`
- `errors`

Kem cac truong runtime:

- `processed`, `skipped`, `now_utc`, `ok`
