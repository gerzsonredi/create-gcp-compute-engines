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
  git

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
GCP_SA_KEY_B64="$(metadata_get GCP_SA_KEY_B64 "")"

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
if [ -n "$GCP_SA_KEY_B64" ]; then
  echo "🔑 Decoding GCP Service Account Key from metadata..."
  GCP_SA_KEY_JSON=$(echo "$GCP_SA_KEY_B64" | base64 -d 2>/dev/null || echo "")
  if [ -n "$GCP_SA_KEY_JSON" ]; then
    # Add GCP_SA_KEY to .env file (escaped for single line)
    if ! grep -q '^GCP_SA_KEY=' "$ENV_PATH"; then
      echo "GCP_SA_KEY=$GCP_SA_KEY_JSON" >> "$ENV_PATH"
      echo "✅ Added GCP_SA_KEY to $ENV_PATH"
    fi
  else
    echo "⚠️  Failed to decode GCP_SA_KEY_B64 from metadata"
  fi
fi

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
  -p 5001:5001 \
  mannequin-segmenter:local

echo "✅ Setup complete. Service is listening on port 5001."
echo "ℹ️  Logs: docker logs -f mannequin-segmenter"


