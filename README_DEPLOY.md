# One-Command Deploy (VPS)

Muc tieu: cap nhat he thong len VPS bang 1 lenh duy nhat, de team non-IT cung co the van hanh.

## 3 buoc duy nhat

### B1) SSH vao VPS
```bash
ssh <user>@<vps_ip>
```

### B2) Vao thu muc du an
```bash
cd /opt/aiplatform
```

### B3) Chay deploy
```bash
./deploy.sh
```

Neu thanh cong, script in:
- `✅ DEPLOY SUCCESS`
- `✅ SMOKE TEST SUCCESS`

Neu that bai, script se exit code khac 0.

## Deploy script tu dong lam gi?

1. Kiem tra repo co file chua commit khong (dirty -> dung de an toan).
2. `git fetch --all --prune` + `git pull --ff-only`.
3. `docker compose build` (bo qua neu `DEPLOY_NO_BUILD=1`).
4. `docker compose up -d --remove-orphans`.
5. Poll `GET /api/healthz` toi da 60 giay (co the config ENV).
6. Chay `scripts/smoke_test.sh`.

## ENV tuy chon cho deploy/smoke

```bash
# Mac dinh la localhost:8000
API_BASE_URL=http://localhost:8000

# Timeout cho health check (giay)
DEPLOY_HEALTH_TIMEOUT_SECONDS=60

# Bo qua build image neu can deploy nhanh
DEPLOY_NO_BUILD=1

# Bat them smoke test cong staging 8001
SMOKE_TEST_STAGING_8001=1
STAGING_API_BASE_URL=http://localhost:8001
```

## Chay local (copy/paste)

```bash
docker compose up -d --build
bash ./scripts/smoke_test.sh
```

## Troubleshoot nhanh (copy/paste)

### Kiem tra container
```bash
docker compose ps
```

### Xem log API 200 dong gan nhat
```bash
docker compose logs --tail=200 api
```

### Kiem tra health/readiness thu cong
```bash
curl -i http://localhost:8000/api/healthz
curl -i http://localhost:8000/api/readyz
```

### Chay smoke test rieng
```bash
bash ./scripts/smoke_test.sh
```

