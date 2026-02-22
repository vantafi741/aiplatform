# One-Command Deploy (VPS)

Muc tieu: deploy cap nhat he thong bang **1 lenh duy nhat**.

## 3 buoc cho non-IT

1) SSH vao VPS
```bash
ssh <user>@<vps_ip>
```

2) Vao thu muc deploy
```bash
cd /opt/aiplatform
```

3) Chay deploy
```bash
./deploy.sh
```

Neu thanh cong, script se in:
- `✅ DEPLOY SUCCESS`
- `✅ SMOKE TEST SUCCESS`

Neu fail, script se tra ve exit code != 0 de biet deploy that bai.

## Script deploy lam gi?

- Kiem tra repo co "dirty" khong (neu co thi dung de tranh mat code local).
- `git fetch` + `git pull --ff-only`.
- `docker compose build`.
- `docker compose up -d --remove-orphans`.
- Cho endpoint `/api/healthz` san sang (toi da 60 giay).
- Chay `scripts/smoke_test.sh`.

## Smoke test kiem tra gi?

- `GET /api/healthz` (bat buoc)
- `GET /api/readyz` (neu 404 thi bo qua, neu loi khac thi fail)
- OpenAPI (`/openapi.json` hoac `/api/openapi.json`)
- Option: test them staging port `8001` neu bat ENV.

## Bien moi truong tuy chon

- `API_BASE_URL` (mac dinh: `http://localhost:8000`)
- `DEPLOY_HEALTH_TIMEOUT_SECONDS` (mac dinh: `60`)
- `SMOKE_TEST_STAGING_8001=1` de bat test cong 8001
- `STAGING_API_BASE_URL` (mac dinh: `http://localhost:8001`)

## Troubleshoot nhanh

- Xem container:
```bash
docker compose ps
```

- Xem log API:
```bash
docker compose logs --tail=200 api
```

- Kiem tra health thu cong:
```bash
curl -i http://localhost:8000/api/healthz
curl -i http://localhost:8000/api/readyz
```

- Chay smoke test rieng:
```bash
bash ./scripts/smoke_test.sh
```

## Chay local

```bash
docker compose up -d --build
bash ./scripts/smoke_test.sh
```
