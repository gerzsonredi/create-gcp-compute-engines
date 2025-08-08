#!/usr/bin/env python3
"""
Smart Docker initialization script for garment-measuring-hpe.
- Local development: Uses existing model files if available
- GCP deployment: Always downloads fresh models from Cloud Storage
"""

import os
import sys
import json
import logging
import time
import random
from pathlib import Path

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Model files to check/download
MODEL_FILES = [
    {
        "name": "pose_hrnet-w48_384x288-deepfashion2_mAP_0.7017.pth",
        "gcp_path": "models/pose_hrnet-w48_384x288-deepfashion2_mAP_0.7017.pth",
        "local_path": "/app/artifacts/pose_hrnet-w48_384x288-deepfashion2_mAP_0.7017.pth",
        "description": "HRNet pose estimation model"
    },
    {
        "name": "bbox_result_val.pkl",
        "gcp_path": "models/bbox_result_val.pkl",
        "local_path": "/app/artifacts/bbox_result_val.pkl",
        "description": "Bounding box validation results"
    }
]

def detect_environment():
    """Detect if we're running locally or on GCP."""
    # Check for GCP metadata server (indicates GCP environment)
    try:
        import requests
        response = requests.get(
            'http://metadata.google.internal/computeMetadata/v1/instance/',
            headers={'Metadata-Flavor': 'Google'},
            timeout=1
        )
        if response.status_code == 200:
            logger.info("🌐 Detected GCP environment")
            return "gcp"
    except:
        pass
    
    # Check for other cloud indicators
    if os.getenv('GOOGLE_CLOUD_PROJECT') or os.getenv('K_SERVICE'):
        logger.info("🌐 Detected GCP environment (via env vars)")
        return "gcp"
    
    # Check if we're in a local Docker environment with mounted volumes
    if os.path.exists('/app/artifacts') and any(Path(f["local_path"]).exists() for f in MODEL_FILES):
        logger.info("🏠 Detected local development environment with existing models")
        return "local_with_models"
    
    logger.info("🏠 Detected local development environment")
    return "local"

def check_model_files():
    """Check if all required model files exist."""
    missing_files = []
    for model_file in MODEL_FILES:
        local_path = Path(model_file["local_path"])
        if not local_path.exists():
            missing_files.append(model_file)
    return missing_files

def download_models_if_needed():
    """Download models based on environment and availability."""
    
    environment = detect_environment()
    missing_files = check_model_files()
    
    if environment == "local_with_models" and not missing_files:
        logger.info("✅ All model files found locally - using existing models")
        for model_file in MODEL_FILES:
            local_path = Path(model_file["local_path"])
            size_mb = local_path.stat().st_size / (1024*1024)
            logger.info(f"  📁 {model_file['name']}: {size_mb:.2f} MB")
        return True
    
    if environment == "gcp" or missing_files:
        if environment == "gcp":
            logger.info("🌐 GCP environment detected - downloading fresh models")
        else:
            logger.info(f"📥 {len(missing_files)} model file(s) missing - attempting download")
        
        # Check if GCP credentials are available
        project_id = os.getenv('GCP_PROJECT_ID')
        sa_key_json = os.getenv('GCP_SA_KEY')
        
        if not project_id or not sa_key_json:
            if environment == "gcp":
                logger.error("❌ GCP environment but no credentials found!")
                return False
            else:
                logger.warning("⚠️  No GCP credentials - running without model download")
                logger.warning("   Set GCP_PROJECT_ID and GCP_SA_KEY environment variables to enable download")
                return False
        
        return download_from_gcp()
    
    logger.info("✅ All models available - proceeding")
    return True

def retry_with_backoff(func, max_retries=5, base_delay=1):
    """Retry function with exponential backoff for rate limit handling."""
    for attempt in range(max_retries):
        try:
            return func()
        except Exception as e:
            if "429" in str(e) or "rateLimitExceeded" in str(e):
                if attempt == max_retries - 1:
                    logger.error(f"❌ Rate limit exceeded after {max_retries} attempts")
                    raise
                
                # Exponential backoff with jitter
                delay = base_delay * (2 ** attempt) + random.uniform(0, 1)
                logger.warning(f"⚠️  Rate limit hit, retrying in {delay:.1f}s (attempt {attempt + 1}/{max_retries})")
                time.sleep(delay)
            elif "5" in str(e)[:1]:  # Server errors (5xx)
                if attempt == max_retries - 1:
                    logger.error(f"❌ Server error after {max_retries} attempts: {e}")
                    raise
                
                delay = base_delay * (2 ** attempt)
                logger.warning(f"⚠️  Server error, retrying in {delay:.1f}s (attempt {attempt + 1}/{max_retries})")
                time.sleep(delay)
            else:
                logger.error(f"❌ Unexpected error: {e}")
                raise

def download_from_gcp():
    """Download models from GCP Cloud Storage with rate limiting."""
    try:
        # Import here to avoid dependency issues
        from google.cloud import storage
        from google.oauth2 import service_account
        
        # Get environment variables
        project_id = os.getenv('GCP_PROJECT_ID')
        sa_key_json = os.getenv('GCP_SA_KEY')
        bucket_name = os.getenv('BUCKET_NAME_ARTIFACTS', 'artifactsredi')
        
        logger.info(f"📦 Using bucket: {bucket_name}")
        
        # Parse service account key
        try:
            sa_info = json.loads(sa_key_json)
            credentials = service_account.Credentials.from_service_account_info(sa_info)
        except json.JSONDecodeError as e:
            logger.error(f"❌ Invalid JSON in GCP_SA_KEY: {e}")
            return False
        
        # Initialize GCS client
        client = storage.Client(credentials=credentials, project=project_id)
        bucket = client.bucket(bucket_name)
        
        # Create artifacts directory
        artifacts_dir = Path("/app/artifacts")
        artifacts_dir.mkdir(parents=True, exist_ok=True)
        
        # Download each file
        success_count = 0
        for model_file in MODEL_FILES:
            name = model_file["name"]
            gcp_path = model_file["gcp_path"]
            local_path = Path(model_file["local_path"])
            description = model_file["description"]
            
            logger.info(f"\n⬇️  Downloading {description}...")
            
            def download_single_model():
                blob = bucket.blob(gcp_path)
                
                # Check if blob exists with retry
                def check_exists():
                    return blob.exists()
                
                if not retry_with_backoff(check_exists, max_retries=3):
                    logger.error(f"❌ Model file not found at gs://{bucket_name}/{gcp_path}")
                    return False
                
                # Get blob size with retry
                def get_size():
                    blob.reload()
                    return blob.size
                
                blob_size = retry_with_backoff(get_size, max_retries=3)
                logger.info(f"   Size: {blob_size / (1024*1024):.2f} MB")
                
                # Download with retry
                def download():
                    blob.download_to_filename(str(local_path))
                    return True
                
                retry_with_backoff(download, max_retries=5, base_delay=2)
                
                # Verify download
                if local_path.exists():
                    downloaded_size = local_path.stat().st_size
                    logger.info(f"✅ {name} downloaded successfully!")
                    
                    if downloaded_size == blob_size:
                        logger.info("✅ File size verification passed")
                        return True
                    else:
                        logger.warning(f"⚠️  File size mismatch! Expected: {blob_size}, Got: {downloaded_size}")
                        return True  # Still count as success
                else:
                    logger.error(f"❌ Download failed for {name}")
                    return False
            
            try:
                if download_single_model():
                    success_count += 1
                    
                # Add delay between downloads to avoid rate limits
                if name != MODEL_FILES[-1]["name"]:  # Don't delay after last file
                    logger.info("⏳ Waiting 3 seconds before next download...")
                    time.sleep(3)
                    
            except Exception as e:
                logger.error(f"❌ Error downloading {name}: {e}")
                continue
        
        if success_count == len(MODEL_FILES):
            logger.info(f"✅ All {success_count} model files downloaded successfully!")
            return True
        elif success_count > 0:
            logger.warning(f"⚠️  Partial success: {success_count}/{len(MODEL_FILES)} files downloaded")
            return True
        else:
            logger.error("❌ No files were downloaded successfully")
            return False
            
    except ImportError:
        logger.error("❌ google-cloud-storage not installed. Cannot download models.")
        return False
    except Exception as e:
        logger.error(f"❌ Error downloading models: {e}")
        return False

def main():
    """Main initialization function."""
    logger.info("🐳 Docker container initializing...")
    logger.info("🔍 Checking model requirements...")
    
    try:
        success = download_models_if_needed()
        if success:
            logger.info("🚀 Initialization complete - starting application...")
        else:
            logger.warning("⚠️  Initialization completed with warnings - starting application anyway...")
        return True
    except Exception as e:
        logger.error(f"❌ Initialization failed: {e}")
        logger.warning("⚠️  Starting application without model initialization...")
        return False

if __name__ == "__main__":
    main() 