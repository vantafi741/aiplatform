# Meta / Facebook Runbook – Scripts & Diagnosis

Scripts kiem tra token, quyen, va dang bai len Page. **Luon chay tu repo root** de .env duoc load dung.

**Exit codes:** 2 = thieu bien env, 3 = token invalid (shape hoac debug_token), 4 = permission missing (scope/page mismatch), 5 = post fail (HTTP != 200).

**Sources legend (env loading):**
- **.env** = gia tri chi doc tu file `.env`.
- **env (preloaded, same as .env)** = bien da co trong process env truoc khi load_dotenv va **bang** gia tri trong .env (chay script lien tiep trong cung session thuong thay).
- **env (overrides .env)** = bien co trong process env va **khac** gia tri trong .env (co the gay flakiness; dung `meta_env_reset_hint.py` de xoa).

---

## 1. Chay tu repo root (bat buoc)

Env duoc load tu file `.env` tai **git repo root** (khong phu thuoc cwd). Neu chay tu thu muc khac, script bao thieu bien va exit(2).

**PowerShell (Windows):**

```powershell
cd D:\ai-ecosystem
python scripts/meta_env_doctor.py
python scripts/meta_verify.py
python scripts/meta_post_test.py --message "Test"
```

**Bash (Linux/Mac):**

```bash
cd /path/to/ai-ecosystem
python scripts/meta_env_doctor.py
python scripts/meta_verify.py
python scripts/meta_post_test.py --message "Test"
```

---

## 2. Thu tu chay (smoke steps)

1. **meta_env_doctor.py** – Kiem tra bien META_*, FACEBOOK_*, WEBHOOK_*; in cwd, repo_root, env_path, nguon (env vs .env). Neu du -> "Next: meta_verify.py".
2. **meta_verify.py** – Xac dinh token la USER hay PAGE; neu USER thi lay Page token qua /me/accounts; in token_type, scopes, required checklist, FACEBOOK_PAGE_ID vs page_id token. Neu hop le -> goi meta_post_test.
3. **meta_post_test.py** – POST len Page feed. Thanh cong tra ve post_id; that bai in [FAIL] kem diagnosis hints neu 403 #200.

---

## 2.1 Fix env overrides (Cursor/PowerShell)

Bien **process env** (trong Cursor/terminal) neu da set truoc khi load `.env` se **override** gia tri trong file, dan den "luc duoc luc khong" vi gia tri cu/stale.

**Cach xu ly:** Chay helper de phat hien override va in lenh xoa bien trong shell hien tai:

```bash
python scripts/meta_env_reset_hint.py
```

- **Neu phat hien override:** Script in cac key dang override, ke theo lenh **PowerShell** / **CMD** / **Git Bash** de xoa tung bien. Copy-paste chay trong cung shell, sau do chay lai doctor/verify/post_test.
- **Neu khong override:** Script in "No overrides detected." va exit 0.

**Vi du output khi co override:**

```
Meta env override check (repo_root=D:\ai-ecosystem)
------------------------------------------------------------
Keys currently overriding .env (set in process env before load_dotenv):
  META_APP_ID: 880370664812608  [source: env (overrides .env)]
  FACEBOOK_PAGE_ACCESS_TOKEN: EAAMgs...xAZDZD  [source: env (overrides .env)]
------------------------------------------------------------
Run the following in your current shell to clear overrides, then rerun scripts.

PowerShell:
  Remove-Item Env:META_APP_ID -ErrorAction SilentlyContinue
  Remove-Item Env:FACEBOOK_PAGE_ACCESS_TOKEN -ErrorAction SilentlyContinue
...
Recommended clean run (after clearing overrides):
  python scripts/meta_env_doctor.py
  python scripts/meta_verify.py
  python scripts/meta_post_test.py --message "Test"
```

Sau khi chay cac lenh Remove-Item (PowerShell) hoac unset/set KEY= (Bash/CMD), chay lai 3 script de dam bao doc tu `.env`.

---

## 3. Vi du output thanh cong (mask token)

**meta_env_doctor.py:**

```
============================================================
Meta/Facebook ENV Doctor
============================================================
Env loading (deterministic from repo root):
  cwd:       D:\ai-ecosystem
  repo_root: D:\ai-ecosystem
  env_path:  D:\ai-ecosystem\.env
  sources:   (.env = file only; env (preloaded, same as .env) = process env matches .env; env (overrides .env) = process env differs from .env)
    META_APP_ID: 880370664812608  [source: .env]
    FACEBOOK_PAGE_ACCESS_TOKEN: EAAMgs...xAZDZD  [source: .env]
    ...
------------------------------------------------------------
Env status:
  META_APP_ID: 880370664812608  [OK]
  ...
Next: python scripts/meta_verify.py
```

**meta_verify.py:** token_type PAGE hoac USER (neu USER thi lay Page token tu /me/accounts), scopes co pages_manage_posts, pages_read_engagement, FACEBOOK_PAGE_ID (env) = page_id (token).

**meta_post_test.py:**

Truoc khi POST, script goi GET /me voi **token se dung de dang bai** (sau khi resolve qua /me/accounts neu can) va in **Posting identity proof**:

```
Posting identity proof:
  posting_token_type: PAGE
  posting_as_id:       114606127057545
  posting_as_name:     An Thanh Phu ...
  expected_page_id:    114606127057545
  match_status:        MATCH
------------------------------------------------------------
Sending POST to Page feed...
  Page ID: 114606127057545
  Message: Test
[OK] Post created. post_id: 114606127057545_123456789
```

---

## 3.1 Posting Identity Proof

meta_post_test **bat buoc** xac minh identity truoc khi dang bai:

- **posting_token_type:** PAGE (khi posting_as_id = expected_page_id) hoac "unknown (binding mismatch)" khi khong trung.
- **posting_as_id, posting_as_name:** Tu GET /me voi token cuoi cung (sau resolve page token).
- **expected_page_id:** FACEBOOK_PAGE_ID tu .env.
- **match_status:** MATCH hoac MISMATCH.

**Khi MISMATCH:** Script **khong** goi POST; thoat voi exit 4 va in diagnosis. Nguyen nhan: token dan cho Page khac voi FACEBOOK_PAGE_ID. Cach sua: cap nhat FACEBOOK_PAGE_ID trong .env cho dung Page, hoac lay dung Page token cho FACEBOOK_PAGE_ID (vd. qua meta_verify /me/accounts).

**Vi du MISMATCH va cach sua:**

```
Posting identity proof:
  posting_token_type: unknown (binding mismatch)
  posting_as_id:       987654321012345
  posting_as_name:     Other Page Name
  expected_page_id:    114606127057545
  match_status:        MISMATCH

Token is bound to a different Page than FACEBOOK_PAGE_ID.
Fix: update FACEBOOK_PAGE_ID in .env to match the Page this token is for, or fetch the correct Page token for FACEBOOK_PAGE_ID (e.g. via meta_verify /me/accounts).
```

Sua: (1) Doi .env: `FACEBOOK_PAGE_ID=987654321012345` neu ban muon dang len "Other Page Name", hoac (2) Lay Page token dung cho `114606127057545` (chay meta_verify de lay token tu /me/accounts) va cap nhat FACEBOOK_PAGE_ACCESS_TOKEN.

---

## 4. Vi du loi va cach xu ly

### 4.1 Thieu bien (exit 2)

**Output:**

```
[ERROR] Thieu bien moi truong: META_APP_ID, FACEBOOK_PAGE_ACCESS_TOKEN
Chay tu repo root de load .env:  cd D:\ai-ecosystem
Chay: python scripts/meta_env_doctor.py de xem huong dan.
```

**Cach xu ly:**

- Chac chan co file `.env` tai repo root (noi co `.git`).
- Chay lai tu repo root: `cd D:\ai-ecosystem` (hoac duong dan repo cua ban), roi chay lai script.
- Dien day du META_APP_ID, META_APP_SECRET, FACEBOOK_PAGE_ID, FACEBOOK_PAGE_ACCESS_TOKEN trong `.env`.

---

### 4.2 403 (#200) – If posting to a page, requires both pages_read_engagement and pages_manage_posts

**Output (meta_post_test.py):**

```
[FAIL] HTTP 403
  error code:    200
  error message: (#200) If posting to a page, requires both pages_read_engagement and pages_manage_posts...
  -> Missing permission (pages_manage_posts) or Page not linked to App.
  Diagnosis (403 #200):
  - token is USER not PAGE -> use Page token or get from /me/accounts for FACEBOOK_PAGE_ID
  - token not granted for this page_id -> ensure token is for the Page in .env
  - user not admin/full control on page -> Page role must be Admin
  - page not linked to app/business/system user -> link Page to App in Meta Business Suite
  - granular scopes not covering this page_id -> in Business Suite grant task for this Page
  - New Pages Experience task not granted -> grant MANAGE permission for the Page (New Pages Experience)
```

**Cach xu ly:**

1. **Token la USER, khong phai PAGE:**  
   Dung Page Access Token. Trong meta_verify.py neu token la USER script tu dong goi /me/accounts va lay Page token cho FACEBOOK_PAGE_ID; neu khong co trong list thi doi FACEBOOK_PAGE_ACCESS_TOKEN trong .env thanh Page token (Graph Explorer -> Get Token -> Get Page Access Token, hoac System User generate token cho Page).

2. **Token khong danh cho page_id trong .env:**  
   Dam bao FACEBOOK_PAGE_ID trong .env dung voi Page ma token duoc cap. Chay meta_verify.py de xem "FACEBOOK_PAGE_ID (env)" vs "page_id (token)".

3. **User khong phai Admin tren Page:**  
   Vao Page Settings -> Page roles -> user phai la Admin (full control).

4. **Page chua lien ket App/Business:**  
   Vao Meta Business Suite / App Dashboard, lien ket Page voi App (hoac System User co quyen quan ly Page).

5. **Granular scopes khong bao gom page_id:**  
   Trong Business Suite, cap quyen (task) cho dung Page (target_ids phai chua FACEBOOK_PAGE_ID).

6. **New Pages Experience:**  
   Cap quyen MANAGE cho Page (New Pages Experience) trong Business Suite / System User.

---

### 4.3 Token het han (190)

**Output:** `[FAIL] HTTP 403` hoac token invalid, error code 190.

**Cach xu ly:** Tao lai Page Access Token (Graph Explorer hoac System User -> Generate token) va cap nhat FACEBOOK_PAGE_ACCESS_TOKEN trong .env.

---

## 5. Exit codes va token shape

| Code | Y nghia |
|------|--------|
| 0 | Thanh cong |
| 2 | Thieu bien bat buoc (chay tu repo root, kiem tra .env) |
| 3 | Token invalid (hinh dang sai: quotes/whitespace, hoac debug_token khong hop le) |
| 4 | Permission missing (scope thieu, page_id mismatch, granular_scopes khong cover page) |
| 5 | Post fail (HTTP != 200 khi dang bai) |

Token/secret phai khong co dau ngoac kep thua, khoang trang dau/cuoi, ky tu dieu khien. Script tu trim; neu sau trim van invalid -> exit 3.

---

## 6. FORMAT_MODE

- Mac dinh `COMPACT` (output dinh lien dong).
- Dat `FORMAT_MODE=PRETTY` de xuong dong giua cac block (de doc hon khi debug).

PowerShell:

```powershell
$env:FORMAT_MODE = "PRETTY"
python scripts/meta_verify.py
```

---

## 7. Tai lieu lien quan

- [docs/META_SETUP.md](docs/META_SETUP.md) – Lay PAGE_ID, PAGE_ACCESS_TOKEN, test Graph Explorer/curl.
- [README_RUNBOOK.md](README_RUNBOOK.md) – Meta Setup Quickstart (3 lenh).
- [.env.example](.env.example) – Mau bien META_*, FACEBOOK_*, WEBHOOK_*.
