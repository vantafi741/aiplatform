# RUNBOOK – Smoke test E2E (scheduler + publish pipeline)

**Mục đích:** Chứng minh scheduler + publish pipeline hoạt động end-to-end.

**Script:** `scripts/smoke_e2e.sh`

**Điều kiện:** API đang chạy (vd. `docker compose up -d` tại repo root), port 8000.

---

## Cách chạy

```bash
# Từ thư mục gốc repo (vd. /opt/aiplatform)
chmod +x scripts/smoke_e2e.sh

# Mặc định: BASE_URL=http://127.0.0.1:8000, TENANT_NAME=SmokeE2E, INDUSTRY=Tech
./scripts/smoke_e2e.sh

# Tùy biến
BASE_URL=http://localhost:8000 TENANT_NAME="My Tenant" INDUSTRY="Retail" ./scripts/smoke_e2e.sh
```

**Flow script:**
1. GET /health
2. POST /api/tenants → lấy tenant_id
3. POST /api/onboarding (industry profile)
4. POST /api/plans/generate → lấy plan_id
5. POST /api/plans/{plan_id}/materialize
6. GET /content/list?tenant_id=... → lấy content_id đầu tiên
7. POST /content/{content_id}/approve
8. POST /content/{content_id}/schedule (scheduled_at = now + 1 phút)
9. Sleep 90s (chờ scheduler tick và gọi publish)
10. GET /publish/logs và GET /audit/events → in kết quả

**Lưu ý:** Nếu không cấu hình Facebook (FACEBOOK_PAGE_ID, FACEBOOK_ACCESS_TOKEN), bước publish có thể **fail** (media_required hoặc facebook_not_configured); script vẫn in logs/audit để kiểm tra scheduler đã pick item và gọi publish.

---

## Verify trên VPS (feature lead-gdrive-assets)

Chạy **một lần** script verify (migrations + security + smoke + logging trace). Trên VPS cần `chmod +x` lần đầu (hoặc sau mỗi lần pull nếu file chưa executable):

```bash
cd /opt/aiplatform
chmod +x scripts/verify_vps_lead_gdrive.sh scripts/smoke_e2e.sh
./scripts/verify_vps_lead_gdrive.sh
```

Script sẽ:
1. In `docker compose ps`, `ss -lntp`, `ufw status` → lưu `/tmp/verify_ports_ufw.txt`
2. Chạy `alembic upgrade head` trong container (workdir `/app`)
3. Chạy `scripts/smoke_e2e.sh` → lưu `/tmp/smoke_e2e_output.txt`
4. Trích log scheduler/publish → lưu `/tmp/publish_trace.txt`

Sau đó **paste** nội dung vào hai phần dưới đây.

---

## Output mẫu (smoke E2E)

Paste nội dung **/tmp/smoke_e2e_output.txt** vào đây (bằng chứng smoke pass/fail).

<details>
<summary>Click để mở: paste /tmp/smoke_e2e_output.txt vào đây</summary>

```
===== /tmp/smoke_e2e_output.txt =====
=== Smoke E2E (scheduler + publish pipeline) ===
BASE_URL=http://127.0.0.1:8000  TENANT_NAME=SmokeE2E  INDUSTRY=Tech

[1/10] GET /health
  OK
[2/10] POST /api/tenants
  tenant_id=c02f66b8-a788-45d9-af04-f5e53dd35622
[3/10] POST /api/onboarding
  OK
[4/10] POST /api/plans/generate
  plan_id=e09862c5-c88c-467e-ac3d-665f4f86aa9c
[5/10] POST /api/plans/e09862c5-c88c-467e-ac3d-665f4f86aa9c/materialize
  {"plan_id":"e09862c5-c88c-467e-ac3d-665f4f86aa9c","content_plans_created":30,"content_items_created":30}
[6/10] GET /content/list?tenant_id=c02f66b8-a788-45d9-af04-f5e53dd35622
  content_id=58f6f0b3-16b5-412d-8437-762516aff955
[7/10] POST /content/58f6f0b3-16b5-412d-8437-762516aff955/approve
  OK
[8/10] POST /content/58f6f0b3-16b5-412d-8437-762516aff955/schedule (scheduled_at=2026-02-20T07:43:57Z)
  {"content_id":"58f6f0b3-16b5-412d-8437-762516aff955","schedule_status":"scheduled","scheduled_at":"2026-02-20T07:43:57Z"}
[9/10] Waiting 90s for scheduler tick...
[10/10] GET /publish/logs and /audit/events
--- /publish/logs?tenant_id=c02f66b8-a788-45d9-af04-f5e53dd35622&limit=10 ---
{"tenant_id":"c02f66b8-a788-45d9-af04-f5e53dd35622","logs":[{"id":"71457a30-702d-4b13-9f7b-bb5adc2478ca","content_id":"58f6f0b3-16b5-412d-8437-762516aff955","platform":"facebook","post_id":null,"status":"fail","error_message":"media_required","published_at":null,"created_at":"2026-02-20T07:44:25.746026Z"}]}
--- /audit/events?tenant_id=c02f66b8-a788-45d9-af04-f5e53dd35622&limit=20 ---
{"tenant_id":"c02f66b8-a788-45d9-af04-f5e53dd35622","events":[{"id":"3f53a2d8-9f1e-48ab-a0b7-64c1935d9928","tenant_id":"c02f66b8-a788-45d9-af04-f5e53dd35622","content_id":"58f6f0b3-16b5-412d-8437-762516aff955","event_type":"PUBLISH_REQUESTED","actor":"SYSTEM","metadata":{"platform":"facebook"},"created_at":"2026-02-20T07:44:25.746026Z"},{"id":"4f90802f-d28c-427a-83b2-0592fcc7f076","tenant_id":"c02f66b8-a788-45d9-af04-f5e53dd35622","content_id":"58f6f0b3-16b5-412d-8437-762516aff955","event_type":"PUBLISH_FAIL","actor":"SYSTEM","metadata":{"error":"media_required","platform":"facebook"},"created_at":"2026-02-20T07:44:25.746026Z"},{"id":"50137248-4470-4904-a75a-00eace1e2554","tenant_id":"c02f66b8-a788-45d9-af04-f5e53dd35622","content_id":"58f6f0b3-16b5-412d-8437-762516aff955","event_type":"SCHEDULE_SET","actor":"HUMAN","metadata":{"scheduled_at":"2026-02-20T07:43:57+00:00"},"created_at":"2026-02-20T07:42:57.565685Z"},{"id":"bc0dd804-0a06-4889-bbd5-8fbaef0c72e8","tenant_id":"c02f66b8-a788-45d9-af04-f5e53dd35622","content_id":"58f6f0b3-16b5-412d-8437-762516aff955","event_type":"APPROVED","actor":"HUMAN","metadata":{"approved_at":"2026-02-20T07:42:57.445233+00:00"},"created_at":"2026-02-20T07:42:57.440788Z"}]}
=== Smoke E2E done ===
```

</details>

---

## Chạy thủ công (không dùng verify script)

```bash
cd /opt/aiplatform
docker compose up -d --force-recreate api postgres redis
# Đợi API healthy (vd. 15–20s)
docker exec ai-content-director-api sh -c "cd /app && alembic upgrade head"
chmod +x scripts/smoke_e2e.sh
./scripts/smoke_e2e.sh | tee /tmp/smoke_e2e_output.txt
```

---

## Publish trace (logging verify)

Paste **mẫu** từ `/tmp/publish_trace.txt` (chứng minh `scheduler.tick`, `scheduler.publish_result`, `facebook_publish.calling|success|fail` và `correlation_id`).

<details>
<summary>Click để mở: paste trích đoạn /tmp/publish_trace.txt</summary>

```
===== /tmp/publish_trace.txt =====
2026-02-20T07:42:25.708314Z [info     ] scheduler.tick                 eligible_count=0
2026-02-20T07:43:25.717999Z [info     ] scheduler.tick                 eligible_count=0
2026-02-20T07:44:25.730539Z [info     ] scheduler.tick                 eligible_count=1
2026-02-20T07:44:25.815200Z [info     ] scheduler.publish_result       attempt=1 content_id=58f6f0b3-16b5-412d-8437-762516aff955 correlation_id=d50b242b-5e6c-4b81-ba9a-6374d6083d32 endpoint=facebook_publish_post error_message=media_required next_at=2026-02-20T07:54:25.804667+00:00 status=retry_scheduled
```

</details>

---

## Nếu smoke E2E fail

- Ghi rõ **step nào** (1–10), **endpoint nào** (URL + method), **log/trace** liên quan (vd. từ `/tmp/smoke_e2e_output.txt` hoặc `docker logs ai-content-director-api`).
- Fix tối thiểu cần thiết (code hoặc config), rồi commit: `fix: make smoke_e2e pass on VPS`.
- Chạy lại `./scripts/verify_vps_lead_gdrive.sh` và paste lại output mẫu vào các phần trên.
