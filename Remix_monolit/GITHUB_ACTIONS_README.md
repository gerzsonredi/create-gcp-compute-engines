# GitHub Actions Model Download

Since your GitHub repository already has the required GCP secrets configured, you can easily download models using GitHub Actions workflows.

## 🔐 Available Secrets

Your repository has these secrets configured:
- `GCP_PROJECT_ID` ✅
- `GCP_SA_KEY` ✅
- `BUCKET_NAME_ARTIFACTS` ✅

## 🚀 Available Workflows

### 1. Download All Models (Combined) - **RECOMMENDED**
**File**: `.github/workflows/download-all-models.yml`

This workflow can download models for one or both projects in a single run.

**How to run:**
1. Go to **Actions** tab → **Download All Models (Combined)**
2. Click **Run workflow**
3. Choose options:
   - **Force re-download**: Check if you want to re-download existing files
   - **Projects**: Select `both`, `mannequin-segmenter`, or `garment-measuring-hpe`

### 2. Individual Project Workflows

#### Mannequin Segmenter Only
**File**: `.github/workflows/download-model.yml`
- Downloads: `checkpoint.pt` (~200MB)
- Location: `mannequin-segmenter/artifacts/20250703_190222/`

#### Garment Measuring HPE Only  
**File**: `.github/workflows/download-hpe-models.yml`
- Downloads: 
  - `pose_hrnet-w48_384x288-deepfashion2_mAP_0.7017.pth` (~243MB)
  - `bbox_result_val.pkl` (~400MB)
- Location: `garment-measuring-hpe/artifacts/`

## 📊 Workflow Features

### ✨ Smart Download Logic
- ✅ **Checks existing files**: Skips download if models already exist
- ✅ **Force re-download option**: Override existing files if needed
- ✅ **File size verification**: Ensures download integrity
- ✅ **Parallel downloads**: HPE models download simultaneously
- ✅ **Detailed logging**: Progress tracking and error reporting

### 📋 Summary Reports
Each workflow generates a summary showing:
- Which models were downloaded
- File sizes and verification status
- Any errors or warnings
- Configuration used

## 🎯 Usage Examples

### Download All Models (First Time)
```bash
Actions → Download All Models (Combined) → Run workflow
- Force re-download: ❌ (false)
- Projects: both
```

### Re-download Specific Project
```bash
Actions → Download All Models (Combined) → Run workflow
- Force re-download: ✅ (true)  
- Projects: garment-measuring-hpe
```

### Update Single Model
```bash
Actions → Download Mannequin Segmenter Model → Run workflow
- Force re-download: ✅ (true)
```

## 📥 What Gets Downloaded

### Mannequin Segmenter
```
mannequin-segmenter/
└── artifacts/
    └── 20250703_190222/
        └── checkpoint.pt  (~200MB)
```

### Garment Measuring HPE
```
garment-measuring-hpe/
└── artifacts/
    ├── pose_hrnet-w48_384x288-deepfashion2_mAP_0.7017.pth  (~243MB)
    └── bbox_result_val.pkl                                 (~400MB)
```

## 🔄 Workflow Status

After running workflows, you can:

1. **Check workflow status** in the Actions tab
2. **View logs** for detailed download progress
3. **Download artifacts** (optional) - workflows can upload models as GitHub artifacts with 7-day retention

## 🐛 Troubleshooting

### Common Issues

1. **Workflow fails with authentication error**
   - Verify the GitHub secrets are correctly set
   - Check if the service account has proper permissions

2. **Model not found error**
   - Verify the model paths in GCP bucket:
     - `gs://artifactsredi/models/Mannequin_segmenter/20250703_190222/checkpoint.pt`
     - `gs://artifactsredi/models/pose_hrnet-w48_384x288-deepfashion2_mAP_0.7017.pth`
     - `gs://artifactsredi/models/bbox_result_val.pkl`

3. **Workflow times out**
   - Large models may take time to download
   - GitHub Actions has 6-hour timeout limit
   - Check network issues or GCP service status

### Debugging Steps

1. **Check workflow logs**:
   - Go to Actions → Select failed workflow → View logs

2. **Verify secrets**:
   - Settings → Secrets and variables → Actions
   - Ensure all three secrets exist and are not empty

3. **Test with single project**:
   - Run individual project workflows first
   - Then try the combined workflow

## 🔄 Integration with Docker

The models downloaded via GitHub Actions are compatible with the Docker setup:

1. **GitHub Actions downloads models** → Repository files
2. **Docker builds use local models** → No need to download again
3. **Volume mounts preserve models** → Persistent across container restarts

## 📋 Best Practices

### For Production
- Run workflows before deploying Docker containers
- Use the combined workflow for efficiency
- Enable workflow status notifications

### For Development
- Download models once, then use Docker volume mounts
- Use force re-download only when models are updated
- Keep local `.env` files in sync with GitHub secrets

## 🎉 Quick Start

**Ready to download models?**

1. Go to [Actions tab](../../actions)
2. Select **"Download All Models (Combined)"**
3. Click **"Run workflow"**
4. Choose **"both"** projects
5. Wait for completion (~5-10 minutes)
6. Models are ready for Docker or local development! 