# Deployment Guide

**Freshora Sp. Z. o. o. — Apple Caliber Scan**

---

## Option A — WSL2 Local Deployment (Windows)

### Prerequisites

- Windows 10/11 with WSL2 enabled
- Ubuntu 22.04 or 24.04 in WSL2
- Python 3.12 (via `deadsnakes` PPA if needed)

### Install System Dependencies

```bash
sudo apt-get update
sudo apt-get install -y \
  libcairo2 libpango-1.0-0 libpangocairo-1.0-0 \
  libgdk-pixbuf2.0-0 libffi-dev shared-mime-info \
  libgirepository1.0-dev python3-dev python3-pip python3-venv \
  python3.12 python3.12-venv
```

### Clone and Configure

```bash
cd /path/to/apple-caliber-scan
python3.12 -m venv .venv
.venv/bin/pip install -e ".[dev]"

cp .env.example .env
# Edit .env:
nano .env
```

Required `.env` values:
```
ACS_WEB_PASSWORD=choose_a_strong_password
ACS_WEB_SECRET_KEY=$(python3 -c "import secrets; print(secrets.token_hex(32))")
```

### Initialize Database

```bash
make init-db
```

### Run Web UI

```bash
make run-web
# Web UI available at http://localhost:8000 from Windows browser
```

WSL2 automatically forwards localhost — no port forwarding configuration needed.

### Run Telegram Bot (optional)

Set `ACS_TELEGRAM_TOKEN` in `.env` (obtain from @BotFather), then:

```bash
make run-bot
```

### Running as Background Services (WSL2)

To keep the server running after closing the terminal, use `screen` or `tmux`:

```bash
screen -S acs-web
make run-web
# Ctrl+A then D to detach
```

---

## Option B — VPS Deployment (Vultr / Ubuntu 22.04)

### Server Requirements

| Resource | Minimum | Recommended |
|----------|---------|-------------|
| CPU | 1 vCPU | 2 vCPU |
| RAM | 1 GB | 2 GB |
| Disk | 20 GB | 40 GB |
| OS | Ubuntu 22.04 LTS | Ubuntu 22.04 LTS |

### Initial Server Setup

```bash
# As root:
apt-get update && apt-get upgrade -y
adduser freshora
usermod -aG sudo freshora
su - freshora
```

### Install System Dependencies

```bash
sudo apt-get install -y \
  libcairo2 libpango-1.0-0 libpangocairo-1.0-0 \
  libgdk-pixbuf2.0-0 libffi-dev shared-mime-info \
  libgirepository1.0-dev python3-dev python3-pip python3-venv \
  git nginx certbot python3-certbot-nginx
```

### Clone and Configure

```bash
cd /home/freshora
git clone <repo_url> apple-caliber-scan
cd apple-caliber-scan

python3 -m venv .venv
.venv/bin/pip install -e "."

cp .env.example .env
nano .env
```

Set in `.env`:
```
ACS_HOST=0.0.0.0
ACS_PORT=8000
ACS_WEB_PASSWORD=<strong_password>
ACS_WEB_SECRET_KEY=<64_hex_chars>
ACS_DATA_DIR=/home/freshora/acs-data
ACS_TELEGRAM_TOKEN=<bot_token_if_using_bot>
```

### Initialize Database

```bash
make init-db
```

### Systemd Service — Web UI

```bash
sudo nano /etc/systemd/system/acs-web.service
```

```ini
[Unit]
Description=Apple Caliber Scan Web UI
After=network.target

[Service]
User=freshora
WorkingDirectory=/home/freshora/apple-caliber-scan
EnvironmentFile=/home/freshora/apple-caliber-scan/.env
ExecStart=/home/freshora/apple-caliber-scan/.venv/bin/uvicorn \
    apple_caliber_scan.web.app:create_app \
    --factory --host 0.0.0.0 --port 8000
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable acs-web
sudo systemctl start acs-web
```

### Systemd Service — Telegram Bot (optional)

```bash
sudo nano /etc/systemd/system/acs-bot.service
```

```ini
[Unit]
Description=Apple Caliber Scan Telegram Bot
After=network.target

[Service]
User=freshora
WorkingDirectory=/home/freshora/apple-caliber-scan
EnvironmentFile=/home/freshora/apple-caliber-scan/.env
ExecStart=/home/freshora/apple-caliber-scan/.venv/bin/python -m apple_caliber_scan run-bot
Restart=on-failure
RestartSec=10

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable acs-bot
sudo systemctl start acs-bot
```

### Nginx Reverse Proxy

```bash
sudo nano /etc/nginx/sites-available/acs
```

```nginx
server {
    listen 80;
    server_name your-domain.com;

    client_max_body_size 250M;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 300s;
    }
}
```

```bash
sudo ln -s /etc/nginx/sites-available/acs /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

### HTTPS with Let's Encrypt

```bash
sudo certbot --nginx -d your-domain.com
```

Certbot will automatically update the nginx config and set up renewal.

---

## Data Directory Layout

```
$ACS_DATA_DIR/               (default: ./data)
├── apple_caliber.db         — SQLite database
├── previews/                — scan preview PNGs (kept)
└── reports/                 — HTML and PDF reports (kept)
```

Scan files are **deleted immediately after ingest** — only the preview PNG is retained.

---

## Backup

Backup these paths regularly:
- `$ACS_DATA_DIR/apple_caliber.db` — all batch and scan metadata
- `$ACS_DATA_DIR/previews/` — preview images
- `$ACS_DATA_DIR/reports/` — generated reports
- `.env` — configuration (store in a secrets manager, not plain backup)

```bash
# Simple daily backup example:
tar -czf /backup/acs-$(date +%F).tar.gz \
    $ACS_DATA_DIR/apple_caliber.db \
    $ACS_DATA_DIR/previews/ \
    $ACS_DATA_DIR/reports/
```

---

## Updating

```bash
cd /home/freshora/apple-caliber-scan
git pull
.venv/bin/pip install -e "."
sudo systemctl restart acs-web acs-bot
```

No database migrations are required for patch updates. Major version updates will note
migration steps in their changelog.
