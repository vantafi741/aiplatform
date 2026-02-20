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
# Paste output của: cat /tmp/smoke_e2e_output.txt
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
# Paste trích đoạn: docker logs --tail=800 ai-content-director-api 2>&1 | grep -E "scheduler\.tick|scheduler\.publish_result|facebook_publish\.(calling|success|fail)" | tail -n 200
```

</details>

---

## Nếu smoke E2E fail

- Ghi rõ **step nào** (1–10), **endpoint nào** (URL + method), **log/trace** liên quan (vd. từ `/tmp/smoke_e2e_output.txt` hoặc `docker logs ai-content-director-api`).
- Fix tối thiểu cần thiết (code hoặc config), rồi commit: `fix: make smoke_e2e pass on VPS`.
- Chạy lại `./scripts/verify_vps_lead_gdrive.sh` và paste lại output mẫu vào các phần trên.
