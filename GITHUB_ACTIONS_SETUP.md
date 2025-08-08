# GitHub Actions Setup for Garment Measuring HPE

This repository is configured to automatically download required model files from GCP Cloud Storage using GitHub Actions.

## 🔐 Required Secrets

The following secrets need to be configured in your GitHub repository:

| Secret Name | Description | Example |
|-------------|-------------|---------|
| `GCP_PROJECT_ID` | Your GCP project ID | `my-project-id` |
| `GCP_SA_KEY` | Service account JSON key | `{"type": "service_account", ...}` |
| `BUCKET_NAME_ARTIFACTS` | GCP bucket name | `artifactsredi` |

### How to Configure Secrets

1. Go to your repository on GitHub
2. Click **Settings** → **Secrets and variables** → **Actions**
3. Click **New repository secret**
4. Add each secret with the exact names above

## 🚀 Available Workflows

### Download Garment Measuring HPE Models
**File**: `.github/workflows/download-models.yml`

Downloads both required model files:
- `pose_hrnet-w48_384x288-deepfashion2_mAP_0.7017.pth` (~243MB)
- `bbox_result_val.pkl` (~400MB)

**How to run:**
1. Go to **Actions** tab
2. Select **"Download Garment Measuring HPE Models"**
3. Click **"Run workflow"**
4. Choose force download option if needed

### Combined Workflows (if copied from main project)
If you copied the combined workflows, they can download models for multiple projects at once.

## 📥 Model Download Process

When you run the workflow, it will:

1. ✅ **Checkout code** from the repository
2. ✅ **Setup Python** environment
3. ✅ **Install dependencies** (google-cloud-storage, google-auth)
4. ✅ **Download models** from GCP using the secrets
5. ✅ **Verify downloads** with file size checks
6. ✅ **Create summary** with download results
7. ✅ **Upload artifacts** (optional, 7-day retention)

## 📊 Expected Output

After successful run, you'll have:
```
artifacts/
├── pose_hrnet-w48_384x288-deepfashion2_mAP_0.7017.pth  (~243MB)
└── bbox_result_val.pkl                                 (~400MB)
```

## 🔧 Workflow Features

- **Smart caching**: Skips download if files already exist
- **Force re-download**: Option to override existing files
- **File verification**: Checks file sizes after download
- **Detailed logging**: Progress tracking and error reporting
- **Summary reports**: GitHub summary with download status
- **Artifact upload**: Optional GitHub artifact storage

## 🐛 Troubleshooting

### Common Issues

1. **Secret not found error**
   ```
   Error: GCP_PROJECT_ID secret not found
   ```
   **Solution**: Configure the missing secret in repository settings

2. **Authentication failed**
   ```
   Error: Invalid JSON in GCP_SA_KEY
   ```
   **Solution**: Verify the service account JSON is properly formatted

3. **Model not found**
   ```
   Error: Model file not found at gs://bucket/path
   ```
   **Solution**: Verify the model exists in the specified GCP bucket path

4. **Permission denied**
   ```
   Error: 403 Forbidden
   ```
   **Solution**: Ensure service account has Storage Object Viewer role

### Debug Steps

1. **Check workflow logs**:
   - Go to Actions → Failed workflow → View logs
   - Look for specific error messages

2. **Verify secrets**:
   - Settings → Secrets and variables → Actions
   - Ensure all three secrets exist

3. **Test locally**:
   - Use the same credentials with local download scripts
   - Verify GCP access works

## 🔄 Integration with Docker

Models downloaded via GitHub Actions are compatible with Docker:

1. **Run GitHub Actions** to download models
2. **Build Docker image** using existing models
3. **Deploy containers** with volume mounts

## 🎯 Best Practices

### For Teams
- Run workflows before major deployments
- Use force re-download when models are updated
- Monitor workflow success in team notifications

### For CI/CD
- Include model download as prerequisite step
- Cache downloaded models between builds
- Verify model availability before deployment

## 🎉 Quick Start

**Ready to download models?**

1. **Configure secrets** (if not already done)
2. Go to [Actions tab](../../actions)
3. Select **"Download Garment Measuring HPE Models"**
4. Click **"Run workflow"**
5. Wait for completion (~5-10 minutes)
6. Models are ready! 🚀

## 📋 Model Information

| Model File | Size | Purpose | GCP Location |
|------------|------|---------|--------------|
| `pose_hrnet-w48_384x288-deepfashion2_mAP_0.7017.pth` | ~243MB | Pose estimation | `gs://artifactsredi/models/pose_hrnet-w48_384x288-deepfashion2_mAP_0.7017.pth` |
| `bbox_result_val.pkl` | ~400MB | Bounding box validation | `gs://artifactsredi/models/bbox_result_val.pkl` |

**Total download size**: ~643MB 