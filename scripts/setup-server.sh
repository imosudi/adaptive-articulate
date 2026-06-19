#!/bin/bash
# setup-server.sh - Automates direct Linux server deployment for AdaptiveArticulate

set -e

# App configuration
APP_DIR="/var/www/adaptive-articulate"
SYSTEMD_SERVICE_FILE="/etc/systemd/system/adaptive-articulate.service"
NGINX_CONF_FILE="/etc/nginx/sites-available/adaptive-articulate"
NGINX_ENABLED_FILE="/etc/nginx/sites-enabled/adaptive-articulate"

echo "=== AdaptiveArticulate On-Server Deployment Setup ==="

# Check root privileges
if [ "$EUID" -ne 0 ]; then
  echo "Please run as root (sudo)."
  exit 1
fi

# 1. Update OS packages and install core dependencies
echo "1. Installing system dependencies..."
apt-get update
apt-get install -y \
  python3-pip \
  python3-venv \
  python3-dev \
  ffmpeg \
  nginx \
  git \
  libpq-dev \
  build-essential

# 2. Setup project directory
echo "2. Setting up directory at $APP_DIR..."
if [ ! -d "$APP_DIR" ]; then
  mkdir -p "$APP_DIR"
fi

# In a real deployment, copy the codebase here
# For setup purposes, we assume files are located in $APP_DIR
# Adjusting ownership to www-data so web server has access
chown -R www-data:www-data "$APP_DIR"

# 3. Create virtual environment & install requirements
echo "3. Creating Python virtual environment..."
cd "$APP_DIR"
sudo -u www-data python3 -m venv venv
sudo -u www-data ./venv/bin/pip install --upgrade pip
sudo -u www-data ./venv/bin/pip install -r requirements.txt

# Pre-download Whisper model into the www-data cache
echo "4. Downloading Whisper 'base' model..."
sudo -u www-data ./venv/bin/python -c "import whisper; whisper.load_model('base')"

# 4. Initialize Database and run migrations
echo "5. Initializing database and running migrations..."
sudo -u www-data FLASK_APP=app:create_app ./venv/bin/flask db upgrade

# 5. Configure Systemd Service
echo "6. Configuring Systemd service..."
cp scripts/adaptive-articulate.service "$SYSTEMD_SERVICE_FILE"
systemctl daemon-reload
systemctl enable adaptive-articulate
systemctl restart adaptive-articulate

# 6. Configure Nginx Reverse Proxy
echo "7. Configuring Nginx reverse proxy..."
cp scripts/nginx.conf "$NGINX_CONF_FILE"

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

echo "=== Deployment Setup Complete! ==="
echo "Access the application at http://your_server_domain_or_ip"
