# AI Content Director – Platform Core Architecture v1

**Core app duy nhất** của platform: FastAPI + PostgreSQL + Alembic. Một DATABASE_URL, một thư mục migration, một .env.example. Gồm: Onboarding, Planner, Content, KB, Approve, Publish, Usage log, Rate limit.

## Yêu cầu

- Python 3.11
- PostgreSQL 16 (hoặc dùng Docker)
- (Tuỳ chọn) Redis cho queue sau này

## Chạy local (không Docker)

1. Clone và vào thư mục:

   ```bash
   cd ai_content_director
   ```

2. Tạo virtualenv và cài dependency:

   ```bash
   python -m venv .venv
   .venv\Scripts\activate   # Windows
   # source .venv/bin/activate   # Linux/macOS
   pip install -r requirements.txt
   ```

3. Cấu hình ENV:

   ```bash
   copy .env.example .env   # Windows
   # cp .env.example .env   # Linux/macOS
   ```

   Sửa `.env`, đặt `DATABASE_URL` đúng với Postgres của bạn, ví dụ:

   ```
   DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/ai_content_director
   ```

4. Tạo DB (nếu chưa có):

   ```bash
   createdb ai_content_director
   ```

5. Chạy migration:

   ```bash
   alembic revision --autogenerate -m "initial"
   alembic upgrade head
   ```

6. Chạy server:

   ```bash
   uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
   ```

7. Smoke test:

   ```bash
   curl http://localhost:8000/health
   curl http://localhost:8000/
   ```

   Kỳ vọng:

   - `GET /health` → `{"status":"ok"}`
   - `GET /` → `{"name":"ai_content_director","version":"0.1.0"}`

8. **Smoke test KB (FAQ + content có ngữ cảnh):**

   - Tạo tenant: `POST /onboarding` với body `{"tenant_name":"KB Test","industry":"Cơ khí","brand_tone":"","main_services":[],"target_customer":"","cta_style":""}` → lưu `tenant.id`.
   - Thêm KB: `POST /kb/items/bulk` với body `{"tenant_id": "<tenant_id>", "items": [{"title": "Gia công CNC", "content": "Chúng tôi gia công chi tiết CNC độ chính xác 0.01mm, vật liệu thép C45.", "tags": ["cnc", "gia-cong"]}]}` → 201, `created: 1`.
   - Kiểm tra: `GET /kb/items?tenant_id=<tenant_id>` → trả về 1 mục.
   - Query: `POST /kb/query` với body `{"tenant_id": "<tenant_id>", "query": "CNC gia công", "top_k": 5}` → `items` có ít nhất 1 phần tử.
   - Tạo plan: `POST /planner/generate?force=true&ai=true` body `{"tenant_id": "<tenant_id>", "days": 7}`.
   - Tạo content (có KB context): `POST /content/generate-samples?force=true&ai=true` body `{"tenant_id": "<tenant_id>", "count": 3}`. Trong log server kỳ vọng thấy `content.kb_context` với `kb_hit_count` ≥ 0, `kb_chars_used` ≥ 0 (nếu có KB trùng chủ đề).

## Chạy bằng Docker Compose

1. Trong thư mục `ai_content_director`:

   ```bash
   copy .env.example .env
   docker compose up -d
   ```

2. Chạy migration trong container:

   ```bash
   docker compose run --rm api alembic revision --autogenerate -m "initial"
   docker compose run --rm api alembic upgrade head
   ```

3. Healthcheck:

   ```bash
   curl http://localhost:8000/health
   curl http://localhost:8000/
   ```

## Cấu trúc repo

- `app/` – FastAPI app: `main.py`, `config.py`, `logging_config.py`, `db.py`
- `app/schemas/` – Pydantic request/response: common, onboarding, planner, content, kb
- `app/models/` – SQLAlchemy 2.0 async: tenant, brand_profile, content_plan, content_item, publish_log, kb_item, ai_usage_log, approval_event, post_metrics
- `app/routers/` – health, onboarding, planner, content, publish, kb
- `app/services/` – onboarding, planner, content, facebook_publish, kb_service (query ILIKE, build_kb_context_string)
- `alembic/` – migrations (env dùng DATABASE_URL, autogenerate từ models)
- `Dockerfile`, `docker-compose.yml` – API + Postgres 16 + Redis (optional)
- `.env.example` – đủ key: APP_ENV, DATABASE_URL, LOG_LEVEL, OPENAI_*, FACEBOOK_*, REDIS_URL, WEBHOOK_URL (AI Lead)

## AI Lead System (Facebook → lead_signals → follow-up)

- **POST /webhooks/facebook** – nhận event comment/inbox; classify intent (rule-first, LLM optional); ghi `lead_signals`, audit `LEAD_SIGNAL_CREATED`, gọi n8n khi `priority=high` (ENV `WEBHOOK_URL`).
- **GET /api/leads** – list lead theo `tenant_id`, filter `status`, pagination.
- Cấu hình: `WEBHOOK_URL`, `LEAD_CLASSIFY_USE_LLM`. Chi tiết: **docs/LEAD_SIGNALS_RUNBOOK.md**.

## API

- `GET /` – app name + version
- `GET /health` – healthcheck
- `POST /webhooks/facebook` – webhook Facebook (comment/inbox) → lead_signals (body/header `tenant_id`).
- `GET /api/leads?tenant_id=...&status=...&limit=50&offset=0` – list lead signals.
- `POST /onboarding` – tạo tenant + brand profile (201)
- `POST /planner/generate?force=false&ai=true` – tạo kế hoạch 30 ngày (201). `ai=true` (mặc định) dùng OpenAI; nếu lỗi hoặc không có `OPENAI_API_KEY` thì tự fallback template. Response có `used_ai`, `used_fallback`, `model`.
- `POST /content/generate-samples?force=false&ai=true` – tạo sample content (draft), tối đa 20 (cost guard). Tương tự `ai` + fallback. Response có `used_ai`, `used_fallback`, `model`.
- `GET /content/list?tenant_id=...&status=draft|approved|published` – liệt kê content (optional filter theo status).
- `POST /content/{content_id}/approve` – duyệt nội dung (HITL). Body: `{"tenant_id": "...", "actor": "HUMAN"}`.
- `POST /content/{content_id}/reject` – từ chối nội dung. Body: `{"tenant_id": "...", "actor": "HUMAN", "reason": "..."}`.
- `GET /audit/events?tenant_id=...&limit=50` – audit log (GENERATE_PLAN, GENERATE_CONTENT, AUTO_APPROVED, NEEDS_REVIEW, ESCALATED, APPROVED, REJECTED, PUBLISH_*).
- `POST /publish/facebook` – đăng một content đã **approved** lên Facebook Page (Graph API). Body: `{"tenant_id": "...", "content_id": "..."}`.
- `GET /publish/logs?tenant_id=...&limit=50` – danh sách publish logs (queued / success / fail).
- `POST /content/{content_id}/schedule` – đặt lịch đăng (chỉ content approved). Body: `{"tenant_id": "...", "scheduled_at": "2026-02-18T09:00:00"}` (ISO).
- `POST /content/{content_id}/unschedule` – xóa lịch. Body: `{"tenant_id": "..."}`.
- `GET /scheduler/status` – trạng thái worker: enabled, interval_seconds, last_tick_at, pending_count.
- `GET /kpi/summary?tenant_id=...&days=7` – KPI: tổng reach, impressions, reactions, comments, shares + danh sách theo post (từ post_metrics).
- `POST /kpi/fetch-now` – Thu thập metrics ngay (không đợi vòng 6h). Body: `{"tenant_id": "...", "days": 7, "limit": 20}` (days ≤ 30, limit ≤ 50). Response: `fetched`, `success`, `fail`.
- **KB (FAQ / ngữ cảnh cho content):**
  - `POST /kb/items` – tạo một mục KB. Body: `{"tenant_id": "...", "title": "...", "content": "...", "tags": ["tag1"]}`.
  - `POST /kb/items/bulk` – bulk ingest. Body: `{"tenant_id": "...", "items": [{"title": "...", "content": "...", "tags": []}, ...]}` (tối đa 500 mục).
  - `GET /kb/items?tenant_id=...` – liệt kê tất cả KB items của tenant.
  - `POST /kb/query` – tìm KB theo query (ILIKE trên title + content). Body: `{"tenant_id": "...", "query": "...", "top_k": 10}`. Response: `items`, `total`. Content generator dùng kết quả này làm KB_CONTEXT inject vào prompt (giới hạn 2000 ký tự). Log: `content.kb_context` với `kb_hit_count`, `kb_chars_used`.

**OpenAI:** Cần set `OPENAI_API_KEY` trong `.env` để dùng AI. Nếu không set hoặc AI lỗi, hệ thống tự fallback sang template (không fail request), và response trả về `used_fallback: true`.

**Biến môi trường OpenAI (trong `app/config.py`):**

| Biến | Mặc định | Mô tả |
|------|----------|--------|
| `OPENAI_API_KEY` | (bắt buộc cho AI) | Key từ OpenAI. Thiếu thì dùng template, không lỗi. |
| `OPENAI_MODEL` | `gpt-4o-mini` | Model Chat Completions. |
| `OPENAI_TIMEOUT_SECONDS` | `45` | Timeout mỗi request. |
| `OPENAI_MAX_RETRIES` | `2` | Số lần retry khi lỗi. |
| `OPENAI_TEMPERATURE` | `0.7` | Nhiệt độ sinh nội dung. |

**Cost guard:** `days` tối đa 30 (planner), `count` tối đa 20 (content). Vượt quá sẽ bị từ chối.

**Daily budget (USD/tenant):** Mỗi lần gọi OpenAI được ghi vào `ai_usage_logs` (tokens + cost_usd). Nếu tổng cost trong ngày (UTC) của tenant ≥ `DAILY_BUDGET_USD` thì không gọi OpenAI, tự fallback template. Cấu hình: `DAILY_BUDGET_USD`, tùy chọn `OPENAI_INPUT_PRICE_PER_1M`, `OPENAI_OUTPUT_PRICE_PER_1M`.

**Rate limit:** Redis sliding window, mặc định 60 req/phút theo `X-Tenant-ID` hoặc `X-API-Key` header. Cần `REDIS_URL`; không set thì không áp dụng limit. Cấu hình: `RATE_LIMIT_PER_MIN`, `REDIS_URL`.

---

## HITL Approval (Human-in-the-loop)

Sau khi generate samples, từng item được gán **review_state** theo `confidence_score`:

| confidence_score | review_state      | Hành động |
|------------------|-------------------|-----------|
| ≥ 0.85           | `auto_approved`   | Tự set `status=approved`, `approved_at=now`, ghi event AUTO_APPROVED |
| 0.70 – 0.85      | `needs_review`    | Giữ `status=draft`, ghi event NEEDS_REVIEW |
| < 0.70           | `escalate_required` | Giữ `status=draft`, ghi event ESCALATED |

**Luồng ví dụ:** generate-samples → một số auto-approved, một số draft → `GET /content/list?status=draft` → duyệt/thu hồi bằng approve/reject → `GET /content/list?status=approved`.

- **Audit log:** Mọi hành động (generate plan, generate content, auto_approved, needs_review, escalated, approve, reject, publish_requested/success/fail) được ghi vào `approval_events`. Xem qua `GET /audit/events?tenant_id=...`.

---

## Facebook Publishing (Graph API)

Chỉ đăng nội dung đã **approved** lên Facebook Page. Dùng **Graph API** (không headless). Mỗi lần đăng ghi `publish_logs` và audit (PUBLISH_REQUESTED → PUBLISH_SUCCESS hoặc PUBLISH_FAIL).

**Biến môi trường:**

| Biến | Mô tả |
|------|--------|
| `FACEBOOK_PAGE_ID` | ID trang Facebook (số hoặc username). |
| `FACEBOOK_ACCESS_TOKEN` | Page Access Token (quyền đăng bài). |
| `FACEBOOK_API_VERSION` | Phiên bản Graph API (mặc định `v20.0`). |

**Lấy Page Access Token (ngắn gọn):**

1. Vào [Meta for Developers](https://developers.facebook.com/) → tạo App (hoặc dùng app có sẵn).
2. Thêm product **Facebook Login** (nếu chưa có). Trong **Tools** → **Graph API Explorer** chọn app và Page, bật quyền `pages_manage_posts`, `pages_read_engagement`.
3. Lấy **User Access Token** (short-lived) từ Graph API Explorer, sau đó gọi API đổi sang **Page Access Token** (long-lived):  
   `GET /me/accounts?access_token={user_token}` → lấy `access_token` của page cần đăng.
4. Hoặc dùng [Access Token Tool](https://developers.facebook.com/tools/accesstoken/) → chọn Page → copy Page token.

Thiếu `FACEBOOK_PAGE_ID` hoặc `FACEBOOK_ACCESS_TOKEN` thì `POST /publish/facebook` trả 503.

---

## Auto Scheduler (đăng bài theo lịch)

Worker chạy trong process FastAPI (single instance, laptop), mỗi **60 giây** quét content đã **approved** và **scheduled** (scheduled_at <= now), gọi Facebook publish. Không dùng Celery/Redis (có thể thêm sau).

**Cách lên lịch một bài:**

1. Content phải ở trạng thái **approved**.
2. Gọi `POST /content/{content_id}/schedule` với body `{"tenant_id": "<uuid>", "scheduled_at": "2026-02-18T09:00:00"}` (ISO datetime; khuyến nghị UTC hoặc nhất quán Asia/Ho_Chi_Minh).
3. Scheduler sẽ tự đăng khi `scheduled_at <= now` (trong vòng 60s kể từ thời điểm due).

**Trạng thái schedule:** `none` | `scheduled` | `publishing` | `published` | `failed`.  
**Chính sách retry:** tối đa 3 lần; sau mỗi lần fail đặt lại `scheduled_at = now + (publish_attempts * 10 phút)`; sau 3 lần giữ `failed`.

**Kiểm tra worker:** `GET /scheduler/status` → `enabled`, `interval_seconds`, `last_tick_at`, `pending_count`.

**Smoke test (1 bài lên lịch sau 2 phút):** xem mục "Smoke test Scheduler" bên dưới hoặc chạy `scripts/smoke_test_scheduler.ps1`.

---

## KPI (Post Metrics)

Sau khi đăng bài lên Facebook, hệ thống thu thập metrics (reach, impressions, reactions, comments, shares) qua Graph API và lưu vào bảng **post_metrics**. Worker metrics chạy mỗi **360 phút** (cùng process với scheduler), chỉ lấy metrics cho bài đăng trong **7 ngày** gần đây.

**Quyền Facebook cần thiết:** Để đọc insights của post cần Page Access Token có quyền **pages_read_engagement** (và tùy metric: **pages_read_user_content**, **pages_show_list**). Thiếu quyền: API trả lỗi, hệ thống ghi audit METRICS_FETCH_FAIL và lưu raw response vào post_metrics.

**API:** `GET /kpi/summary?tenant_id=...&days=7` trả về `totals` (tổng) và `posts` (danh sách theo post_id, fetched_at, reach, impressions, …).  
**Fetch ngay:** `POST /kpi/fetch-now` với body `{"tenant_id": "<uuid>", "days": 7, "limit": 20}` để thu thập metrics ngay (giới hạn: days ≤ 30, limit ≤ 50). Response: `fetched`, `success`, `fail`.

**Smoke test:** Đăng 1 bài (publish/facebook) → gọi `POST /kpi/fetch-now` → gọi `GET /kpi/summary?tenant_id=...&days=7`. Xem `scripts/smoke_test_kpi.ps1`.

**Ví dụ PowerShell (fetch-now rồi xem summary):**
```powershell
$base = "http://localhost:8000"
$tenantId = "YOUR_TENANT_ID"
Invoke-RestMethod -Uri "$base/kpi/fetch-now" -Method Post -ContentType "application/json" -Body (@{ tenant_id = $tenantId; days = 7; limit = 20 } | ConvertTo-Json)
Invoke-RestMethod -Uri "$base/kpi/summary?tenant_id=$tenantId&days=7" -Method Get
```

---

## MVP Core – Ví dụ curl (smoke test)

Giả sử server chạy tại `http://localhost:8000`.

**1) Onboarding – tạo tenant + brand profile (trả về `tenant_id`):**

```bash
curl -s -X POST http://localhost:8000/onboarding \
  -H "Content-Type: application/json" \
  -d "{\"tenant_name\":\"An Thanh Phu Mechanical\",\"industry\":\"Cơ khí chế tạo khuôn dập\",\"brand_tone\":\"Chuyên nghiệp, kỹ thuật, đáng tin\",\"main_services\":[\"Thiết kế & chế tạo khuôn dập\",\"Gia công cơ khí chính xác\",\"Gia công kim loại tấm\"],\"target_customer\":\"Nhà máy, doanh nghiệp sản xuất, xưởng công nghiệp\",\"cta_style\":\"Liên hệ báo giá nhanh / Tư vấn kỹ thuật\"}"
```

Kỳ vọng: HTTP 201, body có `tenant.id` và `brand_profile`. Copy `tenant.id` cho bước sau.

**2) Planner – tạo kế hoạch 30 ngày (thay `TENANT_ID` bằng id từ bước 1):**

```bash
# Dùng AI (cần OPENAI_API_KEY); nếu lỗi sẽ tự fallback
curl -s -X POST "http://localhost:8000/planner/generate?force=false&ai=true" \
  -H "Content-Type: application/json" \
  -d "{\"tenant_id\":\"TENANT_ID\",\"days\":30}"
```

Kỳ vọng: HTTP 201, `created: 30`, `items` (30 phần tử), `used_ai` (true nếu AI chạy thành công), `used_fallback` (true nếu dùng template), `model` (tên model hoặc null).

**Dùng template thuần (không gọi OpenAI):**

```bash
curl -s -X POST "http://localhost:8000/planner/generate?force=false&ai=false" ...
```

**3) Content – tạo 10 sample posts (thay `TENANT_ID`; tối đa 20):**

```bash
curl -s -X POST "http://localhost:8000/content/generate-samples?force=false&ai=true" \
  -H "Content-Type: application/json" \
  -d "{\"tenant_id\":\"TENANT_ID\",\"count\":10}"
```

Kỳ vọng: HTTP 201, `created: 10`, `items`, `used_ai`, `used_fallback`, `model`. Dùng `ai=false` để chỉ tạo template.

---

## Smoke test (full flow)

1. Khởi động DB + server (local hoặc Docker), chạy migration.
2. `curl http://localhost:8000/health` → `{"status":"ok"}`.
3. `curl http://localhost:8000/` → `{"name":"ai_content_director","version":"0.1.0"}`.
4. POST /onboarding (body như trên) → 201, lưu `tenant.id`.
5. POST /planner/generate với `tenant_id` vừa lấy → 201, `created: 30`.
6. POST /content/generate-samples với `tenant_id`, `count: 10` → 201, `created: 10`.

Sau khi copy repo và set `DATABASE_URL`, chạy migration rồi start server là có thể gọi ngay `/health` và `/`.

---

## Smoke test OpenAI (PowerShell)

Đảm bảo server chạy và `OPENAI_API_KEY` đã set trong `.env` để thấy `used_ai: true`, `used_fallback: false`.

**1) Onboarding (lấy `tenant_id`):**

```powershell
$base = "http://localhost:8000"
$onboard = Invoke-RestMethod -Uri "$base/onboarding" -Method Post -ContentType "application/json" -Body '{"tenant_name":"Test OpenAI","industry":"Cơ khí","brand_tone":"Chuyên nghiệp","main_services":["Dịch vụ A"],"target_customer":"SME","cta_style":"Liên hệ"}'
$tenantId = $onboard.tenant.id
```

**2) Planner với AI (kỳ vọng `used_ai: true`, `used_fallback: false`):**

```powershell
$planner = Invoke-RestMethod -Uri "$base/planner/generate?force=false&ai=true" -Method Post -ContentType "application/json" -Body (@{ tenant_id = $tenantId; days = 7 } | ConvertTo-Json)
$planner | ConvertTo-Json -Depth 5
# Kiểm tra: $planner.used_ai -eq $true, $planner.used_fallback -eq $false, $planner.model -ne $null
```

**3) Content samples với AI (kỳ vọng `used_ai: true`, `used_fallback: false`):**

```powershell
$content = Invoke-RestMethod -Uri "$base/content/generate-samples?force=false&ai=true" -Method Post -ContentType "application/json" -Body (@{ tenant_id = $tenantId; count = 3 } | ConvertTo-Json)
$content | ConvertTo-Json -Depth 5
# Kiểm tra: $content.used_ai -eq $true, $content.used_fallback -eq $false, $content.model -ne $null
```

**Dùng template thuần (không gọi OpenAI):** thay `ai=true` bằng `ai=false`. Kỳ vọng `used_ai: false`, `used_fallback: true` (hoặc không dùng fallback nhưng vẫn không gọi AI).

Script đầy đủ: xem `scripts/smoke_test_openai.ps1`.

---

## Smoke test HITL Approval (PowerShell)

Sau khi có `tenant_id` và đã gọi `POST /content/generate-samples` (ít nhất 1 lần):

```powershell
$base = "http://localhost:8000"
$tenantId = "YOUR_TENANT_ID"   # thay bằng tenant_id từ onboarding

# 1) List draft (cần duyệt)
Invoke-RestMethod -Uri "$base/content/list?tenant_id=$tenantId&status=draft" -Method Get

# 2) Lấy content_id từ item đầu tiên (draft), rồi approve
$contentId = (Invoke-RestMethod -Uri "$base/content/list?tenant_id=$tenantId&status=draft" -Method Get).items[0].id
Invoke-RestMethod -Uri "$base/content/$contentId/approve" -Method Post -ContentType "application/json" -Body (@{ tenant_id = $tenantId; actor = "HUMAN" } | ConvertTo-Json)

# 3) List approved
Invoke-RestMethod -Uri "$base/content/list?tenant_id=$tenantId&status=approved" -Method Get

# 4) Audit log
Invoke-RestMethod -Uri "$base/audit/events?tenant_id=$tenantId&limit=20" -Method Get
```

**Từ chối một item (reject):**

```powershell
Invoke-RestMethod -Uri "$base/content/$contentId/reject" -Method Post -ContentType "application/json" -Body (@{ tenant_id = $tenantId; actor = "HUMAN"; reason = "Nội dung chưa phù hợp" } | ConvertTo-Json)
```

Script đầy đủ (từ thư mục gốc repo): `scripts/smoke_test_hitl.ps1`.

---

## Google Drive Dropzone + Media-required Facebook Publish

Đăng bài Facebook có thể **bắt buộc ít nhất 1 ảnh/video** (từ Google Drive). Asset được quét từ thư mục READY, tải về local, sau khi đăng thành công file Drive được chuyển sang PROCESSED; lỗi hoặc invalid → REJECTED.

### Cấu hình Drive folder IDs

1. Trên Google Drive tạo 4 thư mục (hoặc dùng có sẵn): **Ready Images**, **Ready Videos**, **Processed**, **Rejected**.
2. Mở từng thư mục → URL dạng `https://drive.google.com/drive/folders/FOLDER_ID` → copy `FOLDER_ID`.
3. Trong `.env` đặt:
   - `GDRIVE_READY_IMAGES_FOLDER_ID` – thư mục chứa ảnh chờ ingest (jpeg, png, webp; tối đa `ASSET_MAX_IMAGE_MB` MB).
   - `GDRIVE_READY_VIDEOS_FOLDER_ID` – thư mục chứa video chờ ingest (mp4, quicktime; tối đa `ASSET_MAX_VIDEO_MB` MB).
   - `GDRIVE_PROCESSED_FOLDER_ID` – file đã đăng thành công sẽ được chuyển vào đây.
   - `GDRIVE_REJECTED_FOLDER_ID` – file lỗi/không đúng định dạng/size sẽ được chuyển vào đây.

### Upload gdrive-sa.json lên VPS

1. Tạo Service Account trong [Google Cloud Console](https://console.cloud.google.com/) → IAM & Admin → Service Accounts → Create. Tải JSON key.
2. Đặt tên file ví dụ `gdrive-sa.json`, **không commit** vào git.
3. Trên VPS (hoặc máy chạy API):
   - Copy file lên thư mục an toàn, ví dụ `/opt/aiplatform/secrets/gdrive-sa.json`.
   - Trong `.env` đặt: `GDRIVE_SA_JSON_PATH=/opt/aiplatform/secrets/gdrive-sa.json`.
   - Đảm bảo thư mục Drive (Ready/Processed/Rejected) **đã share với email Service Account** (quyền Xem + Chỉnh sửa cho Processed/Rejected).

### Biến môi trường

| Biến | Mặc định | Mô tả |
|------|----------|--------|
| `GDRIVE_SA_JSON_PATH` | (bắt buộc) | Đường dẫn file JSON Service Account. |
| `GDRIVE_READY_IMAGES_FOLDER_ID` | (bắt buộc) | Folder ID chứa ảnh chờ ingest. |
| `GDRIVE_READY_VIDEOS_FOLDER_ID` | (tùy chọn) | Folder ID chứa video chờ ingest. |
| `GDRIVE_PROCESSED_FOLDER_ID` | (bắt buộc) | Folder chứa file đã đăng xong. |
| `GDRIVE_REJECTED_FOLDER_ID` | (bắt buộc) | Folder chứa file lỗi/invalid. |
| `LOCAL_MEDIA_DIR` | `/opt/aiplatform/media_cache` | Thư mục local lưu file tải từ Drive. |
| `ASSET_MAX_IMAGE_MB` | `10` | Giới hạn size ảnh (MB). |
| `ASSET_MAX_VIDEO_MB` | `200` | Giới hạn size video (MB). |

### API

- **POST /api/gdrive/ingest** – Body: `{"tenant_id": "..."}`. Quét thư mục READY, tải file về local, ghi bảng `content_assets`. Trả về `count_ingested`, `count_invalid`.
- **GET /api/assets?tenant_id=...&status=...** – Liệt kê assets (lọc `status`: ready, cached, invalid, uploaded).

### Media-required publish

- `content_items.require_media` mặc định `true`; `primary_asset_type` mặc định `image`.
- **POST /publish/facebook**: nếu content `require_media` và không có asset nào (ready/cached) gắn content → trả 400 với `code: "media_required"` và ghi publish_log fail.
- Có thể dùng asset "unattached" mới nhất của tenant: gửi `"use_latest_asset": true` trong body. Scheduler tự dùng `use_latest_asset=true` khi không có asset gắn content.
- Ảnh: upload lên Page (published=false) → tạo feed post với `attached_media`. Video: upload với description → Graph trả về post_id. Sau khi đăng thành công: cập nhật asset `fb_media_fbid`/`fb_video_id`, `status=uploaded`, chuyển file Drive sang PROCESSED; lỗi → REJECTED và ghi `error_reason`.

### Smoke test (Google Drive + Assets + Publish)

1. Cấu hình `.env`: `GDRIVE_SA_JSON_PATH`, 4 folder IDs, `LOCAL_MEDIA_DIR` (có thể dùng `./media_cache` khi chạy local).
2. Chạy migration: `alembic upgrade head`.
3. Cho ảnh/video vào thư mục READY (đúng định dạng, dưới size limit). Share folder với Service Account.
4. Gọi ingest:
   ```bash
   curl -s -X POST http://localhost:8000/api/gdrive/ingest -H "Content-Type: application/json" -d "{\"tenant_id\":\"<TENANT_UUID>\"}"
   ```
   Kỳ vọng: `count_ingested` ≥ 0, `count_invalid` ≥ 0.
5. Xem assets: `GET /api/assets?tenant_id=<TENANT_UUID>&status=cached`.
6. (Tùy chọn) Gắn asset với content: cập nhật `content_assets.content_id` bằng content_id đã approved (qua DB hoặc API cập nhật sau).
7. Đăng Facebook: `POST /publish/facebook` với `tenant_id`, `content_id` (đã approved). Nếu có asset cached và `require_media=true` có thể dùng `use_latest_asset: true` để dùng asset unattached mới nhất.
8. Kiểm tra: file trong Drive đã chuyển sang PROCESSED; `GET /api/assets?status=uploaded` có bản ghi tương ứng.

---

## Smoke test Facebook Publish (PowerShell)

Đặt `FACEBOOK_PAGE_ID` và `FACEBOOK_ACCESS_TOKEN` trong `.env`. Luồng: có sẵn content **approved** → gọi publish → xem logs.

```powershell
$base = "http://localhost:8000"
$tenantId = "YOUR_TENANT_ID"
# Lấy một content đã approved
$approved = Invoke-RestMethod -Uri "$base/content/list?tenant_id=$tenantId&status=approved" -Method Get
$contentId = $approved.items[0].id

# Đăng lên Facebook
Invoke-RestMethod -Uri "$base/publish/facebook" -Method Post -ContentType "application/json" -Body (@{ tenant_id = $tenantId; content_id = $contentId } | ConvertTo-Json)

# Xem publish logs
Invoke-RestMethod -Uri "$base/publish/logs?tenant_id=$tenantId&limit=10" -Method Get
```

Kỳ vọng: `POST /publish/facebook` trả `status: success` (và `post_id`) khi token hợp lệ; `GET /publish/logs` có ít nhất một bản ghi với `status` success hoặc fail.

---

## Smoke test Scheduler (PowerShell)

Luồng: onboarding → planner → generate-samples → approve 1 item → schedule đăng sau 2 phút → đợi ~2–3 phút (hoặc poll `/publish/logs`) → kiểm tra `publish_logs` status=success và content status=published.

```powershell
# Chạy script đầy đủ (từ thư mục gốc repo)
.\scripts\smoke_test_scheduler.ps1
```

Script sẽ: tạo tenant, plan, samples, approve item đầu tiên, đặt lịch `scheduled_at = now + 2 phút`, in ra thời điểm due và hướng dẫn chờ 2–3 phút rồi gọi `GET /publish/logs` và `GET /content/list?status=published` để xác nhận.
