#!/bin/bash

# 🔧 COMPLETE GCP SERVICE ACCOUNT SETUP SCRIPT
# Run this in Google Cloud Shell or with gcloud CLI installed

set -e

echo "🚀 GCP Service Account Setup for GitHub Actions"
echo "=============================================="

# 1️⃣ VÁLTOZÓK BEÁLLÍTÁSA (MÓDOSÍTSD EZEKET!)
read -p "Enter your GCP Project ID: " PROJECT_ID
SA_NAME="github-actions-deployer"
SA_EMAIL="${SA_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"

echo ""
echo "📋 Configuration:"
echo "Project ID: ${PROJECT_ID}"
echo "Service Account: ${SA_EMAIL}"
echo ""

# Set the project
gcloud config set project ${PROJECT_ID}

# 2️⃣ SERVICE ACCOUNT LÉTREHOZÁSA (ha még nincs)
echo "📧 Creating Service Account..."
gcloud iam service-accounts create ${SA_NAME} \
  --display-name="GitHub Actions Deployer" \
  --description="Service account for GitHub Actions Cloud Run deployment" \
  --project=${PROJECT_ID} || echo "Service Account may already exist"

# 3️⃣ ÖSSZES SZÜKSÉGES SZEREPKÖR HOZZÁADÁSA
echo ""
echo "🔑 Adding IAM roles..."

# Artifact Registry roles
echo "  ✅ Adding Artifact Registry Admin..."
gcloud projects add-iam-policy-binding ${PROJECT_ID} \
  --member="serviceAccount:${SA_EMAIL}" \
  --role="roles/artifactregistry.admin"

# Cloud Run roles  
echo "  ✅ Adding Cloud Run Admin..."
gcloud projects add-iam-policy-binding ${PROJECT_ID} \
  --member="serviceAccount:${SA_EMAIL}" \
  --role="roles/run.admin"

echo "  ✅ Adding Cloud Run Service Agent..."
gcloud projects add-iam-policy-binding ${PROJECT_ID} \
  --member="serviceAccount:${SA_EMAIL}" \
  --role="roles/run.serviceAgent"

echo "  ✅ Adding Service Account User..."
gcloud projects add-iam-policy-binding ${PROJECT_ID} \
  --member="serviceAccount:${SA_EMAIL}" \
  --role="roles/iam.serviceAccountUser"

# Storage roles (for model downloads)
echo "  ✅ Adding Storage Admin..."
gcloud projects add-iam-policy-binding ${PROJECT_ID} \
  --member="serviceAccount:${SA_EMAIL}" \
  --role="roles/storage.admin"

# Logging roles
echo "  ✅ Adding Logging Writer..."
gcloud projects add-iam-policy-binding ${PROJECT_ID} \
  --member="serviceAccount:${SA_EMAIL}" \
  --role="roles/logging.logWriter"

# Extra permissions for Cloud Run
echo "  ✅ Adding Cloud SQL Client..."
gcloud projects add-iam-policy-binding ${PROJECT_ID} \
  --member="serviceAccount:${SA_EMAIL}" \
  --role="roles/cloudsql.client"

# 4️⃣ APIS ENGEDÉLYEZÉSE
echo ""
echo "⚡ Enabling required APIs..."
gcloud services enable artifactregistry.googleapis.com --project=${PROJECT_ID}
gcloud services enable run.googleapis.com --project=${PROJECT_ID}
gcloud services enable cloudbuild.googleapis.com --project=${PROJECT_ID}
gcloud services enable logging.googleapis.com --project=${PROJECT_ID}

# 5️⃣ ARTIFACT REGISTRY REPOSITORY LÉTREHOZÁSA
echo ""
echo "📦 Creating Artifact Registry repository..."
gcloud artifacts repositories create garment-measuring-repo \
  --repository-format=docker \
  --location=europe-west4 \
  --description="Repository for garment measuring API with optimizations" \
  --project=${PROJECT_ID} || echo "Repository may already exist"

# 6️⃣ JSON KEY LÉTREHOZÁSA
echo ""
echo "🔑 Creating JSON key..."
gcloud iam service-accounts keys create ./sa-key.json \
  --iam-account=${SA_EMAIL} \
  --project=${PROJECT_ID}

# 7️⃣ ELLENŐRZÉS
echo ""
echo "🔍 Verifying setup..."
echo "Service Account roles:"
gcloud projects get-iam-policy ${PROJECT_ID} \
  --flatten="bindings[].members" \
  --format="table(bindings.role)" \
  --filter="bindings.members:serviceAccount:${SA_EMAIL}"

echo ""
echo "Artifact Registry repositories:"
gcloud artifacts repositories list --location=europe-west4 --project=${PROJECT_ID}

# 8️⃣ BEFEJEZÉS
echo ""
echo "✅ SETUP COMPLETE!"
echo "========================================"
echo "📧 Service Account: ${SA_EMAIL}"
echo "🔑 JSON Key saved to: ./sa-key.json"
echo ""
echo "🔧 NEXT STEPS:"
echo "1. Copy the content of sa-key.json to GitHub Secret: GCP_SA_KEY"
echo "2. Set GitHub Secret GCP_PROJECT_ID to: ${PROJECT_ID}"
echo "3. Run: cat ./sa-key.json"
echo "4. Copy the entire JSON output to GitHub Secrets"
echo ""
echo "📋 GitHub Secrets to set:"
echo "  - GCP_PROJECT_ID: ${PROJECT_ID}"
echo "  - GCP_SA_KEY: [content of sa-key.json]"
echo "" 