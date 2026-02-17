# Sprint 2 – Deliverables

## 1) Danh sách file thay đổi (kèm lý do)

| File | Lý do |
|------|--------|
| **Migration** | |
| `migrations/versions/20250216000001_sprint2_brand_kb.py` | Mới. Thêm cột onboarding vào brand_profiles; tạo bảng kb_items, idempotency_keys. |
| **Models** | |
| `shared/models.py` | Bổ sung field onboarding (business_name, industry, uvp, persona, tone_of_voice, cta_style, taboo_words, compliance_notes, language, version) cho BrandProfile; thêm model KbItem, IdempotencyKey. |
| **RAG** | |
| `shared/rag.py` | Mới. VectorStoreAdapter interface + PostgresKbAdapter (fallback ILIKE + ranking đơn giản). |
| **Schemas** | |
| `api/schemas/brand_profile.py` | Mới. BrandProfileCreate, BrandProfileUpdate, BrandProfileResponse. |
| `api/schemas/onboarding.py` | Mới. OnboardingRequest, OnboardingResponse. |
| `api/schemas/kb.py` | Mới. KbItemCreate, KbItemResponse, KbBulkIngest*, KbQueryRequest/Response, KbContext. |
| **Routers** | |
| `api/routers/brand_profiles.py` | Mới. GET/POST/PUT brand profile theo tenant_id; audit brand_profile.upsert. |
| `api/routers/onboarding.py` | Mới. POST /onboarding; idempotency qua header Idempotency-Key. |
| `api/routers/kb.py` | Mới. POST /kb/items, POST /kb/bulk_ingest, GET /kb/items, POST /kb/query. |
| **App** | |
| `api/main.py` | Đăng ký router brand_profiles, onboarding, kb; version 0.2.0. |
| **Docs / Playbook** | |
| `docs/prompt_playbook_v1.json` | Mới. Template prompt + brand_rules + output_schema + example_output. |
| **Scripts / Runbook** | |
| `scripts/smoke_test_s2.ps1` | Mới. Smoke test S2: onboarding → bulk_ingest 30 FAQ → query → idempotency. |
| `README.md` | Cập nhật endpoints S2, smoke test S2, prompt playbook, cấu trúc. |
| `docs/SPRINT2_DELIVERABLES.md` | Mới. File này. |

---

## 2) Code implement đầy đủ

Toàn bộ code nằm trong các file liệt kê trên. Điểm chính:

- **Brand Profile v1:** Migration thêm cột; API GET (list + by id), POST, PUT; audit `brand_profile.upsert` khi tạo/cập nhật.
- **Onboarding:** POST /onboarding body `{ tenant, brand_profile }`; header `Idempotency-Key` lưu vào `idempotency_keys`; replay trả cùng tenant_id.
- **KB FAQ:** Bảng `kb_items`; POST /kb/items, POST /kb/bulk_ingest, GET /kb/items?tenant_id=&q=.
- **RAG stub:** VectorStoreAdapter.retrieve() trả (contexts, citations); PostgresKbAdapter dùng ILIKE question/answer, ranking theo từ khóa; POST /kb/query trả top_k contexts + citations.
- **Prompt Playbook:** docs/prompt_playbook_v1.json với system_prompt_template, brand_rules, output_schema, example_output.

---

## 3) Hướng dẫn chạy local (commands)

```bash
# 1. Cấu hình
cp .env.example .env

# 2. Postgres + Redis
docker compose up -d

# 3. Venv + deps
python -m venv venv
venv\Scripts\activate   # Windows
pip install -r requirements.txt

# 4. Migrations (Sprint 1 + 2)
alembic upgrade head

# 5. API
uvicorn api.main:app --reload --host 0.0.0.0 --port 8000

# 6. (Tùy chọn) Worker – terminal khác
python -m workers.worker
```

---

## 4) Smoke test S2 – steps và kết quả mong đợi

**Chạy:** `.\scripts\smoke_test_s2.ps1` (từ thư mục gốc, API đang chạy).

**Các bước:**

1. **POST /onboarding** với body tenant + brand_profile, header `Idempotency-Key: smoke-s2-<random>`.  
   **Mong đợi:** 201; body có `tenant_id`, `brand_profile_id`, `brand_profile` (object).

2. **POST /kb/bulk_ingest?tenant_id=<id>** với 30 items (question, answer, tags, source).  
   **Mong đợi:** 201; `created: 30`, `ids` có 30 phần tử.

3. **POST /kb/query** với `query: "product support"`, `tenant_id`, `top_k: 5`.  
   **Mong đợi:** 200; `contexts` có ít nhất 1 phần tử (vì FAQ chứa "product"); `citations` tương ứng.

4. **POST /onboarding** lại cùng body và cùng `Idempotency-Key`.  
   **Mong đợi:** 200; `tenant_id` trùng lần 1 (idempotent).

**Kết quả cuối:** Script in "Smoke test S2 PASSED."
