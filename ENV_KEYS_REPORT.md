# ENV Keys Report – AI Content Director / AI Marketing Platform

**Ngày tạo:** 2025-02-16  
**Nguồn scan:** Python (pydantic_settings BaseSettings), docs, docker-compose, alembic.

---

## 1) Tổng hợp ENV keys đang được dùng

| ENV_KEY | required | default | used_in_files | notes |
|---------|----------|---------|---------------|-------|
| APP_NAME | No | ai-content-director | shared/config.py | Runtime app name. |
| DEBUG | No | false | shared/config.py | Bật debug (SQL echo, etc.). |
| DATABASE_URL | Yes | postgresql://postgres:postgres@localhost:5432/ai_ecosystem | shared/config.py, shared/database.py, migrations/env.py | Postgres connection string. |
| REDIS_URL | Yes | redis://localhost:6379/0 | shared/config.py, shared/queue.py, shared/content_engine.py, shared/planner_engine.py (nếu có) | Redis cho RQ và cache. |
| REDIS_QUEUE_NAME | No | default | shared/config.py, shared/queue.py | Tên queue RQ. |
| LOG_LEVEL | No | INFO | shared/config.py, api/main.py, workers/worker.py, workers/tasks.py | Level logging. |
| LOG_JSON | No | true | shared/config.py, api/main.py, workers/worker.py, workers/tasks.py | Log format JSON. |
| DEEPSEEK_API_KEY | No | None | shared/config.py, shared/llm.py | API key DeepSeek; không có thì stub. |
| CONTENT_CACHE_TTL_SECONDS | No | 86400 | shared/config.py, shared/content_engine.py | TTL cache content/planner (giây). |

### Meta / Facebook & Security (future integration)

Các key dưới đây có trong `.env.example` và `.env` template; code chưa đọc. Dùng cho Phase Meta Graph API (Page publishing, System User).

| ENV_KEY | required | default | used_in_files | notes |
|---------|----------|---------|---------------|-------|
| META_APP_ID | Yes (khi bật Meta) | — | N/A (future integration) | Lấy: developers.facebook.com → App Dashboard. Nhạy cảm: public. |
| META_APP_SECRET | Yes (khi bật Meta) | — | N/A (future integration) | App Secret. **Secret:** không commit, chỉ ENV. |
| META_BUSINESS_ID | No | — | N/A (future integration) | Business Manager ID (nếu dùng BM). |
| META_SYSTEM_USER_ID | No | — | N/A (future integration) | System User ID (token không hết hạn). |
| FACEBOOK_PAGE_ID | Yes (khi publish) | — | N/A (future integration) | Page ID đăng bài. Lấy: Page → About → Page ID. |
| FACEBOOK_PAGE_ACCESS_TOKEN | Yes (khi publish) | — | N/A (future integration) | Page token hoặc System User token. **Secret:** không commit. |
| WEBHOOK_VERIFY_TOKEN | No | — | N/A (future integration) | Token để Meta verify webhook endpoint. |
| WEBHOOK_SECRET | No | — | N/A (future integration) | Secret ký/verify webhook payload. **Secret.** |
| ENCRYPTION_SECRET_KEY | No | — | N/A (future integration) | Key mã hóa payload. 32-byte hex/base64. **Secret.** |
| JWT_SECRET_KEY | No | — | N/A (future integration) | Key ký JWT. **Secret.** |
| OPENAI_API_KEY | No | — | N/A (future integration) | API key OpenAI. Lấy: platform.openai.com. **Secret.** |

**Ghi chú:** Key hiện dùng được đọc qua `shared/config.py` (pydantic_settings, `env_file=".env"`). Không có `os.getenv`/`os.environ`/`process.env` trực tiếp trong repo.

---

## 2) Key đang thiếu (gọi trong code nhưng chưa có trong .env.example / docs)

**Kết quả:** Không có key nào thiếu. Mọi biến mà `Settings` đọc đều đã có trong `.env.example` và trong bảng trên.

---

## 3) Config / YAML / JSON / INI – hardcode secret hoặc nên đưa sang ENV

| File | Vị trí / Nội dung | Đề xuất |
|------|--------------------|--------|
| docker-compose.yml | `environment: POSTGRES_PASSWORD: postgres` (service postgres) | Chỉ dùng cho container Postgres local. App đọc qua `DATABASE_URL`. Có thể đổi thành `POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:-postgres}` nếu muốn override bằng ENV. |
| shared/config.py | Default `DATABASE_URL`, `REDIS_URL` chứa postgres/postgres, localhost | Đã ưu tiên ENV (pydantic_settings); default chỉ cho dev. Không hardcode secret thật. |
| alembic.ini | Không chứa secret; chỉ ghi chú "Database URL lấy từ ENV" | Giữ nguyên. |

**Kết luận:** Không có file nào đang hardcode secret thật cần gỡ ngay. Ưu tiên ENV cho mọi secret (đã tuân thủ ở `shared/config.py`).

---

## 4) Scan pattern đã thực hiện

- **Python:** `os.getenv`, `os.environ`, `dotenv`, `load_dotenv` → **Không dùng** (chỉ dùng pydantic_settings).
- **Node:** `process.env`, `dotenv.config` → **Không có file Node trong repo.**
- **Config:** `Field(..., env="...")` trong `shared/config.py` → **Đã liệt kê đủ.**
- **Docs/YAML:** Đã quét README, docs/*.md, docker-compose.yml, alembic.ini → Chỉ tham chiếu DATABASE_URL, REDIS_URL, .env; không khai báo key mới.
- **Prefix:** FB_, META_, OPENAI_, DATABASE_, REDIS_, DEEPSEEK_, CONTENT_, LOG_, APP_ → Chỉ DATABASE_, REDIS_, DEEPSEEK_, CONTENT_, LOG_, APP_ có trong config; Meta/OpenAI chưa implement.

---

## 5) Đề xuất chuẩn hóa

- **Secrets:** Tiếp tục chỉ đọc từ ENV (và .env local), không đưa vào repo. `.env.example` chỉ placeholder, không value thật.
- **Config override:** Hiện không có `configs/` hay `config.yaml`; mọi cấu hình chạy qua `shared/config.py` và ENV. Nếu sau này thêm config file, nên dùng ENV để override (ví dụ `DATABASE_URL` override giá trị trong file).
- **.gitignore:** Đã có `.env`; nên thêm `.env.*` và `!.env.example` để tránh commit .env.local, .env.prod, v.v.
