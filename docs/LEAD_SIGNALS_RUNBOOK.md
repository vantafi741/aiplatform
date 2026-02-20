# Lead Signals – Runbook (B2B KPI & AI Lead System)

Bảng `public.lead_signals` lưu sự kiện lead từ comment/inbox. **AI Lead System**: Facebook webhook → classify intent (rule-first, LLM optional) → lead_signals → n8n follow-up khi priority=high.

---

## 1) Cấu hình ENV (AI Lead System)

Thêm vào `.env` (hoặc env của container):

```bash
# n8n webhook: gọi khi priority=high để tạo follow-up task (optional)
WEBHOOK_URL=https://your-n8n-instance/webhook/lead-follow-up

# Classify intent: true = gọi LLM khi rule không match; false = chỉ rule
LEAD_CLASSIFY_USE_LLM=false

# Timeouts (seconds)
LEAD_CLASSIFY_LLM_TIMEOUT_SECONDS=6
N8N_WEBHOOK_TIMEOUT_SECONDS=5
```

- **WEBHOOK_URL**: Để trống thì không gọi n8n; set URL thì khi lead có `priority=high` API sẽ POST payload lên URL này. Timeout clamp 3–10s (N8N_WEBHOOK_TIMEOUT_SECONDS), retry 1.
- **LEAD_CLASSIFY_USE_LLM**: MVP nên `false` (rule-first); bật `true` nếu muốn GPT classify khi intent unknown.
- **LEAD_CLASSIFY_LLM_TIMEOUT_SECONDS**: Timeout gọi LLM khi classify (mặc định 6).
- **N8N_WEBHOOK_TIMEOUT_SECONDS**: Timeout gọi n8n (mặc định 5), clamp 3–10.

---

## 2) Áp dụng migration (Docker)

**Local / VPS:**

```bash
docker compose up -d
docker compose run --rm api alembic upgrade head
```

**Production:**

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d
docker compose -f docker-compose.yml -f docker-compose.prod.yml run --rm api alembic upgrade head
```

**Rollback:**

```bash
docker compose run --rm api alembic downgrade -1
```

---

## 3) API AI Lead System

### 3.1 POST /webhooks/facebook

- **tenant_id**: Ưu tiên header **X-Tenant-ID**, fallback `body.tenant_id`. Log `tenant_id_source` (header | body).
- Parse **entry[]**: mock (message/comment_id/sender_name ở top level) và real (messaging[], changes[].value).
- Dedup theo **external_message_id** (tenant_id + platform + external_message_id unique).

**Ví dụ mock payload:**

```json
{
  "object": "page",
  "entry": [
    {
      "message": "Cho tôi báo giá gói Enterprise",
      "sender_name": "Nguyễn Văn A",
      "sender_id": "123456789",
      "post_id": "post_abc",
      "comment_id": "comment_xyz"
    }
  ]
}
```

**cURL (tenant trong body):**

```bash
curl -X POST http://localhost:8000/webhooks/facebook \
  -H "Content-Type: application/json" \
  -d '{"object":"page","tenant_id":"<TENANT_UUID>","entry":[{"message":"Cho tôi báo giá","sender_name":"Test","sender_id":"u1","post_id":"p1","comment_id":"c1"}]}'
```

**cURL (tenant trong header X-Tenant-ID – ưu tiên):**

```bash
curl -X POST http://localhost:8000/webhooks/facebook \
  -H "Content-Type: application/json" \
  -H "X-Tenant-ID: <TENANT_UUID>" \
  -d '{"object":"page","entry":[{"message":"Cho tôi báo giá","sender_name":"Test","sender_id":"u1","post_id":"p1","comment_id":"c1"}]}'
```

Response: `{"ok": true, "created": 1, "lead_ids": ["<uuid>"]}`.

### 3.2 GET /api/leads

- **tenant_id** (bắt buộc), **status** (optional), **limit**, **offset**.

```bash
curl "http://localhost:8000/api/leads?tenant_id=<TENANT_UUID>&limit=10"
curl "http://localhost:8000/api/leads?tenant_id=<TENANT_UUID>&status=new_auto&limit=10"
```

---

## 4) Luồng xử lý (Facebook → follow-up)

1. **POST /webhooks/facebook**: tenant_id từ X-Tenant-ID (ưu tiên) hoặc body. Log tenant_id_source.
2. Parse entry[] (mock + messaging + changes). Dedup theo external_message_id.
3. Với mỗi message: rule-first classify → intent_label, priority, confidence_score. Nếu unknown và LEAD_CLASSIFY_USE_LLM=true thì gọi LLM (timeout + fallback).
4. Status HITL: >=0.85 → new_auto; 0.70–0.85 → new_draft; <0.70 → new_escalate.
5. Insert lead_signals + audit LEAD_SIGNAL_CREATED (actor=SYSTEM).
6. Nếu priority=high và WEBHOOK_URL có: gọi n8n (timeout 3–5s, retry 1).

---

## 5) Mẫu SQL (dashboard)

```sql
-- Đếm theo status
SELECT status, COUNT(*) AS cnt FROM lead_signals
WHERE tenant_id = :tenant_id AND created_at >= :since GROUP BY status ORDER BY cnt DESC;

-- Đếm theo intent
SELECT intent_label, COUNT(*) AS cnt FROM lead_signals
WHERE tenant_id = :tenant_id AND created_at >= :since GROUP BY intent_label ORDER BY cnt DESC;
```

---

## 6) Smoke test

### 6.1 Pytest (model + webhook + GET leads + dedup)

```bash
cd ai_content_director
pip install -r requirements.txt -r requirements-dev.txt
python -m pytest tests/test_lead_signals_smoke.py -v
```

Kỳ vọng: test_lead_signals_insert_count_and_join, test_webhook_facebook_and_get_leads, test_webhook_dedup đều PASS.

### 6.2 Thủ công (local)

1. Khởi động API + Postgres, migration đã chạy.
2. Lấy `tenant_id` (vd từ `tenants` hoặc POST /onboarding).
3. Gửi webhook (header hoặc body):

   ```bash
   curl -X POST http://localhost:8000/webhooks/facebook \
     -H "Content-Type: application/json" \
     -H "X-Tenant-ID: <TENANT_UUID>" \
     -d '{"object":"page","entry":[{"message":"Tôi muốn báo giá","sender_name":"Smoke","sender_id":"s1","post_id":"p1","comment_id":"smoke-c1"}]}'
   ```

   Kỳ vọng: `created >= 1`, `lead_ids` có 1 phần tử.
4. GET /api/leads: `curl "http://localhost:8000/api/leads?tenant_id=<TENANT_UUID>&limit=5"` → leads có intent_label, priority, confidence_score, status (new_auto | new_draft | new_escalate).
5. Gửi lại cùng payload (cùng comment_id): kỳ vọng `created` = 0 (dedup).
