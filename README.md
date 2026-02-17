# AI Marketing – Sales – Content Ecosystem Platform

**Platform Core Architecture v1.** Core app duy nhất: **ai_content_director**. Xem chi tiết: [README_ROOT.md](README_ROOT.md) và [ai_content_director/README.md](ai_content_director/README.md).

## Chạy local (thống nhất)

Từ thư mục gốc repo:

- **Windows:** `.\scripts\run_mvp_local.ps1`
- **Linux/Mac:** `./scripts/run_mvp_local.sh`

Hoặc thủ công:

```bash
cd ai_content_director
cp .env.example .env
# Sửa .env (DATABASE_URL, OPENAI_*, ...)
python -m venv .venv
.venv\Scripts\activate   # Windows
pip install -r requirements.txt
alembic upgrade head
uvicorn app.main:app --host 127.0.0.1 --port 8000
```

API: http://127.0.0.1:8000 | Docs: http://127.0.0.1:8000/docs

## Cấu trúc (sau hợp nhất)

```
ai_content_director/   # Core app (entrypoint duy nhất)
scripts/               # run_mvp_local.*, run_full_evaluation.ps1, ...
docs/                  # MVP_E2E_STEPS.md, CONSOLIDATION_*, ...
```

## Smoke test / E2E

- **E2E steps + curl:** [docs/MVP_E2E_STEPS.md](docs/MVP_E2E_STEPS.md)
- **Chạy full evaluation:** `.\scripts\run_full_evaluation.ps1` (API phải đang chạy tại 127.0.0.1:8000)
- **Chi tiết API + smoke test KB:** [ai_content_director/README.md](ai_content_director/README.md)

### (Legacy) Sprint 1 (jobs + worker)

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

## Meta Setup Quickstart

Sau khi điền `.env` (Meta keys) trong `ai_content_director/.env` hoặc env, chạy từ repo root:

```bash
python scripts/meta_env_doctor.py
python scripts/meta_verify.py
python scripts/meta_post_test.py --message "Test"
```

- **meta_env_doctor.py**: kiem tra bien META_*, FACEBOOK_*, in huong dan lay key (token duoc mask).
- **meta_verify.py**: xac minh token hop le, page info, scopes; neu sai in huong dan fix.
- **meta_post_test.py**: dang thu 1 bai len Page; tra ve `post_id` neu thanh cong.

**App Mode:** App o che do Development chi admin/tester thay bai dang; chuyen Live de cong khai. Chi tiet: [docs/META_SETUP.md](docs/META_SETUP.md). Runbook day du: [README_RUNBOOK.md](README_RUNBOOK.md).

## Bi?n m?i tr??ng (.env)

Chuẩn: Xem `ai_content_director/.env.example`. Quan trọng: `DATABASE_URL`, `OPENAI_API_KEY`, `REDIS_URL`. S4: `CONTENT_CACHE_TTL_SECONDS`, `DEEPSEEK_API_KEY` (t?y ch?n). **Meta/Facebook:** [docs/META_SETUP.md](docs/META_SETUP.md) ? c�ch l?y token, test Graph Explorer v� curl; kh�ng commit token.

## Prompt Playbook v1

Template prompt v? brand rules + output_schema m?u: `docs/prompt_playbook_v1.json`. C? v? d? `example_output` JSON cho content (headline, body, cta_text, tone_match_score).

## Tài liệu thêm

- [README_ROOT.md](README_ROOT.md) – Platform Core Architecture v1
- [docs/MVP_E2E_STEPS.md](docs/MVP_E2E_STEPS.md) – E2E + curl
- [docs/CONSOLIDATION_CORE_ARCH_V1.md](docs/CONSOLIDATION_CORE_ARCH_V1.md) – Danh sách file xóa/sửa khi hợp nhất
