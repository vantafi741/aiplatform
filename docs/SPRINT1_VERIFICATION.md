# Sprint 1 – Definition of Done Verification

**Ngày kiểm tra:** 2025-02-16  
**Phương pháp:** Review code + cấu hình. Docker không chạy được trên môi trường kiểm tra (Docker không có trong PATH).

---

## 1) Docker services

| Service   | Trạng thái | Ghi chú |
|-----------|------------|--------|
| postgres  | **PASS**   | `docker-compose.yml` có service `postgres` (image postgres:15-alpine), port 5432, healthcheck `pg_isready`. |
| redis     | **PASS**   | `docker-compose.yml` có service `redis` (image redis:7-alpine), port 6379, healthcheck `redis-cli ping`. |
| api       | **PASS**   | API chạy ngoài Docker bằng `uvicorn api.main:app` (đúng runbook README). Không nằm trong compose là thiết kế hiện tại. |

**Kết luận:** PASS. Khi chạy `docker compose up -d` thì postgres và redis đủ để chạy local; API chạy tay theo README.

---

## 2) Health endpoint

| Yêu cầu                    | Trạng thái | Chi tiết |
|----------------------------|------------|----------|
| GET /health trả {"status":"ok"} | **PASS**   | `api/routers/health.py`: `return {"status": "ok", "service": "ai-content-director"}`. Response có đúng key `"status": "ok"`. |

**Kết luận:** PASS.

---

## 3) Database

| Bảng            | Trạng thái | Nguồn |
|-----------------|------------|--------|
| tenants         | **PASS**   | `migrations/versions/20250216000000_schema_v1.py` – `op.create_table("tenants", ...)`. |
| brand_profiles  | **PASS**   | Cùng file – `op.create_table("brand_profiles", ...)`. |
| jobs            | **PASS**   | Cùng file – `op.create_table("jobs", ...)`. |
| job_runs        | **PASS**   | Cùng file – `op.create_table("job_runs", ...)`. |
| audit_logs     | **PASS**   | Cùng file – `op.create_table("audit_logs", ...)`. |

**Kết luận:** PASS. Migration schema v1 tạo đủ 5 bảng, có FK và index đúng.

---

## 4) API

| Endpoint / hành vi | Trạng thái | Chi tiết |
|--------------------|------------|----------|
| POST /tenants hoạt động | **PASS**   | `api/routers/tenants.py`: nhận TenantCreate, tạo Tenant, commit, gọi audit_log, trả TenantResponse 201. |
| POST /jobs hoạt động    | **PASS**   | `api/routers/jobs.py`: nhận JobCreate, tạo Job (status queued), enqueue RQ, audit_log, trả JobResponse 201. Nếu Redis lỗi trả 503. |
| GET /jobs/{id}          | **PASS**   | `api/routers/jobs.py`: get job by UUID, trả 404 nếu không có. |
| Trạng thái queued → running → success | **PASS** | `workers/tasks.py`: cập nhật job status = running, tạo JobRun, sleep 2s, cập nhật job + run = success; khi exception cập nhật = fail và audit. |

**Kết luận:** PASS. Đủ endpoint và luồng trạng thái job.

---

## 5) Logging

| Yêu cầu           | Trạng thái | Chi tiết |
|-------------------|------------|----------|
| Log JSON format   | **PASS**   | `shared/logging_config.py`: `JsonFormatter` xuất một dòng JSON (timestamp, level, logger, message, correlation_id, exception/extra_fields). `setup_logging(log_json=True)` dùng formatter này. |
| Có correlation_id | **PASS**   | ContextVar `correlation_id_var`; middleware `api/main.py` set từ header `X-Correlation-ID` hoặc UUID mới; JsonFormatter thêm `correlation_id` vào mỗi log. Worker set `correlation_id` = `job-{job_id[:8]}`. |
| Có audit_log entry| **PASS**   | `shared/audit.py` ghi vào bảng `audit_logs` với correlation_id. Được gọi tại: POST tenant (tenant.create), POST job (job.create), worker success (job.completed), worker fail (job.failed). |

**Kết luận:** PASS.

---

## Tổng kết

| Mục              | Kết quả |
|------------------|---------|
| 1) Docker services | **PASS** |
| 2) Health endpoint | **PASS** |
| 3) Database        | **PASS** |
| 4) API             | **PASS** |
| 5) Logging         | **PASS** |

**Sprint 1 đạt Definition of Done** (xác minh bằng code và cấu hình).

---

## Ghi chú thêm

- **Chạy thực tế:** Trên máy có Docker và Python env, sau khi `docker compose up -d` và `alembic upgrade head`, chạy API + worker rồi chạy `scripts/smoke_test.ps1` (hoặc curl theo README) để xác nhận end-to-end.
- **Không sửa code:** Không phát hiện lỗi nghiêm trọng; không đề xuất thay đổi code cho DoD này.
