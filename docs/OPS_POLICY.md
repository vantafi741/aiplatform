# OPS Policy - n8n-only Orchestration

## Muc tieu

Tranh double-run pipeline publish bang cach su dung **mot control-plane duy nhat**:

- `n8n` la control-plane duy nhat cho orchestration.
- Internal in-process scheduler trong API mac dinh **tat**.

## Runtime Policy

1. **Mac dinh OFF tuyet doi**
   - Bien moi truong: `ENABLE_INTERNAL_SCHEDULER=0` (hoac khong set).
   - Khi app startup, scheduler service phai log:
     - `scheduler.disabled`
     - reason: `Scheduler disabled (n8n control-plane)`

2. **Chi bat khi explicit opt-in**
   - Chi khi set `ENABLE_INTERNAL_SCHEDULER=1`, internal scheduler moi duoc chay.
   - Day la che do debug/khac biet, khong phai production-default.

3. **Lock/Conflict policy**
   - Neu internal scheduler dang `enabled=true` va endpoint
     `/api/scheduler/run_publish_tick` van duoc goi (thuong tu n8n),
     he thong phai ghi log **ERROR**:
     - event: `scheduler.policy_conflict`
   - Muc dich: canh bao nguy co double-run.

## Van hanh de xuat (production)

- `docker-compose.yml` dat:
  - `ENABLE_INTERNAL_SCHEDULER: "0"`
- n8n goi endpoint:
  - `POST /api/scheduler/run_publish_tick`

## Smoke test nhanh

1) Kiem tra startup log (scheduler OFF):

```bash
docker compose logs --tail=200 api | grep -E "scheduler.disabled|n8n control-plane"
```

2) Goi tay tick endpoint (van chay binh thuong):

```bash
curl -sS -X POST "http://127.0.0.1:8000/api/scheduler/run_publish_tick" \
  -H "Content-Type: application/json" \
  -d '{"batch_size": 1}'
```

Ky vong: HTTP 200 + JSON co `ok`, `processed`, `skipped`, `errors`, `now_utc`.
