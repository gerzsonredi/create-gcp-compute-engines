# Garment Measuring HPE Models Download

This guide explains how to download the required model files for the garment measuring HPE system from GCP Cloud Storage.

## Model Information

The system requires two model files:

1. **HRNet Pose Estimation Model**
   - **File**: `pose_hrnet-w48_384x288-deepfashion2_mAP_0.7017.pth`
   - **GCP Location**: `gs://artifactsredi/models/pose_hrnet-w48_384x288-deepfashion2_mAP_0.7017.pth`
   - **Local Path**: `artifacts/pose_hrnet-w48_384x288-deepfashion2_mAP_0.7017.pth`
   - **Size**: ~243 MB
   - **Description**: Pre-trained HRNet model for pose estimation on fashion images

2. **Bounding Box Validation Results**
   - **File**: `bbox_result_val.pkl`
   - **GCP Location**: `gs://artifactsredi/models/bbox_result_val.pkl`
   - **Local Path**: `artifacts/bbox_result_val.pkl`
   - **Size**: ~400 MB
   - **Description**: Validation bounding box results for model training

## Prerequisites

1. GCP project with access to the `artifactsredi` bucket
2. Service account with Storage Object Viewer permissions
3. Required environment variables (see below)

## Environment Variables

You need to set the following environment variables:

```bash
export GCP_PROJECT_ID="your-gcp-project-id"
export GCP_SA_KEY='{"type": "service_account", "project_id": "...", ...}'  # Full JSON key
export BUCKET_NAME_ARTIFACTS="artifactsredi"  # Optional, defaults to 'artifactsredi'
```

## Download Methods

### Method 1: Python Script (Recommended)

```bash
cd garment-measuring-hpe
python download_models.py
```

The script will:
- Download both model files sequentially
- Verify file sizes after download
- Show progress for each file
- Skip files that already exist (unless forced)

### Method 2: Shell Script

```bash
cd garment-measuring-hpe
./download_models.sh
```

### Method 3: GitHub Actions

The models can be downloaded automatically using GitHub Actions:

1. Go to the **Actions** tab in your GitHub repository
2. Select **Download Garment Measuring HPE Models** workflow
3. Click **Run workflow**
4. Optionally check "Force re-download" if you want to overwrite existing files

The secrets should already be configured in your repository:
- `GCP_PROJECT_ID`
- `GCP_SA_KEY`
- `BUCKET_NAME_ARTIFACTS`

## Installation

Before running the download scripts, make sure you have the required dependencies:

```bash
pip install google-cloud-storage google-auth
```

Or install all garment-measuring-hpe dependencies:

```bash
pip install -r requirements.txt
```

## Interactive Download Experience

When you run the download script, you'll see output like:

```
=== Garment Measuring HPE Model Downloader ===
Downloading 2 model files...

=== Processing HRNet pose estimation model ===
File: pose_hrnet-w48_384x288-deepfashion2_mAP_0.7017.pth
Model file size: 243.15 MB
Downloading from gs://artifactsredi/models/pose_hrnet-w48_384x288-deepfashion2_mAP_0.7017.pth
Download completed successfully!
File size verification passed.

=== Processing Bounding box validation results ===
File: bbox_result_val.pkl
Model file size: 400.22 MB
Downloading from gs://artifactsredi/models/bbox_result_val.pkl
Download completed successfully!
File size verification passed.

=== Download Summary ===
✅ artifacts/pose_hrnet-w48_384x288-deepfashion2_mAP_0.7017.pth
✅ artifacts/bbox_result_val.pkl

SUCCESS: All 2 model files downloaded successfully!
```

## File Structure

After successful download, your directory structure should look like:

```
garment-measuring-hpe/
├── artifacts/
│   ├── pose_hrnet-w48_384x288-deepfashion2_mAP_0.7017.pth  # ← HRNet model
│   └── bbox_result_val.pkl                                 # ← Bbox results
├── download_models.py
├── download_models.sh
├── requirements.txt
└── ...
```

## Troubleshooting

### Authentication Issues

1. **Invalid JSON in GCP_SA_KEY**: Make sure the service account key is properly formatted JSON
2. **Permission denied**: Ensure the service account has `Storage Object Viewer` role on the bucket
3. **Project not found**: Verify the `GCP_PROJECT_ID` is correct

### Download Issues

1. **File not found**: Check if the model paths exist in the bucket:
   - `gs://artifactsredi/models/pose_hrnet-w48_384x288-deepfashion2_mAP_0.7017.pth`
   - `gs://artifactsredi/models/bbox_result_val.pkl`
2. **Network timeout**: Large model files may take time to download, ensure stable internet connection
3. **Disk space**: Make sure you have sufficient disk space (total ~650 MB required)

### File Verification

After download, verify the files:

```bash
ls -lh artifacts/
# Should show both files with correct sizes:
# pose_hrnet-w48_384x288-deepfashion2_mAP_0.7017.pth (~243 MB)
# bbox_result_val.pkl (~400 MB)
```

### Force Re-download

If you need to re-download files that already exist:

**Python script:**
```bash
# Remove files manually then run script
rm artifacts/pose_hrnet-w48_384x288-deepfashion2_mAP_0.7017.pth
rm artifacts/bbox_result_val.pkl
python download_models.py
```

**GitHub Actions:**
- Check the "Force re-download" option when running the workflow

## Model Usage

Once downloaded, these models are used by the garment measuring system:

- **pose_hrnet-w48_384x288-deepfashion2_mAP_0.7017.pth**: Used for detecting human pose landmarks on fashion images
- **bbox_result_val.pkl**: Contains validation data for bounding box detection accuracy

## Security Notes

- Never commit the `GCP_SA_KEY` to version control
- Use GitHub Secrets for CI/CD environments
- Rotate service account keys regularly
- Use minimal required permissions (Storage Object Viewer only)
- These model files are large - consider using Git LFS if committing to version control 