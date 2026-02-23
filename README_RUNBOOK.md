# Runbook – AI Marketing / Sales / Content Ecosystem (Foundation Stack)

Muc tieu: Fresh machine -> deploy trong ~15 phut. Core: ai_content_director (FastAPI) + PostgreSQL + Redis + n8n.

---

## 1) Deploy tren VPS

### Yeu cau

- Docker + Docker Compose (v2)
- Git

### Buoc

```bash
# Clone repo
git clone <repo_url> ai-ecosystem && cd ai-ecosystem

# Tao env local (single source env file cho service api)
cp .env.example .env.local
# Sua key can thiet trong .env.local (OPENAI/FB/GDRIVE...)

# Khoi dong stack
docker compose up -d

# Chay migration
docker compose run --rm api alembic upgrade head

# Kiem tra
curl -s http://localhost:8000/api/healthz
curl -s http://localhost:8000/api/readyz
```

Production: env nam ngoai repo.

```bash
# Tao file /opt/aiplatform/secrets/.env.prod (copy tu .env.example, dien secret that)
API_ENV_FILE=/opt/aiplatform/secrets/.env.prod docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d
API_ENV_FILE=/opt/aiplatform/secrets/.env.prod docker compose -f docker-compose.yml -f docker-compose.prod.yml run --rm api alembic upgrade head

# Quet nguy co secret trong repo
bash scripts/check_secrets_in_repo.sh
```

## 1.1) Release & Deploy flow

### PC/Cursor (tao release tag)

```bash
cd /path/to/ai-ecosystem
bash scripts/pin_release.sh vX.Y.Z
```

Script se:
- tao annotated tag
- push tag len `origin`
- in ra lenh deploy tag cho VPS

### VPS (deploy theo tag hoac branch)

```bash
cd /opt/aiplatform
bash scripts/deploy_vps.sh vX.Y.Z
```

Hoac deploy branch:

```bash
bash scripts/deploy_vps.sh feature/lead-gdrive-assets
```

Deploy script tu dong:
- fetch + checkout ref
- compose down/up --build
- health check retry
- alembic upgrade head
- smoke pipeline (neu co `TENANT_ID`)
- audit runtime report

### Rollback (deploy lai tag cu)

```bash
cd /opt/aiplatform
bash scripts/deploy_vps.sh v0.0.9
```

Rollback theo tag la cach an toan nhat cho operator non-IT.

### Port

| Service   | Port (dev) | Ghi chu                    |
|-----------|------------|-----------------------------|
| API       | 8000       | FastAPI                     |
| Postgres  | 5433       | map 127.0.0.1:5433 -> 5432  |
| Redis     | 6380       | map 127.0.0.1:6380 -> 6379  |
| n8n       | 5679       | map 5679 -> 5678            |

### Local run nhanh (operator style)

```bash
cd /opt/aiplatform
cp .env.example .env.local
docker compose up -d --build
docker compose run --rm api alembic upgrade head
docker compose ps
curl -s http://127.0.0.1:8000/api/healthz
```

### Troubleshooting: port conflict tren Windows

Neu bi loi "port is already allocated", giu nguyen map port trong `docker-compose.yml`:
- Postgres: `127.0.0.1:5433:5432`
- Redis: `127.0.0.1:6380:6379`
- n8n: `5679:5678`

Sau khi sua/kiem tra port:

```bash
docker compose down
docker compose up -d
docker compose ps
```

### Alembic multiple heads da duoc merge

- Merge revision da co trong repo: `07a13d6fc732`
- File: `ai_content_director/alembic/versions/07a13d6fc732_merge_heads_014_and_015.py`

Kiem tra:

```bash
docker compose run --rm api alembic heads
docker compose run --rm api alembic current
```

---

## 2) Backup / Restore Postgres

### Backup (single file)

```bash
# Backup toan bo DB ai_content_director
docker compose exec postgres pg_dump -U postgres -d ai_content_director -F c -f /tmp/backup.dump

# Copy ra host
docker compose cp postgres:/tmp/backup.dump ./backup_$(date +%Y%m%d_%H%M%S).dump
```

Hoac tu host (khi port 5432 exposed):

```bash
pg_dump -h localhost -U postgres -d ai_content_director -F c -f backup_$(date +%Y%m%d).dump
```

### Restore

```bash
# Copy file vao container
docker compose cp ./backup_YYYYMMDD.dump postgres:/tmp/restore.dump

# Restore (tạo DB trước nếu chưa có)
docker compose exec postgres psql -U postgres -c "DROP DATABASE IF EXISTS ai_content_director;"
docker compose exec postgres psql -U postgres -c "CREATE DATABASE ai_content_director;"
docker compose exec postgres pg_restore -U postgres -d ai_content_director -F c /tmp/restore.dump
```

Luu y: Restore co the conflict version alembic; sau restore nen chay `alembic upgrade head` de dong bo.

---

## 3) Rollback co ban

### Rollback migration (1 revision)

```bash
docker compose run --rm api alembic downgrade -1
```

### Rollback nhieu revision

```bash
docker compose run --rm api alembic downgrade <revision_id>
# Vi du: alembic downgrade 008
```

### Rollback container (ve image truoc)

```bash
# Xac dinh image dang chay
docker compose ps

# Sua Dockerfile hoac Docker image, build lai
docker compose build api
docker compose up -d api
```

### Rollback code (git)

```bash
git checkout <commit_or_tag>
docker compose build api
docker compose up -d api
# Sau do chay alembic downgrade neu schema da thay doi
```

---

## 4) Smoke test

Chay script kiem tra nhanh:

```bash
./scripts/smoke.sh
```

Can: API dang chay tai http://localhost:8000 (hoac BASE_URL), Postgres + Redis + n8n dang chay. Script goi /api/healthz, /api/readyz; giu PASS.

---

## 5) Revenue MVP Module 1 – curl examples

Base URL: `http://localhost:8000` (hoac BASE_URL).

### POST /api/tenants (tao tenant)

```bash
curl -s -X POST "$BASE_URL/api/tenants" \
  -H "Content-Type: application/json" \
  -d '{"name":"Tenant Demo","industry":"Tech"}'
```

Tra ve: `{"id":"...","name":"Tenant Demo","industry":"Tech","created_at":"..."}`. Luu `id` lam `TENANT_ID`.

### POST /api/onboarding (tao/cap nhat industry_profile cho tenant_id)

```bash
curl -s -X POST "$BASE_URL/api/onboarding" \
  -H "Content-Type: application/json" \
  -d "{\"tenant_id\":\"$TENANT_ID\",\"name\":\"Industry Profile Name\",\"description\":\"Mo ta ngan\"}"
```

Tra ve: `{"id":"...","tenant_id":"...","name":"...","description":"...","created_at":"...","updated_at":"..."}`.

### POST /api/plans/generate (sinh ke hoach 30 ngay)

```bash
curl -s -X POST "$BASE_URL/api/plans/generate" \
  -H "Content-Type: application/json" \
  -d "{\"tenant_id\":\"$TENANT_ID\"}"
```

Co the them `start_date` (YYYY-MM-DD). Tra ve: `{"plan":{...,"plan_json":{"days":[...]},"confidence_score":...,"approval_status":"DRAFT|APPROVED|ESCALATE"}}`. Luu `plan.id` lam `PLAN_ID`.

### GET /api/plans/{plan_id}

```bash
curl -s "$BASE_URL/api/plans/$PLAN_ID"
```

### GET /api/industry_profile/{tenant_id}

```bash
curl -s "$BASE_URL/api/industry_profile/$TENANT_ID"
```

---

## 6) Revenue MVP Module 2 – Content Generator (curl)

Can: TENANT_ID, PLAN_ID da co (tu Module 1). Day 1..30.

### POST /api/content/generate (sinh 1 content item cho plan + day)

```bash
curl -s -X POST "$BASE_URL/api/content/generate" \
  -H "Content-Type: application/json" \
  -d "{\"tenant_id\":\"$TENANT_ID\",\"plan_id\":\"$PLAN_ID\",\"day\":1}"
```

Tra ve: `{"content":{...,"content_type":"POST|REEL|CAROUSEL","title","caption","hashtags":[...],"confidence_score","approval_status":"APPROVED|DRAFT|ESCALATE"}}`. Luu `content.id` lam `CONTENT_ID`.

### GET /api/content/{content_id}

```bash
curl -s "$BASE_URL/api/content/$CONTENT_ID"
```

### GET /api/content/by_plan/{plan_id}

```bash
curl -s "$BASE_URL/api/content/by_plan/$PLAN_ID"
```

Tra ve: mang content items theo day.

---

## 7) Meta Setup Quickstart (bo sung)

Sau khi dien `.env` (Meta keys: META_APP_ID, META_APP_SECRET, FACEBOOK_PAGE_ID, FACEBOOK_PAGE_ACCESS_TOKEN), chay tu repo root:

```bash
python scripts/meta_env_doctor.py
python scripts/meta_verify.py
python scripts/meta_post_test.py --message "Test"
```

Chi tiet: [docs/META_SETUP.md](docs/META_SETUP.md), [README_META_RUNBOOK.md](README_META_RUNBOOK.md).
