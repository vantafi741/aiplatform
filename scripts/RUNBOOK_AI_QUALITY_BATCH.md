# Runbook: API bằng Docker Compose + AI Quality Batch

Mục tiêu: Chạy FastAPI qua Docker (không dùng venv), rồi chạy batch đánh giá chất lượng AI và xác nhận 2 file JSON được ghi đè bằng response thật.

## Điều kiện

- Docker Desktop đã cài và đang chạy (để lệnh `docker` có trong PATH).
- Python 3 trên host để chạy `scripts/run_ai_quality_evaluation_batch.py`.

---

## Bước 1: Build và khởi động stack

Từ thư mục **ai_content_director** (có file `docker-compose.yml`):

```powershell
cd d:\ai-ecosystem\ai_content_director
docker compose up -d --build
docker compose run --rm api alembic upgrade head
```

Đợi vài phút cho postgres healthy và API start.

---

## Bước 2: Kiểm tra server

```powershell
# PowerShell
Invoke-RestMethod -Uri "http://127.0.0.1:8000/health"
```

Hoặc dùng trình duyệt: http://127.0.0.1:8000/health

Nếu không lên, xem log:

```powershell
cd d:\ai-ecosystem\ai_content_director
docker compose logs --tail 200 api
```

---

## Bước 3: TENANT_ID

- Nếu đã có tenant: set biến môi trường `TENANT_ID=<uuid>`.
- Nếu chưa có: gọi POST /onboarding một lần để tạo tenant và lấy `tenant_id`:

```powershell
$body = @{
  tenant_name = "Eval Tenant"
  industry = "Marketing"
  brand_tone = "Thân thiện, chuyên nghiệp"
  main_services = @("Content", "Ads")
  target_customer = "SME"
  cta_style = "Rõ ràng, kêu gọi hành động"
} | ConvertTo-Json
Invoke-RestMethod -Uri "http://127.0.0.1:8000/onboarding" -Method Post -Body $body -ContentType "application/json"
```

Từ response, lấy `tenant.id` và set: `$env:TENANT_ID = "<tenant_id>"`.

---

## Bước 4: Chạy batch từ host

```powershell
cd d:\ai-ecosystem
# Đặt TENANT_ID nếu chưa set (thay <uuid> bằng id thật)
$env:TENANT_ID = "<uuid>"
python scripts/run_ai_quality_evaluation_batch.py
```

Hoặc: `python scripts/run_ai_quality_evaluation_batch.py <tenant_id>`

---

## Bước 5: Xác nhận output

Hai file sau phải được ghi đè với response thật từ API:

- `scripts/evaluation_planner_7d.json` — có `used_ai`, `used_fallback`, `model`, `items` (7 ngày).
- `scripts/evaluation_content_6.json` — có `used_ai`, `used_fallback`, `model`, `items` (6 bài).

Kiểm tra nhanh: trong file không còn `"used_ai":false,"used_fallback":false,"model":null` với dữ liệu placeholder.

---

## Bước 6: Deliverables (báo cáo)

In ra:

1. **Output /health** — nội dung trả về từ `GET http://127.0.0.1:8000/health`.
2. **Tenant ID đã dùng** — giá trị `TENANT_ID` khi chạy batch.
3. **Console summary từ batch** — phần PLANNER SUMMARY, CONTENT SUMMARY, VALIDATION (và lỗi nếu có).
4. **~40 dòng đầu mỗi file JSON** — đủ để thấy `used_ai`/`used_fallback`/`model` và 2 item đầu.

**Chạy một lệnh (sau khi Docker đã up):** từ repo root:

```powershell
cd d:\ai-ecosystem
.\scripts\run_full_evaluation.ps1
```

Script sẽ: gọi /health, tạo tenant (nếu chưa có TENANT_ID), chạy batch, in ~40 dòng đầu mỗi JSON.
