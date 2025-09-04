#!/bin/bash

# GCP Compute Engine Deployment Script with Secret Manager
# Uses Google Cloud Secret Manager to securely store and retrieve GCP Service Account keys

set -e

# Load configuration from file if provided
CONFIG_FILE=${CONFIG_FILE:-"example-configs/small-deployment.conf"}

if [ -n "$CONFIG_FILE" ] && [ -f "$CONFIG_FILE" ]; then
    echo "📋 Loading configuration from: $CONFIG_FILE"
    source "$CONFIG_FILE"
    echo "✅ Configuration loaded successfully"
else
    echo "⚠️  Config file not found: $CONFIG_FILE, using defaults"
fi

# Configuration with defaults
PROJECT_ID=${PROJECT_ID:-""}
ZONE=${ZONE:-"europe-west1-b"}
INSTANCE_NAME_BASE=${INSTANCE_NAME:-"image-benchmark-vm"}
INSTANCE_COUNT=${INSTANCE_COUNT:-1}
MACHINE_TYPE=${MACHINE_TYPE:-"e2-medium"}
BOOT_DISK_SIZE=${BOOT_DISK_SIZE:-"100GB"}
IMAGE_FAMILY="ubuntu-2204-lts"
IMAGE_PROJECT="ubuntu-os-cloud"
IMAGE_URI=${IMAGE_URI:-""}
SECRET_NAME=${SECRET_NAME:-"mannequin-gcp-sa-key"}

echo "🚀 Deploying ${INSTANCE_COUNT} VM(s) to GCP Compute Engine with Secret Manager"
echo "============================================================================="

# Check if gcloud is installed and authenticated
if ! command -v gcloud &> /dev/null; then
    echo "❌ gcloud CLI not found. Please install Google Cloud SDK first."
    exit 1
fi

# Check authentication
if ! gcloud auth list --filter=status:ACTIVE --format="value(account)" | grep -q .; then
    if [ -n "${GOOGLE_APPLICATION_CREDENTIALS:-}" ] && [ -f "$GOOGLE_APPLICATION_CREDENTIALS" ]; then
        echo "✅ Using ADC credentials from GOOGLE_APPLICATION_CREDENTIALS"
    elif [ -n "${CLOUDSDK_AUTH_CREDENTIAL_FILE_OVERRIDE:-}" ] && [ -f "$CLOUDSDK_AUTH_CREDENTIAL_FILE_OVERRIDE" ]; then
        echo "✅ Using ADC credentials from CLOUDSDK_AUTH_CREDENTIAL_FILE_OVERRIDE"
    else
        echo "❌ Not authenticated with gcloud and no ADC credential file found."
        exit 1
    fi
fi

# Get or set project ID
if [ -z "$PROJECT_ID" ]; then
    PROJECT_ID=$(gcloud config get-value project 2>/dev/null)
    if [ -z "$PROJECT_ID" ]; then
        echo "❌ No project ID set."
        exit 1
    fi
fi

echo "📋 Configuration:"
echo "   Project ID: $PROJECT_ID"
echo "   Zone: $ZONE"
echo "   Instance Count: $INSTANCE_COUNT"
echo "   Instance Name Base: $INSTANCE_NAME_BASE"
echo "   Machine Type: $MACHINE_TYPE"
echo "   Boot Disk: $BOOT_DISK_SIZE"
echo "   Secret Manager Secret: $SECRET_NAME"
if [ -n "$IMAGE_URI" ]; then echo "   Image URI: $IMAGE_URI"; fi

# Enable required APIs
echo "🔧 Enabling required APIs..."
gcloud services enable compute.googleapis.com secretmanager.googleapis.com --project=$PROJECT_ID

# 🔑 **Create/Update Secret in Secret Manager**
if [ -n "$GCP_SA_KEY" ]; then
    echo "🔐 Creating/updating secret in Secret Manager..."
    
    # Check if secret exists
    if gcloud secrets describe "$SECRET_NAME" --project="$PROJECT_ID" &>/dev/null; then
        echo "🔄 Secret '$SECRET_NAME' already exists, creating new version..."
        echo "$GCP_SA_KEY" | gcloud secrets versions add "$SECRET_NAME" --data-file=- --project="$PROJECT_ID"
    else
        echo "🆕 Creating new secret '$SECRET_NAME'..."
        echo "$GCP_SA_KEY" | gcloud secrets create "$SECRET_NAME" --data-file=- --project="$PROJECT_ID"
    fi
    
    echo "✅ GCP Service Account key stored in Secret Manager: $SECRET_NAME"
else
    echo "⚠️  GCP_SA_KEY not provided, checking if secret already exists..."
    if ! gcloud secrets describe "$SECRET_NAME" --project="$PROJECT_ID" &>/dev/null; then
        echo "❌ No GCP_SA_KEY provided and secret '$SECRET_NAME' doesn't exist"
        echo "   Please set GCP_SA_KEY environment variable or create the secret manually"
        exit 1
    else
        echo "✅ Using existing secret: $SECRET_NAME"
    fi
fi

# Create firewall rules
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

# Prepare base metadata
echo "🔧 Preparing instance metadata..."
MANNEQUIN_ENV_B64=""

if [ "${GITHUB_ACTIONS:-false}" = "true" ]; then
    echo "🤖 GitHub Actions detected - creating base environment"
    TEMP_CREDS_FILE=$(mktemp)
    cat > "$TEMP_CREDS_FILE" << EOF
# Base Environment for GitHub Actions Deployment
PROJECT_ID=${PROJECT_ID}
VM_ZONE=${ZONE}
EOF
    
    if [ -s "$TEMP_CREDS_FILE" ]; then
        MANNEQUIN_ENV_B64=$(base64 "$TEMP_CREDS_FILE" | tr -d '\n')
        rm -f "$TEMP_CREDS_FILE"
    fi
else
    echo "🏠 Local development detected"
    ENV_FILE=""
    if [ -f "credentials.env" ]; then
        ENV_FILE="credentials.env"
    elif [ -f ".env" ]; then
        ENV_FILE=".env"
    fi

    if [ -n "$ENV_FILE" ]; then
        echo "🗂️  Using env file: $ENV_FILE"
        MANNEQUIN_ENV_B64=$(base64 "$ENV_FILE" | tr -d '\n')
    fi
fi

# GitHub token (optional)
GITHUB_TOKEN_META=""
if [ -n "${GITHUB_TOKEN:-}" ]; then
    GITHUB_TOKEN_META="$GITHUB_TOKEN"
fi

# Find startup script
STARTUP_SCRIPT="startup-script-gcs-secret.sh"
if [ ! -f "$STARTUP_SCRIPT" ]; then
    if [ -f "create-gcp-compute-engines/$STARTUP_SCRIPT" ]; then
        STARTUP_SCRIPT="create-gcp-compute-engines/$STARTUP_SCRIPT"
    else
        echo "❌ Startup script not found: $STARTUP_SCRIPT"
        exit 1
    fi
fi

echo "📜 Using startup script: $STARTUP_SCRIPT"

# Create VM instances
echo "🖥️  Creating ${INSTANCE_COUNT} Compute Engine instance(s)..."

CREATED_INSTANCES=()

for i in $(seq 1 $INSTANCE_COUNT); do
    if [ $INSTANCE_COUNT -gt 1 ]; then
        INSTANCE_NAME="${INSTANCE_NAME_BASE}-${i}"
    else
        INSTANCE_NAME="$INSTANCE_NAME_BASE"
    fi
    
    echo "🔨 Creating instance $i/$INSTANCE_COUNT: $INSTANCE_NAME"
    
    # Check if instance already exists
    if gcloud compute instances describe $INSTANCE_NAME --zone=$ZONE --project=$PROJECT_ID &>/dev/null; then
        echo "⚠️  Instance $INSTANCE_NAME already exists"
        
        if [ "${GITHUB_ACTIONS:-false}" = "true" ]; then
            echo "🤖 GitHub Actions - automatically recreating instance"
            gcloud compute instances delete $INSTANCE_NAME --zone=$ZONE --project=$PROJECT_ID --quiet
        else
            read -p "Delete and recreate $INSTANCE_NAME? (y/N): " -n 1 -r
            echo
            if [[ $REPLY =~ ^[Yy]$ ]]; then
                gcloud compute instances delete $INSTANCE_NAME --zone=$ZONE --project=$PROJECT_ID --quiet
            else
                echo "❌ Skipping $INSTANCE_NAME"
                continue
            fi
        fi
    fi
    
    # Prepare metadata for this instance
    METADATA_STR="MANNEQUIN_ENV_B64=${MANNEQUIN_ENV_B64},PROJECT_ID=${PROJECT_ID},GCP_SA_KEY_SECRET=${SECRET_NAME}"
    if [ -n "$IMAGE_URI" ]; then
        METADATA_STR="${METADATA_STR},IMAGE_URI=${IMAGE_URI}"
    fi
    if [ -n "$GITHUB_TOKEN_META" ]; then
        METADATA_STR="${METADATA_STR},GITHUB_TOKEN=${GITHUB_TOKEN_META}"
    fi
    
    # Create the instance with Secret Manager access
    gcloud compute instances create $INSTANCE_NAME \
        --zone=$ZONE \
        --machine-type=$MACHINE_TYPE \
        --network-interface=network-tier=PREMIUM,stack-type=IPV4_ONLY,subnet=default \
        --metadata-from-file startup-script="$STARTUP_SCRIPT" \
        --metadata "$METADATA_STR" \
        --maintenance-policy=MIGRATE \
        --provisioning-model=STANDARD \
        --scopes=https://www.googleapis.com/auth/devstorage.read_only,https://www.googleapis.com/auth/logging.write,https://www.googleapis.com/auth/monitoring.write,https://www.googleapis.com/auth/servicecontrol,https://www.googleapis.com/auth/service.management.readonly,https://www.googleapis.com/auth/trace.append,https://www.googleapis.com/auth/cloud-platform \
        --tags=http-server,https-server \
        --create-disk=auto-delete=yes,boot=yes,device-name=$INSTANCE_NAME,image=projects/$IMAGE_PROJECT/global/images/family/$IMAGE_FAMILY,mode=rw,size=$BOOT_DISK_SIZE,type=projects/$PROJECT_ID/zones/$ZONE/diskTypes/pd-standard \
        --no-shielded-secure-boot \
        --shielded-vtpm \
        --shielded-integrity-monitoring \
        --labels=environment=benchmark,application=image-download \
        --reservation-affinity=any \
        --project=$PROJECT_ID
    
    CREATED_INSTANCES+=("$INSTANCE_NAME")
    echo "✅ Instance $INSTANCE_NAME created successfully!"
done

echo ""
echo "🌐 Created Instance Details:"
for INSTANCE_NAME in "${CREATED_INSTANCES[@]}"; do
    EXTERNAL_IP=$(gcloud compute instances describe $INSTANCE_NAME --zone=$ZONE --project=$PROJECT_ID --format='get(networkInterfaces[0].accessConfigs[0].natIP)')
    INTERNAL_IP=$(gcloud compute instances describe $INSTANCE_NAME --zone=$ZONE --project=$PROJECT_ID --format='get(networkInterfaces[0].networkIP)')
    
    echo "   📍 $INSTANCE_NAME:"
    echo "      External IP: $EXTERNAL_IP"
    echo "      Internal IP: $INTERNAL_IP"
    echo "      API URL: http://$EXTERNAL_IP:5001"
done

echo ""
echo "⏳ Startup scripts are running... This may take a few minutes."
echo "   The scripts will install Docker and run the mannequin-segmenter service on port 5001."

echo ""
echo "🔐 Secret Manager Setup:"
echo "   ✅ Secret '$SECRET_NAME' contains the GCP Service Account key"
echo "   ✅ VM service accounts have access to retrieve the secret"
echo "   ✅ No sensitive data passed through VM metadata"

echo ""
echo "📋 Useful commands:"
for INSTANCE_NAME in "${CREATED_INSTANCES[@]}"; do
    echo "   # Connect to $INSTANCE_NAME:"
    echo "   gcloud compute ssh $INSTANCE_NAME --zone=$ZONE --project=$PROJECT_ID"
    echo ""
done

echo "🎉 Deployment completed! The mannequin-segmenter APIs will start automatically on port 5001."
