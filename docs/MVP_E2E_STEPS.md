# MVP E2E – Các bước chạy end-to-end (ai_content_director)

**Base URL:** `http://127.0.0.1:8000`  
**Điều kiện:** Server đang chạy (vd. `.\scripts\run_mvp_local.ps1` hoặc `./scripts/run_mvp_local.sh`).

---

## 1. POST /onboarding

Tạo tenant và brand profile trong một request.

**Request:**

```bash
curl -s -X POST "http://127.0.0.1:8000/onboarding" \
  -H "Content-Type: application/json" \
  -d '{
    "tenant_name": "Tenant E2E",
    "industry": "Cơ khí chế tạo",
    "brand_tone": "Chuyên nghiệp, thân thiện",
    "main_services": ["Gia công CNC", "Khuôn dập"],
    "target_customer": "Doanh nghiệp SME",
    "cta_style": "Liên hệ ngay để nhận báo giá"
  }'
```

**Response (201):** JSON có `tenant.id` và `brand_profile.id`. Lưu `tenant.id` làm `TENANT_ID` cho các bước sau.

**Ví dụ lưu TENANT_ID (bash, cần `jq`):**

```bash
export TENANT_ID=$(curl -s -X POST "http://127.0.0.1:8000/onboarding" \
  -H "Content-Type: application/json" \
  -d '{"tenant_name":"Tenant E2E","industry":"Cơ khí","brand_tone":"","main_services":[],"target_customer":"","cta_style":""}' \
  | jq -r '.tenant.id')
echo "TENANT_ID=$TENANT_ID"
```

**PowerShell (không cần jq):**

```powershell
$r = Invoke-RestMethod -Uri "http://127.0.0.1:8000/onboarding" -Method Post -ContentType "application/json" -Body '{"tenant_name":"Tenant E2E","industry":"Cơ khí","brand_tone":"","main_services":[],"target_customer":"","cta_style":""}'
$env:TENANT_ID = $r.tenant.id
Write-Host "TENANT_ID=$($env:TENANT_ID)"
```

---

## 2. POST /planner/generate (days=7)

Sinh kế hoạch nội dung 7 ngày (cost guard: tối đa 30 ngày).

**Request:**

```bash
curl -s -X POST "http://127.0.0.1:8000/planner/generate?force=false&ai=true" \
  -H "Content-Type: application/json" \
  -d "{\"tenant_id\": \"$TENANT_ID\", \"days\": 7}"
```

**Windows (PowerShell):** thay `$TENANT_ID` bằng `$env:TENANT_ID` trong body.

**Response (201):** `tenant_id`, `created`, `items` (danh sách `day_number`, `topic`, `content_angle`, `status`), `used_ai`, `used_fallback`, `model`.

**Ví dụ đầy đủ (thay `YOUR_TENANT_ID`):**

```bash
curl -s -X POST "http://127.0.0.1:8000/planner/generate?force=false&ai=true" \
  -H "Content-Type: application/json" \
  -d '{"tenant_id": "YOUR_TENANT_ID", "days": 7}'
```

---

## 3. POST /content/generate-samples

Sinh một số bài mẫu (draft). Cost guard: tối đa 20 bài.

**Request:**

```bash
curl -s -X POST "http://127.0.0.1:8000/content/generate-samples?force=false&ai=true" \
  -H "Content-Type: application/json" \
  -d "{\"tenant_id\": \"$TENANT_ID\", \"count\": 6}"
```

**Response (201):** `tenant_id`, `created`, `items` (mỗi item có `id`, `title`, `caption`, `hashtags`, `status`, `confidence_score`, …). Lưu một `items[].id` làm `CONTENT_ID` cho bước approve và publish.

**Ví dụ lưu CONTENT_ID (bash, jq):**

```bash
export CONTENT_ID=$(curl -s -X POST "http://127.0.0.1:8000/content/generate-samples?force=false&ai=true" \
  -H "Content-Type: application/json" \
  -d "{\"tenant_id\": \"$TENANT_ID\", \"count\": 6}" \
  | jq -r '.items[0].id')
echo "CONTENT_ID=$CONTENT_ID"
```

**Ví dụ (thay YOUR_TENANT_ID):**

```bash
curl -s -X POST "http://127.0.0.1:8000/content/generate-samples?force=false&ai=true" \
  -H "Content-Type: application/json" \
  -d '{"tenant_id": "YOUR_TENANT_ID", "count": 6}'
```

---

## 4. POST /content/{content_id}/approve

Duyệt nội dung (HITL). Chỉ content đã approved mới được gửi lên Facebook.

**Request:**

```bash
curl -s -X POST "http://127.0.0.1:8000/content/$CONTENT_ID/approve" \
  -H "Content-Type: application/json" \
  -d "{\"tenant_id\": \"$TENANT_ID\", \"actor\": \"HUMAN\"}"
```

**Ví dụ (thay YOUR_TENANT_ID và YOUR_CONTENT_ID):**

```bash
curl -s -X POST "http://127.0.0.1:8000/content/YOUR_CONTENT_ID/approve" \
  -H "Content-Type: application/json" \
  -d '{"tenant_id": "YOUR_TENANT_ID", "actor": "HUMAN"}'
```

**Response (200):** JSON content item đã cập nhật (status=approved).

---

## 5. POST /publish/facebook (đăng ngay) hoặc schedule

### 5a. Đăng ngay lên Facebook

Chỉ thành công khi đã cấu hình `FACEBOOK_PAGE_ID` và `FACEBOOK_ACCESS_TOKEN` trong `ai_content_director/.env`.

**Request:**

```bash
curl -s -X POST "http://127.0.0.1:8000/publish/facebook" \
  -H "Content-Type: application/json" \
  -d "{\"tenant_id\": \"$TENANT_ID\", \"content_id\": \"$CONTENT_ID\"}"
```

**Ví dụ (thay YOUR_TENANT_ID, YOUR_CONTENT_ID):**

```bash
curl -s -X POST "http://127.0.0.1:8000/publish/facebook" \
  -H "Content-Type: application/json" \
  -d '{"tenant_id": "YOUR_TENANT_ID", "content_id": "YOUR_CONTENT_ID"}'
```

**Response (200):** `tenant_id`, `content_id`, `log_id`, `status` (queued | success | fail), `post_id`, `error_message`.

### 5b. Lên lịch đăng (scheduler trong app sẽ tự đăng khi đến giờ)

**Request:** POST /content/{content_id}/schedule với `scheduled_at` (ISO datetime, UTC hoặc Asia/Ho_Chi_Minh).

```bash
# Ví dụ: đăng lúc 14:00 cùng ngày (Asia/Ho_Chi_Minh)
# scheduled_at phải la ISO 8601, vd. 2025-02-17T14:00:00+07:00
curl -s -X POST "http://127.0.0.1:8000/content/$CONTENT_ID/schedule" \
  -H "Content-Type: application/json" \
  -d "{\"tenant_id\": \"$TENANT_ID\", \"scheduled_at\": \"2025-02-17T14:00:00+07:00\"}"
```

Sau khi schedule, scheduler (chạy trong process API, tick 60s) sẽ tự gọi publish khi `scheduled_at` đến.

---

## Thứ tự tóm tắt

| Bước | Method + Path | Mục đích |
|------|----------------|----------|
| 1 | POST /onboarding | Tạo tenant + brand_profile → lấy `tenant.id` |
| 2 | POST /planner/generate?days=7&ai=true | Sinh plan 7 ngày |
| 3 | POST /content/generate-samples?ai=true | Sinh 6 bài mẫu → lấy `items[].id` |
| 4 | POST /content/{id}/approve | Duyệt 1 bài |
| 5a | POST /publish/facebook | Đăng ngay lên Facebook (cần FACEBOOK_* env) |
| 5b | POST /content/{id}/schedule | Lên lịch đăng (scheduler sẽ đăng khi đến giờ) |

---

## Một số endpoint bổ sung

- **GET /health** – Kiểm tra server sống.
- **GET /content/list?tenant_id=...** – Liệt kê content (có thể lọc `?status=draft|approved|published`).
- **POST /content/{id}/reject** – Từ chối bài (body: `tenant_id`, `actor`, `reason`).
- **GET /publish/logs?tenant_id=...** – Xem lịch sử đăng.
- **GET /scheduler/status** – Trạng thái scheduler (tick 60s).
- **GET /audit/events?tenant_id=...** – Lịch sử audit (approve, publish, …).

---

*Tài liệu chuẩn cho MVP E2E; entrypoint runtime là **ai_content_director** (xem README_ROOT.md).*
