#!/bin/bash

# 🚨 GCP ARTIFACT REGISTRY PERMISSION FIX SCRIPT
# Futtatsd ezt a GCP Cloud Shell-ben vagy lokálisan gcloud CLI-vel

set -e

echo "🚨 GCP ARTIFACT REGISTRY JOGOSULTSÁG JAVÍTÁS"
echo "============================================="

# Változók
PROJECT_ID="${GCP_PROJECT_ID:-$(gcloud config get-value project)}"
SERVICE_ACCOUNT_EMAIL="hpe-78@${PROJECT_ID}.iam.gserviceaccount.com"
REGION="europe-west4"
REPOSITORY_NAME="garment-measuring-repo"

echo "📋 Konfiguráció:"
echo "  Project ID: $PROJECT_ID"
echo "  Service Account: $SERVICE_ACCOUNT_EMAIL"
echo "  Repository: $REPOSITORY_NAME"
echo "  Region: $REGION"
echo

# 1️⃣ ELLENŐRIZD A SERVICE ACCOUNT LÉTEZÉSÉT
echo "1️⃣ Service Account ellenőrzése..."
if gcloud iam service-accounts describe "$SERVICE_ACCOUNT_EMAIL" --project="$PROJECT_ID" >/dev/null 2>&1; then
    echo "✅ Service Account létezik: $SERVICE_ACCOUNT_EMAIL"
else
    echo "❌ Service Account nem létezik: $SERVICE_ACCOUNT_EMAIL"
    echo "🔧 Létrehozás:"
    gcloud iam service-accounts create hpe-78 \
        --display-name="GitHub Actions HPE Deployer" \
        --description="Service account for GitHub Actions deployment" \
        --project="$PROJECT_ID"
    echo "✅ Service Account létrehozva!"
fi

# 2️⃣ ARTIFACT REGISTRY API ENGEDÉLYEZÉSE
echo "2️⃣ Artifact Registry API engedélyezése..."
gcloud services enable artifactregistry.googleapis.com --project="$PROJECT_ID"
echo "✅ API engedélyezve"

# 3️⃣ IAM SZEREPKÖRÖK HOZZÁADÁSA
echo "3️⃣ IAM szerepkörök hozzáadása..."

# Fő szerepkörök
ROLES=(
    "roles/artifactregistry.admin"
    "roles/artifactregistry.createOnPushWriter" 
    "roles/artifactregistry.reader"
    "roles/run.admin"
    "roles/iam.serviceAccountUser"
    "roles/storage.admin"
    "roles/logging.logWriter"
)

for role in "${ROLES[@]}"; do
    echo "  Hozzáadás: $role"
    gcloud projects add-iam-policy-binding "$PROJECT_ID" \
        --member="serviceAccount:$SERVICE_ACCOUNT_EMAIL" \
        --role="$role" \
        --quiet
done

echo "✅ IAM szerepkörök hozzáadva"

# 4️⃣ ARTIFACT REGISTRY REPOSITORY LÉTREHOZÁSA
echo "4️⃣ Artifact Registry repository létrehozása..."
if gcloud artifacts repositories describe "$REPOSITORY_NAME" \
    --location="$REGION" \
    --project="$PROJECT_ID" >/dev/null 2>&1; then
    echo "✅ Repository már létezik: $REPOSITORY_NAME"
else
    echo "📦 Repository létrehozása..."
    gcloud artifacts repositories create "$REPOSITORY_NAME" \
        --repository-format=docker \
        --location="$REGION" \
        --description="Docker repository for garment measuring API" \
        --project="$PROJECT_ID"
    echo "✅ Repository létrehozva: $REPOSITORY_NAME"
fi

# 5️⃣ JOGOSULTSÁGOK ELLENŐRZÉSE
echo "5️⃣ Jogosultságok ellenőrzése..."
echo "Service Account szerepkörei:"
gcloud projects get-iam-policy "$PROJECT_ID" \
    --flatten="bindings[].members" \
    --format="table(bindings.role)" \
    --filter="bindings.members:serviceAccount:$SERVICE_ACCOUNT_EMAIL"

echo
echo "Artifact Registry repositories:"
gcloud artifacts repositories list --location="$REGION" --project="$PROJECT_ID"

# 6️⃣ TESZTELÉS
echo "6️⃣ Jogosultság tesztelés..."
echo "Artifact Registry hozzáférés teszt:"
if gcloud artifacts repositories describe "$REPOSITORY_NAME" \
    --location="$REGION" \
    --project="$PROJECT_ID" >/dev/null 2>&1; then
    echo "✅ Sikeres hozzáférés az Artifact Registry repository-hoz!"
else
    echo "❌ Továbbra is hozzáférési hiba"
fi

echo
echo "🎯 BEFEJEZÉS"
echo "=========="
echo "✅ Service Account konfigurálva: $SERVICE_ACCOUNT_EMAIL"
echo "✅ Artifact Registry repository: $REPOSITORY_NAME"
echo "✅ IAM szerepkörök hozzáadva"
echo
echo "🔧 Ha továbbra is problémák vannak:"
echo "1. Ellenőrizd a szervezeti házirendeket (Organization Policies)"
echo "2. Győződj meg róla, hogy projekt tulajdonos vagy"
echo "3. Próbáld újra a GitHub Actions workflow-t"
echo
echo "📧 Service Account JSON key újragenerálása:"
echo "gcloud iam service-accounts keys create sa-key-new.json --iam-account=$SERVICE_ACCOUNT_EMAIL --project=$PROJECT_ID" 