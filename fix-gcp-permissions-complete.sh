#!/bin/bash

# 🔐 COMPLETE GCP PERMISSIONS FIX FOR DEPLOYMENT
# Run this in GCP Cloud Shell with project owner permissions

echo "🔐 FIXING GCP PERMISSIONS FOR DEPLOYMENT"
echo "======================================="

# Get project ID
PROJECT_ID=$(gcloud config get-value project)
SERVICE_ACCOUNT="hpe-78@${PROJECT_ID}.iam.gserviceaccount.com"
REGION="europe-west4"
REPOSITORY="garment-measuring-repo"

echo "📧 Service Account: $SERVICE_ACCOUNT"
echo "🎯 Project ID: $PROJECT_ID"
echo ""

# 1. ARTIFACT REGISTRY PERMISSIONS
echo "📦 1. ARTIFACT REGISTRY PERMISSIONS"
echo "-----------------------------------"

# Enable Artifact Registry API
echo "🔌 Enabling Artifact Registry API..."
gcloud services enable artifactregistry.googleapis.com

# Add Artifact Registry roles
echo "🏷️ Adding Artifact Registry roles..."
gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:$SERVICE_ACCOUNT" \
  --role="roles/artifactregistry.admin"

gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:$SERVICE_ACCOUNT" \
  --role="roles/artifactregistry.createOnPushWriter"

# 2. CLOUD RUN PERMISSIONS  
echo ""
echo "🚀 2. CLOUD RUN PERMISSIONS"
echo "---------------------------"

# Enable Cloud Run API
echo "🔌 Enabling Cloud Run API..."
gcloud services enable run.googleapis.com

# Add Cloud Run roles
echo "🏷️ Adding Cloud Run roles..."
gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:$SERVICE_ACCOUNT" \
  --role="roles/run.admin"

gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:$SERVICE_ACCOUNT" \
  --role="roles/run.serviceAgent"

# 3. GCP STORAGE PERMISSIONS
echo ""
echo "💾 3. GCP STORAGE PERMISSIONS"
echo "-----------------------------"

# Enable Cloud Storage API
echo "🔌 Enabling Cloud Storage API..."
gcloud services enable storage.googleapis.com

# Add Storage roles
echo "🏷️ Adding Storage roles..."
gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:$SERVICE_ACCOUNT" \
  --role="roles/storage.admin"

# Set bucket-specific permissions
echo "🪣 Setting bucket permissions for artifactsredi..."
gsutil iam ch serviceAccount:$SERVICE_ACCOUNT:objectViewer gs://artifactsredi
gsutil iam ch serviceAccount:$SERVICE_ACCOUNT:legacyBucketReader gs://artifactsredi

echo "🪣 Setting bucket permissions for pictures-not-public..."
gsutil iam ch serviceAccount:$SERVICE_ACCOUNT:objectAdmin gs://pictures-not-public
gsutil iam ch serviceAccount:$SERVICE_ACCOUNT:legacyBucketWriter gs://pictures-not-public

# 4. IAM PERMISSIONS
echo ""
echo "🔑 4. IAM PERMISSIONS" 
echo "--------------------"

# Add IAM roles for service management
echo "🏷️ Adding IAM roles..."
gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:$SERVICE_ACCOUNT" \
  --role="roles/iam.serviceAccountUser"

gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:$SERVICE_ACCOUNT" \
  --role="roles/resourcemanager.projectIamAdmin"

# 5. LOGGING PERMISSIONS
echo ""
echo "📝 5. LOGGING PERMISSIONS"
echo "-------------------------"

# Enable Logging API
echo "🔌 Enabling Logging API..."
gcloud services enable logging.googleapis.com

# Add Logging roles
echo "🏷️ Adding Logging roles..."
gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:$SERVICE_ACCOUNT" \
  --role="roles/logging.admin"

# 6. CREATE ARTIFACT REGISTRY REPOSITORY
echo ""
echo "📦 6. CREATE ARTIFACT REGISTRY REPOSITORY"
echo "-----------------------------------------"

if gcloud artifacts repositories describe $REPOSITORY --location=$REGION >/dev/null 2>&1; then
  echo "✅ Repository already exists: $REPOSITORY"
else
  echo "🔨 Creating Artifact Registry repository..."
  gcloud artifacts repositories create $REPOSITORY \
    --repository-format=docker \
    --location=$REGION \
    --description="Docker repository for garment measuring API"
  
  if [ $? -eq 0 ]; then
    echo "✅ Repository created: $REPOSITORY"
  else
    echo "❌ Failed to create repository"
  fi
fi

# 7. VERIFY PERMISSIONS
echo ""
echo "🔍 7. VERIFY PERMISSIONS"
echo "-----------------------"

echo "Testing permissions..."

# Test Artifact Registry
echo "📦 Testing Artifact Registry access..."
gcloud artifacts repositories list --location=$REGION >/dev/null 2>&1
if [ $? -eq 0 ]; then
  echo "✅ Artifact Registry: OK"
else
  echo "❌ Artifact Registry: FAILED"
fi

# Test Cloud Run  
echo "🚀 Testing Cloud Run access..."
gcloud run services list --region=$REGION >/dev/null 2>&1
if [ $? -eq 0 ]; then
  echo "✅ Cloud Run: OK"
else
  echo "❌ Cloud Run: FAILED"
fi

# Test Storage
echo "💾 Testing Storage access..."
gsutil ls gs://artifactsredi >/dev/null 2>&1
if [ $? -eq 0 ]; then
  echo "✅ Storage artifactsredi: OK"
else
  echo "❌ Storage artifactsredi: FAILED"
fi

gsutil ls gs://pictures-not-public >/dev/null 2>&1
if [ $? -eq 0 ]; then
  echo "✅ Storage pictures-not-public: OK"  
else
  echo "❌ Storage pictures-not-public: FAILED"
fi

echo ""
echo "🎉 PERMISSIONS SETUP COMPLETE!"
echo "==============================="
echo ""
echo "📋 APPLIED ROLES:"
echo "• roles/artifactregistry.admin"
echo "• roles/artifactregistry.createOnPushWriter" 
echo "• roles/run.admin"
echo "• roles/run.serviceAgent"
echo "• roles/storage.admin"
echo "• roles/iam.serviceAccountUser"
echo "• roles/resourcemanager.projectIamAdmin"
echo "• roles/logging.admin"
echo ""
echo "🪣 BUCKET PERMISSIONS:"
echo "• gs://artifactsredi: objectViewer, legacyBucketReader"
echo "• gs://pictures-not-public: objectAdmin, legacyBucketWriter"
echo ""
echo "🚀 NEXT STEPS:"
echo "1. Retry GitHub Actions deployment"
echo "2. Check Cloud Run logs if startup fails"
echo "3. Test API endpoints after successful deployment" 