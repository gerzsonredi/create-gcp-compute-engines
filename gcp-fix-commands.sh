#!/bin/bash

# 🚨 GCP JOGOSULTSÁG JAVÍTÁS - TELJES SCRIPT
# Futtasd ezt a Google Cloud Shell-ben vagy lokálisan gcloud CLI-vel

set -e

echo "🚀 GCP ARTIFACT REGISTRY JOGOSULTSÁG JAVÍTÁS"
echo "============================================="

# Aktuális projekt lekérése
PROJECT_ID=$(gcloud config get-value project 2>/dev/null)
if [ -z "$PROJECT_ID" ]; then
    echo "❌ Nincs beállított GCP projekt!"
    echo "🔧 Beállítás: gcloud config set project YOUR_PROJECT_ID"
    exit 1
fi

SERVICE_ACCOUNT="hpe-78@${PROJECT_ID}.iam.gserviceaccount.com"

echo "📋 Konfiguráció:"
echo "  Project ID: $PROJECT_ID"
echo "  Service Account: $SERVICE_ACCOUNT"
echo

# 1️⃣ SERVICE ACCOUNT LÉTREHOZÁSA
echo "1️⃣ Service Account ellenőrzése/létrehozása..."
if gcloud iam service-accounts describe "$SERVICE_ACCOUNT" >/dev/null 2>&1; then
    echo "✅ Service Account már létezik: $SERVICE_ACCOUNT"
else
    echo "📧 Service Account létrehozása..."
    gcloud iam service-accounts create hpe-78 \
        --display-name="GitHub Actions HPE Deployer" \
        --description="Service account for GitHub Actions deployment"
    echo "✅ Service Account létrehozva!"
fi

# 2️⃣ API-K ENGEDÉLYEZÉSE
echo "2️⃣ Szükséges API-k engedélyezése..."
gcloud services enable artifactregistry.googleapis.com
gcloud services enable run.googleapis.com
gcloud services enable cloudbuild.googleapis.com
gcloud services enable storage-api.googleapis.com
echo "✅ API-k engedélyezve"

# 3️⃣ IAM SZEREPKÖRÖK HOZZÁADÁSA
echo "3️⃣ IAM szerepkörök hozzáadása..."

ROLES=(
    "roles/artifactregistry.admin"
    "roles/artifactregistry.createOnPushWriter"
    "roles/artifactregistry.reader"
    "roles/run.admin"
    "roles/iam.serviceAccountUser"
    "roles/storage.admin"
    "roles/logging.logWriter"
    "roles/cloudsql.client"
)

for role in "${ROLES[@]}"; do
    echo "  ➡️  Hozzáadás: $role"
    gcloud projects add-iam-policy-binding "$PROJECT_ID" \
        --member="serviceAccount:$SERVICE_ACCOUNT" \
        --role="$role" \
        --quiet
done

echo "✅ IAM szerepkörök hozzáadva"

# 4️⃣ ARTIFACT REGISTRY REPOSITORY LÉTREHOZÁSA
echo "4️⃣ Artifact Registry repository létrehozása..."
if gcloud artifacts repositories describe garment-measuring-repo \
    --location=europe-west4 >/dev/null 2>&1; then
    echo "✅ Repository már létezik: garment-measuring-repo"
else
    echo "📦 Repository létrehozása..."
    gcloud artifacts repositories create garment-measuring-repo \
        --repository-format=docker \
        --location=europe-west4 \
        --description="Docker repository for garment measuring API"
    echo "✅ Repository létrehozva!"
fi

# 5️⃣ SERVICE ACCOUNT KEY GENERÁLÁSA
echo "5️⃣ Service Account key generálása..."
if [ -f "sa-key.json" ]; then
    echo "⚠️  sa-key.json már létezik, átnevezés régi verzióra..."
    mv sa-key.json sa-key-backup-$(date +%s).json
fi

gcloud iam service-accounts keys create sa-key.json \
    --iam-account="$SERVICE_ACCOUNT"
echo "✅ Service Account key generálva: sa-key.json"

# 6️⃣ JOGOSULTSÁGOK ELLENŐRZÉSE
echo "6️⃣ Jogosultságok ellenőrzése..."
echo "🔍 Service Account szerepkörei:"
gcloud projects get-iam-policy "$PROJECT_ID" \
    --flatten="bindings[].members" \
    --format="table(bindings.role)" \
    --filter="bindings.members:serviceAccount:$SERVICE_ACCOUNT"

echo
echo "📦 Artifact Registry repositories:"
gcloud artifacts repositories list --location=europe-west4

# 7️⃣ TESZTELÉS
echo "7️⃣ Hozzáférés tesztelése..."
if gcloud artifacts repositories describe garment-measuring-repo \
    --location=europe-west4 >/dev/null 2>&1; then
    echo "✅ Sikeres hozzáférés az Artifact Registry repository-hoz!"
else
    echo "❌ Továbbra is hozzáférési hiba van"
    exit 1
fi

# 8️⃣ GITHUB SECRETS
echo "8️⃣ GitHub Secrets értékei:"
echo "=========================="
echo ""
echo "🔑 Másold ezeket a GitHub repository Settings → Secrets and variables → Actions-be:"
echo ""
echo "GCP_PROJECT_ID:"
echo "$PROJECT_ID"
echo ""
echo "GCP_SA_KEY:"
echo "$(cat sa-key.json | base64 | tr -d '\n')"
echo ""

echo "🎯 BEFEJEZÉS"
echo "============"
echo "✅ Service Account konfigurálva: $SERVICE_ACCOUNT"
echo "✅ Artifact Registry repository: garment-measuring-repo"
echo "✅ Összes jogosultság beállítva"
echo "✅ GitHub Secrets készen állnak"
echo ""
echo "🚀 Most újra futtathatod a GitHub Actions workflow-t!"
echo ""
echo "🗑️  Biztonsági okokból töröld a kulcs fájlt a használat után:"
echo "rm sa-key.json" 