#!/bin/bash

# GCP Compute Engine Deployment Script
# Creates a VM with specified requirements and runs the mannequin-segmenter service

set -e

# Configuration
PROJECT_ID=${PROJECT_ID:-""}
ZONE=${ZONE:-"europe-west1-b"}
INSTANCE_NAME="image-benchmark-vm"
MACHINE_TYPE="e2-medium"  # 2 vCPUs, 4GB RAM
BOOT_DISK_SIZE="100GB"
IMAGE_FAMILY="ubuntu-2204-lts"
IMAGE_PROJECT="ubuntu-os-cloud"
IMAGE_URI=${IMAGE_URI:-""} # e.g. europe-west1-docker.pkg.dev/PROJECT/REPO/mannequin:<tag>

echo "🚀 Deploying Image Download Benchmark to GCP Compute Engine"
echo "============================================================"

# Check if gcloud is installed and authenticated
if ! command -v gcloud &> /dev/null; then
    echo "❌ gcloud CLI not found. Please install Google Cloud SDK first."
    echo "   Visit: https://cloud.google.com/sdk/docs/install"
    exit 1
fi

# Check if authentication is available (WIF/ADC or active account)
if ! gcloud auth list --filter=status:ACTIVE --format="value(account)" | grep -q .; then
    # Fall back to ADC env if provided by the CI (WIF)
    if [ -n "${GOOGLE_APPLICATION_CREDENTIALS:-}" ] && [ -f "$GOOGLE_APPLICATION_CREDENTIALS" ]; then
        echo "✅ Using ADC credentials from GOOGLE_APPLICATION_CREDENTIALS"
    elif [ -n "${CLOUDSDK_AUTH_CREDENTIAL_FILE_OVERRIDE:-}" ] && [ -f "$CLOUDSDK_AUTH_CREDENTIAL_FILE_OVERRIDE" ]; then
        echo "✅ Using ADC credentials from CLOUDSDK_AUTH_CREDENTIAL_FILE_OVERRIDE"
    else
        echo "❌ Not authenticated with gcloud and no ADC credential file found."
        echo "   In CI use WIF; locally run: gcloud auth login"
        exit 1
    fi
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
echo "   Instance Name: $INSTANCE_NAME"
echo "   Machine Type: $MACHINE_TYPE (2 vCPUs, 4GB RAM)"
echo "   Boot Disk: $BOOT_DISK_SIZE"
echo "   OS: Ubuntu 22.04 LTS"
if [ -n "$IMAGE_URI" ]; then echo "   Image URI: $IMAGE_URI"; fi

# Enable required APIs
echo "🔧 Enabling required APIs..."
gcloud services enable compute.googleapis.com --project=$PROJECT_ID

# Check if instance already exists
if gcloud compute instances describe $INSTANCE_NAME --zone=$ZONE --project=$PROJECT_ID &>/dev/null; then
    echo "⚠️  Instance $INSTANCE_NAME already exists in zone $ZONE"
    
    if [ "${GITHUB_ACTIONS:-false}" = "true" ]; then
        echo "🤖 GitHub Actions detected - automatically recreating instance"
        echo "🗑️  Deleting existing instance..."
        gcloud compute instances delete $INSTANCE_NAME --zone=$ZONE --project=$PROJECT_ID --quiet
    else
        read -p "Do you want to delete and recreate it? (y/N): " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            echo "🗑️  Deleting existing instance..."
            gcloud compute instances delete $INSTANCE_NAME --zone=$ZONE --project=$PROJECT_ID --quiet
        else
            echo "❌ Deployment cancelled."
            exit 1
        fi
    fi
fi

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

# Handle credentials differently for GitHub Actions vs local development
MANNEQUIN_ENV_B64=""

if [ "${GITHUB_ACTIONS:-false}" = "true" ]; then
  echo "🤖 GitHub Actions detected - creating credentials from environment variables"
  
  # Create temporary credentials.env from environment variables in GitHub Actions
  TEMP_CREDS_FILE=$(mktemp)
  cat > "$TEMP_CREDS_FILE" << EOF
# Environment Variables for GitHub Actions Deployment
PROJECT_ID=${PROJECT_ID}
VM_ZONE=${ZONE}
GCP_SA_KEY=${GCP_SA_KEY:-}
EOF
  
  if [ -s "$TEMP_CREDS_FILE" ]; then
    echo "🗂️  Using GitHub Actions environment credentials"
    MANNEQUIN_ENV_B64=$(base64 "$TEMP_CREDS_FILE" | tr -d '\n')
    rm -f "$TEMP_CREDS_FILE"
  else
    echo "⚠️  Warning: No credentials found in GitHub Actions environment"
  fi
else
  echo "🏠 Local development detected - looking for credentials files"
  
  # Choose env file to pass to instance (prefer credentials.env, fall back to .env if exists)
  ENV_FILE=""
  if [ -f "credentials.env" ]; then
    ENV_FILE="credentials.env"
  elif [ -f ".env" ]; then
    ENV_FILE=".env"
  fi

  if [ -n "$ENV_FILE" ]; then
    echo "🗂️  Using env file: $ENV_FILE"
    # Base64 encode without newlines (portable across macOS/Linux)
    MANNEQUIN_ENV_B64=$(base64 "$ENV_FILE" | tr -d '\n')
  else
    echo "ℹ️  No env file found (credentials.env or .env). Proceeding without it."
  fi
fi

# Optional GitHub token from environment
GITHUB_TOKEN_META=""
if [ -n "${GITHUB_TOKEN:-}" ]; then
  GITHUB_TOKEN_META="$GITHUB_TOKEN"
fi

# Create the VM instance
echo "🖥️  Creating Compute Engine instance..."
echo "ℹ️  Note: Will clone repository and build Docker image on VM"

# Prepare metadata string
METADATA_STR="MANNEQUIN_ENV_B64=${MANNEQUIN_ENV_B64}"
if [ -n "$IMAGE_URI" ]; then
  METADATA_STR="${METADATA_STR},IMAGE_URI=${IMAGE_URI}"
fi
if [ -n "$GITHUB_TOKEN_META" ]; then
  METADATA_STR="${METADATA_STR},GITHUB_TOKEN=${GITHUB_TOKEN_META}"
fi
if [ -n "$GCP_SA_KEY_B64" ]; then
  METADATA_STR="${METADATA_STR},GCP_SA_KEY_B64=${GCP_SA_KEY_B64}"
fi

gcloud compute instances create $INSTANCE_NAME \
    --zone=$ZONE \
    --machine-type=$MACHINE_TYPE \
    --network-interface=network-tier=PREMIUM,stack-type=IPV4_ONLY,subnet=default \
    --metadata-from-file startup-script=startup-script-mannequin.sh \
    --metadata "$METADATA_STR" \
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

echo "✅ VM instance created successfully!"

# Get instance details
EXTERNAL_IP=$(gcloud compute instances describe $INSTANCE_NAME --zone=$ZONE --project=$PROJECT_ID --format='get(networkInterfaces[0].accessConfigs[0].natIP)')
INTERNAL_IP=$(gcloud compute instances describe $INSTANCE_NAME --zone=$ZONE --project=$PROJECT_ID --format='get(networkInterfaces[0].networkIP)')

echo ""
echo "🌐 Instance Details:"
echo "   Name: $INSTANCE_NAME"
echo "   Zone: $ZONE"
echo "   External IP: $EXTERNAL_IP"
echo "   Internal IP: $INTERNAL_IP"
echo "   Machine Type: $MACHINE_TYPE"

echo ""
echo "⏳ Startup script is running... This may take a few minutes."
echo "   The script will install Docker and run the mannequin-segmenter service on port 5001."

echo ""
echo "📋 Useful commands:"
echo "   # Connect via SSH:"
echo "   gcloud compute ssh $INSTANCE_NAME --zone=$ZONE --project=$PROJECT_ID"
echo ""
echo "   # Check startup script logs:"
echo "   gcloud compute ssh $INSTANCE_NAME --zone=$ZONE --project=$PROJECT_ID --command='sudo journalctl -u google-startup-scripts.service -f'"
echo ""
echo "   # Check service logs:"
echo "   gcloud compute ssh $INSTANCE_NAME --zone=$ZONE --project=$PROJECT_ID --command='sudo docker logs -f mannequin-segmenter'"
echo ""
echo "   # Stop instance:"
echo "   gcloud compute instances stop $INSTANCE_NAME --zone=$ZONE --project=$PROJECT_ID"
echo ""
echo "   # Delete instance:"
echo "   gcloud compute instances delete $INSTANCE_NAME --zone=$ZONE --project=$PROJECT_ID"

echo ""
echo "🎉 Deployment completed! The mannequin-segmenter API will start automatically on port 5001."


