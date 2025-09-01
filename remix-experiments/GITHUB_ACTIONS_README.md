# 🚀 GitHub Actions - Image Download Benchmark

## 📋 Áttekintés

Az automatizált GitHub Actions workflow lehetővé teszi a benchmark tesztek futtatását GCP VM instance-okon közvetlenül a GitHub repository-ból. Teljes CI/CD pipeline docker build-del, VM deployment-tel és eredmény gyűjtéssel.

## 🎯 Workflow Triggers

### 1. Manual Trigger (Workflow Dispatch)
```yaml
workflow_dispatch:
  inputs:
    instance_count: 1-10 VM-ek száma
    machine_type: GCP machine típus (e2-micro, e2-small, e2-medium, stb.)
    deployment_type: single/multi VM deployment
    cleanup_after: VM-ek törlése futtatás után
```

### 2. Automatic Triggers
- **Push to main/develop**: Kód változásoknál automatikus futtatás
- **Pull Request**: PR-eknél validation
- **Schedule**: Napi automatikus benchmark (2 AM UTC)

## 🔧 Setup Requirements

### GitHub Secrets (kötelező):

1. **`GCP_SA_KEY`**: GCP Service Account JSON kulcs
   ```bash
   # Service Account létrehozása
   gcloud iam service-accounts create github-actions-sa \
     --display-name="GitHub Actions Service Account"
   
   # Jogosultságok hozzáadása
   gcloud projects add-iam-policy-binding remix-466614 \
     --member="serviceAccount:github-actions-sa@remix-466614.iam.gserviceaccount.com" \
     --role="roles/compute.admin"
   
   # Kulcs letöltése
   gcloud iam service-accounts keys create sa-key.json \
     --iam-account=github-actions-sa@remix-466614.iam.gserviceaccount.com
   
   # A sa-key.json tartalmát másold be GitHub Secrets-be
   ```

2. **`SSH_PASSPHRASE`**: SSH kulcs jelszava
   ```bash
   # Az SSH kulcs jelszava (credentials.env-ből)
   o3MAcgN%Uaez^kwQB7KCAi
   ```

### GitHub Secrets beállítása:
1. GitHub repo → Settings → Secrets and variables → Actions
2. Add secret: `GCP_SA_KEY` = service account JSON
3. Add secret: `SSH_PASSPHRASE` = SSH kulcs jelszó

## 🎮 Használat

### Manual Futtatás
1. GitHub repo → Actions tab
2. Select "🚀 Image Download Benchmark Deployment"
3. Click "Run workflow"
4. Konfiguráció beállítása:
   - Instance count: 1-10
   - Machine type: e2-micro/small/medium/standard-2/standard-4
   - Deployment type: single/multi
   - Cleanup: true/false

### Automatikus Futtatás
```bash
# Push trigger
git push origin main

# PR trigger  
git push origin feature-branch
# Create PR to main

# Schedule trigger (automatikus napi 2 AM-kor)
```

## 📊 Workflow Jobs

### 1. **Setup & Validation** 🔧
- Konfiguráció beállítása event típus alapján
- Paraméterek validálása
- Output változók generálása

### 2. **Build Docker Image** 🐳
- Docker image build
- Image tesztelés
- Dependency ellenőrzés

### 3. **Single VM Benchmark** 🎯 (ha single mode)
- 1 VM létrehozása
- `full-deploy-benchmark.sh` futtatása
- Eredmények gyűjtése

### 4. **Multi-VM Benchmark** 🎯 (ha multi mode)
- Több VM létrehozása konfig alapján
- `multi-deploy-benchmark.sh` futtatása
- IP címek kigyűjtése
- Párhuzamos benchmark futtatás

### 5. **Notification** 📢
- Státusz összesítés
- Sikeres/sikertelen értesítés

## 📁 Artifacts & Results

### Letölthető Artifacts:
1. **`single-vm-benchmark-results`**: Egyszeri VM eredmények
2. **`multi-vm-benchmark-results-N-instances`**: Multi VM eredmények
3. **`benchmark-summary-report`**: Összefoglaló jelentés

### Tartalom:
```
- logs/                    # Részletes log fájlok
- multi-deployment-*.env   # VM adatok és management parancsok
- benchmark-summary.md     # Markdown összefoglaló
```

## 🛠️ Configuration Examples

### Development Test (gyors és olcsó):
```yaml
instance_count: 1
machine_type: e2-micro
deployment_type: single
cleanup_after: true
```

### Production Benchmark (teljes teszt):
```yaml
instance_count: 5
machine_type: e2-medium
deployment_type: multi
cleanup_after: false  # Manual cleanup
```

### Load Test (nagy terhelés):
```yaml
instance_count: 10
machine_type: e2-standard-4
deployment_type: multi
cleanup_after: true
```

## 🔍 Monitoring & Debugging

### Log Megtekintése:
1. GitHub Actions → Workflow run
2. Expand job steps
3. Download artifacts

### VM-ek Ellenőrzése:
```bash
# Ha cleanup_after: false
gcloud compute instances list --filter="labels.application=image-download"

# SSH VM-be
gcloud compute ssh INSTANCE_NAME --zone=europe-west1-b
```

### Manual Cleanup:
```bash
# Multi deployment cleanup
source multi-deployment-TIMESTAMP.env
gcloud compute instances delete $INSTANCE_1_NAME $INSTANCE_2_NAME --zone=$VM_ZONE
```

## 🚨 Troubleshooting

### Gyakori hibák:

1. **"Permission denied" GCP-nél**
   - Ellenőrizd a `GCP_SA_KEY` secret-et
   - Service Account jogosultságok ellenőrzése

2. **"SSH passphrase required"**
   - Ellenőrizd a `SSH_PASSPHRASE` secret-et
   - SSH kulcs létezése a GCP-n

3. **"Docker build failed"**
   - Dockerfile és requirements.txt ellenőrzése
   - Dependencies frissítése

4. **"VM creation timeout"**
   - GCP quota ellenőrzése
   - Zone availability ellenőrzése

### Debug Mode:
```yaml
# workflow file-ban debug engedélyezése
env:
  ACTIONS_STEP_DEBUG: true
  ACTIONS_RUNNER_DEBUG: true
```

## 📈 Performance Metrics

A workflow automatikusan méri és jelentést készít:

- **VM létrehozási idő**
- **Docker build time**
- **Benchmark execution time**
- **Resource utilization**
- **Cost estimation**

## 🎉 Advanced Features

### Environment-specifikus konfigok:
- **Development**: Gyors és olcsó tesztek
- **Staging**: Közepes terhelés
- **Production**: Teljes benchmark suite

### Notification integráció:
- Slack/Discord webhook
- Email értesítések
- GitHub Status API

### Parallel execution:
- Több zone-ban futtatás
- Different machine types párhuzamosan
- A/B testing support

---

## 💡 Pro Tips

1. **Költség optimalizálás**: `cleanup_after: true` használata development-ben
2. **Gyors iteráció**: `e2-micro` instance-ok development-hez
3. **Load testing**: `e2-standard-4` production load test-hez
4. **Monitoring**: Artifacts rendszeres letöltése és elemzése
