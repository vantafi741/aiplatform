# Hợp nhất kiến trúc – Platform Core Architecture v1

**Mục tiêu:** Một core app duy nhất (ai_content_director), không runtime api/, một DATABASE_URL, một alembic, một .env.example.

---

## 0) Repo hygiene scan (trừ docs/)

- **Chuỗi:** `from shared`, `import shared`, `from api`, `import api`, `from workers`, `import workers`, `shared/`, `workers/`.
- **Kết quả:** **CLEAN** – Không có file code (.py, .ps1, .sh) trong repo (trừ thư mục docs/) còn import hoặc đường dẫn tới shared/api/workers. Chỉ tài liệu trong `docs/` và `ENV_KEYS_REPORT.md` (đã thêm lưu ý legacy) còn nhắc các thư mục đã xóa.

---

## 1) Danh sách file bị xóa

### Thư mục `api/` (loại bỏ khỏi runtime)

| File |
|------|
| `api/__init__.py` |
| `api/main.py` |
| `api/deps.py` |
| `api/routers/__init__.py` |
| `api/routers/health.py` |
| `api/routers/tenants.py` |
| `api/routers/jobs.py` |
| `api/routers/brand_profiles.py` |
| `api/routers/onboarding.py` |
| `api/routers/kb.py` |
| `api/routers/planner.py` |
| `api/routers/content.py` |
| `api/schemas/__init__.py` |
| `api/schemas/tenants.py` |
| `api/schemas/jobs.py` |
| `api/schemas/brand_profile.py` |
| `api/schemas/onboarding.py` |
| `api/schemas/kb.py` |
| `api/schemas/content.py` |

### Thư mục `migrations/` (root – đã gộp vào ai_content_director/alembic)

| File |
|------|
| `migrations/env.py` |
| `migrations/README.md` |
| `migrations/script.py.mako` |
| `migrations/versions/20250216000000_schema_v1.py` |
| `migrations/versions/20250216000001_sprint2_brand_kb.py` |
| `migrations/versions/20250216000002_sprint4_content_assets.py` |

### Thư mục `shared/` (đã xóa – không dùng bởi core app)

| File |
|------|
| `shared/__init__.py` |
| `shared/config.py` |
| `shared/database.py` |
| `shared/models.py` |
| `shared/logging_config.py` |
| `shared/audit.py` |
| `shared/queue.py` |
| `shared/rag.py` |
| `shared/llm.py` |
| `shared/content_engine.py` |

### Thư mục `workers/` (đã xóa – không dùng bởi core app)

| File |
|------|
| `workers/__init__.py` |
| `workers/worker.py` |
| `workers/tasks.py` |

### Root

| File |
|------|
| `alembic.ini` |

---

## 2) Danh sách file bị sửa

| File | Thay đổi |
|------|----------|
| `.env.example` | Thay bằng nội dung ngắn: trỏ sang `ai_content_director/.env.example`, một DATABASE_URL, hướng dẫn chạy. |
| `README_ROOT.md` | Viết lại: Platform Core Architecture v1, một core app (ai_content_director), chuẩn hóa 1 DB / 1 alembic / 1 .env.example, bỏ đề cập api/ và migrations root. |
| `ai_content_director/README.md` | Tiêu đề thành "Platform Core Architecture v1"; bổ sung mô tả core app duy nhất; cập nhật cấu trúc (models gồm ai_usage_log, approval_event, post_metrics). |
| `requirements.txt` (root) | Gỡ fastapi, uvicorn, sqlalchemy, psycopg2, alembic, redis, **rq** (chỉ phục vụ workers/ đã xóa); giữ tối thiểu cho scripts (python-dotenv, requests). |
| `ENV_KEYS_REPORT.md` | Thêm lưu ý đầu file: tham chiếu api/shared/workers đã xóa; chuẩn env là ai_content_director/.env.example. |
| `scripts/run_mvp_local.ps1` | Ghi rõ idempotent (venv 1 lần, pip + alembic mỗi lần); luôn chạy pip install khi có requirements.txt (bắt buộc tồn tại). |
| `docs/CONSOLIDATION_CORE_ARCH_V1.md` | Thêm §5 PASS criteria (checklist), §6 How to verify (3 bước), §7 Known limitations (Facebook env, OpenAI). |

### File mới (hardening)

| File | Mô tả |
|------|--------|
| `scripts/smoke_e2e.ps1` | Smoke E2E: GET /health, POST /onboarding, POST /planner/generate (days=7), POST /content/generate-samples, POST /content/{id}/approve; nếu có FACEBOOK_* thì POST /publish/facebook và kiểm tra publish_logs tăng; in PASS/FAIL, publish SKIPPED nếu không có env. |

---

## 3) Migration mới

| File | Mô tả |
|------|--------|
| `ai_content_director/alembic/versions/008_audit_idempotency_content_usage.py` | Tạo 3 bảng: `audit_logs` (correlation_id, action, resource_type, resource_id, tenant_id, payload, created_at), `idempotency_keys` (key PK, tenant_id, brand_profile_id, response_snapshot, created_at), `content_usage_logs` (id, tenant_id, asset_id, cached_hit, model, estimated_tokens, created_at). Revises: 007. |

---

## 4) README mới / cập nhật

- **README_ROOT.md:** Đã ghi lại theo "Platform Core Architecture v1" – một entrypoint (ai_content_director), chuẩn hóa, cách chạy, cấu trúc repo.
- **ai_content_director/README.md:** Đã cập nhật tiêu đề và đoạn mở đầu thành "Platform Core Architecture v1", core app duy nhất, danh sách models.

---

## 5) PASS criteria (checklist)

- [ ] **Entrypoint duy nhất:** Chỉ chạy `uvicorn app.main:app` từ thư mục `ai_content_director`.
- [ ] **Repo hygiene:** Không còn file code (.py, .ps1) import hoặc tham chiếu `shared/`, `api/`, `workers/` (trừ tài liệu trong docs/).
- [ ] **1 DATABASE_URL:** Dùng duy nhất trong `ai_content_director/.env`, DB name `ai_content_director`.
- [ ] **1 alembic:** Chỉ `ai_content_director/alembic/`; không còn `migrations/` ở root.
- [ ] **1 .env.example:** Chuẩn là `ai_content_director/.env.example`.
- [ ] **Bảng đã gộp:** audit_logs, idempotency_keys, content_usage_logs (migration 008).
- [ ] **Smoke E2E:** `.\scripts\smoke_e2e.ps1` in PASS (health → onboarding → planner → content → approve; publish SKIPPED nếu không có Facebook env).

---

## 6) How to verify

1. **Chạy app (idempotent):**  
   `.\scripts\run_mvp_local.ps1`  
   → Tạo venv nếu chưa có, cài dependencies, `alembic upgrade head`, start uvicorn tại http://127.0.0.1:8000.

2. **Smoke E2E (API phải đang chạy):**  
   `.\scripts\smoke_e2e.ps1`  
   → Gọi /health, POST /onboarding, POST /planner/generate (days=7), POST /content/generate-samples, approve 1 item; nếu có FACEBOOK_* thì gọi publish và kiểm tra publish_logs; in PASS hoặc FAIL.

3. **Kiểm tra nhanh health:**  
   `curl -s http://127.0.0.1:8000/health`  
   → Trả về `{"status":"ok"}`.

---

## 7) Known limitations

- **Facebook publish:** Cần set `FACEBOOK_PAGE_ID` và `FACEBOOK_ACCESS_TOKEN` trong env (vd. `ai_content_director/.env`) thì mới đăng bài thật. Thiếu env thì smoke_e2e in SKIPPED cho bước publish; các bước trước vẫn PASS.
- **OpenAI:** Planner và content generate-samples dùng OpenAI khi có `OPENAI_API_KEY`; không có thì fallback template (vẫn chạy được).

---

---

## 8) Hướng dẫn chạy kiểm tra (3 lệnh)

```powershell
# 1) Khởi động app (từ repo root)
.\scripts\run_mvp_local.ps1

# 2) Trong terminal khác: smoke E2E (API phải đang chạy)
.\scripts\smoke_e2e.ps1

# 3) Health nhanh
curl -s http://127.0.0.1:8000/health
```

*Tài liệu hợp nhất kiến trúc – không thêm tính năng mới, không refactor business logic.*
