# RUNBOOK – Security (Port policy & hardening)

**Repo (VPS):** `/opt/aiplatform` (hoặc đường dẫn deploy thực tế).

## 1. Port policy

| Service   | Port | Bind              | Ghi chú |
|-----------|------|-------------------|--------|
| **Postgres** | 5432 | `127.0.0.1` only | Không expose ra internet. Chỉ API container (internal network) và host (debug/admin). |
| **Redis**    | 6379 | `127.0.0.1` only | Không expose ra internet. Chỉ API container và host. |
| **API**      | 8000 | `0.0.0.0` (trong container) | Có thể expose ra host. **Khuyến nghị:** production dùng reverse proxy (Nginx/Caddy), chỉ proxy 80/443 → 127.0.0.1:8000. |
| **n8n**      | 5678 | Tùy deploy       | Nếu cần truy cập từ ngoài: dùng proxy + auth. |

- **Đã áp dụng trong `docker-compose.yml`:** Postgres và Redis dùng `127.0.0.1:5432:5432` và `127.0.0.1:6379:6379` (chỉ host local).
- **TODO (production):** Thêm Nginx/Caddy trước API; bind API port `127.0.0.1:8000:8000`; chỉ expose 8000/8001 qua reverse proxy (80/443).

## 2. UFW rules mẫu (Linux)

Giả sử:
- SSH: 22
- HTTP/HTTPS: 80, 443
- Không mở 5432, 6379, 8000 ra ngoài (chỉ localhost).

```bash
# Cho phép SSH
sudo ufw allow 22/tcp comment "SSH"

# Cho phép HTTP/HTTPS (cho Nginx/Caddy)
sudo ufw allow 80/tcp comment "HTTP"
sudo ufw allow 443/tcp comment "HTTPS"

# (Tùy chọn) Nếu tạm thời expose API trực tiếp cho dev/staging:
# sudo ufw allow 8000/tcp comment "API dev"

# Mặc định
sudo ufw default deny incoming
sudo ufw default allow outgoing

# Bật (sau khi kiểm tra)
sudo ufw enable
sudo ufw status verbose
```

**Lưu ý:** 5432 và 6379 **không** cần rule allow từ ngoài; chỉ process trên host (và container qua network nội bộ Docker) kết nối được.

## 3. Kiểm tra sau deploy

```bash
# Trên host: Postgres/Redis chỉ listen localhost
ss -tlnp | grep -E '5432|6379'
# Kỳ vọng: 127.0.0.1:5432, 127.0.0.1:6379

# Từ máy ngoài (sẽ fail nếu đúng policy):
# nc -zv <VPS_IP> 5432   -> Connection refused / timeout
# nc -zv <VPS_IP> 6379   -> Connection refused / timeout
```

## 4. Verify trên VPS (bằng chứng merge)

Sau khi chạy `scripts/verify_vps_lead_gdrive.sh`, paste kết quả **ports + ufw** vào đây (hoặc trích từ `/tmp/verify_ports_ufw.txt`).

**Kết luận policy:** Postgres/Redis phải bind `127.0.0.1`; 8000 có thể LISTEN trên 0.0.0.0 (hoặc 127.0.0.1 nếu đã đặt reverse proxy).

<details>
<summary>Paste output: docker compose ps + ss -lntp + ufw status</summary>

```
===== /tmp/verify_ports_ufw.txt =====
=== docker compose ps ===
NAME                      IMAGE                COMMAND                  SERVICE    CREATED          STATUS                            PORTS
ai-content-director-api   aiplatform-api       "uvicorn app.main:ap…"   api        10 seconds ago   Up 8 seconds (health: starting)   0.0.0.0:8000->8000/tcp, [::]:8000->8000/tcp
ai-ecosystem-postgres     postgres:16-alpine   "docker-entrypoint.s…"   postgres   22 seconds ago   Up 20 seconds (healthy)           127.0.0.1:5432->5432/tcp
ai-ecosystem-redis        redis:7-alpine       "docker-entrypoint.s…"   redis      22 seconds ago   Up 20 seconds (healthy)           127.0.0.1:6379->6379/tcp

=== ss -lntp | egrep ':(8000|5432|6379)' ===
LISTEN 0      4096         0.0.0.0:8000      0.0.0.0:*    users:(("docker-proxy",pid=2455818,fd=8))
LISTEN 0      4096       127.0.0.1:5432      0.0.0.0:*    users:(("docker-proxy",pid=2455482,fd=8))
LISTEN 0      4096       127.0.0.1:6379      0.0.0.0:*    users:(("docker-proxy",pid=2455503,fd=8))
LISTEN 0      4096            [::]:8000         [::]:*    users:(("docker-proxy",pid=2455824,fd=8))

=== ufw status verbose ===
Status: active
Logging: on (low)
Default: deny (incoming), allow (outgoing), deny (routed)
New profiles: skip

To                         Action      From
--                         ------      ----
5432/tcp                   DENY IN     Anywhere
6379/tcp                   DENY IN     Anywhere
22/tcp (OpenSSH)           ALLOW IN    Anywhere
80                         ALLOW IN    Anywhere
443                        ALLOW IN    Anywhere
8000/tcp                   ALLOW IN    Anywhere
5678/tcp                   ALLOW IN    Anywhere
5432/tcp (v6)              DENY IN     Anywhere (v6)
6379/tcp (v6)              DENY IN     Anywhere (v6)
22/tcp (OpenSSH (v6))      ALLOW IN    Anywhere (v6)
80 (v6)                    ALLOW IN    Anywhere (v6)
443 (v6)                   ALLOW IN    Anywhere (v6)
8000/tcp (v6)              ALLOW IN    Anywhere (v6)
5678/tcp (v6)              ALLOW IN    Anywhere (v6)
```

</details>

## 5. Secrets

- Không commit `.env` hoặc file chứa mật khẩu/token.
- Trên VPS: dùng `env_file` trỏ tới file ngoài repo (ví dụ `/opt/aiplatform/secrets/.env`).
- Postgres/Redis password: đổi mặc định trong production.
