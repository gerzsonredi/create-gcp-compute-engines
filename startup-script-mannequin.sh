#!/bin/bash

# GCP Compute Engine Startup Script for mannequin-segmenter service
# - Installs Docker and Google Cloud SDK
# - Pulls container image from Artifact Registry / GCR and runs on port 5001

set -euo pipefail

echo "🚀 Starting VM setup for mannequin-segmenter service..."

metadata_get() {
  local key="$1"; shift || true
  local default_value="${1:-}"
  local url="http://metadata.google.internal/computeMetadata/v1/instance/attributes/${key}"
  local header="Metadata-Flavor: Google"
  if curl -sf -H "$header" "$url" >/dev/null; then
    curl -sf -H "$header" "$url"
  else
    echo -n "$default_value"
  fi
}

apt-get update -y
apt-get upgrade -y
apt-get install -y \
  apt-transport-https \
  ca-certificates \
  curl \
  gnupg \
  lsb-release \
  git \
  nginx

echo "🐳 Installing Docker..."
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /usr/share/keyrings/docker-archive-keyring.gpg
echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/docker-archive-keyring.gpg] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" | tee /etc/apt/sources.list.d/docker.list > /dev/null
apt-get update -y
apt-get install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin
systemctl start docker
systemctl enable docker

# Allow current user to use docker (usually root in startup script)
usermod -aG docker "$(whoami)" || true

# Install Google Cloud SDK for Artifact Registry authentication
echo "📦 Installing Google Cloud SDK..."
echo "deb [signed-by=/usr/share/keyrings/cloud.google.gpg] http://packages.cloud.google.com/apt cloud-sdk main" | tee -a /etc/apt/sources.list.d/google-cloud-sdk.list
curl -fsSL https://packages.cloud.google.com/apt/doc/apt-key.gpg | gpg --dearmor -o /usr/share/keyrings/cloud.google.gpg
apt-get update -y
apt-get install -y google-cloud-sdk

APP_DIR="/opt/mannequin-segmenter"
REPO_DIR="${APP_DIR}/repo"
mkdir -p "$APP_DIR"
cd "$APP_DIR"

echo "🔐 Reading metadata..."
MANNEQUIN_ENV_B64="$(metadata_get MANNEQUIN_ENV_B64 "")"
IMAGE_URI="$(metadata_get IMAGE_URI "")"
GITHUB_TOKEN="$(metadata_get GITHUB_TOKEN "")"
GCP_SA_KEY_B64="$(metadata_get GCP_SA_KEY "")"

ENV_PATH="${APP_DIR}/.env"
if [ -n "$MANNEQUIN_ENV_B64" ]; then
  echo "$MANNEQUIN_ENV_B64" | base64 -d > "$ENV_PATH" || true
  if [ -s "$ENV_PATH" ]; then
    echo "✅ Wrote .env from instance metadata to $ENV_PATH"
  else
    echo "⚠️  Failed to decode MANNEQUIN_ENV_B64. Creating empty .env"
    : > "$ENV_PATH"
  fi
else
  echo "ℹ️  No MANNEQUIN_ENV_B64 metadata found. Creating empty .env at $ENV_PATH"
  : > "$ENV_PATH"
fi

# Ensure default PORT is present in env file
DEFAULT_PORT=5001
if ! grep -q '^PORT=' "$ENV_PATH"; then
  echo "PORT=$DEFAULT_PORT" >> "$ENV_PATH"
  echo "ℹ️  Added default PORT=$DEFAULT_PORT to $ENV_PATH"
fi

# Handle GCP Service Account Key from metadata (base64 encoded)
echo "🔍 Debug: GCP_SA_KEY_B64 is ${GCP_SA_KEY_B64:+SET (length: $(echo -n "$GCP_SA_KEY_B64" | wc -c))}${GCP_SA_KEY_B64:-NOT_SET}"
if [ -n "$GCP_SA_KEY_B64" ]; then
  echo "🔑 Decoding GCP Service Account Key from metadata..."
  GCP_SA_KEY_JSON=$(echo "$GCP_SA_KEY_B64" | base64 -d 2>/dev/null || echo "")
  if [ -n "$GCP_SA_KEY_JSON" ]; then
    # Remove any existing GCP_SA_KEY line first
    grep -v '^GCP_SA_KEY=' "$ENV_PATH" > "${ENV_PATH}.tmp" 2>/dev/null || cp "$ENV_PATH" "${ENV_PATH}.tmp"
    # Add GCP_SA_KEY to .env file (escaped for single line)
    echo "GCP_SA_KEY=$GCP_SA_KEY_JSON" >> "${ENV_PATH}.tmp"
    mv "${ENV_PATH}.tmp" "$ENV_PATH"
    echo "✅ Added GCP_SA_KEY to $ENV_PATH"
    echo "🔍 Debug: .env file now contains $(wc -l < "$ENV_PATH") lines"
  else
    echo "⚠️  Failed to decode GCP_SA_KEY from metadata"
  fi
else
  echo "⚠️  No GCP_SA_KEY found in metadata - service will not have GCS access"
fi

# ===============================================
# NGINX + STATIC RESULTS DIRECTORY SETUP
# ===============================================

# Create results directory and set permissions
RESULTS_DIR_DEFAULT="/var/www/d/results"
mkdir -p "$RESULTS_DIR_DEFAULT"
# Owner root, group www-data; allow read/execute (and write for owner)
chown -R root:www-data /var/www/d
chmod -R 755 /var/www/d

# Helpers to get env vars from .env safely (without sourcing whole file)
get_env_var() {
  local key="$1"
  local value
  value=$(grep -E "^${key}=" "$ENV_PATH" | head -n1 | cut -d'=' -f2- || true)
  echo -n "$value"
}

# Determine PUBLIC_BASE_URL default from instance external IP if missing
echo "🌐 Determining PUBLIC_BASE_URL and SECURE_LINK_SECRET defaults..."
PUBLIC_BASE_URL_VAL="$(get_env_var PUBLIC_BASE_URL)"
if [ -z "$PUBLIC_BASE_URL_VAL" ]; then
  EXT_IP=$(curl -sf -H "Metadata-Flavor: Google" \
    http://metadata.google.internal/computeMetadata/v1/instance/network-interfaces/0/access-configs/0/external-ip || echo "")
  if [ -n "$EXT_IP" ]; then
    PUBLIC_BASE_URL_VAL="http://$EXT_IP"
    echo "PUBLIC_BASE_URL=$PUBLIC_BASE_URL_VAL" >> "$ENV_PATH"
    echo "ℹ️  Set PUBLIC_BASE_URL default to $PUBLIC_BASE_URL_VAL"
  fi
fi

# Ensure SECURE_LINK_SECRET exists (generate if missing)
SECURE_LINK_SECRET_VAL="$(get_env_var SECURE_LINK_SECRET)"
if [ -z "$SECURE_LINK_SECRET_VAL" ]; then
  SECURE_LINK_SECRET_VAL=$(openssl rand -hex 16)
  echo "SECURE_LINK_SECRET=$SECURE_LINK_SECRET_VAL" >> "$ENV_PATH"
  echo "ℹ️  Generated SECURE_LINK_SECRET"
fi

# SIGNED_URL_TTL default
SIGNED_URL_TTL_VAL="$(get_env_var SIGNED_URL_TTL)"
if [ -z "$SIGNED_URL_TTL_VAL" ]; then
  SIGNED_URL_TTL_VAL=600
  echo "SIGNED_URL_TTL=$SIGNED_URL_TTL_VAL" >> "$ENV_PATH"
  echo "ℹ️  Set SIGNED_URL_TTL default to $SIGNED_URL_TTL_VAL"
fi

# RESULTS_DIR default
RESULTS_DIR_VAL="$(get_env_var RESULTS_DIR)"
if [ -z "$RESULTS_DIR_VAL" ]; then
  RESULTS_DIR_VAL="$RESULTS_DIR_DEFAULT"
  echo "RESULTS_DIR=$RESULTS_DIR_VAL" >> "$ENV_PATH"
  echo "ℹ️  Set RESULTS_DIR default to $RESULTS_DIR_VAL"
fi

# Configure Nginx secure_link for signed URLs: /d/results/<filename>?expires=...&md5=...
NGINX_CONF="/etc/nginx/conf.d/secure_results.conf"
cat > "$NGINX_CONF" <<EOF
server {
    listen 80 default_server;
    server_name _;

    # Static files with secure links
    set $secret $SECURE_LINK_SECRET_VAL;

    location /d/results/ {
        # Validate signature and expiry
        secure_link $arg_md5,$arg_expires;
        secure_link_md5 "$secure_link_expires$uri $secret";

        if ($secure_link = "") { return 403; }
        if ($secure_link = "0") { return 410; }

        root /var/www;
        try_files $uri =404;
        add_header Cache-Control "public, max-age=31536000";
    }
}
EOF

systemctl enable nginx
systemctl restart nginx

echo "📦 Cloning mannequin-segmenter repository..."
echo "🔍 Debug: REPO_DIR=$REPO_DIR"
echo "🔍 Debug: GITHUB_TOKEN is ${GITHUB_TOKEN:+SET}${GITHUB_TOKEN:-NOT_SET}"

if [ -d "$REPO_DIR" ]; then
  echo "🧹 Removing existing repository directory"
  rm -rf "$REPO_DIR"
fi

mkdir -p "$REPO_DIR"
cd "$REPO_DIR"
echo "🔍 Debug: Current directory: $(pwd)"

if [ -n "$GITHUB_TOKEN" ]; then
  echo "🔑 Using GitHub token for private repository access"
  echo "🔍 Debug: Attempting git clone with token..."
  if git clone https://${GITHUB_TOKEN}@github.com/gerzsonredi/mannequin-segmenter-new.git .; then
    echo "✅ Repository cloned successfully"
    echo "🔍 Debug: Repository contents:"
    ls -la
  else
    echo "❌ Failed to clone repository with token"
    exit 1
  fi
else
  echo "⚠️  No GitHub token found, attempting public clone"
  echo "🔍 Debug: Attempting public git clone..."
  if git clone https://github.com/gerzsonredi/mannequin-segmenter-new.git .; then
    echo "✅ Repository cloned successfully (public)"
    echo "🔍 Debug: Repository contents:"
    ls -la
  else
    echo "❌ Failed to clone repository (public access)"
    exit 1
  fi
fi

if [ ! -f "Dockerfile" ]; then
  echo "❌ Dockerfile not found in repository"
  echo "🔍 Debug: Current directory contents:"
  ls -la
  exit 1
else
  echo "✅ Dockerfile found in repository"
fi

echo "🔑 Configuring Docker auth for registry..."
# Configure registry authentication if IMAGE_URI is provided (for pushing custom builds)
if [ -n "$IMAGE_URI" ]; then
  REGISTRY_HOST="$(echo "$IMAGE_URI" | awk -F/ '{print $1}')"
  if [[ "$REGISTRY_HOST" == *"gcr.io"* || "$REGISTRY_HOST" == *"pkg.dev"* ]]; then
    gcloud auth configure-docker "$REGISTRY_HOST" --quiet
  fi
fi

echo "🧹 Removing any existing container"
if docker ps -a --format '{{.Names}}' | grep -q '^mannequin-segmenter$'; then
  docker rm -f mannequin-segmenter || true
fi

echo "🏗️  Building Docker image from source..."
docker build -t mannequin-segmenter:local -f Dockerfile .

echo "▶️  Starting mannequin-segmenter container on port 5001"
docker run -d \
  --name mannequin-segmenter \
  --restart unless-stopped \
  --env-file "$ENV_PATH" \
  -e PORT=5001 \
  -v "$RESULTS_DIR_VAL":"$RESULTS_DIR_VAL":rw \
  -p 5001:5001 \
  mannequin-segmenter:local

echo "✅ Setup complete. Service is listening on port 5001."
echo "ℹ️  Logs: docker logs -f mannequin-segmenter"


