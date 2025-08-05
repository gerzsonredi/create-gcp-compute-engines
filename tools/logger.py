import os
from datetime import datetime
from google.cloud import storage


class EVFSAMLogger:
    """
    Simple logger for EVF-SAM application.
    Logs are saved locally and uploaded to GCP Cloud Storage.
    Each day a new log file is created, named with the date and 'evfsam' marker.
    """
    def __init__(self):
        # 🚀 GCP CLOUD STORAGE CONFIGURATION
        # In Cloud Run, service account is automatically authenticated
        # For local development, set GOOGLE_APPLICATION_CREDENTIALS
        
        self.bucket_name = "pictures-not-public"  # Use images bucket for logs
        
        try:
            self.storage_client = storage.Client()
            self.bucket = self.storage_client.bucket(self.bucket_name)
            print(f"[LOGGER] GCP Storage client initialized for bucket: {self.bucket_name}")
        except Exception as e:
            print(f"[LOGGER] Failed to initialize GCP Storage client: {e}")
            self.storage_client = None
            self.bucket = None
            
        self.log_dir = "logs"
        os.makedirs(self.log_dir, exist_ok=True)

    def _get_log_filepath(self):
        today = datetime.now().strftime("%Y-%m-%d")
        filename = f"evfsam{today}.log"
        return os.path.join(self.log_dir, filename)

    def log(self, message: str):
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        logline = f"[{timestamp}] {message}\n"
        self.log_file = self._get_log_filepath()
        with open(self.log_file, "a") as f:
            f.write(logline)
        self._upload_to_gcp()

    def _upload_to_gcp(self):
        """Upload log file to GCP Cloud Storage"""
        if self.storage_client is None or self.bucket is None:
            return
        try:
            # Upload to evfsam/ prefix (same structure as S3)
            blob_name = f"evfsam/{os.path.basename(self.log_file)}"
            blob = self.bucket.blob(blob_name)
            blob.upload_from_filename(self.log_file)
            
        except Exception as e:
            # If upload fails, just skip (do not crash the app)
            print(f"[LOGGER] Failed to upload log to GCP: {e}")
            pass
