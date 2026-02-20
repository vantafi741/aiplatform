# DEPLOY TO VPS – Branch feature/lead-gdrive-assets

**Branch:** `feature/lead-gdrive-assets`  
**Repo:** https://github.com/vantafi741/aiplatform  
**Pull request:** https://github.com/vantafi741/aiplatform/pull/new/feature/lead-gdrive-assets

---

## 1. Danh sách commits + files + diffstat

### Commits (4)

| # | Commit hash | Message |
|---|-------------|---------|
| 1 | `8c56a20` | feat(db): add lead_signals migration 012 |
| 2 | `b9c96a3` | feat(db): add content_assets + require_media migration 013 |
| 3 | `7973fe0` | feat(api): add facebook webhook + leads API + gdrive ingest/assets + docs/tests |
| 4 | `5ec9073` | docs: add DEPLOY_TO_VPS checklist for feature branch |

### Files theo commit

**Commit 1 – lead_signals (3 files):**
- `ai_content_director/alembic/versions/012_lead_signals.py`
- `ai_content_director/app/models/lead_signal.py`
- `ai_content_director/app/schemas/leads.py`

**Commit 2 – content_assets + require_media (4 files):**
- `ai_content_director/alembic/versions/013_content_assets_and_require_media.py`
- `ai_content_director/app/models/content_asset.py`
- `ai_content_director/app/schemas/gdrive_assets.py`
- `ai_content_director/app/models/__init__.py`

**Commit 3 – API + docs + tests (37 files):**
- Cập nhật: `.env.example`, `README.md`, `config.py`, `main.py`, `content_item.py`, `publish_log.py`, `tenant.py`, `routers/__init__.py`, `content_router.py`, `planner_router.py`, `publish_router.py`, `revenue_mv1_router.py`, `content.py`, `publish.py`, `revenue_mv1.py`, `content_service.py`, `facebook_publish_service.py`, `plan_service_mv1.py`, `planner_service.py`, `scheduler_service.py`, `requirements.txt`
- Mới: `facebook_webhook_router.py`, `gdrive_assets_router.py`, `leads_router.py`, `gdrive_dropzone.py`, `lead_classify_service.py`, `lead_service.py`, `n8n_webhook_service.py`, `app/utils/__init__.py`, `app/utils/query_params.py`, `pytest.ini`, `requirements-dev.txt`, `tests/conftest.py`, `test_ai_query_param.py`, `test_lead_signals_smoke.py`, `test_plan_materialize.py`, `docs/LEAD_SIGNALS_RUNBOOK.md`

### Diffstat (branch vs master)

```
44 files changed, 2583 insertions(+), 93 deletions(-)
```

---

## 2. Link branch

- **Branch name:** `feature/lead-gdrive-assets`
- **GitHub:** https://github.com/vantafi741/aiplatform/tree/feature/lead-gdrive-assets
- **Tạo PR:** https://github.com/vantafi741/aiplatform/pull/new/feature/lead-gdrive-assets

---

## 3. Kết quả smoke/test (local)

| Kiểm tra | Kết quả | Ghi chú |
|----------|---------|--------|
| **pytest** | **Chưa chạy** | Venv thiếu `pytest` (có trong `requirements-dev.txt`). Trên VPS/máy khác: `cd ai_content_director && pip install -r requirements-dev.txt && pytest tests/ -v` |
| **scripts/smoke_e2e.ps1** | **Cần API chạy** | Script gọi health → onboarding → planner → content → approve → (publish nếu có Facebook env). Chạy khi API đang listen tại `http://127.0.0.1:8000`. Lệnh: `.\scripts\smoke_e2e.ps1` (từ thư mục gốc repo). |

**Khuyến nghị:** Trên VPS sau khi deploy, chạy `pytest` và `smoke_e2e` (hoặc curl từng endpoint) để xác nhận.

---

## 4. Lệnh deploy VPS

Thực hiện trên VPS (hoặc máy deploy), **không lộ secrets** (dùng `.env` đã cấu hình sẵn).

### Bước 1: Pull branch

```bash
cd /path/to/ai-ecosystem   # hoặc clone nếu mới
git fetch origin
git checkout feature/lead-gdrive-assets
git pull origin feature/lead-gdrive-assets
```

### Bước 2: Docker Compose (nếu dùng Docker)

```bash
# Từ thư mục gốc repo (có docker-compose.yml)
docker compose build
docker compose up -d
```

Nếu dùng file prod:

```bash
docker compose -f docker-compose.prod.yml build
docker compose -f docker-compose.prod.yml up -d
```

### Bước 3: Chạy migration (Alembic)

Nếu chạy API trong container, vào container rồi chạy alembic:

```bash
# Ví dụ container tên là ai_content_director-api-1 (xem bằng docker compose ps)
docker compose exec <tên_service_api> bash -c "cd /app && alembic upgrade head"
```

Hoặc trên VPS chạy trực tiếp (không Docker):

```bash
cd ai_content_director
# Đảm bảo .env có DATABASE_URL
source .venv/bin/activate   # Linux; Windows: .venv\Scripts\activate
alembic upgrade head
```

### Bước 4: Smoke endpoints (curl)

Sau khi API chạy (port 8000 hoặc theo cấu hình):

```bash
# Health
curl -s http://localhost:8000/health
curl -s http://localhost:8000/api/healthz
curl -s http://localhost:8000/api/readyz

# Root
curl -s http://localhost:8000/
```

Nếu dùng domain/HTTPS, thay `http://localhost:8000` bằng base URL thực tế.

### Checklist deploy (copy-paste)

- [ ] `git checkout feature/lead-gdrive-assets && git pull`
- [ ] `docker compose build` (hoặc `docker compose -f docker-compose.prod.yml build`)
- [ ] `docker compose up -d` (hoặc prod)
- [ ] `alembic upgrade head` (trong container hoặc venv với DATABASE_URL)
- [ ] `curl .../api/healthz` → 200
- [ ] `curl .../api/readyz` → 200 (DB + Redis nếu có)
- [ ] (Tùy chọn) Chạy `pytest tests/` trong `ai_content_director`
- [ ] (Tùy chọn) Chạy `.\scripts\smoke_e2e.ps1` hoặc smoke tương đương

---

*Tài liệu này đi kèm branch `feature/lead-gdrive-assets`. Cập nhật khi thay đổi quy trình deploy.*
