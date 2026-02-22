# Audit trạng thái VPS (Enterprise)

Script tạo báo cáo hiện trạng dự án trên VPS: Git, Docker, endpoints, logs, ENV (masked), DB tables + row counts, N8N (masked), storage, disk/mem. **Không in lộ secret** – mọi token/URL chỉ hiển thị 4 ký tự đầu + 4 ký tự cuối.

## Output

- File: **`/opt/aiplatform/REPORT_STATUS_VPS.md`** (hoặc `$REPORT_FILE`).

## Smoke step – lệnh chạy một dòng

```bash
cd /opt/aiplatform && chmod +x scripts/audit_status.sh && ./scripts/audit_status.sh
```

Chạy xong mở `REPORT_STATUS_VPS.md` để xem báo cáo.

## Biến môi trường (tùy chọn)

| Biến | Mặc định | Ý nghĩa |
|------|----------|---------|
| `REPO_ROOT` | `/opt/aiplatform` | Thư mục gốc repo |
| `REPORT_FILE` | `$REPO_ROOT/REPORT_STATUS_VPS.md` | File báo cáo |
| `LOG_LINES` | `200` | Số dòng log api/worker |
| `BASE_URL` | `http://localhost:8000` | Base URL cho healthz/readyz |

Ví dụ:

```bash
REPO_ROOT=/opt/aiplatform REPORT_FILE=/tmp/audit.md ./scripts/audit_status.sh
```

## Nội dung báo cáo (section headers mẫu)

1. **1) Git** – Branch, last commit, `git status`
2. **2) Docker** – `docker compose ps`, images, health & ports
3. **3) Logs** – 200 dòng gần nhất (api, worker nếu có)
4. **4) Endpoints** – HTTP code: `/api/healthz`, `/api/readyz`, HEAD `/openapi.json`
5. **5) ENV** – Key quan trọng (DATABASE_URL, REDIS_URL, OPENAI_*, FB_*, N8N_*, GDRIVE_*) – **mask 4 đầu + 4 cuối**
6. **6) DB** – Danh sách bảng, mô tả bảng chính, row counts
7. **7) N8N** – Trạng thái container, env webhook/N8N (mask 4 đầu + 4 cuối)
8. **8) Storage** – `/data`, `LOCAL_MEDIA_DIR`
9. **9) Disk & Memory snapshot** – `df -h`, `free -m`

## Python helper

- `audit_status.py mask_env [path]` – Đọc file .env (hoặc stdin), in key quan trọng với giá trị đã mask (4 đầu … 4 cuối).
- `audit_status.py table_descriptions` – In mô tả ngắn các bảng chính.

## .gitignore – Tại sao bỏ qua một số file

- **REPORT_STATUS_VPS.md** – Báo cáo sinh trên VPS, môi trường cụ thể. Không commit để tránh nhầm lẫn giữa các máy và tránh rủi ro nếu script đổi làm lộ dữ liệu. Báo cáo **tái tạo được** bằng lệnh smoke ở trên.
- **data/** – Thư mục dữ liệu runtime/backup trên server, không đưa vào repo.
- **secrets/** – Thư mục chứa file nhạy cảm (nếu dùng), không đưa vào repo.

Nếu muốn **track** REPORT_STATUS_VPS.md (ví dụ để lưu snapshot), có thể xóa `REPORT_STATUS_VPS.md` khỏi `.gitignore` và commit thủ công sau khi đã kiểm tra nội dung không lộ secret.
