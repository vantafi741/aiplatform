# Sprint 4 – Text Content Factory – Deliverables

## 1) Danh sách file thay đổi (kèm lý do)

| File | Lý do |
|------|--------|
| **Migration** | |
| `migrations/versions/20250216000002_sprint4_content_assets.py` | Mới. Bảng content_plans, content_plan_items (S3 minimal), content_assets, content_asset_versions, content_usage_logs. Index tenant_id, plan_item_id, asset_id. |
| **Models / Config** | |
| `shared/models.py` | Mới (hoặc bổ sung). Toàn bộ model S1–S4: Tenant, BrandProfile, Job, JobRun, AuditLog, KbItem, IdempotencyKey, ContentPlan, ContentPlanItem, ContentAsset, ContentAssetVersion, ContentUsageLog. |
| `shared/config.py` | Mới (hoặc bổ sung). deepseek_api_key, content_cache_ttl_seconds. |
| **Engine / LLM** | |
| `shared/llm.py` | Mới. call_llm_content(prompt, system_prompt) -> dict (caption, body, hashtags, cta). Stub hoặc DeepSeek. |
| `shared/content_engine.py` | Mới. Playbook + brand + RAG -> prompt -> LLM -> validate + 1 retry -> confidence/tier -> versioning, cache fingerprint, content_usage_logs. |
| **API** | |
| `api/schemas/content.py` | Mới. GenerateRequest/Response, RegenerateResponse, StatusUpdate, GetResponse. |
| `api/routers/content.py` | Mới. POST /content/generate, GET /content/{asset_id}, POST /content/{asset_id}/regenerate, PUT /content/{asset_id}/status. |
| `api/routers/planner.py` | Mới (minimal). POST /planner/generate tạo 1 plan + 1 item cho S4 smoke test. |
| `api/main.py` | Mới hoặc cập nhật. Đăng ký planner, content; version 0.4.0. |
| **Audit** | content.generate, content.regenerate, content.status_update trong router. |
| **Scripts / Docs** | |
| `scripts/smoke_test_s4.ps1` | Mới. onboarding -> kb ingest -> planner/generate -> content/generate -> regenerate -> approve. |
| `docs/SPRINT4_DELIVERABLES.md` | File này. |
| `README.md` | Thêm endpoints S4, smoke test S4, CONTENT_CACHE_TTL_SECONDS. |
| `.env.example` | CONTENT_CACHE_TTL_SECONDS, DEEPSEEK_API_KEY (comment). |

---

## 2) Code implement đầy đủ

- **DB:** content_assets (tenant_id, plan_id, plan_item_id, asset_type=TEXT_POST, status, current_version); content_asset_versions (asset_id, version, prompt_fingerprint, model, input_snapshot, output, confidence, approval_tier); content_usage_logs (tenant_id, asset_id, cached_hit, model, estimated_tokens).
- **Content engine:** Load playbook, brand_profile, plan_item, RAG contexts; build prompt; call_llm_content; validate JSON (caption, body, hashtags, cta); retry 1 với repair prompt; confidence + tier (>=0.85 auto, 0.70–0.85 draft, <0.70 escalate); lưu version; cache Redis theo fingerprint; ghi content_usage_logs.
- **API:** POST /content/generate, GET /content/{asset_id}, POST /content/{asset_id}/regenerate, PUT /content/{asset_id}/status.

---

## 3) Hướng dẫn chạy local

```bash
cp .env.example .env
docker compose up -d
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
alembic upgrade head
uvicorn api.main:app --reload --host 0.0.0.0 --port 8000
```

---

## 4) Smoke test S4 – steps và kết quả mong đợi

**Chạy:** `.\scripts\smoke_test_s4.ps1`

**Các bước:**  
1. POST /onboarding → tenant_id.  
2. POST /kb/bulk_ingest → ingest KB.  
3. POST /planner/generate → plan_id, plan_item_id.  
4. POST /content/generate → asset_id, version.  
5. POST /content/{asset_id}/regenerate → version mới.  
6. PUT /content/{asset_id}/status body `{"status":"approved"}` → status = approved.

**Kết quả mong đợi:** Script in "Smoke test S4 PASSED."
