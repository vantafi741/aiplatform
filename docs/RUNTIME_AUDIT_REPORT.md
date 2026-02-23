# Runtime Audit Report (VPS)
mode=LOCAL

- Generated at: `2026-02-23T15:36:51+07:00`
- Repo root: `/mnt/d/ai-ecosystem`
- API base URL: `http://127.0.0.1:8000`

## 1) Git Branch + Last Commit
```text
branch=feature/lead-gdrive-assets
last_commit=8960a9a Replace pipeline stub with DB-first implementation
```

## 2) Docker Compose PS (Health)
```text
NAME                      IMAGE                COMMAND                  SERVICE    CREATED          STATUS                    PORTS
ai-content-director-api   ai-ecosystem-api     "uvicorn app.main:ap..."   api        17 minutes ago   Up 17 minutes (healthy)   0.0.0.0:8000->8000/tcp, [::]:8000->8000/tcp
ai-ecosystem-n8n          n8nio/n8n:latest     "tini -- /docker-ent..."   n8n        13 minutes ago   Up 13 minutes (healthy)   0.0.0.0:5679->5678/tcp, [::]:5679->5678/tcp
ai-ecosystem-postgres     postgres:16-alpine   "docker-entrypoint.s..."   postgres   18 minutes ago   Up 18 minutes (healthy)   127.0.0.1:5433->5432/tcp
ai-ecosystem-redis        redis:7-alpine       "docker-entrypoint.s..."   redis      17 minutes ago   Up 17 minutes (healthy)   127.0.0.1:6380->6379/tcp
```

## 3) API Logs (tail 200)
```text
ai-content-director-api  | INFO:     Started server process [1]
ai-content-director-api  | INFO:     Waiting for application startup.
ai-content-director-api  | 2026-02-23T08:19:22.054878Z [info     ] app_started                    version=0.1.0
ai-content-director-api  | 2026-02-23T08:19:22.054950Z [info     ] scheduler.disabled             enable_internal_scheduler=0 reason=Scheduler disabled (n8n control-plane)
ai-content-director-api  | INFO:     Application startup complete.
ai-content-director-api  | INFO:     Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)
ai-content-director-api  | INFO:     127.0.0.1:57628 - "GET /api/healthz HTTP/1.1" 200 OK
ai-content-director-api  | INFO:     127.0.0.1:55636 - "GET /api/healthz HTTP/1.1" 200 OK
ai-content-director-api  | INFO:     127.0.0.1:43348 - "GET /api/healthz HTTP/1.1" 200 OK
ai-content-director-api  | INFO:     127.0.0.1:46810 - "GET /api/healthz HTTP/1.1" 200 OK
ai-content-director-api  | INFO:     127.0.0.1:43502 - "GET /api/healthz HTTP/1.1" 200 OK
ai-content-director-api  | INFO:     127.0.0.1:60864 - "GET /api/healthz HTTP/1.1" 200 OK
ai-content-director-api  | INFO:     127.0.0.1:44316 - "GET /api/healthz HTTP/1.1" 200 OK
ai-content-director-api  | INFO:     127.0.0.1:50446 - "GET /api/healthz HTTP/1.1" 200 OK
ai-content-director-api  | INFO:     127.0.0.1:42028 - "GET /api/healthz HTTP/1.1" 200 OK
ai-content-director-api  | INFO:     127.0.0.1:54652 - "GET /api/healthz HTTP/1.1" 200 OK
ai-content-director-api  | INFO:     127.0.0.1:55402 - "GET /api/healthz HTTP/1.1" 200 OK
ai-content-director-api  | INFO:     127.0.0.1:51606 - "GET /api/healthz HTTP/1.1" 200 OK
ai-content-director-api  | INFO:     127.0.0.1:57226 - "GET /api/healthz HTTP/1.1" 200 OK
ai-content-director-api  | INFO:     127.0.0.1:37448 - "GET /api/healthz HTTP/1.1" 200 OK
ai-content-director-api  | INFO:     127.0.0.1:55052 - "GET /api/healthz HTTP/1.1" 200 OK
ai-content-director-api  | INFO:     127.0.0.1:33816 - "GET /api/healthz HTTP/1.1" 200 OK
ai-content-director-api  | INFO:     127.0.0.1:39610 - "GET /api/healthz HTTP/1.1" 200 OK
ai-content-director-api  | INFO:     127.0.0.1:41470 - "GET /api/healthz HTTP/1.1" 200 OK
ai-content-director-api  | INFO:     127.0.0.1:54752 - "GET /api/healthz HTTP/1.1" 200 OK
ai-content-director-api  | INFO:     127.0.0.1:47948 - "GET /api/healthz HTTP/1.1" 200 OK
ai-content-director-api  | INFO:     127.0.0.1:55934 - "GET /api/healthz HTTP/1.1" 200 OK
ai-content-director-api  | INFO:     127.0.0.1:59510 - "GET /api/healthz HTTP/1.1" 200 OK
ai-content-director-api  | INFO:     127.0.0.1:37696 - "GET /api/healthz HTTP/1.1" 200 OK
ai-content-director-api  | INFO:     127.0.0.1:46686 - "GET /api/healthz HTTP/1.1" 200 OK
ai-content-director-api  | INFO:     127.0.0.1:50022 - "GET /api/healthz HTTP/1.1" 200 OK
ai-content-director-api  | INFO:     127.0.0.1:54542 - "GET /api/healthz HTTP/1.1" 200 OK
ai-content-director-api  | INFO:     127.0.0.1:60456 - "GET /api/healthz HTTP/1.1" 200 OK
ai-content-director-api  | INFO:     127.0.0.1:48082 - "GET /api/healthz HTTP/1.1" 200 OK
ai-content-director-api  | INFO:     172.20.0.1:58468 - "GET /api/healthzcurl HTTP/1.1" 404 Not Found
ai-content-director-api  | INFO:     172.20.0.1:58468 - "GET /api/healthz HTTP/1.1" 200 OK
ai-content-director-api  | INFO:     127.0.0.1:53596 - "GET /api/healthz HTTP/1.1" 200 OK
ai-content-director-api  | INFO:     127.0.0.1:44416 - "GET /api/healthz HTTP/1.1" 200 OK
ai-content-director-api  | INFO:     127.0.0.1:50870 - "GET /api/healthz HTTP/1.1" 200 OK
ai-content-director-api  | INFO:     127.0.0.1:36322 - "GET /api/healthz HTTP/1.1" 200 OK
ai-content-director-api  | INFO:     127.0.0.1:34804 - "GET /api/healthz HTTP/1.1" 200 OK
ai-content-director-api  | INFO:     127.0.0.1:60434 - "GET /api/healthz HTTP/1.1" 200 OK
ai-content-director-api  | INFO:     127.0.0.1:52612 - "GET /api/healthz HTTP/1.1" 200 OK
ai-content-director-api  | INFO:     127.0.0.1:53372 - "GET /api/healthz HTTP/1.1" 200 OK
ai-content-director-api  | INFO:     127.0.0.1:41466 - "GET /api/healthz HTTP/1.1" 200 OK
ai-content-director-api  | INFO:     127.0.0.1:57982 - "GET /api/healthz HTTP/1.1" 200 OK
ai-content-director-api  | INFO:     127.0.0.1:48856 - "GET /api/healthz HTTP/1.1" 200 OK
ai-content-director-api  | INFO:     127.0.0.1:48316 - "GET /api/healthz HTTP/1.1" 200 OK
ai-content-director-api  | INFO:     127.0.0.1:34622 - "GET /api/healthz HTTP/1.1" 200 OK
ai-content-director-api  | INFO:     127.0.0.1:57944 - "GET /api/healthz HTTP/1.1" 200 OK
ai-content-director-api  | INFO:     127.0.0.1:38050 - "GET /api/healthz HTTP/1.1" 200 OK
ai-content-director-api  | INFO:     127.0.0.1:51354 - "GET /api/healthz HTTP/1.1" 200 OK
ai-content-director-api  | INFO:     127.0.0.1:35542 - "GET /api/healthz HTTP/1.1" 200 OK
ai-content-director-api  | INFO:     127.0.0.1:57274 - "GET /api/healthz HTTP/1.1" 200 OK
ai-content-director-api  | INFO:     127.0.0.1:40084 - "GET /api/healthz HTTP/1.1" 200 OK
ai-content-director-api  | INFO:     127.0.0.1:47918 - "GET /api/healthz HTTP/1.1" 200 OK
ai-content-director-api  | INFO:     127.0.0.1:54714 - "GET /api/healthz HTTP/1.1" 200 OK
ai-content-director-api  | INFO:     127.0.0.1:43984 - "GET /api/healthz HTTP/1.1" 200 OK
ai-content-director-api  | INFO:     127.0.0.1:51866 - "GET /api/healthz HTTP/1.1" 200 OK
ai-content-director-api  | INFO:     127.0.0.1:53784 - "GET /api/healthz HTTP/1.1" 200 OK
ai-content-director-api  | INFO:     127.0.0.1:58744 - "GET /api/healthz HTTP/1.1" 200 OK
ai-content-director-api  | INFO:     127.0.0.1:45712 - "GET /api/healthz HTTP/1.1" 200 OK
ai-content-director-api  | INFO:     127.0.0.1:40690 - "GET /api/healthz HTTP/1.1" 200 OK
ai-content-director-api  | INFO:     127.0.0.1:55830 - "GET /api/healthz HTTP/1.1" 200 OK
ai-content-director-api  | INFO:     127.0.0.1:35338 - "GET /api/healthz HTTP/1.1" 200 OK
ai-content-director-api  | INFO:     127.0.0.1:46144 - "GET /api/healthz HTTP/1.1" 200 OK
ai-content-director-api  | INFO:     127.0.0.1:59630 - "GET /api/healthz HTTP/1.1" 200 OK
ai-content-director-api  | INFO:     127.0.0.1:33942 - "GET /api/healthz HTTP/1.1" 200 OK
ai-content-director-api  | INFO:     127.0.0.1:56584 - "GET /api/healthz HTTP/1.1" 200 OK
ai-content-director-api  | INFO:     127.0.0.1:35322 - "GET /api/healthz HTTP/1.1" 200 OK
ai-content-director-api  | INFO:     127.0.0.1:34308 - "GET /api/healthz HTTP/1.1" 200 OK
ai-content-director-api  | INFO:     127.0.0.1:49414 - "GET /api/healthz HTTP/1.1" 200 OK
ai-content-director-api  | INFO:     127.0.0.1:45670 - "GET /api/healthz HTTP/1.1" 200 OK
ai-content-director-api  | INFO:     127.0.0.1:47360 - "GET /api/healthz HTTP/1.1" 200 OK
ai-content-director-api  | INFO:     172.20.0.1:40510 - "GET /api/healthz HTTP/1.1" 200 OK
ai-content-director-api  | INFO:     172.20.0.1:40516 - "GET /openapi.json HTTP/1.1" 200 OK
ai-content-director-api  | INFO:     127.0.0.1:34570 - "GET /api/healthz HTTP/1.1" 200 OK
ai-content-director-api  | INFO:     127.0.0.1:33880 - "GET /api/healthz HTTP/1.1" 200 OK
ai-content-director-api  | INFO:     127.0.0.1:37946 - "GET /api/healthz HTTP/1.1" 200 OK
ai-content-director-api  | INFO:     127.0.0.1:48482 - "GET /api/healthz HTTP/1.1" 200 OK
ai-content-director-api  | INFO:     127.0.0.1:45928 - "GET /api/healthz HTTP/1.1" 200 OK
ai-content-director-api  | INFO:     127.0.0.1:45108 - "GET /api/healthz HTTP/1.1" 200 OK
ai-content-director-api  | INFO:     127.0.0.1:34410 - "GET /api/healthz HTTP/1.1" 200 OK
ai-content-director-api  | INFO:     127.0.0.1:47648 - "GET /api/healthz HTTP/1.1" 200 OK
ai-content-director-api  | INFO:     127.0.0.1:47706 - "GET /api/healthz HTTP/1.1" 200 OK
ai-content-director-api  | INFO:     127.0.0.1:51564 - "GET /api/healthz HTTP/1.1" 200 OK
ai-content-director-api  | INFO:     127.0.0.1:46704 - "GET /api/healthz HTTP/1.1" 200 OK
ai-content-director-api  | INFO:     127.0.0.1:47750 - "GET /api/healthz HTTP/1.1" 200 OK
ai-content-director-api  | INFO:     127.0.0.1:36798 - "GET /api/healthz HTTP/1.1" 200 OK
ai-content-director-api  | INFO:     127.0.0.1:35130 - "GET /api/healthz HTTP/1.1" 200 OK
ai-content-director-api  | INFO:     127.0.0.1:49050 - "GET /api/healthz HTTP/1.1" 200 OK
ai-content-director-api  | INFO:     127.0.0.1:57248 - "GET /api/healthz HTTP/1.1" 200 OK
ai-content-director-api  | INFO:     127.0.0.1:60706 - "GET /api/healthz HTTP/1.1" 200 OK
ai-content-director-api  | INFO:     127.0.0.1:34466 - "GET /api/healthz HTTP/1.1" 200 OK
ai-content-director-api  | INFO:     127.0.0.1:44132 - "GET /api/healthz HTTP/1.1" 200 OK
ai-content-director-api  | INFO:     127.0.0.1:35082 - "GET /api/healthz HTTP/1.1" 200 OK
ai-content-director-api  | INFO:     127.0.0.1:49436 - "GET /api/healthz HTTP/1.1" 200 OK
ai-content-director-api  | INFO:     127.0.0.1:50716 - "GET /api/healthz HTTP/1.1" 200 OK
ai-content-director-api  | INFO:     127.0.0.1:35454 - "GET /api/healthz HTTP/1.1" 200 OK
ai-content-director-api  | INFO:     127.0.0.1:39718 - "GET /api/healthz HTTP/1.1" 200 OK
ai-content-director-api  | INFO:     127.0.0.1:55856 - "GET /api/healthz HTTP/1.1" 200 OK
ai-content-director-api  | INFO:     127.0.0.1:38086 - "GET /api/healthz HTTP/1.1" 200 OK
ai-content-director-api  | INFO:     127.0.0.1:44302 - "GET /api/healthz HTTP/1.1" 200 OK
ai-content-director-api  | INFO:     127.0.0.1:55068 - "GET /api/healthz HTTP/1.1" 200 OK
ai-content-director-api  | INFO:     127.0.0.1:59790 - "GET /api/healthz HTTP/1.1" 200 OK
ai-content-director-api  | INFO:     127.0.0.1:58066 - "GET /api/healthz HTTP/1.1" 200 OK
ai-content-director-api  | INFO:     127.0.0.1:35150 - "GET /api/healthz HTTP/1.1" 200 OK
ai-content-director-api  | INFO:     127.0.0.1:39710 - "GET /api/healthz HTTP/1.1" 200 OK
ai-content-director-api  | INFO:     127.0.0.1:44296 - "GET /api/healthz HTTP/1.1" 200 OK
ai-content-director-api  | INFO:     127.0.0.1:35180 - "GET /api/healthz HTTP/1.1" 200 OK
ai-content-director-api  | INFO:     127.0.0.1:53852 - "GET /api/healthz HTTP/1.1" 200 OK
ai-content-director-api  | INFO:     127.0.0.1:46000 - "GET /api/healthz HTTP/1.1" 200 OK
ai-content-director-api  | INFO:     127.0.0.1:46958 - "GET /api/healthz HTTP/1.1" 200 OK
ai-content-director-api  | INFO:     127.0.0.1:45018 - "GET /api/healthz HTTP/1.1" 200 OK
```

## 4) API Health Check
```text
http_code=200
{"status":"ok"}###END:HEALTHZ
```

## 5) OpenAPI Path Count
```text
http_code=200
paths_count=37
```

## 6) PostgreSQL Tables
```text
Did not find any relations.
```

## 7) PostgreSQL Row Counts (Top 15)
```text
tenants=n/a
brand_profiles=n/a
industry_profile=n/a
generated_plans=n/a
content_plans=n/a
content_items=n/a
revenue_content_items=n/a
content_assets=n/a
asset_summaries=n/a
publish_logs=n/a
approval_events=n/a
post_metrics=n/a
ai_usage_logs=n/a
lead_signals=n/a
kb_items=n/a
```

## 8) Alembic Current
```text
INFO  [alembic.runtime.migration] Context impl PostgresqlImpl.
INFO  [alembic.runtime.migration] Will assume transactional DDL.
```

## 9) Alembic History (Last 10)
```text
009 -> 010, 
008 -> 009, industry_profile (foundation schema)
007 -> 008, Audit logs, idempotency_keys, content_usage_logs (g...p t... ki...n tr...c c...)
006 -> 007, AI usage logs (cost guard: tokens + cost_usd per tenant)
005 -> 006, KB items table (FAQ / ng... c...nh cho content generator)
004 -> 005, Post metrics table (KPI)
003 -> 004, Scheduler columns on content_items
002 -> 003, Add error_message to publish_logs
001 -> 002, HITL approval workflow + audit log
<base> -> 001, initial
```

## 10) Important ENV Variables (Length Only)
> Security note: values are hidden, only lengths are shown.
```text
APP_ENV len=5
DATABASE_URL len=72
REDIS_URL len=20
OPENAI_API_KEY len=0
OPENAI_MODEL len=11
OPENAI_VISION_MODEL len=11
FACEBOOK_PAGE_ID len=0
FACEBOOK_ACCESS_TOKEN len=0
FB_PAGE_ACCESS_TOKEN len=0
GDRIVE_SA_JSON_PATH len=0
GDRIVE_READY_IMAGES_FOLDER_ID len=0
GDRIVE_READY_VIDEOS_FOLDER_ID len=0
GDRIVE_PROCESSED_FOLDER_ID len=0
GDRIVE_REJECTED_FOLDER_ID len=0
WEBHOOK_URL len=0
API_BASE_URL len=21
TENANT_ID len=0
ENABLE_INTERNAL_SCHEDULER len=1
DISABLE_SCHEDULER len=0
```

---
Audit checklist:
- [ ] Report generated/refreshed successfully.
- [ ] No secret values exposed in report.

## 11) Go-Live Verification Commands (Local Stage-1)

### docker compose ps
```text
NAME                      IMAGE                                                                     COMMAND                  SERVICE    CREATED          STATUS                    PORTS
ai-content-director-api   sha256:a457f0c30ac89edcce06dee139851c198d542e722a4febe5a5ffbb914cc52666   "uvicorn app.main:ap…"   api        33 minutes ago   Up 33 minutes (healthy)   0.0.0.0:8000->8000/tcp, [::]:8000->8000/tcp
ai-ecosystem-n8n          n8nio/n8n:latest                                                          "tini -- /docker-ent…"   n8n        29 minutes ago   Up 29 minutes (healthy)   0.0.0.0:5679->5678/tcp, [::]:5679->5678/tcp
ai-ecosystem-postgres     postgres:16-alpine                                                        "docker-entrypoint.s…"   postgres   34 minutes ago   Up 34 minutes (healthy)   127.0.0.1:5433->5432/tcp
ai-ecosystem-redis        redis:7-alpine                                                            "docker-entrypoint.s…"   redis      33 minutes ago   Up 33 minutes (healthy)   127.0.0.1:6380->6379/tcp
```

### docker compose run --rm api alembic heads
```text
07a13d6fc732 (head)
```

### docker compose run --rm api alembic current
```text
INFO  [alembic.runtime.migration] Context impl PostgresqlImpl.
INFO  [alembic.runtime.migration] Will assume transactional DDL.
07a13d6fc732 (head) (mergepoint)
```
