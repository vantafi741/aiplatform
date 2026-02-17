# AI Marketing – Sales – Content Ecosystem Platform

**Platform Core Architecture v1**

Repo root: `d:\ai-ecosystem` (hoặc tương đương Linux/Mac).

---

## 1) Một core app duy nhất: ai_content_director

**Entrypoint runtime duy nhất** là **ai_content_director**. Không còn chạy `api/` hay dùng migrations ở root.

| Thư mục | Vai trò |
|--------|--------|
| **`ai_content_director/`** | **Core app** – FastAPI, 1 DATABASE_URL, 1 alembic, 1 .env.example. Gồm: Onboarding, Planner, Content, KB, Approve, Publish, Usage log, Rate limit. |
| `scripts/` | run_mvp_local.ps1, run_mvp_local.sh, run_full_evaluation.ps1, … |
| `docs/` | MVP_E2E_STEPS.md, AUDIT_*, … |

---

## 2) Chuẩn hóa

- **1 DATABASE_URL:** Trong `ai_content_director/.env`: `DATABASE_URL=postgresql+asyncpg://.../ai_content_director`
- **1 thư mục migration:** `ai_content_director/alembic/` – chạy `alembic upgrade head` trong thư mục `ai_content_director`
- **1 .env.example:** `ai_content_director/.env.example` – copy sang `ai_content_director/.env` và điền giá trị

---

## 3) Chạy local

Từ repo root:

- **Windows:** `.\scripts\run_mvp_local.ps1`
- **Linux/Mac:** `./scripts/run_mvp_local.sh`

Script sẽ: kiểm tra env → venv + pip → `alembic upgrade head` (trong ai_content_director) → `uvicorn app.main:app --host 127.0.0.1 --port 8000`

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

---

## 4) Tài liệu

- **Core app (kiến trúc, API, cost guard, rate limit):** [ai_content_director/README.md](ai_content_director/README.md)
- **E2E + curl:** [docs/MVP_E2E_STEPS.md](docs/MVP_E2E_STEPS.md)
- **Audit MVP:** [docs/AUDIT_MVP_AI_MARKETING_PLATFORM.md](docs/AUDIT_MVP_AI_MARKETING_PLATFORM.md)

---

## 5) Cấu trúc repo (sau hợp nhất)

```
ai_content_director/          # Core app (entrypoint duy nhất)
  app/
  alembic/
  .env.example
  docker-compose.yml
  README.md

scripts/
docs/
```

---

*Platform Core Architecture v1 – một app, một DB, một bộ migration và env.*
