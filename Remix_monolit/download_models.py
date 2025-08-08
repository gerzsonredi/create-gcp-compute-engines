#!/usr/bin/env python3
"""
Script to download the garment measuring HPE models from GCP Cloud Storage.
This script downloads two files:
1. pose_hrnet-w48_384x288-deepfashion2_mAP_0.7017.pth
2. bbox_result_val.pkl
"""

import os
import json
import logging
import time
import random
from pathlib import Path
from google.cloud import storage
from google.oauth2 import service_account
from google.api_core import retry
from google.api_core.exceptions import TooManyRequests, ServerError

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Model files to download
MODEL_FILES = [
    {
        "name": "pose_hrnet-w48_384x288-deepfashion2_mAP_0.7017.pth",
        "gcp_path": "models/pose_hrnet-w48_384x288-deepfashion2_mAP_0.7017.pth",
        "description": "HRNet pose estimation model"
    },
    {
        "name": "bbox_result_val.pkl",
        "gcp_path": "models/bbox_result_val.pkl", 
        "description": "Bounding box validation results"
    }
]

def retry_with_backoff(func, max_retries=5, base_delay=1):
    """Retry function with exponential backoff for rate limit handling."""
    for attempt in range(max_retries):
        try:
            return func()
        except TooManyRequests as e:
            if attempt == max_retries - 1:
                logger.error(f"❌ Rate limit exceeded after {max_retries} attempts")
                raise
            
            # Exponential backoff with jitter
            delay = base_delay * (2 ** attempt) + random.uniform(0, 1)
            logger.warning(f"⚠️  Rate limit hit, retrying in {delay:.1f}s (attempt {attempt + 1}/{max_retries})")
            time.sleep(delay)
        except ServerError as e:
            if attempt == max_retries - 1:
                logger.error(f"❌ Server error after {max_retries} attempts: {e}")
                raise
            
            delay = base_delay * (2 ** attempt)
            logger.warning(f"⚠️  Server error, retrying in {delay:.1f}s (attempt {attempt + 1}/{max_retries})")
            time.sleep(delay)
        except Exception as e:
            logger.error(f"❌ Unexpected error: {e}")
            raise

def download_models_from_gcp():
    """
    Download the garment measuring HPE models from GCP Cloud Storage.
    Includes rate limiting and retry logic for GCP API limits.
    
    Environment variables required:
    - GCP_PROJECT_ID: GCP project ID
    - GCP_SA_KEY: Service account key as JSON string
    - BUCKET_NAME_ARTIFACTS: GCP bucket name (defaults to 'artifactsredi')
    """
    
    # Get environment variables
    project_id = os.getenv('GCP_PROJECT_ID')
    sa_key_json = os.getenv('GCP_SA_KEY')
    bucket_name = os.getenv('BUCKET_NAME_ARTIFACTS', 'artifactsredi')
    
    if not project_id:
        raise ValueError("GCP_PROJECT_ID environment variable is required")
    if not sa_key_json:
        raise ValueError("GCP_SA_KEY environment variable is required")
    
    logger.info(f"Using project ID: {project_id}")
    logger.info(f"Using bucket: {bucket_name}")
    
    # Parse service account key
    try:
        sa_info = json.loads(sa_key_json)
        credentials = service_account.Credentials.from_service_account_info(sa_info)
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON in GCP_SA_KEY: {e}")
    except Exception as e:
        raise ValueError(f"Error creating credentials: {e}")
    
    # Initialize GCS client
    client = storage.Client(credentials=credentials, project=project_id)
    bucket = client.bucket(bucket_name)
    
    # Define destination directory
    dest_dir = Path(__file__).parent / "artifacts"
    dest_dir.mkdir(parents=True, exist_ok=True)
    
    downloaded_files = []
    
    for model_file in MODEL_FILES:
        file_name = model_file["name"]
        gcp_path = model_file["gcp_path"]
        description = model_file["description"]
        dest_file = dest_dir / file_name
        
        logger.info(f"\n=== Processing {description} ===")
        logger.info(f"File: {file_name}")
        
        # Check if file already exists
        if dest_file.exists():
            logger.info(f"Model file already exists at {dest_file}")
            file_size = dest_file.stat().st_size
            logger.info(f"Existing file size: {file_size / (1024*1024):.2f} MB")
            
            # Ask user if they want to overwrite
            response = input(f"File {file_name} already exists. Do you want to re-download? (y/N): ").strip().lower()
            if response not in ['y', 'yes']:
                logger.info("Skipping download.")
                downloaded_files.append(str(dest_file))
                continue
        
        def download_single_file():
            # Get blob info
            blob = bucket.blob(gcp_path)
            
            # Check if blob exists with retry
            def check_blob_exists():
                return blob.exists()
            
            if not retry_with_backoff(check_blob_exists, max_retries=3):
                raise FileNotFoundError(f"Model file not found at gs://{bucket_name}/{gcp_path}")
            
            # Get blob size with retry
            def get_blob_info():
                blob.reload()
                return blob.size
            
            blob_size = retry_with_backoff(get_blob_info, max_retries=3)
            logger.info(f"Model file size: {blob_size / (1024*1024):.2f} MB")
            
            # Download the file with retry
            logger.info(f"Downloading from gs://{bucket_name}/{gcp_path}")
            logger.info(f"Destination: {dest_file}")
            
            def download_blob():
                blob.download_to_filename(str(dest_file))
                return True
            
            retry_with_backoff(download_blob, max_retries=5, base_delay=2)
            
            # Verify download
            if dest_file.exists():
                downloaded_size = dest_file.stat().st_size
                logger.info(f"Download completed successfully!")
                logger.info(f"Downloaded file size: {downloaded_size / (1024*1024):.2f} MB")
                
                if downloaded_size == blob_size:
                    logger.info("File size verification passed.")
                else:
                    logger.warning(f"File size mismatch! Expected: {blob_size}, Got: {downloaded_size}")
                
                downloaded_files.append(str(dest_file))
                return True
            else:
                raise Exception("Download failed - file not found after download")
        
        try:
            download_single_file()
            # Add delay between downloads to avoid rate limits
            if file_name != MODEL_FILES[-1]["name"]:  # Don't delay after last file
                logger.info("⏳ Waiting 2 seconds before next download to avoid rate limits...")
                time.sleep(2)
                
        except Exception as e:
            logger.error(f"Error downloading {file_name}: {e}")
            raise
    
    return downloaded_files

def main():
    """Main function to run the download script."""
    try:
        logger.info("=== Garment Measuring HPE Model Downloader ===")
        logger.info(f"Downloading {len(MODEL_FILES)} model files...")
        
        downloaded_files = download_models_from_gcp()
        
        logger.info(f"\n=== Download Summary ===")
        for file_path in downloaded_files:
            logger.info(f"✅ {file_path}")
        
        print(f"SUCCESS: All {len(downloaded_files)} model files downloaded successfully!")
        
    except Exception as e:
        logger.error(f"Failed to download models: {e}")
        print(f"ERROR: {e}")
        exit(1)

if __name__ == "__main__":
    main() 