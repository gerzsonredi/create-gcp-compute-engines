#!/bin/bash

# GCP Compute Engine Deployment Script
# Creates a VM with specified requirements and runs the image download benchmark

set -e

# Configuration
PROJECT_ID=${PROJECT_ID:-""}
ZONE=${ZONE:-"europe-west1-b"}
INSTANCE_NAME="image-benchmark-vm"
MACHINE_TYPE="e2-medium"  # 2 vCPUs, 4GB RAM
BOOT_DISK_SIZE="100GB"
IMAGE_FAMILY="ubuntu-2204-lts"
IMAGE_PROJECT="ubuntu-os-cloud"

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
echo "   Instance Name: $INSTANCE_NAME"
echo "   Machine Type: $MACHINE_TYPE (2 vCPUs, 4GB RAM)"
echo "   Boot Disk: $BOOT_DISK_SIZE"
echo "   OS: Ubuntu 22.04 LTS"

# Enable required APIs
echo "🔧 Enabling required APIs..."
gcloud services enable compute.googleapis.com --project=$PROJECT_ID

# Check if instance already exists
if gcloud compute instances describe $INSTANCE_NAME --zone=$ZONE --project=$PROJECT_ID &>/dev/null; then
    echo "⚠️  Instance $INSTANCE_NAME already exists in zone $ZONE"
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

# Create firewall rule for HTTP traffic (if needed)
echo "🔒 Setting up firewall rules..."
if ! gcloud compute firewall-rules describe allow-http --project=$PROJECT_ID &>/dev/null; then
    gcloud compute firewall-rules create allow-http \
        --allow tcp:80,tcp:443 \
        --source-ranges 0.0.0.0/0 \
        --description "Allow HTTP and HTTPS traffic" \
        --project=$PROJECT_ID
fi

# Create the VM instance
echo "🖥️  Creating Compute Engine instance..."
gcloud compute instances create $INSTANCE_NAME \
    --zone=$ZONE \
    --machine-type=$MACHINE_TYPE \
    --network-interface=network-tier=PREMIUM,stack-type=IPV4_ONLY,subnet=default \
    --metadata-from-file startup-script=startup-script.sh \
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
echo "⏳ Startup script is running... This may take 3-5 minutes."
echo "   The script will install Docker and run the benchmark automatically."

echo ""
echo "📋 Useful commands:"
echo "   # Connect via SSH:"
echo "   gcloud compute ssh $INSTANCE_NAME --zone=$ZONE --project=$PROJECT_ID"
echo ""
echo "   # Check startup script logs:"
echo "   gcloud compute ssh $INSTANCE_NAME --zone=$ZONE --project=$PROJECT_ID --command='sudo journalctl -u google-startup-scripts.service -f'"
echo ""
echo "   # View benchmark results:"
echo "   gcloud compute ssh $INSTANCE_NAME --zone=$ZONE --project=$PROJECT_ID --command='sudo ls -la /opt/benchmark-results/'"
echo ""
echo "   # Stop instance:"
echo "   gcloud compute instances stop $INSTANCE_NAME --zone=$ZONE --project=$PROJECT_ID"
echo ""
echo "   # Delete instance:"
echo "   gcloud compute instances delete $INSTANCE_NAME --zone=$ZONE --project=$PROJECT_ID"

echo ""
echo "🎉 Deployment completed! The benchmark will run automatically on startup."
