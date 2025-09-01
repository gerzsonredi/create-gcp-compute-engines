# 🚀 Multi-Instance Benchmark Deployment Guide

## 📋 Áttekintés

Az új multi-deployment rendszer lehetővé teszi több VM instance egyidejű létrehozását és benchmark futtatását. Teljesen konfigurálható és automatizált.

## 🔧 Konfigurációs Fájl

### Alapértelmezett konfig: `deployment-config.conf`

```bash
# Főbb beállítások
INSTANCE_COUNT=3                    # Hány VM-et hozzon létre (1-20)
PROJECT_ID="remix-466614"           # GCP projekt ID
ZONE="europe-west1-b"               # GCP zone
MACHINE_TYPE="e2-medium"            # VM méret (2 CPU, 4GB RAM)
BOOT_DISK_SIZE="100GB"              # Disk méret

# VM nevezési
INSTANCE_NAME_PREFIX="benchmark-vm" # VM nevek előtagja

# Benchmark beállítások  
RUN_BENCHMARK_ON_CREATION=true      # Futassa le azonnal a benchmark-et
SHOW_IP_ADDRESSES=true              # Mutassa az IP címeket
SHOW_DETAILED_RESULTS=true          # Részletes eredmények
```

## 🎯 Használat

### 1. Alapértelmezett konfig használata
```bash
# Szerkeszd a deployment-config.conf fájlt
nano deployment-config.conf

# Futtatás
./multi-deploy-benchmark.sh
```

### 2. Custom konfig használata
```bash
# Másold át a példa konfigot
cp example-configs/small-deployment.conf my-config.conf

# Szerkeszd
nano my-config.conf

# Futtasd a custom config-gal
CONFIG_FILE=my-config.conf ./multi-deploy-benchmark.sh
```

## 📊 Előre elkészített konfigok

### Small Deployment (2 VM, olcsóbb)
```bash
CONFIG_FILE=example-configs/small-deployment.conf ./multi-deploy-benchmark.sh
```

### Large Deployment (5 VM, teljes teljesítmény)
```bash
CONFIG_FILE=example-configs/large-deployment.conf ./multi-deploy-benchmark.sh
```

## 🎯 Funkciók

### ✅ Automatikus létrehozás
- Több VM egyidejű létrehozása
- Docker telepítés mindegyikre
- Benchmark fájlok másolása
- Párhuzamos benchmark futtatás

### 📱 IP címek megjelenítése
```
========================================
        VM INSTANCES & IP ADDRESSES    
========================================
Instance 1:
  Name: benchmark-vm-1756740123-1
  External IP: 35.189.226.7
  Internal IP: 10.132.0.6
  Zone: europe-west1-b

Instance 2:
  Name: benchmark-vm-1756740123-2
  External IP: 104.199.106.106
  Internal IP: 10.132.0.7
  Zone: europe-west1-b
```

### 📊 Eredmények összesítése
- Minden VM-ről automatikus eredmény gyűjtés
- Fájlok száma és mérete VM-enként
- Összesített statisztikák

### 🛠️ Management parancsok
```bash
# SSH bármelyik instance-ra
gcloud compute ssh benchmark-vm-1756740123-1 --zone=europe-west1-b

# Összes VM leállítása
gcloud compute instances stop benchmark-vm-1756740123-1 benchmark-vm-1756740123-2 --zone=europe-west1-b

# Összes VM törlése
gcloud compute instances delete benchmark-vm-1756740123-1 benchmark-vm-1756740123-2 --zone=europe-west1-b
```

## 🔧 Konfigurációs opciók

| Beállítás | Leírás | Alapértelmezett |
|-----------|--------|-----------------|
| `INSTANCE_COUNT` | VM-ek száma | 3 |
| `MACHINE_TYPE` | VM típus | e2-medium |
| `BOOT_DISK_SIZE` | Disk méret | 100GB |
| `RUN_BENCHMARK_ON_CREATION` | Automatikus benchmark | true |
| `SHOW_IP_ADDRESSES` | IP címek kiírása | true |
| `SHOW_DETAILED_RESULTS` | Részletes eredmények | true |
| `DELETE_INSTANCES_AFTER_BENCHMARK` | Auto törlés | false |
| `STOP_INSTANCES_AFTER_BENCHMARK` | Auto leállítás | false |

## 💡 Tippek

### Költség optimalizálás
```bash
# Kis VM-ek használata
MACHINE_TYPE="e2-micro"      # 1 CPU, 1GB RAM
BOOT_DISK_SIZE="50GB"        # Kisebb disk

# Automatikus leállítás
STOP_INSTANCES_AFTER_BENCHMARK=true
```

### Teljesítmény optimalizálás  
```bash
# Nagy VM-ek használata
MACHINE_TYPE="e2-standard-4" # 4 CPU, 16GB RAM
BOOT_DISK_SIZE="200GB"       # Nagyobb disk
```

### Batch futtatás
```bash
# Több deployment egymás után
for config in small large; do
    CONFIG_FILE=example-configs/${config}-deployment.conf ./multi-deploy-benchmark.sh
    sleep 300  # 5 perc várakozás
done
```

## 📁 Kimeneti fájlok

- `multi-deployment-TIMESTAMP.env` - Deployment összesítő
- VM-enként: `~/benchmark-results/` - Letöltött képek
- Automatikus cleanup a startup scriptnek

## 🎉 Példa futtatás

```bash
# 1. Konfig ellenőrzése
cat deployment-config.conf

# 2. Futtatás
./multi-deploy-benchmark.sh

# Kimenet:
# ✅ 3 VM létrehozva
# 📊 IP címek megjelenítve  
# 🏃 Benchmark-ek párhuzamosan futnak
# 📊 Eredmények összesítve
# 💾 Management parancsok generálva
```

## 🆘 Hibaelhárítás

### SSH problémák
```bash
# SSH agent újraindítása
./setup-ssh-agent.sh
```

### VM-ek nem válaszolnak
```bash
# Manual ellenőrzés
gcloud compute instances list --filter="labels.application=image-download"
```

### Konfig problémák
```bash
# Konfig validálás
bash -n multi-deploy-benchmark.sh  # Syntax check
```
