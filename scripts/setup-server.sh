#!/bin/bash
# setup-server.sh - Automates direct Linux server deployment for AdaptiveArticulate

set -e

# Check root privileges
if [ "$EUID" -ne 0 ]; then
  echo "Please run as root (sudo)."
  exit 1
fi

echo "=== AdaptiveArticulate On-Server Deployment Setup ==="

# 1. Load configuration from .env file if it exists
ENV_FILE=".env"
if [ -f "$ENV_FILE" ]; then
  echo "Loading configurations from $ENV_FILE..."
  # Clean up and export the variables (excluding comments and empty lines)
  export $(grep -v '^#' "$ENV_FILE" | grep -v '^$' | xargs)
else
  echo ".env file not found. Using default hosting parameters..."
fi

# 2. Set default values for flexible parameters
SERVER_NAME=${SERVER_NAME:-"_"}
APP_DIR=${APP_DIR:-"/var/www/adaptive-articulate"}
WHISPER_MODEL=${WHISPER_MODEL:-"base"}
WEB_SERVER=${WEB_SERVER:-"nginx"}
FLASK_ENV=${FLASK_ENV:-"production"}
SECRET_KEY=${SECRET_KEY:-"prod-secret-key-change-me-$(openssl rand -hex 12)"}
PORT=${PORT:-"5000"}
WORKERS=${WORKERS:-"3"}

# Normalize WEB_SERVER to lowercase
WEB_SERVER=$(echo "$WEB_SERVER" | tr '[:upper:]' '[:lower:]')

# If DATABASE_URL is set, define the Environment line for systemd
if [ -n "$DATABASE_URL" ]; then
  DATABASE_URL_LINE="Environment=\"DATABASE_URL=${DATABASE_URL}\""
else
  DATABASE_URL_LINE=""
fi

# Files
SYSTEMD_SERVICE_FILE="/etc/systemd/system/adaptive-articulate.service"
NGINX_CONF_FILE="/etc/nginx/sites-available/adaptive-articulate"
NGINX_ENABLED_FILE="/etc/nginx/sites-enabled/adaptive-articulate"

# 3. Update OS packages and install core dependencies
echo "1. Installing system dependencies..."
apt-get update

if [ "$WEB_SERVER" = "apache2" ]; then
  WEB_SERVER_PKG="apache2"
else
  WEB_SERVER_PKG="nginx"
fi

apt-get install -y \
  python3-pip \
  python3-venv \
  python3-dev \
  ffmpeg \
  "$WEB_SERVER_PKG" \
  git \
  libpq-dev \
  build-essential

# 4. Setup project directory
echo "2. Setting up directory at $APP_DIR..."
if [ ! -d "$APP_DIR" ]; then
  mkdir -p "$APP_DIR"
fi

# Copy codebase to target directory if script is run outside it
CURRENT_DIR="$(pwd)"
if [ "$CURRENT_DIR" != "$APP_DIR" ] && [ -d "$APP_DIR" ]; then
  echo "Copying application files from $CURRENT_DIR to $APP_DIR..."
  cp -r . "$APP_DIR"
fi

# Adjusting ownership to www-data so web server has access
chown -R www-data:www-data "$APP_DIR"

# 5. Create virtual environment & install requirements
echo "3. Creating Python virtual environment..."
cd "$APP_DIR"
sudo -u www-data python3 -m venv venv
sudo -u www-data ./venv/bin/pip install --upgrade pip
sudo -u www-data ./venv/bin/pip install -r requirements.txt

# Pre-download Whisper model into the www-data cache
echo "4. Downloading Whisper '$WHISPER_MODEL' model..."
sudo -u www-data ./venv/bin/python -c "import whisper; whisper.load_model('${WHISPER_MODEL}')"

# 6. Initialize Database and run migrations
echo "5. Initializing database and running migrations..."
sudo -u www-data FLASK_APP=app:create_app ./venv/bin/flask db upgrade

# 7. Configure Systemd Service from template
echo "6. Configuring Systemd service..."
sed -e "s|{{APP_DIR}}|${APP_DIR}|g" \
    -e "s|{{FLASK_ENV}}|${FLASK_ENV}|g" \
    -e "s|{{SECRET_KEY}}|${SECRET_KEY}|g" \
    -e "s|{{DATABASE_URL_LINE}}|${DATABASE_URL_LINE}|g" \
    -e "s|{{WORKERS}}|${WORKERS}|g" \
    -e "s|{{PORT}}|${PORT}|g" \
    scripts/adaptive-articulate.service.template > "$SYSTEMD_SERVICE_FILE"

systemctl daemon-reload
systemctl enable adaptive-articulate
systemctl restart adaptive-articulate

# 8. Configure Web Server Reverse Proxy from template
if [ "$WEB_SERVER" = "apache2" ]; then
  echo "7. Configuring Apache2 reverse proxy..."
  APACHE_CONF_FILE="/etc/apache2/sites-available/adaptive-articulate.conf"
  sed -e "s|{{SERVER_NAME}}|${SERVER_NAME}|g" \
      -e "s|{{PORT}}|${PORT}|g" \
      -e "s|{{APP_DIR}}|${APP_DIR}|g" \
      scripts/apache.conf.template > "$APACHE_CONF_FILE"

  # Enable required modules
  a2enmod proxy || true
  a2enmod proxy_http || true
  a2enmod headers || true
  a2enmod rewrite || true

  # Disable default site to prevent host header conflicts
  if [ -f /etc/apache2/sites-enabled/000-default.conf ]; then
    a2dissite 000-default || true
  fi

  # Enable new site and reload Apache
  a2ensite adaptive-articulate || true
  systemctl restart apache2
else
  echo "7. Configuring Nginx reverse proxy..."
  sed -e "s|{{SERVER_NAME}}|${SERVER_NAME}|g" \
      -e "s|{{PORT}}|${PORT}|g" \
      -e "s|{{APP_DIR}}|${APP_DIR}|g" \
      scripts/nginx.conf.template > "$NGINX_CONF_FILE"

  # Link to sites-enabled if not already done
  if [ ! -f "$NGINX_ENABLED_FILE" ]; then
    ln -s "$NGINX_CONF_FILE" "$NGINX_ENABLED_FILE"
  fi

  # Remove default site if it conflicts
  if [ -f /etc/nginx/sites-enabled/default ]; then
    rm /etc/nginx/sites-enabled/default
  fi

  # Test and restart Nginx
  nginx -t
  systemctl restart nginx
fi

echo "=== Deployment Setup Complete! ==="
echo "Access the application at http://${SERVER_NAME} (if configured) or http://127.0.0.1:${PORT}"
