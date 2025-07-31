import os, boto3, json
from datetime import datetime

class EVFSAMLogger:
    """
    Simple logger for EVF-SAM application.
    Logs are saved locally and uploaded to S3 logs-redi bucket.
    Each day a new log file is created, named with the date and 'evfsam' marker.
    """
    def __init__(self):
        CONFIG_FILE = "configs/config_general_aws.json"
        with open(CONFIG_FILE, "r") as jf:
            self.__config = json.load(jf)
        self.bucket_name            = self.__config.get("AWS_S3_BUCKET_NAME")
        self.aws_access_key_id      = self.__config.get("AWS_ACCESS_KEY_ID")
        self.aws_secret_access_key  = self.__config.get("AWS_SECRET_ACCESS_KEY")
        self.aws_s3_region          = self.__config.get("AWS_S3_REGION")
        self.s3_client = None
        if all([self.aws_access_key_id, self.aws_secret_access_key, self.aws_s3_region]):
            self.s3_client = boto3.client(
                's3',
                aws_access_key_id=self.aws_access_key_id,
                aws_secret_access_key=self.aws_secret_access_key,
                region_name=self.aws_s3_region
            )
        self.log_dir = "logs"
        os.makedirs(self.log_dir, exist_ok=True)
        self.log_file = self._get_log_filepath()

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
        self._upload_to_s3()

    def _upload_to_s3(self):
        if self.s3_client is None:
            return
        try:
            s3_key = f"evfsam/{os.path.basename(self.log_file)}"
            self.s3_client.upload_file(self.log_file, self.bucket_name, s3_key)
        except Exception as e:
            # If upload fails, just skip (do not crash the app)
            pass
