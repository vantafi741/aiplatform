# BÁO CÁO AUDIT – AI MARKETING / SALES / CONTENT ECOSYSTEM PLATFORM

**Ngày audit:** 2025-02-17  
**Workspace:** d:\ai-ecosystem  
**Đối chiếu:** Kế hoạch MVP 60–90 ngày + Kiến trúc yêu cầu (Control plane, Processing plane, PostgreSQL, AI layer, Retry/rate limit, Confidence-based approval).

**Phương pháp:** Scan toàn bộ repo (file, router, model, migration, config); không phỏng đoán. Thiếu config/env được ghi rõ.

---

## A) TÌNH TRẠNG HIỆN TẠI THEO TỪNG MODULE

### 1. MVP 60–90 ngày – Đối chiếu từng hạng mục

| Module MVP | Mô tả yêu cầu | Trạng thái | % Hoàn thành | Ghi chú |
|------------|----------------|------------|--------------|--------|
| **Industry Onboarding** | Tạo tenant + profile (industry, brand) | **Đã hoàn thành** | **100%** | Có ở **cả hai** codebase: `api/routers/onboarding.py` (idempotency), `ai_content_director/app/routers/onboarding_router.py`. Schema khác nhau (api: tenant+slug, brand_profiles onboarding fields; ai_content_director: tenant+industry, brand_profiles brand_tone/main_services/...). |
| **AI Content Director** | Ứng dụng điều phối nội dung AI | **Đã hoàn thành** | **95%** | Thư mục `ai_content_director/` là một FastAPI app độc lập: planner 30 ngày, content samples, publish, scheduler, audit, KPI. Thiếu KB/FAQ trong chính app này (KB chỉ có ở `api/`). |
| **Planner 30 ngày** | Kế hoạch nội dung 30 ngày | **Đã hoàn thành** | **100%** | `ai_content_director`: POST /planner/generate, days 1–30, OpenAI hoặc template fallback, cost guard max 30 days. `api/`: POST /planner/generate minimal (1 plan + 1 item cho S4). |
| **Content Factory (text)** | Sinh nội dung text từ plan | **Đã hoàn thành** | **90%** | **ai_content_director**: POST /content/generate-samples (OpenAI/template), count≤20 (cost guard), approve/reject/schedule. **api**: POST /content/generate, content_assets + versions, shared/content_engine + shared/llm (DeepSeek), confidence/tier, content_usage_logs. Hai schema khác nhau (content_items vs content_assets). |
| **Facebook semi-auto publish** | Đăng bài đã duyệt lên Facebook | **Đã hoàn thành** | **95%** | **Chỉ trong ai_content_director**: `publish_router` (POST /publish/facebook, GET /publish/logs), `facebook_publish_service` (Graph API, retry 2 lần), `scheduler_service` (60s tick, FOR UPDATE SKIP LOCKED). Cần FACEBOOK_PAGE_ID, FACEBOOK_ACCESS_TOKEN trong .env. api/ không có publish. |
| **KB FAQ cơ bản** | Knowledge base, FAQ, ingest/query | **Đang làm dở** | **70%** | **Chỉ trong api/**: `api/routers/kb.py` (POST /kb/items, bulk_ingest, GET /kb/items, POST /kb/query), `shared/rag.py` (PostgresKbAdapter, ILIKE). **ai_content_director không có** router KB hay model kb_items. RAG chưa có vector DB thật (chỉ ILIKE). |
| **Approval workflow (HITL)** | Human-in-the-loop duyệt nội dung | **Đã hoàn thành** | **90%** | **ai_content_director**: `approval_service` (approve_content, reject_content, review_state_from_confidence 0.85/0.70), audit events (APPROVED, REJECTED, ...), POST content/approve, content/reject. **api**: PUT content status, approval_tier trên ContentAssetVersion. Thiếu: assignee, queue “pending review” riêng (có thể bù bằng n8n sau). |
| **Logging + cost guard** | Log có cấu trúc, giới hạn chi phí AI | **Đang làm dở** | **75%** | Logging: `ai_content_director/app/logging_config.py` (structlog), `shared/logging_config.py` (JSON, correlation_id). Cost guard: ai_content_director có **days≤30, count≤20** trong planner/content; **api** có bảng content_usage_logs + shared/content_engine ghi usage; **ai_content_director không có** bảng usage log hay quota theo tenant. |

### 2. Kiến trúc yêu cầu – Đối chiếu

| Thành phần kiến trúc | Yêu cầu | Trạng thái | % | Ghi chú |
|----------------------|--------|------------|---|--------|
| **Control plane (n8n)** | n8n điều khiển, webhook vào API | **Chưa có** | **0%** | README nhắc “n8n (ngoài repo), webhook trả tới API”. Repo **không có** workflow n8n, không có endpoint webhook Meta/n8n được implement. Scripts có WEBHOOK_VERIFY_TOKEN, WEBHOOK_SECRET trong .env.example (chưa dùng). |
| **Processing plane** | FastAPI/Python services xử lý | **Đã có** | **100%** | Hai ứng dụng FastAPI: `api/main.py` (Sprint 1–4) và `ai_content_director` (app.main). Workers: `workers/` (RQ) cho api jobs. ai_content_director chạy scheduler trong process. |
| **PostgreSQL schema** | Schema nhất quán, migrations | **Đang làm dở** | **70%** | **Hai schema tách biệt**: (1) `migrations/` + `shared/models.py` → DB `ai_ecosystem` (tenants, brand_profiles, jobs, job_runs, audit_logs, kb_items, idempotency_keys, content_plans, content_plan_items, content_assets, content_asset_versions, content_usage_logs). (2) `ai_content_director/alembic/` → DB `ai_content_director` (tenants, brand_profiles, content_plans, content_items, publish_logs, approval_events, post_metrics, ...). Không dùng chung một schema. |
| **AI layer** | LLM router hoặc GPT integration | **Đã có** | **90%** | **ai_content_director**: `app/services/llm_service.py` (OpenAI, planner + samples, fallback template). **api**: `shared/llm.py` (DeepSeek/stub), `shared/content_engine.py` (playbook, RAG, confidence, cache). Hai kênh AI khác nhau (OpenAI vs DeepSeek). |
| **Retry / rate limit** | Retry có chính sách, rate limit | **Một phần** | **50%** | Retry: facebook_publish_service (2 lần), scheduler retry backoff 10 phút, OPENAI_MAX_RETRIES=2; content_engine 1 retry với repair prompt. **Rate limit**: không thấy middleware hoặc giới hạn theo tenant/API key trong code. |
| **Confidence-based approval** | Duyệt theo confidence | **Đã có** | **95%** | ai_content_director: review_state_from_confidence (≥0.85 auto_approved, 0.70–0.85 needs_review, <0.70 escalate_required). approval_events, approve/reject API. api: approval_tier trên ContentAssetVersion. |

---

## B) DANH SÁCH FILE THEO MODULE

### Module: Industry Onboarding

| File | Vai trò |
|------|--------|
| `api/routers/onboarding.py` | POST /onboarding, idempotency key |
| `api/schemas/onboarding.py` | OnboardingRequest, OnboardingResponse |
| `ai_content_director/app/routers/onboarding_router.py` | POST /onboarding (tenant + brand_profile) |
| `ai_content_director/app/schemas/onboarding.py` | OnboardingRequest, TenantOut, BrandProfileOut |
| `ai_content_director/app/services/onboarding_service.py` | create_tenant_and_profile |
| `migrations/versions/20250216000001_sprint2_brand_kb.py` | idempotency_keys, brand_profiles onboarding |
| `ai_content_director/alembic/versions/001_initial.py` | tenants, brand_profiles (ai_content_director schema) |

### Module: AI Content Director (app)

| File | Vai trò |
|------|--------|
| `ai_content_director/app/main.py` | FastAPI app, lifespan, routers |
| `ai_content_director/app/config.py` | Settings (DATABASE_URL, OPENAI_*, FACEBOOK_*, REDIS_URL) |
| `ai_content_director/app/db.py` | async_session_factory, get_db |
| `ai_content_director/app/logging_config.py` | structlog configure |
| `ai_content_director/app/routers/health_router.py` | GET /health |
| `ai_content_director/README.md` | Runbook, env, cost guard |

### Module: Planner 30 ngày

| File | Vai trò |
|------|--------|
| `ai_content_director/app/routers/planner_router.py` | POST /planner/generate (days, force, ai) |
| `ai_content_director/app/services/planner_service.py` | generate_30_day_plan, OpenAI/template |
| `ai_content_director/app/schemas/planner.py` | PlannerGenerateRequest/Response |
| `ai_content_director/app/models/content_plan.py` | ContentPlan (day_number, topic, content_angle, status) |
| `api/routers/planner.py` | POST /planner/generate (minimal, 1 plan + 1 item) |

### Module: Content Factory (text)

| File | Vai trò |
|------|--------|
| `ai_content_director/app/routers/content_router.py` | generate-samples, list, approve, reject, schedule, unschedule |
| `ai_content_director/app/services/content_service.py` | generate_sample_posts, list_content, schedule_content, unschedule_content |
| `ai_content_director/app/schemas/content.py` | ContentGenerateSamplesRequest/Response, ContentItemOut, ApproveRequest, ... |
| `ai_content_director/app/models/content_item.py` | ContentItem (title, caption, hashtags, status, confidence_score, schedule_*) |
| `api/routers/content.py` | POST /content/generate, GET /{asset_id}, regenerate, PUT status |
| `api/schemas/content.py` | GenerateRequest/Response, ContentGetResponse, ... |
| `shared/content_engine.py` | Playbook + brand + RAG → LLM → validate, retry, confidence/tier, content_usage_logs |
| `shared/llm.py` | call_llm_content (DeepSeek/stub) |

### Module: Facebook semi-auto publish

| File | Vai trò |
|------|--------|
| `ai_content_director/app/routers/publish_router.py` | POST /publish/facebook, GET /publish/logs |
| `ai_content_director/app/services/facebook_publish_service.py` | publish_post (Graph API), list_publish_logs |
| `ai_content_director/app/models/publish_log.py` | PublishLog |
| `ai_content_director/app/services/scheduler_service.py` | Tick 60s, FOR UPDATE SKIP LOCKED, _publish_one, retry backoff |
| `ai_content_director/app/routers/scheduler_router.py` | GET /scheduler/status |
| `ai_content_director/alembic/versions/003_publish_log_error_message.py` | error_message on publish_logs |

### Module: KB FAQ

| File | Vai trò |
|------|--------|
| `api/routers/kb.py` | POST /kb/items, bulk_ingest, GET /kb/items, POST /kb/query |
| `api/schemas/kb.py` | KbItemCreate, KbItemResponse, KbQueryRequest/Response |
| `shared/rag.py` | VectorStoreAdapter, PostgresKbAdapter (ILIKE) |
| `shared/models.py` | KbItem |
| `migrations/versions/20250216000001_sprint2_brand_kb.py` | kb_items |

### Module: Approval workflow (HITL)

| File | Vai trò |
|------|--------|
| `ai_content_director/app/services/approval_service.py` | log_audit_event, approve_content, reject_content, review_state_from_confidence |
| `ai_content_director/app/models/approval_event.py` | ApprovalEvent |
| `ai_content_director/app/routers/audit_router.py` | GET /audit/events |
| `ai_content_director/alembic/versions/002_hitl_approval_audit.py` | approval_events |

### Module: Logging + cost guard

| File | Vai trò |
|------|--------|
| `ai_content_director/app/logging_config.py` | structlog, configure_logging |
| `shared/logging_config.py` | JsonFormatter, correlation_id, setup_logging |
| `shared/audit.py` | audit_logs (api) |
| `shared/content_engine.py` | _log_usage → content_usage_logs (api path) |
| `shared/models.py` | ContentUsageLog (api schema) |
| `migrations/versions/20250216000002_sprint4_content_assets.py` | content_usage_logs table |
| Planner/Content routers (ai_content_director) | Cost guard: days≤30, count≤20 |

### Module: KPI / metrics (ai_content_director)

| File | Vai trò |
|------|--------|
| `ai_content_director/app/routers/kpi_router.py` | GET /kpi/summary, POST /kpi/fetch-now |
| `ai_content_director/app/services/facebook_metrics_service.py` | fetch_now_metrics, get_recent_success_publish_logs |
| `ai_content_director/app/models/post_metrics.py` | PostMetrics |
| `ai_content_director/alembic/versions/005_post_metrics.py` | post_metrics |

### Config / env

| File | Ghi chú |
|------|--------|
| `d:\ai-ecosystem\.env.example` | DATABASE_URL, REDIS_URL, LOG_*, DEEPSEEK_API_KEY, CONTENT_CACHE_TTL_SECONDS, META_*, FACEBOOK_*, WEBHOOK_*, OPENAI_* (root) |
| `ai_content_director\.env.example` | APP_ENV, DATABASE_URL (postgresql+asyncpg), OPENAI_*, FACEBOOK_PAGE_ID, FACEBOOK_ACCESS_TOKEN, REDIS_URL |
| `ai_content_director\.env` | Thực tế dùng khi chạy ai_content_director (có thể ghi đè DATABASE_URL) |
| `shared/config.py` | Settings cho api (DATABASE_URL mặc định ai_ecosystem, REDIS_URL, DEEPSEEK_API_KEY) |
| `app/config.py` (ai_content_director) | Settings (DATABASE_URL mặc định ai_content_director, OPENAI_*, FACEBOOK_*) |

---

## C) NHỮNG PHẦN THIẾU NGHIÊM TRỌNG ĐỂ MVP CHẠY END-TO-END

1. **Một điểm vào duy nhất cho MVP**  
   Hiện có **hai ứng dụng** (api/ và ai_content_director/) với **hai DB** (ai_ecosystem và ai_content_director). Không có một runbook duy nhất “chạy 1 lệnh → onboarding → planner → content → approve → publish”. Script batch đánh giá (`scripts/run_ai_quality_evaluation_batch.py`) gọi **ai_content_director** (localhost:8000), không gọi api/. Thiếu: quyết định rõ MVP chính thức chạy app nào, DB nào; hoặc gộp/đồng bộ hai luồng.

2. **KB/FAQ trong luồng “Content Director”**  
   ai_content_director **không có** KB router hay RAG. Nếu MVP là “onboarding → nhập FAQ → planner → content (có ngữ cảnh FAQ)” thì ai_content_director thiếu bước ingest/query KB. Hiện content sinh dựa trên brand_profile + plan, không dùng RAG trong ai_content_director.

3. **Control plane (n8n) và webhook**  
   README nói control plane là n8n, webhook trả về API. Trong repo **không có** workflow n8n, không có endpoint webhook (vd. Meta webhook verify/post). MVP “semi-auto” có thể chạy chỉ với scheduler trong ai_content_director; nhưng nếu yêu cầu “n8n điều khiển” thì thiếu hoàn toàn.

4. **Config/env thống nhất**  
   - Root `.env.example` dùng `FACEBOOK_PAGE_ACCESS_TOKEN`, `META_APP_ID`, ...; ai_content_director `.env.example` dùng `FACEBOOK_PAGE_ID`, `FACEBOOK_ACCESS_TOKEN` (tên khác).  
   - api dùng `DATABASE_URL` → `ai_ecosystem`; ai_content_director dùng `ai_content_director`. Hai docker-compose (root vs ai_content_director) tạo hai DB khác tên. Thiếu một bộ env/runbook rõ ràng cho “1 tenant, 1 DB, chạy từ A đến Z”.

5. **Cost guard / quota AI đầy đủ**  
   ai_content_director có giới hạn days/count nhưng **không** ghi log usage vào DB (không có bảng content_usage_logs trong schema ai_content_director). api có content_usage_logs nhưng không có rate limit theo tenant. Thiếu: quota theo tenant hoặc theo key, và (tùy chọn) alert khi vượt ngưỡng.

6. **Rate limit**  
   Không thấy middleware hoặc dependency FastAPI nào giới hạn request theo IP/tenant/API key. Rủi ro lạm dụng khi mở công khai.

---

## D) CÓ CHẠY ĐƯỢC END-TO-END DEMO 1 TENANT CHƯA?

**Trả lời: Có thể, nhưng chỉ với một codebase và phải đủ điều kiện.**

- **Nếu chọn ai_content_director làm MVP chính:**
  - **Có thể** chạy e2e: POST /onboarding → POST /planner/generate (days=7 hoặc 30) → POST /content/generate-samples → POST content/approve → POST /publish/facebook hoặc đợi scheduler đăng.
  - **Điều kiện:** PostgreSQL (DB ai_content_director) + Redis (scheduler dùng REDIS_URL cho metrics, không bắt buộc cho publish); OPENAI_API_KEY (hoặc chấp nhận fallback template); FACEBOOK_PAGE_ID + FACEBOOK_ACCESS_TOKEN để thật sự đăng.
  - **Chưa có trong ai_content_director:** KB/FAQ (không ingest FAQ, không RAG trong content). Demo “có FAQ” phải dùng api/ song song hoặc thêm KB vào ai_content_director.

- **Nếu chọn api/ làm MVP chính:**
  - Có onboarding, KB, planner (minimal), content (assets/versions, usage log). **Không có** Facebook publish, không có scheduler đăng bài. E2E “đến lúc đăng lên Facebook” **không** chạy được chỉ với api/.

**Kết luận:** End-to-end “1 tenant: onboarding → plan → content → duyệt → đăng Facebook” **chỉ** chạy được với **ai_content_director** (và đủ env). **Chưa** chạy được e2e nếu định nghĩa bao gồm “KB FAQ tham gia vào content” trong cùng app đó; khi đó còn thiếu tích hợp KB vào ai_content_director hoặc quy trình dùng cả hai app.

---

## E) KIẾN TRÚC HIỆN TẠI CÓ LỆCH ROADMAP KHÔNG?

**Có.** Các điểm lệch chính:

1. **Hai processing plane thay vì một**  
   Roadmap nói “Processing plane (FastAPI/Python services)”. Thực tế có **hai** FastAPI app (api + ai_content_director) với hai schema DB, hai bộ env, hai cách chạy (uvicorn api.main vs uvicorn app.main từ ai_content_director). Không có kiến trúc “một API gateway hoặc một app duy nhất” cho MVP.

2. **Control plane (n8n)**  
   Roadmap: n8n điều khiển, webhook. Thực tế: không có code n8n, không có webhook handler trong repo. Điều khiển thực tế là: gọi HTTP API thủ công hoặc script; scheduler nằm trong process FastAPI (ai_content_director).

3. **PostgreSQL schema**  
   Roadmap: “PostgreSQL schema” (số ít). Thực tế: hai schema (ai_ecosystem và ai_content_director), hai thư mục migrations, hai default DB name. Không thống nhất một schema cho toàn platform.

4. **AI layer**  
   Roadmap: “LLM router hoặc GPT integration”. Thực tế: hai tích hợp (OpenAI trong ai_content_director, DeepSeek/stub trong api), không có “router” chọn model theo tenant/config.

5. **Retry có; rate limit không**  
   Retry đã có ở publish, scheduler, LLM. Rate limit theo tenant/API không có trong code.

---

## F) ĐÁNH GIÁ TRUNG THỰC

### Rủi ro nếu tiếp tục build theo hiện trạng

- **Duy trì hai codebase:** Mọi tính năng mới (vd. KB vào content, quota, n8n) phải quyết định implement ở api hay ai_content_director hay cả hai → trùng lặp, dễ lệch hành vi, khó bảo trì.
- **Hai DB/schema:** Migrations, backup, restore phải làm hai lần; không có foreign key hay dữ liệu chung giữa hai DB.
- **Env/config phân tán:** Dễ sai (chạy api nhưng set FACEBOOK_* của ai_content_director, hoặc ngược lại). Runbook và docs phải luôn chỉ rõ “đang nói tới app nào”.
- **Thiếu rate limit / quota:** Khi mở API cho nhiều tenant hoặc bên ngoài, rủi ro tốn chi phí AI và tải.

### Có đang over-engineering không?

- **Không** theo hướng “nhiều abstraction, ít giá trị”. Code khá gần nghiệp vụ (router → service → DB), ít layer thừa.
- **Có** sự trùng lặp **chức năng** giữa hai app (onboarding, planner, content) với hai cách làm → có thể xem là “duplicate engineering” hơn là over-engineering. Nếu gộp về một app và một schema thì giảm được nhiều mã và đầu mối cấu hình.

### Khuyến nghị tóm tắt

1. **Chốt một app MVP:** Chọn ai_content_director **hoặc** api làm điểm vào duy nhất cho demo 60–90 ngày; app còn lại giữ làm reference hoặc merge dần.
2. **Một DB, một bộ migrations:** Thống nhất tên DB và một thư mục alembic/migrations; nếu cần giữ hai app tạm thời thì ít nhất dùng chung một DB và đồng bộ schema.
3. **Bổ sung thiếu tối thiểu:** (a) Nếu cần “content có ngữ cảnh FAQ” trong app chính → thêm KB + RAG (hoặc gọi api/kb) vào app đó; (b) Rate limit đơn giản theo tenant hoặc API key; (c) Cost guard: ghi usage (vd. content_usage_logs hoặc tương đương) trong app chính và (tùy chọn) giới hạn theo tenant.
4. **Control plane:** Nếu roadmap vẫn yêu cầu n8n, thêm ít nhất một webhook endpoint (vd. Meta) và tài liệu n8n mẫu; nếu không, cập nhật roadmap để phản ánh “scheduler trong app + gọi API thủ công/script”.

---

*Báo cáo dựa trên file và code thực tế trong repo; không phỏng đoán hành vi bên ngoài.*
