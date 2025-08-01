#!/bin/bash

# GCP Setup Script for GitHub Actions Deployment
# This script creates the necessary GCP resources and permissions

set -e

echo "🚀 GCP SETUP FOR GITHUB ACTIONS DEPLOYMENT"
echo "=========================================="

# Variables
PROJECT_ID="${GCP_PROJECT_ID:-$(gcloud config get-value project)}"
SERVICE_ACCOUNT_NAME="github-actions-deployer"
SERVICE_ACCOUNT_EMAIL="${SERVICE_ACCOUNT_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"
REGION="europe-west4"
REPOSITORY_NAME="garment-measuring-repo"

echo "📋 Configuration:"
echo "  Project ID: $PROJECT_ID"
echo "  Service Account: $SERVICE_ACCOUNT_EMAIL"
echo "  Region: $REGION"
echo "  Repository: $REPOSITORY_NAME"
echo

# Check if project exists and is accessible
echo "🔍 Verifying project access..."
if ! gcloud projects describe "$PROJECT_ID" >/dev/null 2>&1; then
    echo "❌ Cannot access project '$PROJECT_ID'. Please check:"
    echo "   1. Project ID is correct"
    echo "   2. You have access to the project"
    echo "   3. You are authenticated: gcloud auth login"
    exit 1
fi

# Enable required APIs
echo "🔧 Enabling required APIs..."
gcloud services enable \
    artifactregistry.googleapis.com \
    run.googleapis.com \
    cloudbuild.googleapis.com \
    storage-api.googleapis.com \
    logging.googleapis.com \
    sql-component.googleapis.com \
    --project="$PROJECT_ID"

echo "✅ APIs enabled successfully"

# Create Service Account
echo "👤 Creating Service Account..."
if gcloud iam service-accounts describe "$SERVICE_ACCOUNT_EMAIL" --project="$PROJECT_ID" >/dev/null 2>&1; then
    echo "ℹ️  Service Account already exists: $SERVICE_ACCOUNT_EMAIL"
else
    gcloud iam service-accounts create "$SERVICE_ACCOUNT_NAME" \
        --display-name="GitHub Actions Deployer" \
        --description="Service account for automated GitHub Actions deployments" \
        --project="$PROJECT_ID"
    echo "✅ Service Account created: $SERVICE_ACCOUNT_EMAIL"
fi

# Add IAM roles
echo "🔐 Adding IAM roles to Service Account..."

# Core deployment roles
ROLES=(
    "roles/artifactregistry.admin"
    "roles/run.admin"
    "roles/iam.serviceAccountUser"
    "roles/storage.admin"
    "roles/logging.logWriter"
    "roles/cloudsql.client"
)

# Add organization-level roles if possible (for repository creation)
ADDITIONAL_ROLES=(
    "roles/resourcemanager.projectEditor"
    "roles/serviceusage.serviceUsageAdmin"
)

for role in "${ROLES[@]}"; do
    echo "  Adding role: $role"
    gcloud projects add-iam-policy-binding "$PROJECT_ID" \
        --member="serviceAccount:$SERVICE_ACCOUNT_EMAIL" \
        --role="$role" \
        --quiet
done

echo "🔄 Attempting to add additional roles for repository management..."
for role in "${ADDITIONAL_ROLES[@]}"; do
    echo "  Trying role: $role"
    if gcloud projects add-iam-policy-binding "$PROJECT_ID" \
        --member="serviceAccount:$SERVICE_ACCOUNT_EMAIL" \
        --role="$role" \
        --quiet 2>/dev/null; then
        echo "  ✅ Added: $role"
    else
        echo "  ⚠️  Could not add: $role (may require organization admin)"
    fi
done

echo "✅ IAM roles configured"

# Create Artifact Registry repository
echo "📦 Creating Artifact Registry repository..."
if gcloud artifacts repositories describe "$REPOSITORY_NAME" \
    --location="$REGION" \
    --project="$PROJECT_ID" >/dev/null 2>&1; then
    echo "ℹ️  Repository already exists: $REPOSITORY_NAME"
else
    if gcloud artifacts repositories create "$REPOSITORY_NAME" \
        --repository-format=docker \
        --location="$REGION" \
        --description="Docker repository for garment measuring API" \
        --project="$PROJECT_ID"; then
        echo "✅ Repository created: $REPOSITORY_NAME"
    else
        echo "❌ Failed to create repository. This may require manual creation by a project owner."
        echo "   Run this command as a project owner:"
        echo "   gcloud artifacts repositories create $REPOSITORY_NAME --repository-format=docker --location=$REGION --project=$PROJECT_ID"
    fi
fi

# Generate Service Account key
echo "🔑 Generating Service Account key..."
KEY_FILE="sa-key.json"
gcloud iam service-accounts keys create "$KEY_FILE" \
    --iam-account="$SERVICE_ACCOUNT_EMAIL" \
    --project="$PROJECT_ID"

echo "✅ Service Account key generated: $KEY_FILE"

echo
echo "🎯 GITHUB SECRETS SETUP"
echo "======================="
echo "Add these secrets to your GitHub repository:"
echo
echo "1. GCP_PROJECT_ID:"
echo "   $PROJECT_ID"
echo
echo "2. GCP_SA_KEY (content of $KEY_FILE):"
echo "   $(cat "$KEY_FILE" | base64 | tr -d '\n')"
echo
echo "🔐 AWS SECRETS (if not already set):"
echo "Add these from your config_general_aws.json:"
echo "   - AWS_ACCESS_KEY_ID"
echo "   - AWS_SECRET_ACCESS_KEY" 
echo "   - AWS_S3_BUCKET_NAME"
echo "   - AWS_S3_REGION"
echo

echo "🚨 SECURITY NOTE:"
echo "The Service Account key file contains sensitive credentials."
echo "Please delete it after copying to GitHub Secrets:"
echo "   rm $KEY_FILE"
echo

echo "✅ GCP SETUP COMPLETED!"
echo
echo "🔧 TROUBLESHOOTING:"
echo "If you get 'artifactregistry.repositories.create' permission errors:"
echo "1. Ask a project owner to run this script"
echo "2. Or manually create the repository:"
echo "   gcloud artifacts repositories create $REPOSITORY_NAME --repository-format=docker --location=$REGION"
echo "3. Check that Artifact Registry API is enabled"
echo

echo "🚀 Next steps:"
echo "1. Copy the secrets to GitHub repository settings"
echo "2. Push your code to trigger the deployment"
echo "3. Monitor the GitHub Actions workflow" 