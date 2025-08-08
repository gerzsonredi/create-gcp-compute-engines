import os
import threading
import time
from datetime import datetime

class EVFSAMLogger:
    """
    Simplified logger for production deployment.
    Logs locally only to avoid GCP rate limiting issues.
    """
    def __init__(self, upload_interval=30):
        self.log_dir = "logs"
        os.makedirs(self.log_dir, exist_ok=True)
        
        # Disable GCP upload to prevent rate limiting
        self.gcp_upload_enabled = False
        print("[LOGGER] GCP upload disabled to prevent rate limiting")

    def _get_log_filepath(self):
        today = datetime.now().strftime("%Y-%m-%d")
        filename = f"evfsam{today}.log"
        return os.path.join(self.log_dir, filename)

    def log(self, message: str):
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        logline = f"[{timestamp}] {message}\n"
        log_file = self._get_log_filepath()
        
        # Write to local file only
        try:
            with open(log_file, "a") as f:
                f.write(logline)
        except Exception as e:
            print(f"[LOGGER] Failed to write to local log: {e}")
        
        # Also print to console for debugging
        print(f"[LOG] {message}") 