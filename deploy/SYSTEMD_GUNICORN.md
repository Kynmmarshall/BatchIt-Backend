Systemd + Gunicorn + Nginx (example deployment)

This file explains how to install the systemd unit and Nginx site to run the Django app in production.

Files in this repo:
- `deploy/systemd/batchit.service` -- systemd unit file (edit placeholders before installing)
- `deploy/nginx/batchit.conf` -- example Nginx site (edit domain and paths)

Steps (run as root or with sudo):

1) Edit placeholders
- Open `deploy/systemd/batchit.service` and set:
  - `User` / `Group` (e.g., `www-data` or `deploy`)
  - `WorkingDirectory` -> absolute path to your repo (e.g., `/srv/batchit/BatchIt-Backend`)
  - `Environment PATH` -> path to your venv bin (e.g., `/srv/batchit/BatchIt-Backend/.venv/bin`)
  - `ExecStart` -> point to the venv `gunicorn` binary and WSGI path
- Open `deploy/nginx/batchit.conf` and set `server_name` and `alias` for static files.

2) Copy files to system locations

```bash
# copy systemd unit
sudo cp deploy/systemd/batchit.service /etc/systemd/system/batchit.service
# copy nginx site
sudo cp deploy/nginx/batchit.conf /etc/nginx/sites-available/batchit.conf
sudo ln -s /etc/nginx/sites-available/batchit.conf /etc/nginx/sites-enabled/
```

3) Create socket directory and set ownership (if using unix socket)

```bash
sudo mkdir -p /run
sudo chown www-data:www-data /run
```

4) Reload systemd and enable service

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now batchit.service
sudo systemctl status batchit.service
```

5) Test and reload Nginx

```bash
sudo nginx -t
sudo systemctl restart nginx
```

6) Logs and troubleshooting

- Check Gunicorn/systemd logs: `journalctl -u batchit.service -f`
- Check Nginx logs: `/var/log/nginx/batchit_error.log` and `/var/log/nginx/batchit_access.log`

Security and best practices
- Use a dedicated user for the app (do not run as root)
- Serve static files directly from Nginx via `STATIC_ROOT`
- Use `systemd` environment file or secrets manager for DB credentials, do NOT hardcode in unit file
- Consider using `socket` activation and file permissions carefully when binding to unix sockets

