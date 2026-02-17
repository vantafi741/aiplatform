# Runbook – AI Content Director

## Meta Setup Quickstart

Sau khi dien `.env` (Meta keys: META_APP_ID, META_APP_SECRET, FACEBOOK_PAGE_ID, FACEBOOK_PAGE_ACCESS_TOKEN), chay tu repo root:

```bash
python scripts/meta_env_doctor.py
python scripts/meta_verify.py
python scripts/meta_post_test.py --message "Test"
```

- **meta_env_doctor.py**: kiem tra bien META_*, FACEBOOK_*, WEBHOOK_*; token/secret duoc mask (6 ky tu dau + ... + 6 ky tu cuoi). Key rong hien thi `(empty)  [SKIP]`.
- **meta_verify.py**: xac minh token hop le, goi /me, Page, debug_token; in token_valid, app_id, expires_at, scopes.
- **meta_post_test.py**: dang thu 1 bai len Page; tra ve `post_id` neu thanh cong.

**FORMAT_MODE:** Mac dinh `COMPACT` (output dinh lien dong, dung contract). Dat `FORMAT_MODE=PRETTY` de in xuong dong giua cac block.

**App Mode:** App o che do Development chi admin/tester thay bai dang; chuyen Live de cong khai. Chi tiet: [docs/META_SETUP.md](docs/META_SETUP.md).
