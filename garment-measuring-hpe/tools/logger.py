import os
import threading
import time
from datetime import datetime

# 🚨 FALLBACK: Try to import GCP storage, fallback to mock if not available
try:
    from google.cloud import storage
    GCP_AVAILABLE = True
    print("[LOGGER] google-cloud-storage imported successfully")
except ImportError as e:
    print(f"[LOGGER] ⚠️ WARNING: google-cloud-storage not available: {e}")
    print("[LOGGER] Using fallback mode - log uploads will be skipped")
    GCP_AVAILABLE = False
    storage = None


class EVFSAMLogger:
    """
    Enhanced logger for EVF-SAM application with batch upload to prevent rate limiting.
    Logs are saved locally and uploaded to GCP Cloud Storage every 10 seconds.
    Each day a new log file is created, named with the date and 'evfsam' marker.
    """
    def __init__(self, upload_interval=10):
        # 🚀 GCP CLOUD STORAGE CONFIGURATION
        # In Cloud Run, service account is automatically authenticated
        # For local development, set GOOGLE_APPLICATION_CREDENTIALS
        
        self.bucket_name = "pictures-not-public"  # Use images bucket for logs
        self.upload_interval = upload_interval  # Upload every 10 seconds
        self.last_upload_time = 0
        self.upload_lock = threading.Lock()
        self.pending_upload = False
        
        if GCP_AVAILABLE:
            try:
                self.storage_client = storage.Client()
                self.bucket = self.storage_client.bucket(self.bucket_name)
                print(f"[LOGGER] GCP Storage client initialized for bucket: {self.bucket_name}")
            except Exception as e:
                print(f"[LOGGER] Failed to initialize GCP Storage client: {e}")
                print("[LOGGER] Falling back to local-only logging")
                self.storage_client = None
                self.bucket = None
        else:
            print("[LOGGER] Using fallback mode - logs will be local only")
            self.storage_client = None
            self.bucket = None
            
        self.log_dir = "logs"
        os.makedirs(self.log_dir, exist_ok=True)
        
        # Start background upload thread
        if self.storage_client is not None:
            self.upload_thread = threading.Thread(target=self._background_uploader, daemon=True)
            self.upload_thread.start()
            print(f"[LOGGER] Background uploader started (interval: {upload_interval}s)")

    def _get_log_filepath(self):
        today = datetime.now().strftime("%Y-%m-%d")
        filename = f"evfsam{today}.log"
        return os.path.join(self.log_dir, filename)

    def log(self, message: str):
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        logline = f"[{timestamp}] {message}\n"
        self.log_file = self._get_log_filepath()
        
        # Write to local file immediately
        with open(self.log_file, "a") as f:
            f.write(logline)
        
        # Mark that we have pending upload
        with self.upload_lock:
            self.pending_upload = True

    def _background_uploader(self):
        """Background thread that uploads logs every 10 seconds"""
        while True:
            try:
                time.sleep(self.upload_interval)
                
                with self.upload_lock:
                    if not self.pending_upload:
                        continue
                    
                    # Reset flag before upload
                    self.pending_upload = False
                
                # Upload the current log file
                self._upload_to_gcp_safe()
                
            except Exception as e:
                print(f"[LOGGER] Background uploader error: {e}")
                time.sleep(5)  # Wait a bit before retrying

    def _upload_to_gcp_safe(self):
        """Upload log file to GCP Cloud Storage with rate limiting protection"""
        if self.storage_client is None or self.bucket is None:
            return
            
        try:
            current_log_file = self._get_log_filepath()
            
            # Check if file exists and has content
            if not os.path.exists(current_log_file) or os.path.getsize(current_log_file) == 0:
                return
            
            # Upload to evfsam/ prefix (same structure as S3)
            blob_name = f"evfsam/{os.path.basename(current_log_file)}"
            blob = self.bucket.blob(blob_name)
            
            # Add timestamp to track uploads
            upload_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            # Upload with retry logic for rate limiting
            max_retries = 3
            for attempt in range(max_retries):
                try:
                    blob.upload_from_filename(current_log_file)
                    print(f"[LOGGER] Successfully uploaded log to GCP at {upload_time}")
                    break
                except Exception as e:
                    if "429" in str(e) or "rateLimitExceeded" in str(e):
                        if attempt < max_retries - 1:
                            wait_time = (2 ** attempt) * 5  # 5, 10, 20 seconds
                            print(f"[LOGGER] Rate limit hit, waiting {wait_time}s before retry...")
                            time.sleep(wait_time)
                            continue
                        else:
                            print(f"[LOGGER] Rate limit exceeded after {max_retries} attempts, skipping upload")
                    else:
                        print(f"[LOGGER] Upload failed: {e}")
                    break
                    
        except Exception as e:
            # If upload fails, just skip (do not crash the app)
            print(f"[LOGGER] Failed to upload log to GCP: {e}")

    def _upload_to_gcp(self):
        """Legacy method - now just marks for batch upload"""
        with self.upload_lock:
            self.pending_upload = True

    def force_upload(self):
        """Force immediate upload (useful for shutdown)"""
        if self.storage_client is not None:
            print("[LOGGER] Forcing immediate log upload...")
            self._upload_to_gcp_safe()
