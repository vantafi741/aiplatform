# Fix Alembic InvalidPasswordError trên VPS (sau merge main)

**Bối cảnh:** Volume Postgres cũ giữ mật khẩu cũ; `POSTGRES_PASSWORD=postgres` trong compose chỉ áp dụng khi **tạo DB mới**. `DATABASE_URL` trong API dùng `postgres:postgres` → mismatch → Alembic fail.

**VPS:** `/opt/aiplatform`, branch `main` tại commit `6042c0c`.

---

## Cách A) Reset DB sạch (xóa volume, tạo lại từ đầu)

**Dùng khi:** Bạn chấp nhận **mất toàn bộ dữ liệu** trong Postgres (tenants, plans, content, logs…). Phù hợp staging / dev hoặc khi data không cần giữ.

### Lệnh (chạy từ `/opt/aiplatform`)

```bash
cd /opt/aiplatform

# 1) Dừng và xóa container + network + volume
docker compose down -v --remove-orphans

# 2) Khởi động lại postgres, redis, api
docker compose up -d postgres redis api

# 3) Đợi Postgres + Redis healthy (compose đã có healthcheck)
sleep 15

# 4) Chạy migration (DB mới nên password = postgres)
docker exec ai-content-director-api sh -c 'cd /app && alembic upgrade head'

# 5) Health check
curl -s http://127.0.0.1:8000/api/healthz
curl -s http://127.0.0.1:8000/api/readyz

# 6) Smoke E2E
chmod +x scripts/smoke_e2e.sh scripts/verify_vps_lead_gdrive.sh
./scripts/smoke_e2e.sh
```

**Output mong đợi (tóm tắt):**
- `alembic upgrade head`: in các revision (001 → 013) hoặc "Running upgrade ... -> 013".
- `curl .../api/healthz`: HTTP 200, body có `"status":"ok"`.
- `curl .../api/readyz`: HTTP 200, body có `"status":"ok"` (hoặc tương đương).
- `smoke_e2e.sh`: [1/10]–[10/10] chạy; có thể fail bước publish (media_required) nhưng flow tenant → plan → content → approve → schedule → logs/audit in ra đầy đủ.

---

## Cách B) Giữ DB (đổi mật khẩu Postgres cho khớp `postgres:postgres`)

**Dùng khi:** Cần **giữ dữ liệu** hiện có; chỉ sửa mật khẩu user `postgres` trong container cho đúng với `DATABASE_URL`.

### Lệnh (chạy từ `/opt/aiplatform`)

```bash
cd /opt/aiplatform

# 1) Đặt lại mật khẩu user postgres trong container (khớp với DATABASE_URL)
docker exec -it ai-ecosystem-postgres psql -U postgres -d ai_content_director -c "ALTER USER postgres WITH PASSWORD 'postgres';"

# 2) Restart API để dùng lại connection pool với password mới
docker compose restart api

# 3) Đợi API qua healthcheck
sleep 20

# 4) Kiểm tra kết nối (asyncpg) qua readyz (readyz gọi DB)
curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:8000/api/readyz
# Kỳ vọng: 200

# 5) Chạy migration
docker exec ai-content-director-api sh -c 'cd /app && alembic upgrade head'

# 6) Health
curl -s http://127.0.0.1:8000/api/healthz
curl -s http://127.0.0.1:8000/api/readyz

# 7) Smoke E2E
chmod +x scripts/smoke_e2e.sh scripts/verify_vps_lead_gdrive.sh
./scripts/smoke_e2e.sh
```

**Lưu ý:** Nếu lúc chạy cách B mà container postgres chưa chạy (vd. vừa `up -d`), đợi healthy rồi mới chạy `ALTER USER`:

```bash
docker compose up -d postgres redis
sleep 10
docker exec ai-ecosystem-postgres psql -U postgres -d ai_content_director -c "ALTER USER postgres WITH PASSWORD 'postgres';"
docker compose up -d api
sleep 20
# ... tiếp bước 4–7 ở trên
```

**Output mong đợi (tóm tắt):**
- `ALTER USER`: in `ALTER ROLE`.
- `alembic upgrade head`: "Already at head" hoặc chạy các revision còn thiếu.
- Health/readyz: 200, body ok.
- Smoke E2E: giống cách A.

---

## Sau khi fix: chạy verify script

```bash
cd /opt/aiplatform
./scripts/verify_vps_lead_gdrive.sh
```

**Output mong đợi (tóm tắt):**
- **1) Security verify:** `docker compose ps` có api/postgres/redis Up; `ss -lntp` có 127.0.0.1:5432, 127.0.0.1:6379, 0.0.0.0:8000 (hoặc tương đương); ufw in ra (nếu có).
- **2) Migrations:** `alembic upgrade head` in "Already at head" hoặc upgrade thành công.
- **3) Smoke E2E:** Script chạy [1/10]–[10/10]; exit 0 hoặc exit khác 0 nếu publish fail (media_required) – vẫn coi pipeline OK nếu scheduler + audit đã ghi.
- **4) Publish trace:** Có dòng `scheduler.tick`, `scheduler.publish_result` (vd. với correlation_id).
- **Kết luận ports:** [OK] Postgres bind 127.0.0.1:5432, [OK] Redis bind 127.0.0.1:6379.

---

## So sánh nhanh

| Tiêu chí           | A) Reset DB      | B) Giữ DB              |
|--------------------|------------------|-------------------------|
| Dữ liệu            | Mất hết          | Giữ nguyên             |
| Thời gian          | Nhanh            | Rất nhanh (chỉ ALTER)  |
| Rủi ro             | Chỉ mất data     | Sai password có thể lock |
| Dùng khi           | Staging/dev, OK mất data | Production / cần giữ data |

---

## Nếu vẫn lỗi sau cách B

- Kiểm tra `DATABASE_URL` trong api có đúng `postgres:postgres@postgres:5432/ai_content_director` (không lẫn host/password khác).
- Vào container postgres: `docker exec -it ai-ecosystem-postgres psql -U postgres -d ai_content_director -c "\du"` và thử đăng nhập với password mới.
- Xem log API: `docker logs --tail=100 ai-content-director-api` để đọc lỗi asyncpg/Alembic chi tiết.
