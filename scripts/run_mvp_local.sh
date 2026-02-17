#!/usr/bin/env bash
# Run MVP local: env check -> migrate -> uvicorn ai_content_director
# Chạy từ thư mục gốc repo: ./scripts/run_mvp_local.sh
# Cần: Python 3.10+, PostgreSQL (DB ai_content_director), ai_content_director/.env

set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
ACD="$REPO_ROOT/ai_content_director"

if [ ! -d "$ACD" ]; then
  echo "Không tìm thấy thư mục: $ACD"
  exit 1
fi

echo "=== MVP Local (entrypoint: ai_content_director) ==="
echo "Repo root: $REPO_ROOT"
echo "ai_content_director: $ACD"
echo ""

# 1) Kiểm tra env
ENV_OK=false
if [ -f "$ACD/.env" ]; then
  echo "[OK] Tồn tại $ACD/.env"
  ENV_OK=true
fi
if [ -n "$DATABASE_URL" ]; then
  echo "[OK] DATABASE_URL đã set (env)"
  ENV_OK=true
fi
if [ "$ENV_OK" = false ]; then
  echo "[WARN] Chưa có .env hoặc DATABASE_URL. Copy ai_content_director/.env.example sang .env và điền DATABASE_URL."
  read -r -p "Tiếp tục? (y/N) " confirm
  if [ "$confirm" != "y" ] && [ "$confirm" != "Y" ]; then
    exit 1
  fi
fi

# 2) Venv
VENV_PATH="$ACD/.venv"
PY_EXE="$VENV_PATH/bin/python"
if [ ! -f "$PY_EXE" ]; then
  echo "Tạo venv: $VENV_PATH ..."
  (cd "$ACD" && python3 -m venv .venv)
  if [ ! -f "$PY_EXE" ]; then
    (cd "$ACD" && python -m venv .venv)
  fi
  if [ ! -f "$PY_EXE" ]; then
    echo "Tạo venv thất bại. Kiểm tra python3/python trong PATH."
    exit 1
  fi
fi
echo "[OK] Venv: $VENV_PATH"

# 3) Dependencies
if [ -f "$ACD/requirements.txt" ]; then
  echo "Cập nhật dependencies (pip install -r requirements.txt) ..."
  "$PY_EXE" -m pip install -r "$ACD/requirements.txt" -q
  echo "[OK] Dependencies"
fi

# 4) Migrate
echo "Chạy alembic upgrade head ..."
(cd "$ACD" && "$PY_EXE" -m alembic upgrade head) || {
  echo "alembic upgrade head thất bại. Kiểm tra PostgreSQL và DATABASE_URL."
  exit 1
}
echo "[OK] Migrations"

# 5) Start uvicorn (foreground)
echo ""
echo "Khởi động server: http://127.0.0.1:8000"
echo "Dừng: Ctrl+C"
echo ""
(cd "$ACD" && "$PY_EXE" -m uvicorn app.main:app --host 127.0.0.1 --port 8000)
