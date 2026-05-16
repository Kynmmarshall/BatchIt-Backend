# Using Django migrations (recommended)

This project uses Django migrations to manage the database schema. Instead of running a raw SQL script, run Django migrations on your VPS. The `batchit_app` app already contains an initial migration at `batchit_app/migrations/0001_initial.py`.

Below are step-by-step instructions to provision a PostgreSQL database and apply migrations on a VPS.

1) Create database role and database (run as the `postgres` superuser):

```bash
# replace values as needed
sudo -u postgres psql -c "CREATE ROLE batchit_user WITH LOGIN PASSWORD 'secure_password';"
sudo -u postgres psql -c "CREATE DATABASE batchit OWNER batchit_user;"
sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE batchit TO batchit_user;"
```

2) Install Python dependencies (inside a virtualenv is recommended):

```bash
python -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

3) Configure PostgreSQL settings for Django

Update `batchit_proj/settings.py` to use the Postgres database (or set the `DATABASE_URL` environment variable if you use a helper):

```py
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': 'batchit',
        'USER': 'batchit_user',
        'PASSWORD': 'secure_password',
        'HOST': 'localhost',
        'PORT': '5432',
    }
}
```

Optionally, use environment variables and `django-environ` for safer configuration in production.

4) Run migrations (creates tables according to `batchit_app` models):

```bash
python manage.py migrate
```

5) Create a superuser and optional initial data:

```bash
python manage.py createsuperuser
python manage.py loaddata initial_fixture.json  # if you have fixtures
```

6) Additional production steps

- Configure a WSGI/ASGI server (Gunicorn + Nginx or Daphne + Nginx) and systemd services.
- Run `python manage.py collectstatic` if serving static files via a static server.
- Use migrations to evolve schema — do *not* hand-edit the database schema outside of migrations.

Why migrations?
- Migrations are the Django-native way to evolve schema; they preserve model history, can be rolled back, and are tracked in source control.
- Using migrations keeps development, CI, and production databases in sync.

If you'd like, I can:
- Generate/update any missing migrations locally (run `makemigrations`) and add them to the repo.
- Create a small `deploy.sh` that performs the above steps on a VPS.

---
File references:
- Initial migration: `batchit_app/migrations/0001_initial.py`
- Models: `batchit_app/models.py`
