#!/bin/bash

# GCP Compute Engine Deployment Script
# Creates a VM with specified requirements and runs the mannequin-segmenter service

set -e

# Optional config load (supports CONFIG_FILE env, first positional arg, or deployment-config.conf)
CONFIG_FILE="${CONFIG_FILE:-}"
if [ -z "$CONFIG_FILE" ] && [ -n "${1:-}" ]; then
  CONFIG_FILE="$1"
fi
if [ -z "$CONFIG_FILE" ] && [ -f "deployment-config.conf" ]; then
  CONFIG_FILE="deployment-config.conf"
fi
if [ -n "$CONFIG_FILE" ]; then
  if [ -f "$CONFIG_FILE" ]; then
    # shellcheck disable=SC1090
    . "$CONFIG_FILE"
    echo "🧩 Loaded configuration from $CONFIG_FILE"
  else
    echo "❌ Config file not found: $CONFIG_FILE"
    exit 1
  fi
fi

# Configuration (allow overrides from env or config file)
PROJECT_ID=${PROJECT_ID:-""}
ZONE=${ZONE:-"europe-west1-b"}
INSTANCE_NAME_PREFIX=${INSTANCE_NAME_PREFIX:-"image-benchmark-vm"}
MACHINE_TYPE=${MACHINE_TYPE:-"e2-medium"}  # 2 vCPUs, 4GB RAM
BOOT_DISK_SIZE=${BOOT_DISK_SIZE:-"100GB"}
IMAGE_FAMILY=${IMAGE_FAMILY:-"ubuntu-2204-lts"}
IMAGE_PROJECT=${IMAGE_PROJECT:-"ubuntu-os-cloud"}
IMAGE_URI=${IMAGE_URI:-""} # e.g. europe-west1-docker.pkg.dev/PROJECT/REPO/mannequin:<tag>
INSTANCE_COUNT=${INSTANCE_COUNT:-1}
SHOW_IP_ADDRESSES=${SHOW_IP_ADDRESSES:-true}

echo "🚀 Deploying Image Download Benchmark to GCP Compute Engine"
echo "============================================================"

# Check if gcloud is installed and authenticated
if ! command -v gcloud &> /dev/null; then
    echo "❌ gcloud CLI not found. Please install Google Cloud SDK first."
    echo "   Visit: https://cloud.google.com/sdk/docs/install"
    exit 1
fi

# Check if user is authenticated
if ! gcloud auth list --filter=status:ACTIVE --format="value(account)" | grep -q .; then
    echo "❌ Not authenticated with gcloud. Please run:"
    echo "   gcloud auth login"
    exit 1
fi

# Get or set project ID
if [ -z "$PROJECT_ID" ]; then
    PROJECT_ID=$(gcloud config get-value project 2>/dev/null)
    if [ -z "$PROJECT_ID" ]; then
        echo "❌ No project ID set. Please run:"
        echo "   gcloud config set project YOUR_PROJECT_ID"
        echo "   or set PROJECT_ID environment variable"
        exit 1
    fi
fi

echo "📋 Configuration:"
echo "   Project ID: $PROJECT_ID"
echo "   Zone: $ZONE"
echo "   Instance Prefix: $INSTANCE_NAME_PREFIX"
echo "   Instance Count: $INSTANCE_COUNT"
echo "   Machine Type: $MACHINE_TYPE (2 vCPUs, 4GB RAM)"
echo "   Boot Disk: $BOOT_DISK_SIZE"
echo "   OS: Ubuntu 22.04 LTS"
if [ -n "$IMAGE_URI" ]; then echo "   Image URI: $IMAGE_URI"; fi

# Enable required APIs
echo "🔧 Enabling required APIs..."
gcloud services enable compute.googleapis.com --project=$PROJECT_ID

# Create firewall rules for HTTP/HTTPS and mannequin-segmenter port 5001 (if needed)
echo "🔒 Setting up firewall rules..."
if ! gcloud compute firewall-rules describe allow-http --project=$PROJECT_ID &>/dev/null; then
    gcloud compute firewall-rules create allow-http \
        --allow tcp:80,tcp:443 \
        --source-ranges 0.0.0.0/0 \
        --description "Allow HTTP and HTTPS traffic" \
        --project=$PROJECT_ID
fi
if ! gcloud compute firewall-rules describe allow-mannequin-5001 --project=$PROJECT_ID &>/dev/null; then
    gcloud compute firewall-rules create allow-mannequin-5001 \
        --allow tcp:5001 \
        --source-ranges 0.0.0.0/0 \
        --description "Allow mannequin-segmenter service on port 5001" \
        --project=$PROJECT_ID
fi

# Prepare metadata for startup script and credentials
echo "🔧 Preparing instance metadata..."

# Choose env file to pass to instance (prefer credentials.env, fall back to .env if exists)
ENV_FILE=""
if [ -f "credentials.env" ]; then
  ENV_FILE="credentials.env"
elif [ -f ".env" ]; then
  ENV_FILE=".env"
fi

MANNEQUIN_ENV_B64=""
if [ -n "$ENV_FILE" ]; then
  echo "🗂️  Using env file: $ENV_FILE"
  # Base64 encode without newlines (portable across macOS/Linux)
  MANNEQUIN_ENV_B64=$(base64 "$ENV_FILE" | tr -d '\n')
else
  echo "ℹ️  No env file found (credentials.env or .env). Proceeding without it."
fi

# Optional GitHub token from environment
GITHUB_TOKEN_META=""
if [ -n "${GITHUB_TOKEN:-}" ]; then
  GITHUB_TOKEN_META="$GITHUB_TOKEN"
fi

# Create the VM instances
echo "🖥️  Creating Compute Engine instance(s)..."
if [ -z "$IMAGE_URI" ]; then
  echo "❌ IMAGE_URI environment variable not set. Example: europe-west1-docker.pkg.dev/$PROJECT_ID/mannequin-repo/mannequin:$(git rev-parse --short HEAD)"
  echo "   Set IMAGE_URI and rerun."
  exit 1
fi

TIMESTAMP=$(date +%s)

declare -a CREATED_INSTANCE_NAMES=()

for i in $(seq 1 $INSTANCE_COUNT); do
  INSTANCE_NAME="${INSTANCE_NAME_PREFIX}-${TIMESTAMP}-${i}"

  # Skip creation if instance already exists
  if gcloud compute instances describe "$INSTANCE_NAME" --zone=$ZONE --project=$PROJECT_ID &>/dev/null; then
    echo "⚠️  Instance $INSTANCE_NAME already exists in zone $ZONE, skipping creation."
  else
    echo "🧱 Creating instance: $INSTANCE_NAME"
    gcloud compute instances create $INSTANCE_NAME \
        --zone=$ZONE \
        --machine-type=$MACHINE_TYPE \
        --network-interface=network-tier=PREMIUM,stack-type=IPV4_ONLY,subnet=default \
        --metadata-from-file startup-script=startup-script-mannequin.sh \
        --metadata "MANNEQUIN_ENV_B64=${MANNEQUIN_ENV_B64},IMAGE_URI=${IMAGE_URI}" \
        --maintenance-policy=MIGRATE \
        --provisioning-model=STANDARD \
        --scopes=https://www.googleapis.com/auth/devstorage.read_only,https://www.googleapis.com/auth/logging.write,https://www.googleapis.com/auth/monitoring.write,https://www.googleapis.com/auth/servicecontrol,https://www.googleapis.com/auth/service.management.readonly,https://www.googleapis.com/auth/trace.append \
        --tags=http-server,https-server \
        --create-disk=auto-delete=yes,boot=yes,device-name=$INSTANCE_NAME,image=projects/$IMAGE_PROJECT/global/images/family/$IMAGE_FAMILY,mode=rw,size=$BOOT_DISK_SIZE,type=projects/$PROJECT_ID/zones/$ZONE/diskTypes/pd-standard \
        --no-shielded-secure-boot \
        --shielded-vtpm \
        --shielded-integrity-monitoring \
        --labels=environment=benchmark,application=image-download \
        --reservation-affinity=any \
        --project=$PROJECT_ID
    echo "✅ Created $INSTANCE_NAME"
  fi

  CREATED_INSTANCE_NAMES+=("$INSTANCE_NAME")

  if [ "$SHOW_IP_ADDRESSES" = true ]; then
    EXTERNAL_IP=$(gcloud compute instances describe $INSTANCE_NAME --zone=$ZONE --project=$PROJECT_ID --format='get(networkInterfaces[0].accessConfigs[0].natIP)')
    INTERNAL_IP=$(gcloud compute instances describe $INSTANCE_NAME --zone=$ZONE --project=$PROJECT_ID --format='get(networkInterfaces[0].networkIP)')
    echo ""
    echo "🌐 Instance Details:"
    echo "   Name: $INSTANCE_NAME"
    echo "   Zone: $ZONE"
    echo "   External IP: $EXTERNAL_IP"
    echo "   Internal IP: $INTERNAL_IP"
    echo "   Machine Type: $MACHINE_TYPE"
  fi
done

echo ""
echo "⏳ Startup scripts are running... This may take a few minutes."
echo "   Each instance installs Docker and runs the mannequin-segmenter service on port 5001."

echo ""
echo "📋 Useful commands:"
for name in "${CREATED_INSTANCE_NAMES[@]}"; do
  echo "   # Connect via SSH:"
  echo "   gcloud compute ssh $name --zone=$ZONE --project=$PROJECT_ID"
  echo "   # Check startup script logs:"
  echo "   gcloud compute ssh $name --zone=$ZONE --project=$PROJECT_ID --command='sudo journalctl -u google-startup-scripts.service -f'"
  echo "   # Check service logs:"
  echo "   gcloud compute ssh $name --zone=$ZONE --project=$PROJECT_ID --command='sudo docker logs -f mannequin-segmenter'"
  echo ""
done

echo "   # Stop instances:"
echo "   gcloud compute instances stop ${CREATED_INSTANCE_NAMES[*]} --zone=$ZONE --project=$PROJECT_ID"
echo ""
echo "   # Delete instances:"
echo "   gcloud compute instances delete ${CREATED_INSTANCE_NAMES[*]} --zone=$ZONE --project=$PROJECT_ID"

echo ""
echo "🎉 Deployment completed! The mannequin-segmenter API will start automatically on port 5001 on each instance."


