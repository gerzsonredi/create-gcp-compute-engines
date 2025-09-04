#!/bin/bash

# Setup script to help configure GCP Service Account key automatically
# This script helps you set up the GCP_SA_KEY in credentials.env

set -e

echo "🔑 GCP Service Account Key Setup Helper"
echo "======================================"

CREDENTIALS_FILE="credentials.env"

# Check if credentials.env already exists
if [ -f "$CREDENTIALS_FILE" ]; then
    echo "📁 Found existing $CREDENTIALS_FILE"
    if grep -q "^GCP_SA_KEY=" "$CREDENTIALS_FILE"; then
        echo "✅ GCP_SA_KEY is already configured in $CREDENTIALS_FILE"
        read -p "Do you want to update it? (y/N): " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            echo "❌ Setup cancelled."
            exit 0
        fi
    fi
else
    echo "📝 Creating new $CREDENTIALS_FILE"
    cat > "$CREDENTIALS_FILE" << EOF
# Environment Variables for Local Development
PROJECT_ID=remix-466614
VM_ZONE=europe-west1-b
# GCP Service Account JSON key will be added below
EOF
fi

echo ""
echo "🔑 Please choose how to add your GCP Service Account key:"
echo "1. Paste JSON directly (recommended)"
echo "2. Load from file"
echo "3. Use existing gcloud credentials (automatic)"

read -p "Enter your choice (1-3): " -n 1 -r
echo

case $REPLY in
    1)
        echo "📋 Please paste your GCP Service Account JSON (press Ctrl+D when done):"
        echo "   Example: {\"type\":\"service_account\",\"project_id\":\"remix-466614\",...}"
        echo ""
        
        # Read multiline input until EOF
        GCP_SA_KEY=""
        while IFS= read -r line; do
            GCP_SA_KEY="${GCP_SA_KEY}${line}"
        done
        
        if [ -n "$GCP_SA_KEY" ]; then
            # Remove existing GCP_SA_KEY line and add the new one
            grep -v '^GCP_SA_KEY=' "$CREDENTIALS_FILE" > "${CREDENTIALS_FILE}.tmp" 2>/dev/null || cp "$CREDENTIALS_FILE" "${CREDENTIALS_FILE}.tmp"
            echo "GCP_SA_KEY=$GCP_SA_KEY" >> "${CREDENTIALS_FILE}.tmp"
            mv "${CREDENTIALS_FILE}.tmp" "$CREDENTIALS_FILE"
            echo "✅ GCP_SA_KEY added to $CREDENTIALS_FILE"
        else
            echo "❌ No JSON provided. Setup cancelled."
            exit 1
        fi
        ;;
    2)
        read -p "Enter path to your service account JSON file: " SA_FILE
        if [ -f "$SA_FILE" ]; then
            GCP_SA_KEY=$(cat "$SA_FILE" | tr -d '\n')
            # Remove existing GCP_SA_KEY line and add the new one
            grep -v '^GCP_SA_KEY=' "$CREDENTIALS_FILE" > "${CREDENTIALS_FILE}.tmp" 2>/dev/null || cp "$CREDENTIALS_FILE" "${CREDENTIALS_FILE}.tmp"
            echo "GCP_SA_KEY=$GCP_SA_KEY" >> "${CREDENTIALS_FILE}.tmp"
            mv "${CREDENTIALS_FILE}.tmp" "$CREDENTIALS_FILE"
            echo "✅ GCP_SA_KEY loaded from $SA_FILE and added to $CREDENTIALS_FILE"
        else
            echo "❌ File not found: $SA_FILE"
            exit 1
        fi
        ;;
    3)
        echo "🔍 Generating Service Account key from current gcloud credentials..."
        
        # Get current project
        PROJECT_ID=$(gcloud config get-value project 2>/dev/null)
        if [ -z "$PROJECT_ID" ]; then
            echo "❌ No gcloud project configured. Run: gcloud config set project YOUR_PROJECT_ID"
            exit 1
        fi
        
        echo "📋 Current project: $PROJECT_ID"
        
        # List service accounts
        echo "🔍 Available service accounts:"
        gcloud iam service-accounts list --project="$PROJECT_ID" --format="table(email,displayName)"
        
        read -p "Enter service account email (or press Enter for default): " SA_EMAIL
        if [ -z "$SA_EMAIL" ]; then
            # Try to find github-actions-sa or similar
            SA_EMAIL=$(gcloud iam service-accounts list --project="$PROJECT_ID" --filter="email:github-actions-sa@*" --format="value(email)" | head -n1)
            if [ -z "$SA_EMAIL" ]; then
                echo "❌ No default service account found. Please specify one."
                exit 1
            fi
            echo "🎯 Using: $SA_EMAIL"
        fi
        
        # Generate new key
        TEMP_KEY_FILE=$(mktemp).json
        if gcloud iam service-accounts keys create "$TEMP_KEY_FILE" --iam-account="$SA_EMAIL" --project="$PROJECT_ID"; then
            GCP_SA_KEY=$(cat "$TEMP_KEY_FILE" | tr -d '\n')
            rm -f "$TEMP_KEY_FILE"
            
            # Remove existing GCP_SA_KEY line and add the new one
            grep -v '^GCP_SA_KEY=' "$CREDENTIALS_FILE" > "${CREDENTIALS_FILE}.tmp" 2>/dev/null || cp "$CREDENTIALS_FILE" "${CREDENTIALS_FILE}.tmp"
            echo "GCP_SA_KEY=$GCP_SA_KEY" >> "${CREDENTIALS_FILE}.tmp"
            mv "${CREDENTIALS_FILE}.tmp" "$CREDENTIALS_FILE"
            echo "✅ New Service Account key generated and added to $CREDENTIALS_FILE"
        else
            echo "❌ Failed to generate Service Account key"
            exit 1
        fi
        ;;
    *)
        echo "❌ Invalid choice. Setup cancelled."
        exit 1
        ;;
esac

echo ""
echo "🎉 Setup complete!"
echo ""
echo "📋 Next steps:"
echo "1. Deploy VM: ./deploy-gcp.sh"
echo "2. The GCP_SA_KEY will be automatically set in the VM's .env file"
echo "3. No more manual SSH editing needed! 🎉"
echo ""
echo "🔍 Test the setup:"
echo "   ./deploy-gcp.sh"
echo "   # Then SSH into VM and check:"
echo "   # sudo cat /opt/mannequin-segmenter/.env | grep GCP_SA_KEY"
