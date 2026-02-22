# Phase 2.2.6 - n8n Auto Pipeline (Drive -> Facebook)

Mục tiêu: tự động chạy luồng:

1. `POST /api/gdrive/ingest`
2. `GET /api/assets?tenant_id=...&status=cached`
3. Mỗi asset mới (tối đa 3/run):
   - `POST /api/media/analyze`
   - Ensure plan (generate + materialize nếu chưa có `plan_id` trong static data)
   - `POST /api/content/generate`
   - `POST /publish/facebook`
   - chỉ mark processed khi publish thành công

## File workflow

- `docs/n8n/workflows/phase_2_2_6_drive_to_facebook.json`

## 5 bước setup trên n8n UI

1. Mở n8n UI (`http://<host>:5678`) -> **Workflows** -> **Import from file**.  
   Chọn file `phase_2_2_6_drive_to_facebook.json`.

2. Đặt ENV cho n8n container (qua `docker-compose.yml` + `.env`):
   - `API_BASE_URL` (khuyên dùng trong Docker network: `http://api:8000`)
   - `TENANT_ID` (UUID tenant cần chạy auto)
   - optional: `N8N_TIMEZONE=Asia/Ho_Chi_Minh`

3. Restart n8n để nhận ENV mới:
   ```bash
   docker compose up -d n8n
   ```

4. Mở workflow vừa import, bấm **Test workflow** 1 lần để kiểm tra output logs.

5. Bật **Active** để chạy tự động mỗi 5 phút (Cron mặc định).

## Static data được dùng trong workflow

- `plan_id`: lưu kế hoạch đã tạo, tái sử dụng cho run sau.
- `day_counter`: bắt đầu 1, tăng sau mỗi lần publish thành công, quay vòng về 1 khi >30.
- `processed_asset_ids`: dedup asset đã publish thành công.

## Guardrails đã áp dụng

- Tối đa `3 assets / run`.
- Publish fail => **không** mark asset processed.
- Toàn bộ trạng thái chạy ghi vào output (`logs`) của execution.

## Troubleshoot nhanh

- Xem log n8n:
  ```bash
  docker compose logs --tail=200 n8n
  ```

- Kiểm tra API từ trong n8n container:
  ```bash
  docker exec -it ai-ecosystem-n8n sh -lc "wget -qO- http://api:8000/api/healthz"
  ```

- Nếu workflow báo thiếu tenant:
  - kiểm tra `TENANT_ID` trong env n8n.
  - kiểm tra tenant tồn tại trong DB.

## Facebook Permission Checklist

Khi `/publish/facebook` trả OAuthException `code=10`, `subcode=2069007`, làm theo thứ tự:

1. Trong Meta App, bật **Facebook Login** product.
2. Đảm bảo app/token có các quyền:  
   `pages_manage_posts`, `pages_read_engagement`, `pages_show_list`.
3. Generate **user token** có đủ scopes, sau đó đổi sang **page token** qua `/{user-id}/accounts` (hoặc `/me/accounts`).
4. Kiểm tra user có **Page task CREATE_CONTENT** trên đúng Facebook Page.
5. Cập nhật token vào `.env` (`FB_PAGE_ACCESS_TOKEN` hoặc `FACEBOOK_ACCESS_TOKEN`), restart service.
6. Chạy script chẩn đoán:
   ```bash
   docker exec -it ai-content-director-api sh -lc "bash /app/scripts/facebook_debug.sh"
   ```

Lệnh verify nhanh (kiểm tra file có trong image):
```bash
docker exec -it ai-content-director-api sh -lc "ls -lah /app/scripts && bash /app/scripts/facebook_debug.sh"
```

Muốn test publish thật thì thêm `DRY_RUN=0`:
```bash
docker exec -it ai-content-director-api sh -lc "DRY_RUN=0 bash /app/scripts/facebook_debug.sh"
```
