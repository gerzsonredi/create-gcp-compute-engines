# Model Management Summary

This document provides an overview of all available methods for downloading and managing models for the mannequin-segmenter and garment-measuring-hpe projects.

## 📦 Available Models

| Project | Model File | Size | GCP Location |
|---------|------------|------|--------------|
| **Mannequin Segmenter** | `checkpoint.pt` | ~200MB | `gs://artifactsredi/models/Mannequin_segmenter/20250703_190222/checkpoint.pt` |
| **Garment Measuring HPE** | `pose_hrnet-w48_384x288-deepfashion2_mAP_0.7017.pth` | ~243MB | `gs://artifactsredi/models/pose_hrnet-w48_384x288-deepfashion2_mAP_0.7017.pth` |
| **Garment Measuring HPE** | `bbox_result_val.pkl` | ~400MB | `gs://artifactsredi/models/bbox_result_val.pkl` |

**Total Size**: ~843MB

## 🚀 Download Methods

### 1. 🤖 GitHub Actions (RECOMMENDED)
**Best for**: Automated downloads, CI/CD, team collaboration

✅ **Secrets already configured**: `GCP_PROJECT_ID`, `GCP_SA_KEY`, `BUCKET_NAME_ARTIFACTS`

#### Available Workflows:
- **Download All Models (Combined)** - Downloads both projects ⭐
- **Download Mannequin Segmenter Model** - Single project
- **Download Garment Measuring HPE Models** - Single project

**Usage**: 
```
Actions tab → Select workflow → Run workflow → Choose options
```

**Features**:
- ✅ Force re-download option
- ✅ Project selection (both/individual)
- ✅ Detailed summary reports
- ✅ File integrity verification
- ✅ Parallel processing

📖 **[Full GitHub Actions Guide](GITHUB_ACTIONS_README.md)**

---

### 2. 🐳 Docker Automatic Download
**Best for**: Production deployment, containerized environments

**How it works**:
- Container starts → Checks for models → Downloads if missing → Starts application

**Setup**:
```bash
# Copy environment template
cp mannequin-segmenter/env.example mannequin-segmenter/.env
cp garment-measuring-hpe/env.example garment-measuring-hpe/.env

# Fill in GCP credentials (same as GitHub secrets)
# Then run:
docker-compose up --build
```

**Features**:
- ✅ Automatic initialization
- ✅ Graceful degradation (starts without models if no credentials)
- ✅ Volume persistence
- ✅ Smart caching (skips if models exist)

📖 **[Full Docker Guide](DOCKER_SETUP_README.md)**

---

### 3. 💻 Local Scripts
**Best for**: Development, manual control, debugging

#### Python Scripts:
```bash
# Mannequin Segmenter
cd mannequin-segmenter
python download_model.py

# Garment Measuring HPE  
cd garment-measuring-hpe
python download_models.py
```

#### Shell Scripts:
```bash
# Mannequin Segmenter
cd mannequin-segmenter
./download_model.sh

# Garment Measuring HPE
cd garment-measuring-hpe  
./download_models.sh
```

**Features**:
- ✅ Interactive prompts
- ✅ Detailed progress logging
- ✅ File size verification
- ✅ Error handling

📖 **Individual project README files for detailed guides**

## 🔧 Configuration

### Required Environment Variables
```bash
GCP_PROJECT_ID=your-gcp-project-id
GCP_SA_KEY={"type": "service_account", "project_id": "...", ...}
BUCKET_NAME_ARTIFACTS=artifactsredi  # Optional, defaults to this
```

### 🎯 GitHub Secrets (Already Configured) ✅
The same values are available as GitHub repository secrets for automated workflows.

## 📋 Decision Matrix

| Scenario | Recommended Method | Why |
|----------|-------------------|-----|
| **First time setup** | GitHub Actions | Easy, automated, no local setup needed |
| **Production deployment** | Docker Automatic | Integrated with container lifecycle |
| **Development/Testing** | Local Scripts | Full control, debugging capabilities |
| **CI/CD Pipeline** | GitHub Actions | Already integrated, team collaboration |
| **Model updates** | GitHub Actions | Centralized, tracked, reproducible |
| **Offline development** | Local Scripts | Works without internet after download |

## 🔄 Integration Workflows

### For New Developers
1. **GitHub Actions**: Download models to repository
2. **Docker**: Use downloaded models in containers
3. **Local**: Copy models from containers if needed

### For Production
1. **GitHub Actions**: Download/update models
2. **Docker**: Deploy with automatic model detection
3. **Monitoring**: Check Docker logs for model status

### For CI/CD
1. **GitHub Actions**: Model download as separate workflow
2. **Docker Build**: Use existing models
3. **Testing**: Verify model availability

## 🐛 Common Issues & Solutions

| Issue | GitHub Actions | Docker | Local Scripts |
|-------|---------------|--------|---------------|
| **Authentication Failed** | Check secrets | Check `.env` file | Check environment variables |
| **Model Not Found** | Verify GCP paths | Same | Same |
| **Network Timeout** | Re-run workflow | Restart container | Re-run script |
| **Disk Space** | Use smaller runners | Check volume space | Check local space |
| **Permission Denied** | Check service account | Check Docker permissions | Check file permissions |

## 📊 Performance Comparison

| Method | Setup Time | Download Speed | Automation | Debugging |
|--------|------------|---------------|------------|-----------|
| **GitHub Actions** | None | Fast | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ |
| **Docker Automatic** | 5 min | Fast | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ |
| **Local Scripts** | 2 min | Fast | ⭐⭐ | ⭐⭐⭐⭐⭐ |

## 🎉 Quick Start Recommendations

### For Most Users:
1. **Use GitHub Actions** to download models initially
2. **Use Docker** for running the applications
3. **Keep local scripts** as backup/debugging option

### Command sequence:
```bash
# 1. Download models via GitHub Actions
# (Go to Actions tab → Download All Models)

# 2. Setup Docker environment  
cp mannequin-segmenter/env.example mannequin-segmenter/.env
cp garment-measuring-hpe/env.example garment-measuring-hpe/.env
# (Fill in the same credentials as GitHub secrets)

# 3. Run with Docker
docker-compose up --build
```

## 📁 Final File Structure
```
project/
├── .github/workflows/
│   ├── download-all-models.yml       # Combined workflow ⭐
│   ├── download-model.yml            # Mannequin only
│   └── download-hpe-models.yml       # HPE only
├── mannequin-segmenter/
│   ├── artifacts/20250703_190222/
│   │   └── checkpoint.pt             # Downloaded model
│   ├── download_model.py             # Local script
│   ├── download_model.sh             # Shell wrapper
│   ├── docker_init.py                # Docker initialization
│   ├── entrypoint.sh                 # Docker entrypoint
│   └── env.example                   # Template
├── garment-measuring-hpe/
│   ├── artifacts/
│   │   ├── pose_hrnet-w48_384x288-deepfashion2_mAP_0.7017.pth
│   │   └── bbox_result_val.pkl
│   ├── download_models.py            # Local script
│   ├── download_models.sh            # Shell wrapper
│   ├── docker_init.py                # Docker initialization
│   ├── entrypoint.sh                 # Docker entrypoint
│   └── env.example                   # Template
└── Documentation/
    ├── GITHUB_ACTIONS_README.md      # GitHub Actions guide
    ├── DOCKER_SETUP_README.md        # Docker guide
    └── MODEL_MANAGEMENT_SUMMARY.md   # This file
```

**All methods are ready to use with your existing GitHub secrets!** 🎉 