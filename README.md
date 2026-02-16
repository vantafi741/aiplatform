# AI Content Director ? MVP

Backend: FastAPI + RQ workers + Postgres + Redis. Control plane (n8n) g?i webhook; processing qua queue. Sprint 2: onboarding, brand profile, KB FAQ, RAG stub.

## Ki?n tr?c

- **Control plane**: n8n (ngo?i repo) ? ch? c?n webhook tr? t?i API.
- **Processing**: FastAPI (API) + worker RQ (Redis Queue).
- **Data**: Postgres (Alembic migrations), object storage (MinIO optional sau).
- **RAG**: VectorStoreAdapter interface + stub retrieval Postgres (ILIKE).

## C?u tr?c th? m?c

```
api/           # FastAPI app, routers, schemas
workers/       # RQ worker, tasks
shared/        # config, db, models, logging, audit, queue, rag
migrations/    # Alembic
scripts/       # ti?n ?ch, smoke test
docs/          # t?i li?u, prompt_playbook_v1.json
```

## Y?u c?u

- Python 3.10+
- Docker + Docker Compose (Postgres + Redis local)
- (T?y ch?n) .env copy t? .env.example

## Ch?y local

### 1. C?u h?nh

```bash
cp .env.example .env
# S?a .env n?u c?n (m?c ??nh ?? kh?p docker-compose)
```

### 2. Kh?i ??ng Postgres + Redis

```bash
docker compose up -d
```

??i v?i gi?y cho DB s?n s?ng.

### 3. Virtual env v? dependencies

```bash
python -m venv venv
venv\Scripts\activate   # Windows
# source venv/bin/activate   # Linux/Mac
pip install -r requirements.txt
```

### 4. Migrations

```bash
alembic upgrade head
```

### 5. Ch?y API

```bash
uvicorn api.main:app --reload --host 0.0.0.0 --port 8000
```

API: http://localhost:8000  
Docs: http://localhost:8000/docs

### 6. Ch?y worker (terminal kh?c, cho jobs)

```bash
venv\Scripts\activate
python -m workers.worker
```

## Smoke test

### Sprint 1 (jobs + worker)

Ch?y l?n l??t sau khi API + worker ?ang ch?y.

1. **Health:** `curl -s http://localhost:8000/health` ? `{"status":"ok",...}`
2. **T?o tenant:** `POST /tenants` v?i `{"name":"Smoke Tenant","slug":"smoke-tenant"}` ? l?u `id`.
3. **T?o job:** `POST /jobs` v?i `{"tenant_id":"<TENANT_ID>","type":"smoke_test","payload":{}}` ? l?u `id`.
4. ??i ~4s r?i `GET /jobs/<JOB_ID>` ? `status` = `success`.

Ho?c ch?y script: `.\scripts\smoke_test.ps1`

### Sprint 2 (onboarding + KB + RAG query)

Sau khi API ch?y (worker kh?ng b?t bu?c cho S2):

```powershell
.\scripts\smoke_test_s2.ps1
```

**C?c b??c script th?c hi?n:**

1. **POST /onboarding** v?i header `Idempotency-Key` ? t?o tenant + brand_profile, tr? v? `tenant_id`, `brand_profile_id`.
2. **POST /kb/bulk_ingest?tenant_id=...** v?i 30 FAQ items ? tr? v? `created: 30`, `ids`.
3. **POST /kb/query** v?i `query`, `tenant_id`, `top_k` ? tr? v? `contexts` v? `citations`.
4. G?i l?i **POST /onboarding** c?ng `Idempotency-Key` ? tr? v? c?ng `tenant_id` (idempotent).

**K?t qu? mong ??i:** Script in "Smoke test S2 PASSED."

### Sprint 4 (Text Content Factory)

```powershell
.\scripts\smoke_test_s4.ps1
```

Flow: onboarding -> kb ingest -> planner/generate -> content/generate -> regenerate -> approve. K?t qu?: "Smoke test S4 PASSED."

## Endpoints

| Method | Path | M? t? |
|--------|------|--------|
| GET | /health | Health check |
| POST | /tenants | T?o tenant |
| GET | /tenants/{id}/brand-profiles | List brand profiles |
| GET | /tenants/{id}/brand-profiles/{pid} | Chi ti?t brand profile |
| POST | /tenants/{id}/brand-profiles | T?o brand profile |
| PUT | /tenants/{id}/brand-profiles/{pid} | C?p nh?t brand profile |
| POST | /onboarding | T?o tenant + brand_profile (header Idempotency-Key t?y ch?n) |
| POST | /jobs | Enqueue job |
| GET | /jobs/{id} | Chi ti?t job |
| POST | /kb/items?tenant_id= | T?o 1 KB item |
| POST | /kb/bulk_ingest?tenant_id= | Ingest nhi?u KB items |
| GET | /kb/items?tenant_id= | List KB items (q t?y ch?n) |
| POST | /kb/query | RAG query: top_k contexts + citations |
| **Sprint 4** | | |
| POST | /planner/generate | T?o plan + 1 item (minimal cho S4) |
| POST | /content/generate | Sinh content t? plan_item (caption/body/hashtags/cta) |
| GET | /content/{asset_id} | Chi ti?t asset + versions |
| POST | /content/{asset_id}/regenerate | Regenerate ? version m?i |
| PUT | /content/{asset_id}/status | draft \| approved \| rejected |

## Bi?n m?i tr??ng (.env)

Xem `.env.example`. Quan tr?ng: `DATABASE_URL`, `REDIS_URL`. S4: `CONTENT_CACHE_TTL_SECONDS`, `DEEPSEEK_API_KEY` (t?y ch?n). **Meta/Facebook** (PAGE_ID, PAGE_ACCESS_TOKEN, webhook): xem [docs/META_SETUP.md](docs/META_SETUP.md) ? cách l?y token, test Graph Explorer và curl; không commit token.

## Prompt Playbook v1

Template prompt v? brand rules + output_schema m?u: `docs/prompt_playbook_v1.json`. C? v? d? `example_output` JSON cho content (headline, body, cta_text, tone_match_score).

## T?i li?u th?m

- `docs/` ? prompt playbook, verification.
- `migrations/README.md` ? c?ch d?ng Alembic.
