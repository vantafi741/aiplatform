# BÁO CÁO TRẠNG THÁI DỰ ÁN – AI MARKETING / SALES / CONTENT ECOSYSTEM PLATFORM

**Ngày audit:** 2026-02-20  
**Repo local:** Cursor workspace `d:\ai-ecosystem`  
**Mục đích:** Snapshot “đã làm gì / cần làm gì” để gửi GPT hoặc team (chỉ audit, không chỉnh logic).

---

## PHẦN A — THU THẬP THÔNG TIN

### 1) Repo & Git status

**Lệnh đã chạy (PowerShell, từ `d:\ai-ecosystem`):**

| Lệnh | Output / Evidence |
|------|-------------------|
| `Get-Location` | `Path: D:\ai-ecosystem` |
| `git rev-parse --show-toplevel` | `D:/ai-ecosystem` |
| `git branch --show-current` | `master` |
| `git status` | Branch **master**; **Changes not staged:** 22 files modified trong `ai_content_director/` (config, routers, services, models, schemas, README, .env.example, requirements.txt). **Untracked:** migrations `012_lead_signals.py`, `013_content_assets_and_require_media.py`; models `content_asset.py`, `lead_signal.py`; routers `facebook_webhook_router.py`, `gdrive_assets_router.py`, `leads_router.py`; schemas `gdrive_assets.py`, `leads.py`; services `gdrive_dropzone.py`, `lead_classify_service.py`, `lead_service.py`, `n8n_webhook_service.py`; `app/utils/`; `pytest.ini`, `requirements-dev.txt`; tests `conftest.py`, `test_ai_query_param.py`, `test_lead_signals_smoke.py`, `test_plan_materialize.py`; `docs/LEAD_SIGNALS_RUNBOOK.md`. |
| `git log -20 --oneline --decorate` | `eca723a (HEAD -> master, origin/main) feat(revenue-mv2): content generator + migration 011` → `719781a` → `6c1fc5e` → `2da9be6` → `57cb409` → `9fb5bd9` (feat/chore meta env, .env.example, ENV_KEYS_REPORT) |
| `git remote -v` | `origin  https://github.com/vantafi741/aiplatform.git (fetch/push)` |
| `git diff --stat` | 22 files changed, 605 insertions(+), 93 deletions(-) |

**Git diff (trích 200 dòng đầu):**  
- `.env.example`: thêm GDRIVE_*, LOCAL_MEDIA_DIR, ASSET_*, WEBHOOK_URL, LEAD_CLASSIFY_*, N8N_WEBHOOK_*.  
- `README.md`: thêm AI Lead System (POST /webhooks/facebook, GET /api/leads), Google Drive Dropzone + media-required publish.  
- `app/config.py`: thêm Settings cho GDRIVE_*, webhook_n8n_url, lead_classify_*, n8n_webhook_timeout.  
- `app/main.py`: include `gdrive_assets_router`, `facebook_webhook_router`, `leads_router`.  
- `app/models/__init__.py`: export `LeadSignal`, `ContentAsset`.  
- Các file còn lại: cập nhật content_item, publish_log, tenant; routers content/planner/publish/revenue_mv1; schemas; services (facebook_publish, plan_service_mv1, planner, content, scheduler).

---

### 2) Cấu trúc project (file quan trọng)

**Cây file (maxdepth ~3, bỏ .git / venv / __pycache__):**

- **Root:** `.env`, `.env.example`, `.gitignore`, `docker-compose.yml`, `docker-compose.prod.yml`, `README.md`, `README_META_RUNBOOK.md`, `README_ROOT.md`, `README_RUNBOOK.md`, `ENV_KEYS_REPORT.md`, `requirements.txt`
- **ai_content_director/**  
  - `alembic.ini`, `alembic/env.py`, `alembic/script.py.mako`, `alembic/versions/` (001→013)  
  - `app/main.py`, `app/config.py`, `app/db.py`, `app/logging_config.py`  
  - `app/routers/`: api_health, health, onboarding, planner, content, publish, audit, scheduler, kpi, kb, revenue_mv1, revenue_mv2, gdrive_assets, facebook_webhook, leads  
  - `app/models/`: tenant, brand_profile, content_plan, content_item, content_asset, publish_log, approval_event, post_metrics, kb_item, ai_usage_log, generated_plan, industry_profile, revenue_content_item, lead_signal  
  - `app/schemas/`, `app/services/`, `app/middleware/`, `app/infrastructure/`, `app/utils/`  
  - `Dockerfile`, `docker-compose.yml`, `README.md`, `requirements.txt`, `requirements-dev.txt`, `pytest.ini`  
  - `tests/`: conftest.py, test_ai_query_param.py, test_lead_signals_smoke.py, test_plan_materialize.py, test_revenue_mv1_schema.py, test_revenue_mv2_schema.py  
- **docs/**: AUDIT_MVP_AI_MARKETING_PLATFORM.md, CONSOLIDATION_CORE_ARCH_V1.md, FOUNDATION_STACK_CHANGELIST.md, FULL_AUDIT_AI_MARKETING_PLATFORM.md, LEAD_SIGNALS_RUNBOOK.md, META_SETUP.md, MVP_E2E_STEPS.md, README.md, SPRINT1_VERIFICATION.md, SPRINT2_DELIVERABLES.md, SPRINT4_DELIVERABLES.md, prompt_playbook_v1.json  
- **scripts/**: meta_env_doctor.py, meta_verify.py, meta_post_test.py, meta_env_reset_hint.py, _meta_common.py, smoke*.ps1, smoke.sh, run_mvp_local.ps1, run_mvp_local.sh, run_full_evaluation.ps1, run_ai_quality_evaluation_batch.py, push_revenue_mv2_to_github.ps1, RUNBOOK_AI_QUALITY_BATCH.md, README.md  
- **backend/**, **frontend/**, **add/** (có trong ls gốc; chi tiết có thể list thêm nếu cần)

**Ghi chú:** FastAPI app nằm tại `ai_content_director/app/main.py`. Không có `app/main.py` ở root.

---

### 3) Kiểm tra endpoints FastAPI

**Cách kiểm tra:** Import `app` từ `ai_content_director.app.main` cần `DATABASE_URL` (engine khởi tạo lúc import). Trong môi trường audit không set DATABASE_URL nên không chạy được script import app. **Danh sách route** lấy từ code (routers + prefix):

**Entrypoint:** `ai_content_director/app/main.py` → `app = FastAPI(...)`.

**ROUTES (theo thứ tự include):**

| Route | Method | Ghi chú MVP |
|-------|--------|-------------|
| `/` | GET | App name + version |
| `/api/healthz` | GET | **MVP** Liveness |
| `/api/readyz` | GET | **MVP** Readiness (DB + Redis) |
| `/health` | GET | Healthcheck đơn giản |
| `/onboarding` | POST | **MVP** Tạo tenant + brand profile (legacy) |
| `/planner/generate` | POST | **MVP** Kế hoạch 30 ngày (query: force, ai) |
| `/content/generate-samples` | POST | **MVP** Tạo sample content (draft) |
| `/content/list` | GET | List content |
| `/content/{content_id}/approve` | POST | **MVP** Approval workflow |
| `/content/{content_id}/reject` | POST | **MVP** Reject |
| `/content/{content_id}/schedule` | POST | Schedule |
| `/content/{content_id}/unschedule` | POST | Unschedule |
| `/publish/facebook` | POST | **MVP** Đăng Facebook (media_required, use_latest_asset) |
| `/publish/logs` | GET | **MVP** Publish logs |
| `/audit/events` | GET | Audit events |
| `/scheduler/status` | GET | Scheduler |
| `/kpi/summary` | GET | **MVP** KPI tối thiểu |
| `/kpi/fetch-now` | POST | Fetch KPI |
| `/kb/items` | POST/GET | KB items |
| `/kb/items/bulk` | POST | KB bulk |
| `/kb/query` | POST | KB query |
| `/api/tenants` | POST | **MVP** Tạo tenant (revenue_mv1) |
| `/api/onboarding` | POST | Industry onboarding |
| `/api/industry_profile/{tenant_id}` | GET | Industry profile |
| `/api/plans/generate` | POST | **MVP** Generate plan 30 ngày → Postgres |
| `/api/plans/{plan_id}` | GET | **MVP** Get plan |
| `/api/plans/{plan_id}/materialize` | POST | Materialize plan |
| `/api/content` (revenue_mv2) | POST | Tạo content item |
| `/api/content/{content_id}` | GET | Get content |
| `/api/content/by_plan/{plan_id}` | GET | List content by plan |
| `/api/gdrive/ingest` | POST | Ingest từ GDrive (media-required flow) |
| `/api/assets` | GET | List assets |
| `/webhooks/facebook` | POST | Facebook comment/inbox → lead_signals, n8n |
| `/api/leads` | GET | List lead signals |

**Kết luận:** Các route MVP đã có: onboarding (tenant), planner/generate, plans/generate + plans/{id}, content (generate-samples, approve/reject), publish/facebook + publish/logs, healthz/readyz, kpi. Thêm mới (chưa commit): webhooks/facebook, api/leads, api/gdrive/ingest, api/assets.

---

### 4) DB schema / migrations

- **Alembic:** Có. `ai_content_director/alembic.ini`, `ai_content_director/alembic/env.py` (dùng DATABASE_URL từ app config).
- **Lệnh:**  
  - `alembic current`: Chạy được; output có `Context impl PostgresqlImpl`, `Will assume transactional DDL` (không in revision id khi không kết nối DB).  
  - `alembic history`:  
    - `013` (head) ← 012 (lead_signals)  
    - 012 ← 011, 011 ← 010, … 001 (initial).  
    - 002: HITL approval + audit; 003: publish_logs error_message; 004: scheduler columns; 005: post_metrics; 006: kb_items; 007: ai_usage_logs; 008: audit idempotency, content_usage; 009: industry_profile; 010: generated_plans; 011: revenue content items; 012: lead_signals; 013: content_assets + require_media.
- **Versions:**  
  - `ai_content_director/alembic/versions/001_initial.py` … `011_revenue_content_items.py` (tracked).  
  - `012_lead_signals.py`, `013_content_assets_and_require_media.py` (untracked).
- **Schema SQL:** Không tìm file `*schema*.sql` riêng; schema được quản lý qua Alembic + SQLAlchemy models trong `app/models/`.

---

### 5) Cấu hình & integration keys (không lộ secrets)

**Biến ENV được dùng trong code (rg):**

- **OPENAI:** `OPENAI_API_KEY`, `OPENAI_MODEL`, `OPENAI_TIMEOUT_SECONDS`, `OPENAI_MAX_RETRIES`, `OPENAI_TEMPERATURE`, `OPENAI_INPUT_PRICE_PER_1M`, `OPENAI_OUTPUT_PRICE_PER_1M` — `ai_content_director/app/config.py`, `llm_service.py`, `content_service_mv2.py`, `ai_usage_service.py`.
- **DATABASE_URL:** `app/config.py`, `alembic/env.py`.
- **FACEBOOK / META:** `FACEBOOK_PAGE_ID`, `FACEBOOK_ACCESS_TOKEN`, `FACEBOOK_API_VERSION`; scripts: `META_APP_ID`, `META_APP_SECRET`, `META_BUSINESS_ID`, `META_SYSTEM_USER_ID`, `FACEBOOK_PAGE_ACCESS_TOKEN` — `config.py`, `publish_router.py`, `facebook_publish_service.py`, `facebook_metrics_service.py`, `scripts/_meta_common.py`, `meta_verify.py`, `meta_env_doctor.py`, `meta_post_test.py`.
- **GDRIVE:** `GDRIVE_SA_JSON_PATH`, `GDRIVE_READY_IMAGES_FOLDER_ID`, `GDRIVE_READY_VIDEOS_FOLDER_ID`, `GDRIVE_PROCESSED_FOLDER_ID`, `GDRIVE_REJECTED_FOLDER_ID`, `LOCAL_MEDIA_DIR`, `ASSET_MAX_IMAGE_MB`, `ASSET_MAX_VIDEO_MB` — `config.py`, `gdrive_dropzone.py`, `gdrive_assets_router.py`.
- **N8N / WEBHOOK:** `WEBHOOK_URL`, `N8N_WEBHOOK_TIMEOUT_SECONDS` — `config.py`, `n8n_webhook_service.py`.
- **REDIS:** `REDIS_URL` — `config.py`, `redis_cache.py`, `rate_limit.py`.

**File cấu hình:**  
- Root: `.env`, `.env.example` (có trong ls).  
- `ai_content_director/.env`, `ai_content_director/.env.example`.  
- Không có `config*.yml` trong list file đã quét.

**Quy ước báo cáo:** Không in token/secret; chỉ ghi tên biến và file. Nếu cần evidence “có set” có thể kiểm tra `len(env_var)` hoặc 6 ký tự đầu (đã mask).

---

### 6) Test / smoke scripts

**File test/smoke/run:**

- **ai_content_director:**  
  - `pytest.ini`, `requirements-dev.txt`  
  - `tests/conftest.py`, `tests/test_ai_query_param.py`, `tests/test_lead_signals_smoke.py`, `tests/test_plan_materialize.py`, `tests/test_revenue_mv1_schema.py`, `tests/test_revenue_mv2_schema.py`
- **scripts:**  
  - `smoke_test.ps1`, `smoke_test_hitl.ps1`, `smoke_test_facebook_publish.ps1`, `smoke_test_kpi.ps1`, `smoke_test_openai.ps1`, `smoke_test_scheduler.ps1`, `smoke_test_s2.ps1`, `smoke_test_s4.ps1`, `smoke_e2e.ps1`, `smoke.sh`  
  - `run_mvp_local.ps1`, `run_mvp_local.sh`, `run_full_evaluation.ps1`, `run_ai_quality_evaluation_batch.py`  
  - `meta_post_test.py`, `meta_verify.py`, `meta_env_doctor.py`

**Build/run:**  
- Root: `requirements.txt` (192 bytes).  
- `ai_content_director`: `requirements.txt`, `requirements-dev.txt`; không thấy `Makefile` hoặc `pyproject.toml` trong list file đã liệt kê.

---

## PHẦN B — CHECKLIST DEFINITION OF DONE (MVP END-TO-END)

| Hạng mục | Trạng thái | Evidence / Ghi chú |
|----------|------------|--------------------|
| Onboarding → tạo tenant demo | **Done** | POST /onboarding, POST /api/tenants; `onboarding_router.py`, `tenant_service_mv1.py`; docs MVP_E2E_STEPS.md |
| Generate planner 30 ngày → lưu Postgres | **Done** | POST /planner/generate, POST /api/plans/generate; `planner_service.py`, `plan_service_mv1.py`; migration 010 generated_plans |
| Tạo content items (text/image/video) tối thiểu | **Done** (text); **Partial** (image/video) | POST /content/generate-samples, POST /api/content; content_asset + GDrive ingest hỗ trợ ảnh/video; require_media + assets (013) |
| Approval workflow (draft/approved) | **Done** | POST /content/{id}/approve, /reject; approval_service, audit; migration 002 HITL |
| Facebook semi-auto publish | **Done** | POST /publish/facebook; facebook_publish_service (Graph API, media_required, use_latest_asset); publish_router |
| Ghi publish logs + KPI tối thiểu | **Done** | GET /publish/logs; publish_log model; GET /kpi/summary; post_metrics; migrations 003, 005 |
| Logging/metrics cơ bản | **Done** | logging_config, get_logger; middleware correlation_id, rate_limit |
| API contract rõ (request/response) | **Done** | Pydantic schemas trong `app/schemas/`; routers có response_model |
| Runbook chạy local (README) | **Done** | README_RUNBOOK.md, MVP_E2E_STEPS.md, run_mvp_local.ps1/.sh, ai_content_director/README.md |
| Error handling + retry/rate limit | **Partial** | Rate limit (Redis); retry trong n8n_webhook; Facebook/OpenAI có xử lý lỗi trong service |
| AI Lead (webhook FB → lead_signals → n8n) | **Partial** | Code có: webhooks/facebook, api/leads, lead_signal, n8n_webhook; migrations 012 untracked; chưa đủ test E2E |
| GDrive dropzone + media-required publish | **Partial** | Code có: api/gdrive/ingest, api/assets, content_asset, 013; config + README; cần kiểm tra E2E với Drive thật |

---

## PHẦN C — KẾT LUẬN

### 1) ĐÃ LÀM ĐƯỢC (facts + evidence)

- **Repo:** Git root `D:\ai-ecosystem`, branch `master`, remote `origin` → `https://github.com/vantafi741/aiplatform.git`. Commit gần nhất: revenue-mv2 + migration 011.
- **Backend FastAPI:** Ứng dụng `ai_content_director` với đủ route onboarding, planner, content (generate-samples, list, approve, reject, schedule), publish Facebook, publish logs, audit, scheduler, KPI, KB, healthz/readyz; thêm revenue_mv1 (tenants, plans/generate, plans/{id}, materialize), revenue_mv2 (content CRUD), GDrive ingest/assets, webhook Facebook, leads.
- **DB:** Alembic 001→013; schema: tenants, brand_profile, content_plans, content_items, publish_logs, approval_event, post_metrics, kb_items, ai_usage_logs, generated_plans, industry_profile, revenue_content_item, lead_signal (012), content_assets + require_media (013). Migrations 012/013 chưa commit.
- **Integrations:** Config và code cho OPENAI, DATABASE_URL, FACEBOOK_*, META_* (scripts), GDRIVE_*, REDIS, WEBHOOK_URL/N8N; không in secret trong báo cáo.
- **Runbook & script:** README_RUNBOOK.md, MVP_E2E_STEPS.md, run_mvp_local, smoke_* (hitl, facebook, kpi, openai, scheduler, s2, s4), meta_env_doctor, meta_verify, meta_post_test.
- **Test:** pytest trong ai_content_director (conftest, test_ai_query_param, test_lead_signals_smoke, test_plan_materialize, test_revenue_mv1/mv2_schema).

### 2) ĐANG LÀM (in-progress)

- **Thay đổi chưa commit:** 22 file sửa + nhiều file untracked (migrations 012/013, lead_signal, content_asset, webhook/leads/gdrive routers, services, tests, docs/LEAD_SIGNALS_RUNBOOK.md). Diff: +605/-93 dòng.
- **Tính năng mới chưa đóng:** AI Lead (Facebook → lead_signals → n8n), GDrive dropzone + media-required publish; đã có API và migration nhưng chưa đủ test E2E và runbook chi tiết.

### 3) CẦN LÀM TIẾP (ưu tiên P0 / P1 / P2)

- **P0 (blocker MVP E2E):**  
  - Commit và push các thay đổi hiện tại (hoặc tách branch feature) để tránh mất code (migrations 012/013, leads, GDrive, webhook).  
  - Chạy `alembic upgrade head` trên DB đích và xác nhận 012, 013 apply thành công.  
  - Smoke E2E: onboarding → planner → content generate-samples → approve → publish/facebook (có hoặc không dùng GDrive) theo README_RUNBOOK / MVP_E2E_STEPS.

- **P1 (hoàn thiện MVP):**  
  - Viết/chuẩn hóa API contract (request/response) cho webhooks/facebook và api/leads (ví dụ OpenAPI/Swagger).  
  - Runbook cho AI Lead (docs/LEAD_SIGNALS_RUNBOOK.md đã có; bổ sung bước verify n8n + lead_signals).  
  - Runbook + smoke cho GDrive ingest → assets → publish (media_required).  
  - Đảm bảo .env.example (root + ai_content_director) đồng bộ với config (GDRIVE_*, WEBHOOK_*, LEAD_*).

- **P2 (nice-to-have / scale):**  
  - Test tự động: mở rộng pytest cho flow publish (mock Graph API), lead webhook, GDrive ingest.  
  - Retry/backoff thống nhất cho external API (Facebook, n8n, OpenAI).  
  - Monitoring/metrics (ví dụ cost_usd theo tenant từ ai_usage_logs).

---

## PHẦN D — TÓM TẮT XUẤT BÁO CÁO

1. **Snapshot repo:** Branch master, 22 file modified, untracked: migrations 012/013, lead/asset models, webhook/leads/gdrive routers & services, tests, LEAD_SIGNALS_RUNBOOK.
2. **Routes + modules:** Xem bảng routes mục A.3; entrypoint `ai_content_director/app/main.py`; modules: routers, services, models, schemas, middleware, infrastructure.
3. **DB schema/migrations:** Alembic 001→013; 012 lead_signals, 013 content_assets + require_media; current/head cần chạy với DATABASE_URL.
4. **Integrations state (masked):** OPENAI, DATABASE_URL, FACEBOOK/META, GDRIVE, REDIS, WEBHOOK_URL/N8N được dùng trong config và code; không hiển thị giá trị secret.
5. **Checklist DoD:** Onboarding, planner, content (text + partial image/video), approval, Facebook publish, publish logs + KPI, logging, API contract, runbook → Done/Partial; error handling/retry/rate limit Partial; AI Lead & GDrive Partial.
6. **Next actions:**  
   - **P0:** Commit/push + alembic upgrade head + smoke E2E.  
   - **P1:** API contract webhook/leads, runbook AI Lead & GDrive, đồng bộ .env.example.  
   - **P2:** Pytest mở rộng, retry thống nhất, monitoring cost.

---

*File báo cáo: `REPORT_STATUS_CURSOR.md` (root repo). Chỉ audit, không chỉnh logic dự án.*
