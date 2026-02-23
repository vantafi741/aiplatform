# Rotate Keys Runbook

## Muc tieu

Huong dan rotate key khi nghi ngo lo secret cho:

- Facebook Graph API tokens
- OpenAI API key
- Google Drive service account credential

> Luu y: Khong tu dong rewrite git history neu chua co phe duyet. Uu tien rotate key truoc.

## 0) Trieu chung can rotate ngay

- Token lo trong commit/chat/screenshot/log.
- API tra loi `invalid token`, `permission denied`, `code=190`, `code=10`.
- Script `scripts/check_secrets_in_repo.sh` canh bao.

## 1) Rotate OpenAI key

1. Vao OpenAI dashboard -> API Keys.
2. Tao key moi.
3. Update vao file runtime env:
   - Local: `.env.local`
   - VPS: `/opt/aiplatform/secrets/.env.prod`
4. Restart API:
   ```bash
   API_ENV_FILE=/opt/aiplatform/secrets/.env.prod docker compose up -d --force-recreate api
   ```
5. Revoke key cu.

## 2) Rotate Facebook token

1. Tao lai User token (permissions: `pages_manage_posts`, `pages_read_engagement`, `pages_show_list`).
2. Doi sang Page token (`/me/accounts`).
3. Update:
   - `FACEBOOK_PAGE_ID`
   - `FACEBOOK_ACCESS_TOKEN` (hoac `FB_PAGE_ACCESS_TOKEN`)
4. Restart API.
5. Verify:
   ```bash
   docker exec -it ai-content-director-api sh -lc 'bash /app/scripts/facebook_debug.sh'
   ```
6. Vo hieu hoa token cu trong Meta dashboard.

## 3) Rotate Google Drive credential

1. Tao service account key moi (JSON) trong Google Cloud.
2. Luu file moi tai VPS path an toan (ngoai repo), vi du:
   - `/opt/aiplatform/secrets/gdrive-sa.json`
3. Update `GDRIVE_SA_JSON_PATH` trong env runtime.
4. Restart API.
5. Revoke/xoa key cu trong Google Cloud IAM.

## 4) Kiem tra sau rotate

```bash
cd /opt/aiplatform
bash scripts/check_secrets_in_repo.sh
API_ENV_FILE=/opt/aiplatform/secrets/.env.prod docker compose up -d --force-recreate api
curl -sS http://127.0.0.1:8000/api/healthz
```

## 5) Neu nghi ro ri trong lich su commit

- Ghi nhan incident + pham vi lo.
- Rotate tat ca key lien quan ngay.
- Danh dau canh bao trong report audit/incident.
- Chi rewrite git history khi co quyet dinh chinh thuc (vi anh huong team/workflow).
