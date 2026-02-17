# FULL AUDIT – AI MARKETING / SALES / CONTENT ECOSYSTEM PLATFORM

**Ngày audit:** 2025-02-16  
**Workspace:** d:\ai-ecosystem  
**Phương pháp:** Scan file thực tế, không suy đoán.

---

## 1) TÓM TẮT TRẠNG THÁI

| Mục | Kết quả |
|-----|--------|
| **Repo tồn tại** | **YES** – 1 repo (ai-ecosystem), backend Python tại thư mục gốc. |
| **Backend framework** | **FastAPI** – `api/main.py`, uvicorn, `api/routers/` (health, tenants, jobs, brand_profiles, onboarding, kb, planner, content). |
| **Database setup** | **Postgres + Alembic** – `docker-compose.yml` (postgres:15-alpine, redis:7-alpine), `alembic.ini`, `migrations/` (3 versions), `shared/database.py`, `shared/models.py`. |
| **AI module** | **CÓ** – `shared/content_engine.py`, `shared/llm.py` (stub/DeepSeek), `docs/prompt_playbook_v1.json`; planner + content generate/regenerate; confidence + approval_tier. |
| **Publish module** | **NOT FOUND** – Không có service gọi Facebook Graph API hay publish; chỉ có chuỗi channel `"facebook"` trong `api/routers/planner.py`. |
| **HITL module** | **MỘT PHẦN** – Có `status` (draft/approved/rejected) và `approval_tier` (auto/draft/escalate) trên content; không có workflow HITL riêng (task queue người duyệt, bước duyệt). |
| **RAG module** | **CÓ (stub)** – `shared/rag.py`: interface `VectorStoreAdapter`, implementation `PostgresKbAdapter` (ILIKE trên question/answer). Không có vector DB thật (embedding, index vector). |

---

## 2) BẢNG ĐỐI CHIẾU VỚI PHASE 1 ROADMAP

| Phase 1 Item | Exists? | File Path | Notes |
|--------------|---------|-----------|-------|
| Hạ tầng backend | YES | `docker-compose.yml`, `api/main.py`, `shared/database.py`, `migrations/`, `requirements.txt` | Postgres + Redis, FastAPI, Alembic. |
| Logging | YES | `shared/logging_config.py` | JSON format, correlation_id, `setup_logging()`. |
| Security | PARTIAL | `.env.example`, `shared/config.py` | Cấu hình ENV, không thấy auth/JWT/OAuth trong scope scan. |
| Industry Profile | PARTIAL | `shared/models.py` (BrandProfile), `migrations/` | Có bảng `brand_profiles` với cột `industry`; không có bảng/entity tên `IndustryProfile` riêng. |
| Script Generator | PARTIAL | `shared/content_engine.py`, `shared/llm.py` | Sinh content text (caption, body, hashtags, cta) từ plan_item + brand + RAG; không có module tên “Script Generator” hay “Video script” riêng. |
| Video Agent cơ bản | NOT FOUND | — | Không có file/route liên quan video agent. |
| Facebook Auto Post | NOT FOUND | — | Chỉ có `channel="facebook"` trong planner; không có Graph API, publish endpoint, hay service đăng bài. |
| KB FAQ | YES | `shared/models.py` (KbItem), `api/routers/kb.py`, `migrations/versions/20250216000001_sprint2_brand_kb.py` | Bảng `kb_items`, POST /kb/items, bulk_ingest, GET /kb/items, POST /kb/query. |
| Approval Workflow | PARTIAL | `api/routers/content.py` (PUT status), `shared/models.py` (ContentAsset.status, ContentAssetVersion.approval_tier) | Có draft/approved/rejected và tier; không có workflow HITL (bước duyệt, assignee, lịch sử duyệt). |
| Quota AI | NOT FOUND | — | Không có module/quota/token limit cho AI. |

---

## 3) KIỂM TRA TỒN TẠI THEO YÊU CẦU

### 3.1 Thư mục/repo liên quan (marketing, platform, content, fastapi, n8n)

- **marketing / platform / content:** Có trong README, tên repo “AI Content Director”, `shared/content_engine.py`, `api/routers/content.py`, `docs/prompt_playbook_v1.json`.
- **fastapi:** Có – `api/main.py`, `requirements.txt` (fastapi, uvicorn), toàn bộ `api/routers/`.
- **n8n:** Chỉ được nhắc trong README (control plane, webhook); không có code n8n trong repo.

### 3.2 File / cấu trúc

| Item | Tồn tại | Đường dẫn / Ghi chú |
|------|--------|---------------------|
| docker-compose.yml | YES | `docker-compose.yml` (postgres, redis) |
| requirements.txt | YES | `requirements.txt` |
| pyproject.toml | NOT FOUND | — |
| alembic/ | YES (config) | `alembic.ini`; migrations nằm ở `migrations/` |
| migrations/ | YES | `migrations/env.py`, `migrations/versions/*.py`, `migrations/script.py.mako` |
| main.py | YES | `api/main.py` |
| app.py | NOT FOUND | — |
| routers/ | YES | `api/routers/` (9 file) |
| models/ | N/A (dùng shared) | Không có `api/models/`; models ở `shared/models.py` |

### 3.3 Schema DB (đối chiếu tên yêu cầu vs thực tế)

| Yêu cầu | Có trong DB? | Bảng / Model | Ghi chú |
|--------|----------------|--------------|--------|
| Tenant | YES | `tenants` | `shared/models.py` – Tenant |
| IndustryProfile | NO | — | Có `brand_profiles.industry` (cột), không có bảng IndustryProfile. |
| BrandTone | NO | — | Có `brand_profiles.tone_of_voice` (và các field brand khác), không có bảng BrandTone riêng. |
| Planner | YES | `content_plans`, `content_plan_items` | ContentPlan, ContentPlanItem |
| ContentItem | PARTIAL | `content_plan_items`, `content_assets` | Không có bảng tên “ContentItem”; có plan item và content asset (text). |

---

## 4) KẾT LUẬN (chọn 1)

**C) Đã có foundation nhưng chưa có AI layer**  
→ **Điều chỉnh theo thực tế:** Đã có **foundation** (FastAPI, Postgres, Redis, Docker, migrations, logging, audit) **và** đã có **một phần AI layer** (AI Content Director: content engine, LLM adapter, RAG stub, planner, content generate). Chưa có: Facebook publish, Video Agent, Quota AI, HITL workflow đầy đủ, IndustryProfile/BrandTone riêng.

- **A) Chưa có bất kỳ nền tảng code nào** – **SAI** (đã có repo + backend).
- **B) Có repo nhưng chưa đạt foundation** – **SAI** (đã có Docker, DB, API, migrations).
- **C) Đã có foundation nhưng chưa có AI layer** – **MỘT PHẦN** – Đúng là có foundation; AI layer đã có (content director, RAG stub) nhưng chưa đủ theo Phase 1 (thiếu publish, video agent, quota, HITL đầy đủ).

**Kết luận chính thức:** **C**, với ghi chú: Foundation đã có; AI layer đã có ở mức Content Director + RAG stub; Phase 1 còn thiếu Facebook Auto Post, Video Agent, Quota AI, Approval Workflow đầy đủ.

---

## 5) ĐỀ XUẤT BƯỚC TIẾP THEO (dựa trên dữ liệu audit)

1. **Facebook Auto Post** – Chưa có: cần service/endpoint gọi Facebook Graph API (hoặc tương đương) để publish content đã approve (dựa trên `ContentAsset` / content_asset_versions).
2. **Approval Workflow (HITL)** – Đã có status + approval_tier; nên bổ sung: bảng/flow “pending review” → assignee → approve/reject + audit (hoặc tích hợp với n8n).
3. **Video Agent cơ bản** – Chưa có: nếu Phase 1 cần, thêm module/route sinh script hoặc metadata cho video (có thể tái dùng content_engine/LLM).
4. **Quota AI** – Chưa có: thêm tracking (vd. `content_usage_logs` đã có) và giới hạn theo tenant/key (rate limit, token quota).
5. **IndustryProfile / BrandTone** – Nếu cần entity tách: thêm bảng `industry_profiles` và/hoặc `brand_tones` + migration; hiện có thể tiếp tục dùng `brand_profiles` (industry, tone_of_voice).
6. **RAG thật** – Hiện dùng Postgres ILIKE; khi cần: thêm VectorStoreAdapter implementation với vector DB (vd. pgvector, Pinecone) và embedding pipeline.

---

*Audit chỉ dựa trên file tồn tại trong workspace; không phỏng đoán.*
