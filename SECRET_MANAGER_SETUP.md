# 🔐 Secret Manager Setup Guide

Ez az útmutató bemutatja, hogyan használhatod a **Google Cloud Secret Manager**-t a GCP Service Account kulcsok biztonságos kezelésére.

## 🎯 **Miért Secret Manager?**

### ❌ **Jelenlegi problémák:**
- VM metadata méret limit (~256KB)
- Base64 encoding/decoding hibák  
- Environment variable escape problémák
- Sensitive data VM metadata-ban

### ✅ **Secret Manager előnyei:**
- **Biztonságos tárolás:** Encrypted at rest és in transit
- **Méret limit:** Nincs gyakorlati limit (64KB/secret)
- **Access control:** IAM-based jogosultságkezelés
- **Audit logging:** Ki, mikor, mit ért el
- **Verzió kezelés:** Automatic key rotation support
- **Runtime retrieval:** VM startup-kor biztonságos lekérés

## 🚀 **Beállítás lépései**

### **1. Secret Manager API engedélyezése**

```bash
gcloud services enable secretmanager.googleapis.com --project=YOUR_PROJECT_ID
```

### **2. Secret létrehozása (egyszeri)**

```bash
# A GCP Service Account JSON kulcsot Secret Manager-be mentjük
echo "YOUR_GCP_SA_KEY_JSON" | gcloud secrets create mannequin-gcp-sa-key \
  --data-file=- \
  --project=YOUR_PROJECT_ID
```

### **3. VM Service Account jogosultságok**

A VM-ek default service account-jának hozzáférést kell adni:

```bash
# Secret Manager Secret Accessor szerepkör hozzáadása
gcloud projects add-iam-policy-binding YOUR_PROJECT_ID \
  --member="serviceAccount:PROJECT_NUMBER-compute@developer.gserviceaccount.com" \
  --role="roles/secretmanager.secretAccessor"
```

**Projekt számot megtalálni:**
```bash
gcloud projects describe YOUR_PROJECT_ID --format="value(projectNumber)"
```

### **4. Deployment futtatása**

#### **GitHub Actions-ben:**
```yaml
# A új workflow használata
name: deploy-benchmark-secret.yml

# Inputs:
config_file: 'example-configs/small-deployment.conf'
secret_name: 'mannequin-gcp-sa-key'
```

#### **Local deployment:**
```bash
export PROJECT_ID="your-project-id"
export ZONE="europe-west1-b" 
export GCP_SA_KEY="$(cat path/to/service-account-key.json)"
export CONFIG_FILE="example-configs/small-deployment.conf"
export SECRET_NAME="mannequin-gcp-sa-key"

./deploy-gcp-secret.sh
```

## 🔧 **Fájlok és használat**

### **Új fájlok:**
- `deploy-gcp-secret.sh` - Secret Manager-t használó deployment script
- `startup-script-gcs-secret.sh` - VM startup script Secret Manager-rel  
- `deploy-benchmark-secret.yml` - GitHub Actions workflow
- `SECRET_MANAGER_SETUP.md` - Ez az útmutató

### **Működés:**
1. **Deploy script** létrehozza/frissíti a secret-et Secret Manager-ben
2. **VM startup** biztonságosan lekéri a kulcsot Secret Manager-ből
3. **Kulcs hozzáadása** a `.env` fájlhoz container számára
4. **Service elindítása** a proper credentials-szel

## 🔍 **Troubleshooting**

### **Secret Manager hozzáférési hibák:**
```bash
# Ellenőrizd a VM service account jogosultságait
gcloud projects get-iam-policy YOUR_PROJECT_ID \
  --flatten="bindings[].members" \
  --filter="bindings.members:*compute@developer.gserviceaccount.com"
```

### **Secret létezésének ellenőrzése:**
```bash
gcloud secrets describe mannequin-gcp-sa-key --project=YOUR_PROJECT_ID
```

### **VM logs monitorozása:**
```bash
# VM-en belül ellenőrizd a startup script logokat
gcloud compute ssh INSTANCE_NAME --zone=ZONE --project=PROJECT_ID \
  --command='sudo journalctl -u google-startup-scripts.service -f'
```

### **Container logs:**
```bash
# Ellenőrizd hogy a GCP_SA_KEY sikeresen be lett-e töltve
gcloud compute ssh INSTANCE_NAME --zone=ZONE --project=PROJECT_ID \
  --command='sudo docker logs mannequin-segmenter | grep -i gcp'
```

## 🛡️ **Biztonsági előnyök**

- ✅ **No metadata exposure:** Sensitive data nem jelenik meg VM metadata-ban
- ✅ **Runtime retrieval:** Kulcs csak VM startup-kor kerül lekérésre
- ✅ **Encrypted storage:** Google-managed encryption
- ✅ **Audit trail:** Minden hozzáférés naplózva
- ✅ **IAM controlled:** Fine-grained access control
- ✅ **Rotation ready:** Könnyen lecserélhető kulcsok

## 🔄 **Kulcs frissítése**

Ha új Service Account kulcsot kell használni:

```bash
# Új verzió hozzáadása a meglévő secret-hez
echo "NEW_GCP_SA_KEY_JSON" | gcloud secrets versions add mannequin-gcp-sa-key \
  --data-file=- \
  --project=YOUR_PROJECT_ID

# VM-ek restart-elése az új kulcs használatához
gcloud compute instances reset INSTANCE_NAME --zone=ZONE --project=PROJECT_ID
```

## 📚 **További információk**

- [Google Cloud Secret Manager Documentation](https://cloud.google.com/secret-manager/docs)
- [IAM Roles for Secret Manager](https://cloud.google.com/secret-manager/docs/access-control)
- [Best Practices for Secret Management](https://cloud.google.com/secret-manager/docs/best-practices)
