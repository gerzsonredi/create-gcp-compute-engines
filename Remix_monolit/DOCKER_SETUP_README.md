# Docker Setup with Automatic Model Download

This guide explains how to run the mannequin-segmenter and garment-measuring-hpe services using Docker with automatic model download from GCP Cloud Storage.

## 🚀 Quick Start

Both services are configured to automatically download required models from GCP Cloud Storage when the Docker containers start.

### Prerequisites

1. Docker and Docker Compose installed
2. GCP service account with access to the `artifactsredi` bucket
3. Environment variables configured (see below)

## 📋 Environment Configuration

### Step 1: Create Environment Files

Copy the example environment files and fill in your GCP credentials:

```bash
# For mannequin-segmenter
cp mannequin-segmenter/env.example mannequin-segmenter/.env

# For garment-measuring-hpe  
cp garment-measuring-hpe/env.example garment-measuring-hpe/.env
```

### Step 2: Configure GCP Credentials

Edit the `.env` files with your actual GCP credentials:

```bash
# Required for automatic model download
GCP_PROJECT_ID=your-actual-gcp-project-id
GCP_SA_KEY={"type": "service_account", "project_id": "your-project", ...}  # Full JSON key
BUCKET_NAME_ARTIFACTS=artifactsredi
```

**Important**: The `GCP_SA_KEY` should be the entire JSON service account key as a single line string.

### 🎯 GitHub Actions Secrets Available

The following secrets are already configured in your GitHub repository:
- `GCP_PROJECT_ID` ✅
- `GCP_SA_KEY` ✅  
- `BUCKET_NAME_ARTIFACTS` ✅

You can use the same values from these secrets for your local `.env` files.

## 🐳 Running the Services

### Option 1: Run Individual Services

#### Mannequin Segmenter
```bash
cd mannequin-segmenter
docker-compose up --build
```

#### Garment Measuring HPE
```bash
cd garment-measuring-hpe
docker-compose up --build
```

### Option 2: Run Both Services Together

Create a root `docker-compose.yml` file:

```yaml
version: '3.8'

services:
  mannequin-segmenter:
    build: ./mannequin-segmenter
    ports:
      - "5001:5001"
    env_file:
      - ./mannequin-segmenter/.env
    volumes:
      - ./mannequin-segmenter/logs:/app/logs
      - ./mannequin-segmenter/artifacts:/app/artifacts
    restart: unless-stopped

  garment-measuring-hpe:
    build: ./garment-measuring-hpe
    ports:
      - "5003:5003"
    env_file:
      - ./garment-measuring-hpe/.env
    volumes:
      - ./garment-measuring-hpe/logs:/app/logs
      - ./garment-measuring-hpe/artifacts:/app/artifacts
    restart: unless-stopped
```

Then run:
```bash
docker-compose up --build
```

## 📥 Automatic Model Download Process

When containers start, you'll see output like this:

### Mannequin Segmenter
```
🐳 Starting mannequin-segmenter container...
🔍 Running initialization...
🐳 Docker container initializing...
🔍 Checking for required model files...
📥 Model file not found, attempting download from GCP...
📦 Using bucket: artifactsredi
⬇️  Downloading model (XXX.XX MB)...
✅ Model downloaded successfully! (XXX.XX MB)
✅ File size verification passed
🚀 Initialization complete - starting application...
🚀 Starting main application...
```

### Garment Measuring HPE
```
🐳 Starting garment-measuring-hpe container...
🔍 Running initialization...
🐳 Docker container initializing...
🔍 Checking for required model files...
📥 2 model file(s) missing:
   - pose_hrnet-w48_384x288-deepfashion2_mAP_0.7017.pth
   - bbox_result_val.pkl
📦 Attempting download from GCP...
⬇️  Downloading HRNet pose estimation model...
✅ pose_hrnet-w48_384x288-deepfashion2_mAP_0.7017.pth downloaded successfully!
⬇️  Downloading Bounding box validation results...
✅ bbox_result_val.pkl downloaded successfully!
✅ All 2 model files downloaded successfully!
🚀 Initialization complete - starting application...
```

## 🔧 Manual Model Management

### Check Model Status
```bash
# Mannequin segmenter
docker exec -it <container_name> ls -la /app/artifacts/20250703_190222/

# Garment measuring HPE
docker exec -it <container_name> ls -la /app/artifacts/
```

### Force Model Re-download
Remove the model files from the host volume and restart the container:

```bash
# Mannequin segmenter
rm -rf mannequin-segmenter/artifacts/20250703_190222/checkpoint.pt
docker-compose restart mannequin-segmenter

# Garment measuring HPE
rm -rf garment-measuring-hpe/artifacts/*.pth
rm -rf garment-measuring-hpe/artifacts/*.pkl
docker-compose restart garment-measuring-hpe
```

## 🌐 Service Endpoints

After successful startup:

- **Mannequin Segmenter**: http://localhost:5001
- **Garment Measuring HPE**: http://localhost:5003

## 📊 Container Behavior

### With GCP Credentials
- ✅ Models download automatically on first run
- ✅ Subsequent runs skip download if models exist
- ✅ File integrity verification
- ✅ Graceful error handling

### Without GCP Credentials
- ⚠️ Container starts but models are not downloaded
- ⚠️ Warning messages logged
- ⚠️ Manual model placement required
- ⚠️ Application may fail without models

## 🎯 Production Deployment

### Environment Variables in Production

Set these environment variables in your deployment system:

```bash
export GCP_PROJECT_ID="your-project-id"
export GCP_SA_KEY='{"type": "service_account", ...}'
export BUCKET_NAME_ARTIFACTS="artifactsredi"
```

### Docker Volumes

For persistent model storage in production:

```yaml
volumes:
  - /path/to/persistent/storage/mannequin-artifacts:/app/artifacts
  - /path/to/persistent/storage/hpe-artifacts:/app/artifacts
```

### Health Checks

Add health checks to ensure services are ready:

```yaml
healthcheck:
  test: ["CMD", "curl", "-f", "http://localhost:5001/health"]
  interval: 30s
  timeout: 10s
  retries: 3
```

## 🐛 Troubleshooting

### Common Issues

1. **Models not downloading**
   - Check GCP credentials in `.env` file
   - Verify service account has Storage Object Viewer role
   - Check network connectivity

2. **Permission denied errors**
   - Ensure proper file permissions on volume mounts
   - Check Docker user permissions

3. **Out of disk space**
   - Models require ~650MB total storage
   - Ensure sufficient disk space available

4. **Container fails to start**
   - Check Docker logs: `docker-compose logs <service_name>`
   - Verify all environment variables are set

### Debug Mode

Run containers with debug output:

```bash
docker-compose up --build --verbose
```

### Manual Model Download

If automatic download fails, you can manually download models:

```bash
# Enter container
docker exec -it <container_name> bash

# Run download script manually
python download_model.py  # or download_models.py for HPE
```

## 🔐 Security Notes

- Never commit `.env` files to version control
- Use Docker secrets in production environments
- Rotate GCP service account keys regularly
- Use minimal required permissions for service accounts
- Consider using external secret management systems

## 📁 File Structure

After successful Docker deployment:

```
project/
├── mannequin-segmenter/
│   ├── artifacts/
│   │   └── 20250703_190222/
│   │       └── checkpoint.pt
│   ├── .env
│   └── docker-compose.yml
├── garment-measuring-hpe/
│   ├── artifacts/
│   │   ├── pose_hrnet-w48_384x288-deepfashion2_mAP_0.7017.pth
│   │   └── bbox_result_val.pkl
│   ├── .env
│   └── docker-compose.yml
└── docker-compose.yml (optional combined setup)
``` 