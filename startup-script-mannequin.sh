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
usermod -aG docker "$USER" || true

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

if [ -z "$IMAGE_URI" ]; then
  echo "❌ IMAGE_URI metadata is required (e.g., REGION-docker.pkg.dev/PROJECT/REPO/mannequin:TAG)"
  exit 1
fi

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

echo "🔑 Configuring Docker auth for registry..."
# Derive registry host from IMAGE_URI (before first '/')
REGISTRY_HOST="$(echo "$IMAGE_URI" | awk -F/ '{print $1}')"
if [[ "$REGISTRY_HOST" == *"gcr.io"* || "$REGISTRY_HOST" == *"pkg.dev"* ]]; then
  gcloud auth configure-docker "$REGISTRY_HOST" --quiet
fi

echo "🧹 Removing any existing container"
if docker ps -a --format '{{.Names}}' | grep -q '^mannequin-segmenter$'; then
  docker rm -f mannequin-segmenter || true
fi

echo "⬇️  Pulling image: $IMAGE_URI"
docker pull "$IMAGE_URI"

echo "▶️  Starting mannequin-segmenter container on port 5001"
docker run -d \
  --name mannequin-segmenter \
  --restart unless-stopped \
  --env-file "$ENV_PATH" \
  -p 5001:5001 \
  "$IMAGE_URI"

echo "✅ Setup complete. Service is listening on port 5001."
echo "ℹ️  Logs: docker logs -f mannequin-segmenter"


