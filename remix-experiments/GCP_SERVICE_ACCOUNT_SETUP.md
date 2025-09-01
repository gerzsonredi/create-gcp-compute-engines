# 🔑 GCP Service Account Setup Guide

## 📋 Áttekintés

A benchmark system GCP Service Account authentication-t használ mind lokálisan, mind GitHub Actions-ben. Ez biztonságosabb és megbízhatóbb, mint SSH kulcs authentication.

## 🚀 Service Account Létrehozása

### 1. **Service Account létrehozása**
```bash
gcloud iam service-accounts create github-actions-sa \
  --display-name="GitHub Actions Service Account" \
  --project=remix-466614
```

### 2. **Jogosultságok hozzáadása**
```bash
# Compute Admin (VM-ek kezeléséhez)
gcloud projects add-iam-policy-binding remix-466614 \
  --member="serviceAccount:github-actions-sa@remix-466614.iam.gserviceaccount.com" \
  --role="roles/compute.admin"

# Service Management Consumer (API-k használatához)
gcloud projects add-iam-policy-binding remix-466614 \
  --member="serviceAccount:github-actions-sa@remix-466614.iam.gserviceaccount.com" \
  --role="roles/servicemanagement.serviceController"

# Storage Object Viewer (ha szükséges image letöltéshez)
gcloud projects add-iam-policy-binding remix-466614 \
  --member="serviceAccount:github-actions-sa@remix-466614.iam.gserviceaccount.com" \
  --role="roles/storage.objectViewer"
```

### 3. **JSON kulcs letöltése**
```bash
gcloud iam service-accounts keys create sa-key.json \
  --iam-account=github-actions-sa@remix-466614.iam.gserviceaccount.com \
  --project=remix-466614
```

## 🔧 Lokális Konfiguráció

### 1. **Service Account JSON beszúrása**
Nyisd meg a `credentials.env` fájlt és illeszd be a Service Account JSON-t:

```bash
# credentials.env
GCP_SA_KEY={"type":"service_account","project_id":"remix-466614",...}
```

**Két formátum támogatott:**

#### **Raw JSON (ajánlott lokálisan):**
```bash
GCP_SA_KEY={"type":"service_account","project_id":"remix-466614","private_key_id":"...","private_key":"-----BEGIN PRIVATE KEY-----\n...\n-----END PRIVATE KEY-----\n","client_email":"github-actions-sa@remix-466614.iam.gserviceaccount.com","client_id":"...","auth_uri":"https://accounts.google.com/o/oauth2/auth","token_uri":"https://oauth2.googleapis.com/token"}
```

#### **Base64 encoded (GitHub Secret-ben):**
```bash
# Base64 kódolás:
cat sa-key.json | base64 | tr -d '\n'

# Eredmény:
GCP_SA_KEY=eyJ0eXBlIjoic2VydmljZV9hY2NvdW50IiwicHJvamVjdF9pZCI6InJlbWl4LTQ2NjYxNCIsInByaXZhdGVfa2V5X2lkIjoiLi4uIn0=
```

### 2. **Tesztelés**
```bash
# Multi-VM deployment teszt
./multi-deploy-benchmark.sh

# Single VM deployment teszt  
./full-deploy-benchmark.sh
```

## 🔑 GitHub Secrets

### GitHub repository beállítása:
1. **GitHub repo** → **Settings** → **Secrets and variables** → **Actions**
2. **Add secret**:

| Secret Name | Value | Format |
|-------------|--------|---------|
| `GCP_SA_KEY` | Service Account JSON | Raw JSON vagy Base64 |
| `PROJECT_ID` | `remix-466614` | String |

**⚠️ Fontos:** A `SSH_PASSPHRASE` már **NINCS szükség** GitHub Actions-ben!

## 🔍 Hibaelhárítás

### **"Permission denied" hibaüzenet**
```bash
# Ellenőrizd a jogosultságokat
gcloud projects get-iam-policy remix-466614 \
  --flatten="bindings[].members" \
  --filter="bindings.members:github-actions-sa@remix-466614.iam.gserviceaccount.com"
```

### **"Invalid JSON" hiba**
```bash
# Validáld a JSON formátumot
echo "$GCP_SA_KEY" | jq .

# Vagy base64 dekódolás után
echo "$GCP_SA_KEY" | base64 -d | jq .
```

### **Service Account nem található**
```bash
# Listázd a Service Account-okat
gcloud iam service-accounts list --project=remix-466614
```

### **API nem engedélyezett**
```bash
# Engedélyezd a szükséges API-kat
gcloud services enable compute.googleapis.com --project=remix-466614
gcloud services enable cloudresourcemanager.googleapis.com --project=remix-466614
```

## 🎯 Előnyök

### **Service Account vs SSH Key:**
| Szempont | Service Account | SSH Key |
|----------|----------------|---------|
| **Biztonság** | ✅ Központi kezelés | ❌ Privát kulcs kezelés |
| **GitHub Actions** | ✅ Natív támogatás | ❌ Complex setup |
| **Audit** | ✅ GCP audit log | ❌ Korlátozott |
| **Rotáció** | ✅ Automatikus | ❌ Manuális |
| **Jogosultságok** | ✅ Fine-grained | ❌ SSH access only |

## 📁 Fájl Struktúra

```
remix-experiments/
├── credentials.env          # GCP_SA_KEY itt
├── multi-deploy-benchmark.sh    # Service Account support
├── full-deploy-benchmark.sh     # Service Account support  
├── setup-ssh-agent.sh          # Fallback SSH support
└── .github/workflows/           # GitHub Actions
    └── benchmark-deployment.yml
```

## 🎉 Sikeres Setup Ellenőrzése

Ha minden jól van beállítva:

```bash
# Lokális tesztek
✅ ./multi-deploy-benchmark.sh    # GCP Service Account auth
✅ gcloud compute instances list  # Működik hitelesítés nélkül

# GitHub Actions
✅ Workflow futás sikeres
✅ VM-ek létrehozva
✅ Benchmark eredmények
```
