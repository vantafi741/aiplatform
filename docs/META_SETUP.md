# Meta / Facebook Graph API – Thiết lập và test đăng bài

Tài liệu ngắn: lấy `PAGE_ID` và `PAGE_ACCESS_TOKEN`, test bằng Graph Explorer và curl. **Không bao giờ commit token vào repo.**

---

## Lấy PAGE_ID và PAGE_ACCESS_TOKEN

### PAGE_ID (Facebook Page ID)

1. Vào [Facebook](https://www.facebook.com) → trang (Page) cần đăng bài.
2. **About** → cuộn xuống **Page ID** (số dài). Hoặc dùng [Meta for Developers](https://developers.facebook.com/tools/explorer/) → chọn Page → field `id` trong response.
3. Ghi vào `.env`: `FACEBOOK_PAGE_ID=<số_id>`.

### PAGE_ACCESS_TOKEN (hoặc System User token)

- **Cách 1 – Token Page (user token, có thể hết hạn):**  
  [Graph API Explorer](https://developers.facebook.com/tools/explorer/) → chọn App → chọn quyền `pages_manage_posts`, `pages_read_engagement` → chọn Page → **Get Token** → **Get Page Access Token** → copy token.  
  Ghi vào `.env`: `FACEBOOK_PAGE_ACCESS_TOKEN=<token>`.

- **Cách 2 – System User (token lâu dài, khuyến nghị cho backend):**  
  Meta Business Suite → **Business Settings** → **Users** → **System Users** → tạo/lấy System User → **Generate New Token** → chọn App, quyền Page (ví dụ `pages_manage_posts`) → chọn Page → copy token.  
  Dùng token này cho `FACEBOOK_PAGE_ACCESS_TOKEN` (hoặc token riêng cho System User nếu có biến tách).

**Bảo mật:** Token là secret. Chỉ đặt trong `.env` (đã gitignore), không đưa vào code/config trong repo.

---

## Test bằng Graph Explorer

1. Mở [Graph API Explorer](https://developers.facebook.com/tools/explorer/).
2. Chọn App, lấy Page Access Token (quyền `pages_manage_posts`).
3. Chọn method **POST**, endpoint:  
   `https://graph.facebook.com/v24.0/{page-id}/feed`
4. Body (form): `message` = `Test từ Graph Explorer`.
5. Submit → kiểm tra bài đăng trên Page.

---

## Test từ backend (curl)

Sau khi đã điền `FACEBOOK_PAGE_ID` và `FACEBOOK_PAGE_ACCESS_TOKEN` vào `.env`:

```bash
# Linux/Mac (export từ .env hoặc thay bằng giá trị thật)
export FACEBOOK_PAGE_ID="<PAGE_ID>"
export FACEBOOK_PAGE_ACCESS_TOKEN="<PAGE_ACCESS_TOKEN>"

curl -X POST "https://graph.facebook.com/v24.0/${FACEBOOK_PAGE_ID}/feed" \
  -H "Authorization: Bearer ${FACEBOOK_PAGE_ACCESS_TOKEN}" \
  -d "message=Test đăng bài từ backend"
```

**Windows (PowerShell):**

```powershell
$env:FACEBOOK_PAGE_ID = "<PAGE_ID>"
$env:FACEBOOK_PAGE_ACCESS_TOKEN = "<PAGE_ACCESS_TOKEN>"
curl.exe -X POST "https://graph.facebook.com/v24.0/$env:FACEBOOK_PAGE_ID/feed" `
  -H "Authorization: Bearer $env:FACEBOOK_PAGE_ACCESS_TOKEN" `
  -d "message=Test đăng bài từ backend"
```

Response thành công: JSON có `id` (post id). Lỗi: kiểm tra token, quyền Page và App.

---

## Bảo mật

- **Không commit** `.env` hoặc bất kỳ file chứa `META_APP_SECRET`, `FACEBOOK_PAGE_ACCESS_TOKEN`, `WEBHOOK_SECRET`, `JWT_SECRET_KEY`, `ENCRYPTION_SECRET_KEY`.
- Dùng `.env.example` chỉ làm mẫu (không điền secret thật).
- Production: dùng secret manager (e.g. AWS Secrets Manager, env inject từ CI/CD).
