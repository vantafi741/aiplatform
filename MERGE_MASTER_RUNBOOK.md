# RUNBOOK – Merge feature/lead-gdrive-assets vào master

**Repo:** aiplatform (GitHub: vantafi741/aiplatform)  
**Feature branch:** `feature/lead-gdrive-assets`  
**Commit verify đã push:** `61aedba384c22ce6d9be98df462ef5ed6e42c514`

---

## Lưu ý quan trọng

### Lỗi "fatal: invalid refspec 'feature/...'"
- **Nguyên nhân:** Dùng **placeholder** hoặc tên branch sai (ví dụ `feature/...` thay vì tên thật).
- **Cách tránh:** Luôn dùng đúng tên branch: `feature/lead-gdrive-assets` (không có dấu ba chấm, không thiếu chữ).

### Bảo mật – KHÔNG commit/push secrets
- **Không** commit file `.env` hoặc bất kỳ file nào chứa token/API key/password.
- Nếu phát hiện token trong `.env` hoặc trong output compose/config đã lỡ commit: **rotate key ngay** (tạo key mới, thu hồi key cũ) và **loại secret khỏi repo** (xóa khỏi history hoặc dùng BFG/git filter-repo; sau đó force-push chỉ khi đã thống nhất với team).
- Trên VPS: dùng `env_file` trỏ tới file **ngoài repo** (vd. `/opt/aiplatform/secrets/.env`).

### Rủi ro port 8000
- Trên VPS, **8000 đang ALLOW IN** trong UFW → API có thể bị truy cập từ internet.
- **Đề xuất bước tiếp theo:** Đặt reverse proxy (Nginx/Caddy) trước API; bind API `127.0.0.1:8000:8000`; chỉ expose 80/443 ra ngoài; sau đó **UFW bỏ allow 8000** (chỉ allow 22, 80, 443). Chi tiết: RUNBOOK_SECURITY.md.

---

## A) Trên local (máy chạy Cursor)

### A.1) Mở repo, fetch đầy đủ

```bash
cd d:\ai-ecosystem   # hoặc đường dẫn repo local của bạn
git fetch origin
git fetch origin feature/lead-gdrive-assets:feature/lead-gdrive-assets   # nếu cần cập nhật ref local
```

### A.2) Kiểm tra branch feature/lead-gdrive-assets có commit 61aedba

```bash
git log -1 --oneline feature/lead-gdrive-assets
# Kỳ vọng: 61aedba docs(runbooks): paste VPS verify evidence ...

git rev-parse feature/lead-gdrive-assets
# Kỳ vọng: 61aedba384c22ce6d9be98df462ef5ed6e42c514
```

### A.3) Đảm bảo working tree sạch

```bash
git status --short
# Nên không có file modified/untracked “rác”. Nếu có file nhạy cảm (vd. .env) thì KHÔNG add, dùng .gitignore.
git status
# Working tree clean (hoặc chỉ những file an toàn đã chủ đích).
```

### A.4) Tạo PR từ feature/lead-gdrive-assets → master

**Cách 1 – Trình duyệt (khuyến nghị):**

1. Mở: **https://github.com/vantafi741/aiplatform/compare/master...feature/lead-gdrive-assets**
2. Hoặc: Vào repo → tab **Pull requests** → **New pull request**.
3. **Base:** `master` | **Compare:** `feature/lead-gdrive-assets`.
4. Title ví dụ: `Merge feature/lead-gdrive-assets: Lead + GDrive + Assets + verify runbooks`.
5. Trong description paste **Checklist review** (xem A.5).
6. **Create pull request**.

**Cách 2 – GitHub CLI (nếu đã cài `gh`):**

```bash
gh pr create --base master --head feature/lead-gdrive-assets --title "Merge feature/lead-gdrive-assets: Lead + GDrive + Assets + verify runbooks" --body "See MERGE_MASTER_RUNBOOK.md checklist."
```

**Lưu ý:** Cursor không tạo PR qua UI; dùng GitHub web hoặc `gh` như trên.

### A.5) Checklist review PR

- [ ] **Migrations 012/013:** Có trong branch (alembic/versions/012_lead_signals.py, 013_content_assets_and_require_media.py); không conflict với master.
- [ ] **Smoke E2E:** RUNBOOK_SMOKE_TEST.md có paste `/tmp/smoke_e2e_output.txt`; flow 1–10 chạy; publish có thể fail `media_required` (đúng khi chưa cấu hình GDrive/Facebook).
- [ ] **Verify ports/UFW:** RUNBOOK_SECURITY.md có paste `/tmp/verify_ports_ufw.txt`; Postgres 127.0.0.1:5432, Redis 127.0.0.1:6379; UFW DENY 5432/6379.
- [ ] **Correlation_id logs:** RUNBOOK_SMOKE_TEST.md có paste `/tmp/publish_trace.txt`; có `scheduler.tick`, `scheduler.publish_result` với `correlation_id=...`.
- [ ] **Không có secrets trong commit:** `git show 61aedba --name-only` và diff không chứa `.env`, token, password; RUNBOOK paste không lộ token thật.

### A.6) Merge trên GitHub – đề xuất

- **Khuyến nghị: Squash and merge**
  - **Lý do:** Branch feature có nhiều commit (feat db, feat api, docs, …); squash gộp thành **một commit trên master** dễ đọc history, dễ revert một lần nếu cần, và giữ master “linear”.
  - **Cách làm:** Trong PR → **Squash and merge** → chỉnh title/description nếu cần → **Confirm squash and merge**.

- **Thay thế: Merge commit (Create a merge commit)**
  - Giữ toàn bộ lịch sử commit của feature; history đầy đủ hơn nhưng master nhiều commit hơn.
  - Dùng nếu team muốn giữ từng commit riêng trên master.

### A.7) Sau khi merge

```bash
git checkout master
git pull origin master
# (Tùy chọn) Tag release nhẹ:
git tag -a v0.2.0-lead-gdrive -m "Merge feature/lead-gdrive-assets: Lead signals, GDrive assets, verify runbooks"
git push origin v0.2.0-lead-gdrive
# Nếu không cần tag thì bỏ qua 2 dòng trên; chỉ cần pull master.
```

---

## B) Trên VPS /opt/aiplatform (chỉ lệnh – bạn chạy thủ công)

### B.1) Checkout master, pull

```bash
cd /opt/aiplatform
git fetch origin
git checkout master
git pull origin master
```

### B.2) Dừng stack cũ, build và chạy lại

```bash
docker compose down --remove-orphans
docker compose up -d --build api postgres redis
```

Đợi vài phút cho API healthy (healthcheck).

### B.3) Chạy migration trong container

```bash
docker exec -it ai-content-director-api sh -c 'cd /app && alembic upgrade head'
```

(Kỳ vọng: upgrade lên 013 hoặc "Already at head".)

### B.4) Kiểm tra health

```bash
curl -s http://127.0.0.1:8000/api/healthz
curl -s http://127.0.0.1:8000/api/readyz
```

(Kỳ vọng: 200, body có `"status":"ok"` hoặc tương đương.)

### B.5) Chạy smoke E2E

```bash
chmod +x scripts/smoke_e2e.sh scripts/verify_vps_lead_gdrive.sh
./scripts/smoke_e2e.sh
```

(Kỳ vọng: các bước 1–10 in ra; bước publish có thể fail `media_required` nếu chưa cấu hình Facebook/GDrive – vẫn coi pipeline OK nếu scheduler đã pick item và ghi audit.)

### B.6) Nếu fail – lấy log + rollback nhanh

**Lấy log:**

```bash
docker logs --tail=500 ai-content-director-api
docker compose ps
curl -s http://127.0.0.1:8000/api/readyz
```

**Rollback nhanh (về commit master trước merge):**

```bash
cd /opt/aiplatform
git log -1 --oneline master   # ghi lại hash sau merge (vd. abc1234)
git checkout <hash_commit_master_truoc_merge>   # hash master trước khi merge
docker compose down --remove-orphans
docker compose up -d --build api postgres redis
docker exec -it ai-content-director-api sh -c 'cd /app && alembic downgrade -1'   # hoặc downgrade về revision cần thiết
# Sau khi xử lý xong, quay lại: git checkout master && git pull
```

---

## Tóm tắt step-by-step

| # | Nơi | Hành động |
|---|-----|-----------|
| 1 | Local | `git fetch origin`; kiểm tra `feature/lead-gdrive-assets` có 61aedba; `git status` sạch |
| 2 | GitHub | Mở compare/master...feature/lead-gdrive-assets → New PR; điền checklist A.5 vào description |
| 3 | GitHub | Review checklist → **Squash and merge** (hoặc Merge commit) |
| 4 | Local | `git checkout master && git pull origin master`; (tùy chọn) tag `v0.2.0-lead-gdrive` và push tag |
| 5 | VPS | `cd /opt/aiplatform && git checkout master && git pull origin master` |
| 6 | VPS | `docker compose down --remove-orphans && docker compose up -d --build api postgres redis` |
| 7 | VPS | `docker exec -it ai-content-director-api sh -c 'cd /app && alembic upgrade head'` |
| 8 | VPS | `curl` /api/healthz, /api/readyz |
| 9 | VPS | `./scripts/smoke_e2e.sh` |
| 10 | Nếu fail | Lấy log (B.6); rollback bằng checkout hash cũ + downgrade alembic nếu cần |

---

*File: MERGE_MASTER_RUNBOOK.md – dùng cho lần merge feature/lead-gdrive-assets vào master.*
