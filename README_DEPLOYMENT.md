# 🚀 Image Download Benchmark - Complete Deployment Guide

## 📋 Available Scripts

### 1. `full-deploy-benchmark.sh` - Complete New Deployment
**Teljes automatizálás új VM-mel**

```bash
./full-deploy-benchmark.sh
```

**Mit csinál:**
- ✅ Létrehoz egy új GCP VM-et (2 CPU, 4GB RAM, 100GB storage)
- ✅ Telepíti a Docker-t
- ✅ Másolia és buildeli a kódot
- ✅ Futtatja a benchmark-et
- ✅ Kiírja az eredményeket
- ✅ Elmenti a deployment adatokat

### 2. `run-benchmark-existing-vm.sh` - Meglévő VM Használata
**Gyors futtatás meglévő VM-en**

```bash
# Alapértelmezett VM használata
./run-benchmark-existing-vm.sh

# Vagy saját VM név/zone megadásával
VM_NAME=my-vm VM_ZONE=europe-west1-b ./run-benchmark-existing-vm.sh
```

**Mit csinál:**
- ✅ Ellenőrzi és elindítja a VM-et (ha leállt)
- ✅ Frissíti a kódot
- ✅ Újrabuildi a Docker image-et
- ✅ Futtatja a benchmark-et
- ✅ Kiírja az eredményeket

### 3. `deploy-gcp.sh` - Manuális Deployment
**Eredeti deployment script**

```bash
./deploy-gcp.sh
```

## 🎯 Használati Példák

### Első alkalommal (új VM)
```bash
# Teljes deployment - minden automatikusan
./full-deploy-benchmark.sh
```

### Ismételt futtatás (meglévő VM)
```bash
# Gyors újrafuttatás
./run-benchmark-existing-vm.sh
```

### Konkrét VM használata
```bash
# Ha van egy saját VM neved
VM_NAME=image-benchmark-vm-1693574234 VM_ZONE=europe-west1-b ./run-benchmark-existing-vm.sh
```

## 📊 Eredmények

A scriptek automatikusan:
- Futtatják a benchmark teszteket (1x, 10x, 50x párhuzamos letöltés)
- Kiírják a teljesítmény statisztikákat
- Megjelenítik a letöltött fájlok számát és méretét
- Elmentik a deployment információkat

## 🔧 Előfeltételek

1. **Google Cloud SDK telepítve**
   ```bash
   # Ellenőrzés
   gcloud --version
   ```

2. **Autentikáció**
   ```bash
   gcloud auth login
   gcloud config set project YOUR_PROJECT_ID
   ```

3. **Szükséges fájlok** (automatikusan ellenőrzi)
   - `image_download_benchmark.py`
   - `requirements.txt`
   - `Dockerfile` 
   - `.dockerignore`

## 🛠️ Troubleshooting

### SSH kapcsolódási problémák
```bash
# SSH kulcs újragenerálása
gcloud compute config-ssh

# VM újraindítása
gcloud compute instances reset VM_NAME --zone=ZONE
```

### VM leállítása/törlése
```bash
# Leállítás (költségmegtakarítás)
gcloud compute instances stop VM_NAME --zone=ZONE

# Törlés (teljes cleanup)
gcloud compute instances delete VM_NAME --zone=ZONE
```

## 💡 Tippek

- A `full-deploy-benchmark.sh` minden alkalommal új VM-et hoz létre egyedi névvel
- A `run-benchmark-existing-vm.sh` használható ismételt teszteléshez
- A deployment információk automatikusan elmentődnek `deployment-info-*.env` fájlokba
- A VM-ek automatikusan `image-benchmark-vm-TIMESTAMP` nevet kapnak

## 🎉 Gyors Start

```bash
# 1. Ellenőrizd az előfeltételeket
gcloud auth list
gcloud config get-value project

# 2. Futtasd a teljes deployment-et
./full-deploy-benchmark.sh

# 3. Várj 3-5 percet és élvezd az eredményeket! 🚀
```


