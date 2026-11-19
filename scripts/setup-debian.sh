#!/usr/bin/env bash
# Install on a dedicated Debian 12/13 server. Run from an uploaded project copy.
set -Eeuo pipefail
umask 022

usage() {
    cat <<'EOF'
Usage: sudo bash scripts/setup-debian.sh --host HOST [--email EMAIL | --http] [--skip-admin]

  --host HOST     Domain (HTTPS) or IPv4/domain (HTTP LAN).
  --email EMAIL   Let's Encrypt email; required unless --http is supplied.
  --http          HTTP only, for a trusted LAN. Secure cookies are disabled.
  --skip-admin    Only for restoring existing accounts; skip admin creation.

The project is copied to /opt/vomantis/app. Secrets are retained on reruns.
Fresh install: schema, permission groups, and one admin. No demo data.
Admin username defaults to admin; setup prompts for its password.
For unattended setup, export DJANGO_SUPERUSER_PASSWORD (username/email optional).
EOF
}
die() { echo "ERROR: $*" >&2; exit 1; }
trap 'echo "Setup failed at line $LINENO. Fix the error and rerun the same command." >&2' ERR
HOST=''
EMAIL=''
HTTP=0
SEED_ADMIN=1
while (($#)); do
    case "$1" in
        --host) [[ $# -ge 2 ]] || die 'Missing --host value'; HOST=$2; shift 2 ;;
        --email) [[ $# -ge 2 ]] || die 'Missing --email value'; EMAIL=$2; shift 2 ;;
        --http) HTTP=1; shift ;;
        --skip-admin) SEED_ADMIN=0; shift ;;
        -h|--help) usage; exit 0 ;;
        *) die "Unknown argument: $1" ;;
    esac
done
[[ $EUID -eq 0 ]] || die 'Run as root or with sudo.'
[[ ${#HOST} -le 253 && $HOST =~ ^[a-zA-Z0-9]([a-zA-Z0-9.-]*[a-zA-Z0-9])?$ ]] || die 'Specify a domain or IPv4 with --host (without scheme, port, or path).'
if ((HTTP == 0)); then
    [[ $HOST == *.* && ! $HOST =~ ^[0-9.]+$ ]] || die 'HTTPS requires a domain pointing to this server.'
    [[ $EMAIL =~ ^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$ ]] || die 'Specify --email for HTTPS, or --http for a trusted LAN.'
fi
source /etc/os-release
[[ $ID == debian && ( $VERSION_ID == 12 || $VERSION_ID == 13 ) ]] || die 'Supported systems: Debian 12 and 13.'
[[ -d /run/systemd/system ]] || die 'systemd must be running.'

SOURCE_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)
APP_DIR=/opt/vomantis/app
ENV_FILE=/etc/vomantis/vomantis.env
[[ -f $SOURCE_DIR/manage.py && -f $SOURCE_DIR/requirements-production.txt && -d $SOURCE_DIR/maintenance/migrations ]] || die 'Upload the complete VOMANTIS project first.'
SCHEME=https
((HTTP == 0)) || SCHEME=http
if [[ -f $ENV_FILE ]]; then
    # This file is root-owned shell-compatible KEY=value configuration.
    set -a
    source "$ENV_FILE"
    set +a
    [[ ${DJANGO_ALLOWED_HOSTS:-} == "$HOST" && ${DJANGO_CSRF_TRUSTED_ORIGINS:-} == "$SCHEME://$HOST" ]] || die 'Existing installation has a different host/protocol. Reuse its original arguments.'
    [[ ${DB_NAME:-} == vomantis && ${DB_USER:-} == vomantis && ${DB_HOST:-} == 127.0.0.1 && ${DB_PASSWORD:-} =~ ^[a-f0-9]{64}$ ]] || die 'Existing database settings differ from the installer configuration; manage this installation manually.'
fi

# Stop writers before package upgrades, code changes, or schema migration.
# A failed upgrade remains stopped until the operator fixes and reruns setup.
for unit in vomantis-scheduler.timer vomantis-scheduler.service vomantis.service; do
    if systemctl cat "$unit" >/dev/null 2>&1; then systemctl stop "$unit"; fi
done
export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get install -y python3 python3-venv python3-dev build-essential pkg-config \
    default-libmysqlclient-dev mariadb-server mariadb-client nginx rsync curl openssl ca-certificates tzdata
if ((HTTP == 0)); then
    apt-get install -y certbot python3-certbot-nginx
fi
systemctl enable --now mariadb nginx
# Keep the database on loopback; no remote DB user is created.
cat >/etc/mysql/mariadb.conf.d/60-vomantis.cnf <<'EOF'
[mysqld]
bind-address = 127.0.0.1
character-set-server = utf8mb4
collation-server = utf8mb4_unicode_ci
default-storage-engine = InnoDB
EOF
systemctl restart mariadb
# Django's timezone-aware date grouping needs MariaDB's timezone tables.
mariadb-tzinfo-to-sql /usr/share/zoneinfo | mariadb mysql

if ! id vomantis >/dev/null 2>&1; then
    useradd --system --user-group --home-dir /var/lib/vomantis --create-home --shell /usr/sbin/nologin vomantis
fi
install -d -m 0755 /opt/vomantis "$APP_DIR" /var/lib/vomantis /var/www/vomantis
install -d -o vomantis -g www-data -m 0750 /var/lib/vomantis/media
install -d -o vomantis -g www-data -m 0755 /var/www/vomantis/static
install -d -o root -g root -m 0700 /etc/vomantis
if [[ ! -f $ENV_FILE ]]; then
    DB_PASSWORD=$(openssl rand -hex 32)
    SECRET=$(openssl rand -hex 48)
    SECURE=1
    ((HTTP == 0)) || SECURE=0
    (umask 077; cat >"$ENV_FILE" <<EOF
DB_ENGINE=mariadb
DB_NAME=vomantis
DB_USER=vomantis
DB_PASSWORD=$DB_PASSWORD
DB_HOST=127.0.0.1
DB_PORT=3306
DJANGO_DEBUG=0
DJANGO_SECRET_KEY=$SECRET
DJANGO_ALLOWED_HOSTS=$HOST
DJANGO_CSRF_TRUSTED_ORIGINS=$SCHEME://$HOST
DJANGO_COOKIE_SECURE=$SECURE
DJANGO_SECURE_SSL_REDIRECT=$SECURE
DJANGO_TRUST_PROXY=1
DJANGO_STATIC_ROOT=/var/www/vomantis/static
DJANGO_MEDIA_ROOT=/var/lib/vomantis/media
PYTHONDONTWRITEBYTECODE=1
PYTHONUNBUFFERED=1
EOF
    )
fi
chmod 0600 "$ENV_FILE"
chown root:root "$ENV_FILE"
# Hex-only generated password is safe in SQL; never print it or pass it in argv.
mariadb <<EOF
CREATE DATABASE IF NOT EXISTS vomantis CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER IF NOT EXISTS 'vomantis'@'127.0.0.1' IDENTIFIED BY '$DB_PASSWORD';
ALTER USER 'vomantis'@'127.0.0.1' IDENTIFIED BY '$DB_PASSWORD';
GRANT ALL PRIVILEGES ON vomantis.* TO 'vomantis'@'127.0.0.1';
EOF

if [[ $SOURCE_DIR != "$APP_DIR" ]]; then
    rsync -a --chown=root:root --chmod=D755,F644 \
        --exclude='.git/' --exclude='.venv/' --exclude='.env*' --exclude='*.sqlite3*' \
        --exclude='.aws/' --exclude='.codex/' --exclude='.agents/' \
        --exclude='Main_data.sql' --exclude='seed_demo.py' --exclude='fixtures/' \
        --exclude='media/' --exclude='staticfiles/' --exclude='__pycache__/' --exclude='*.pyc' \
        --exclude='artifacts/' --exclude='ss_fitur/' --exclude='*.log' --exclude='*.json.gz' \
        "$SOURCE_DIR/" "$APP_DIR/"
fi
python3 -m venv /opt/vomantis/venv
/opt/vomantis/venv/bin/python -m pip install --upgrade pip
/opt/vomantis/venv/bin/python -m pip install -r "$APP_DIR/requirements-production.txt"

cat >/usr/local/bin/vomantis-manage <<'EOF'
#!/usr/bin/env bash
set -Eeuo pipefail
[[ $EUID -eq 0 ]] || { echo 'Run with sudo.' >&2; exit 1; }
set -a
source /etc/vomantis/vomantis.env
set +a
cd /opt/vomantis/app
exec runuser -u vomantis -g www-data -- /opt/vomantis/venv/bin/python manage.py "$@"
EOF
chmod 0755 /usr/local/bin/vomantis-manage
vomantis-manage check --database default
vomantis-manage migrate --noinput
vomantis-manage create_roles
if ((SEED_ADMIN)); then
    vomantis-manage seed_admin
fi
unset DJANGO_SUPERUSER_PASSWORD
vomantis-manage collectstatic --noinput

cat >/etc/systemd/system/vomantis.service <<'EOF'
[Unit]
Description=VOMANTIS Gunicorn
After=network.target mariadb.service
Requires=mariadb.service

[Service]
User=vomantis
Group=www-data
WorkingDirectory=/opt/vomantis/app
EnvironmentFile=/etc/vomantis/vomantis.env
RuntimeDirectory=vomantis
RuntimeDirectoryMode=0750
UMask=0007
ExecStart=/opt/vomantis/venv/bin/gunicorn --workers 3 --timeout 120 --bind unix:/run/vomantis/gunicorn.sock --access-logfile - --error-logfile - vomantis.wsgi:application
Restart=on-failure
RestartSec=5
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=true
ReadWritePaths=/var/lib/vomantis/media

[Install]
WantedBy=multi-user.target
EOF
cat >/etc/systemd/system/vomantis-scheduler.service <<'EOF'
[Unit]
Description=VOMANTIS monthly maintenance schedule generation
After=network.target mariadb.service
Requires=mariadb.service

[Service]
Type=oneshot
User=vomantis
Group=www-data
WorkingDirectory=/opt/vomantis/app
EnvironmentFile=/etc/vomantis/vomantis.env
ExecStart=/opt/vomantis/venv/bin/python manage.py generate_schedules
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=true
EOF
cat >/etc/systemd/system/vomantis-scheduler.timer <<'EOF'
[Unit]
Description=Run VOMANTIS scheduler every hour

[Timer]
OnCalendar=hourly
Persistent=true
Unit=vomantis-scheduler.service

[Install]
WantedBy=timers.target
EOF

# Preserve Certbot's generated HTTPS configuration on subsequent runs.
if [[ ! -f /etc/nginx/sites-available/vomantis ]]; then
    cat >/etc/nginx/sites-available/vomantis <<EOF
server {
    listen 80;
    listen [::]:80;
    server_name $HOST;
    client_max_body_size 110m;

    location /static/ {
        alias /var/www/vomantis/static/;
        expires 7d;
        add_header X-Content-Type-Options nosniff always;
    }

    # Uploaded files must pass Django's authentication and authorization.
    location /media/ { return 404; }
    location / {
        proxy_pass http://unix:/run/vomantis/gunicorn.sock;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$remote_addr;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_read_timeout 120s;
    }
}
EOF
fi
ln -sfn /etc/nginx/sites-available/vomantis /etc/nginx/sites-enabled/vomantis
nginx -t
systemctl daemon-reload
systemctl enable --now vomantis.service
systemctl reload nginx
if ((HTTP == 0)); then
    certbot --nginx --non-interactive --agree-tos --email "$EMAIL" --domains "$HOST" --redirect --keep-until-expiring
    systemctl enable --now certbot.timer
fi
# Verify that Gunicorn is serving requests before starting automatic writes.
curl --fail --silent --show-error --retry 10 --retry-connrefused --retry-delay 2 \
    --unix-socket /run/vomantis/gunicorn.sock -H "Host: $HOST" \
    -H "X-Forwarded-Proto: $SCHEME" http://localhost/login/ >/dev/null
systemctl start vomantis-scheduler.service
systemctl enable --now vomantis-scheduler.timer
echo "VOMANTIS ready: $SCHEME://$HOST/"
echo 'Administrator command: sudo vomantis-manage seed_admin'
echo 'Logs: sudo journalctl -u vomantis -u vomantis-scheduler -n 100 --no-pager'
