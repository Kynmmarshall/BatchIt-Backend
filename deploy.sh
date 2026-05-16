#!/usr/bin/env bash
# deploy.sh - Provision Postgres DB and run Django migrations on a VPS
# Usage: sudo ./deploy.sh  (script will use sudo for DB provisioning)

set -euo pipefail

# Configurable environment variables (override before running)
DB_NAME=${DB_NAME:-batchit}
DB_USER=${DB_USER:-batchit_user}
DB_PASS=${DB_PASS:-Batchit123.}
DB_HOST=${DB_HOST:-localhost}
DB_PORT=${DB_PORT:-5432}
APP_DIR=${APP_DIR:-$(pwd)}
VENV_DIR=${VENV_DIR:-${APP_DIR}/.venv}
PYTHON=${PYTHON:-python3}
DJANGO_SETTINGS_MODULE=${DJANGO_SETTINGS_MODULE:-batchit_proj.settings}

export DJANGO_SETTINGS_MODULE

# Helper: run a psql command as the postgres superuser
psql_exec() {
  sudo -u postgres psql -v ON_ERROR_STOP=1 --username postgres --no-password -c "$1"
}

echo "[deploy] Starting deployment in ${APP_DIR}"
cd "${APP_DIR}"

if [ ! -f manage.py ]; then
  echo "ERROR: manage.py not found in ${APP_DIR}. Run this from the Django project root." >&2
  exit 2
fi

# 1) Provision Postgres role and database (idempotent)
echo "[deploy] Provisioning Postgres role and database (requires sudo)"
ROLE_EXISTS=$(sudo -u postgres psql -tAc "SELECT 1 FROM pg_roles WHERE rolname='${DB_USER}';" | tr -d '[:space:]' || echo)
if [ "${ROLE_EXISTS}" != "1" ]; then
  echo "[deploy] Creating role ${DB_USER}"
  psql_exec "CREATE ROLE \"${DB_USER}\" WITH LOGIN PASSWORD '${DB_PASS}';"
else
  echo "[deploy] Role ${DB_USER} already exists"
fi

DB_EXISTS=$(sudo -u postgres psql -tAc "SELECT 1 FROM pg_database WHERE datname='${DB_NAME}';" | tr -d '[:space:]' || echo)
if [ "${DB_EXISTS}" != "1" ]; then
  echo "[deploy] Creating database ${DB_NAME} owned by ${DB_USER}"
  psql_exec "CREATE DATABASE \"${DB_NAME}\" OWNER \"${DB_USER}\";"
else
  echo "[deploy] Database ${DB_NAME} already exists"
fi

# Ensure extensions used by models (uuid-ossp, pgcrypto)
echo "[deploy] Ensuring required Postgres extensions (uuid-ossp, pgcrypto)"
sudo -u postgres psql -d "${DB_NAME}" -v ON_ERROR_STOP=1 -c "CREATE EXTENSION IF NOT EXISTS \"uuid-ossp\";"
sudo -u postgres psql -d "${DB_NAME}" -v ON_ERROR_STOP=1 -c "CREATE EXTENSION IF NOT EXISTS pgcrypto;"

# 2) Create/activate virtualenv and install requirements
echo "[deploy] Setting up Python virtualenv at ${VENV_DIR}"
if [ ! -d "${VENV_DIR}" ]; then
  ${PYTHON} -m venv "${VENV_DIR}"
fi
# shellcheck disable=SC1090
source "${VENV_DIR}/bin/activate"

echo "[deploy] Upgrading pip and installing requirements"
python -m pip install --upgrade pip setuptools wheel
if [ -f requirements.txt ]; then
  pip install -r requirements.txt
else
  echo "[deploy] WARNING: requirements.txt not found, skipping pip install"
fi

# 3) Export DATABASE_URL for Django (temporary for this run)
export DATABASE_URL="postgres://${DB_USER}:${DB_PASS}@${DB_HOST}:${DB_PORT}/${DB_NAME}"
echo "[deploy] Using DATABASE_URL=${DATABASE_URL} (exported for this session)"

# If your settings.py reads DATABASES directly, you can alternatively write settings or rely on env vars.

# 4) Run migrations and collectstatic
echo "[deploy] Running Django migrations"
python manage.py migrate --noinput

echo "[deploy] Collecting static files"
python manage.py collectstatic --noinput || echo "[deploy] collectstatic failed or no staticfiles configured"

# 5) Create a superuser if it doesn't exist (non-interactive)
DJANGO_SUPERUSER_EMAIL=${DJANGO_SUPERUSER_EMAIL:-admin@localhost}
DJANGO_SUPERUSER_USERNAME=${DJANGO_SUPERUSER_USERNAME:-admin}
DJANGO_SUPERUSER_PASSWORD=${DJANGO_SUPERUSER_PASSWORD:-adminpass}

echo "[deploy] Ensuring a Django superuser exists (${DJANGO_SUPERUSER_EMAIL})"
python - <<PYCODE
import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', '${DJANGO_SETTINGS_MODULE}')
import django
django.setup()
from django.contrib.auth import get_user_model
User = get_user_model()
email='${DJANGO_SUPERUSER_EMAIL}'
username='${DJANGO_SUPERUSER_USERNAME}'
password='${DJANGO_SUPERUSER_PASSWORD}'
if not User.objects.filter(email=email).exists():
    print('[deploy] Creating superuser', email)
    User.objects.create_superuser(username=username, email=email, password=password)
else:
    print('[deploy] Superuser already exists')
PYCODE

# 6) Final notes and recommended next steps
cat <<EOF
[deploy] Done.
Next steps (recommended):
 - Configure a process manager (systemd) or WSGI/ASGI server (gunicorn/daphne) to run the Django app.
 - Configure Nginx as a reverse proxy and static file server.
 - Use a secrets manager or environment variables for DB credentials rather than hardcoding.
 - Review firewall rules to allow DB only from trusted hosts if DB is remote.

To run this script:
sudo DB_NAME=batchit DB_USER=batchit_user DB_PASS='S3cure!' APP_DIR=/path/to/repo ./deploy.sh
EOF

exit 0
