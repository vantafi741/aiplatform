# Foundation Stack – Danh sách file thay đổi / thêm mới

Giai đoạn 0: Fresh machine → deploy trong ~15 phút. Core: ai_content_director (FastAPI) + PostgreSQL + Redis + n8n.

---

## File mới (tạo 100%)

| File | Lý do |
|------|--------|
| `docker-compose.yml` (root) | Compose đầy đủ: api (build ai_content_director), postgres, redis, n8n; healthcheck từng service; volume persist cho postgres, redis, n8n. |
| `docker-compose.prod.yml` (root) | Override production: restart unless-stopped; không expose port Postgres/Redis ra host; healthcheck interval dài hơn. |
| `ai_content_director/app/middleware/correlation_id.py` | Middleware gắn X-Correlation-ID (đọc header hoặc tạo mới), bind vào structlog contextvars, trả header trong response. |
| `ai_content_director/app/routers/api_health_router.py` | Router prefix /api: GET /healthz (liveness), GET /readyz (readiness: check DB + Redis). |
| `ai_content_director/alembic/versions/009_industry_profile.py` | Migration tạo bảng industry_profile (id, tenant_id FK bắt buộc, name, description, created_at, updated_at). |
| `ai_content_director/app/models/industry_profile.py` | Model SQLAlchemy IndustryProfile, relationship với Tenant. |
| `ai_content_director/app/infrastructure/__init__.py` | Package infrastructure. |
| `ai_content_director/app/infrastructure/redis_cache.py` | Placeholder Redis cache: cache_get, cache_set, cache_delete; no-op khi không có REDIS_URL. |
| `scripts/smoke.sh` | Smoke test: curl /api/healthz, /api/readyz, n8n up; in PASS/FAIL. |
| `docs/FOUNDATION_STACK_CHANGELIST.md` | Tài liệu danh sách file thay đổi và lý do. |

---

## File sửa

| File | Thay đổi / lý do |
|------|-------------------|
| `ai_content_director/app/main.py` | Thêm CorrelationIdMiddleware, api_health_router; mount router /api (healthz, readyz). |
| `ai_content_director/app/routers/__init__.py` | Export và import api_health_router. |
| `ai_content_director/app/models/__init__.py` | Export IndustryProfile; import industry_profile. |
| `ai_content_director/app/models/tenant.py` | Thêm relationship industry_profiles → IndustryProfile. |
| `ai_content_director/alembic/env.py` | Import IndustryProfile vào target_metadata (để alembic biết model mới). |
| `README_RUNBOOK.md` | Viết lại: deploy VPS, backup/restore Postgres, rollback cơ bản, smoke test, port table; giữ phần Meta Quickstart. |
| `.env.example` (root) | Bổ sung hướng dẫn Foundation Stack, Docker env, mục SECRETS (không commit password/token). |
| `ai_content_director/.env.example` | Thêm dòng “Secrets” và “Hướng dẫn secrets” (không commit .env). |

---

## Không thay đổi (giữ nguyên)

- Business logic MVP (onboarding, planner, content, publish, KB, …): không đụng.
- Cấu trúc app hiện tại: chỉ thêm foundation (healthz/readyz, correlation-id, industry_profile, cache placeholder).
- Rate limit: đã có trong middleware; Redis cache placeholder là module riêng dùng chung sau.

---

## Kiểm tra nhanh

```bash
docker compose up -d
docker compose run --rm api alembic upgrade head
./scripts/smoke.sh
curl -s http://localhost:8000/api/healthz
curl -s http://localhost:8000/api/readyz
```
