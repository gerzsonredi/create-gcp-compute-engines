import json, io, requests, time, os, torch, cv2
from PIL import Image
import numpy as np
from urllib.parse import urlparse
from tools.turbojpeg_loader import turbojpeg_loader

# 🚨 FALLBACK: Try to import GCP storage, fallback to mock if not available
try:
    from google.cloud import storage
    GCP_AVAILABLE = True
    print("[GCP_STORAGE] google-cloud-storage imported successfully")
except ImportError as e:
    print(f"[GCP_STORAGE] ⚠️ WARNING: google-cloud-storage not available: {e}")
    print("[GCP_STORAGE] Using fallback mode - uploads will be skipped")
    GCP_AVAILABLE = False
    storage = None


class GCPStorageLoader:
    def __init__(self, logger):
        self.__logger = logger
        
        # 🚀 GCP CLOUD STORAGE CONFIGURATION
        # In Cloud Run, service account is automatically authenticated
        # For local development, set GOOGLE_APPLICATION_CREDENTIALS
        
        # Bucket names (same as S3 structure)
        self.artifacts_bucket_name = "artifactsredi"  # Models bucket
        self.images_bucket_name = "pictures-not-public"  # Images bucket
        
        # Model configuration
        self.model_name = os.getenv("MODEL_NAME", "models/pose_hrnet-w48_384x288-deepfashion2_mAP_0.7017.pth")
        
        # Initialize GCP Storage client with fallback
        if GCP_AVAILABLE:
            try:
                self.storage_client = storage.Client()
                print(f"[GCP_STORAGE] Client initialized successfully")
                self.__logger.log(f"[GCP_STORAGE] Client initialized successfully")
                
                # Get bucket references
                self.artifacts_bucket = self.storage_client.bucket(self.artifacts_bucket_name)
                self.images_bucket = self.storage_client.bucket(self.images_bucket_name)
                
                print(f"[GCP_STORAGE] Buckets configured: {self.artifacts_bucket_name}, {self.images_bucket_name}")
                self.__logger.log(f"[GCP_STORAGE] Buckets configured: {self.artifacts_bucket_name}, {self.images_bucket_name}")
                
            except Exception as e:
                error_msg = f"[GCP_STORAGE] Failed to initialize client: {e}"
                print(error_msg)
                self.__logger.log(error_msg)
                print("[GCP_STORAGE] Falling back to mock mode")
                self.__logger.log("[GCP_STORAGE] Falling back to mock mode")
                self.storage_client = None
                self.artifacts_bucket = None
                self.images_bucket = None
        else:
            print("[GCP_STORAGE] Using mock mode - no actual storage operations")
            self.__logger.log("[GCP_STORAGE] Using mock mode - no actual storage operations")
            self.storage_client = None
            self.artifacts_bucket = None
            self.images_bucket = None

    def upload_s3_image(self, public_url="", image_path="", image_data=None, predicted_image=False):
        """
        Upload image to GCP Cloud Storage (keeping S3 method name for compatibility)
        
        Args:
            public_url: URL to download image from
            image_path: Local path to image file
            image_data: Raw image data (numpy array)
            predicted_image: Whether this is a processed/predicted image
            
        Returns:
            str: Public URL to uploaded image
        """
        try:
            # 🚨 FALLBACK: If no GCP client, return mock URL
            if self.storage_client is None or self.images_bucket is None:
                mock_url = f"https://storage.googleapis.com/{self.images_bucket_name}/mock_upload_{int(time.time())}.jpg"
                print(f"[GCP_STORAGE] MOCK: Would upload to {mock_url}")
                self.__logger.log(f"[GCP_STORAGE] MOCK: Would upload to {mock_url}")
                return mock_url
            
            timestamp = int(time.time() * 1000)
            
            if predicted_image:
                # Processed images go to predictions folder
                blob_name = f"Remix_data/predictions/image_{timestamp}.jpg"
            else:
                # Original images go to originals folder
                blob_name = f"Remix_data/originals/image_{timestamp}.jpg"
            
            blob = self.images_bucket.blob(blob_name)
            
            # Handle different input types
            if image_data is not None:
                # Upload from numpy array/cv2 image
                if isinstance(image_data, np.ndarray):
                    # Convert numpy array to JPEG bytes
                    success, buffer = cv2.imencode('.jpg', image_data)
                    if not success:
                        raise Exception("Failed to encode image data to JPEG")
                    image_bytes = buffer.tobytes()
                else:
                    image_bytes = image_data
                
                blob.upload_from_string(image_bytes, content_type='image/jpeg')
                
            elif image_path and os.path.exists(image_path):
                # Upload from local file
                blob.upload_from_filename(image_path, content_type='image/jpeg')
                
            elif public_url:
                # Download from URL and upload
                response = requests.get(public_url, timeout=30)
                response.raise_for_status()
                blob.upload_from_string(response.content, content_type='image/jpeg')
                
            else:
                raise ValueError("No valid image source provided")
            
            # Generate public URL
            public_url = f"https://storage.googleapis.com/{self.images_bucket_name}/{blob_name}"
            
            print(f"[GCP_STORAGE] ✅ Image uploaded: {blob_name}")
            self.__logger.log(f"[GCP_STORAGE] ✅ Image uploaded: {blob_name}")
            
            return public_url
            
        except Exception as e:
            error_msg = f"[GCP_STORAGE] ❌ Image upload failed: {e}"
            print(error_msg)
            self.__logger.log(error_msg)
            return None

    def load_hrnet_model(self):
        """
        Load HRNet model from GCP Cloud Storage artifacts bucket
        
        Returns:
            torch model state dict or None if failed
        """
        try:
            # 🚨 FALLBACK: If no GCP client, return None (will trigger local file fallback)
            if self.storage_client is None or self.artifacts_bucket is None:
                print(f"[GCP_STORAGE] MOCK: Would load model from gs://{self.artifacts_bucket_name}/{self.model_name}")
                self.__logger.log(f"[GCP_STORAGE] MOCK: Would load model from gs://{self.artifacts_bucket_name}/{self.model_name}")
                print("[GCP_STORAGE] Fallback mode - returning None to trigger local file loading")
                self.__logger.log("[GCP_STORAGE] Fallback mode - returning None to trigger local file loading")
                return None
            
            print(f"[GCP_STORAGE] Loading model from bucket: {self.artifacts_bucket_name}, path: {self.model_name}")
            self.__logger.log(f"[GCP_STORAGE] Loading model from bucket: {self.artifacts_bucket_name}, path: {self.model_name}")
            
            # Get model blob
            blob = self.artifacts_bucket.blob(self.model_name)
            
            # Check if blob exists
            if not blob.exists():
                error_msg = f"[GCP_STORAGE] ❌ Model not found: gs://{self.artifacts_bucket_name}/{self.model_name}"
                print(error_msg)
                self.__logger.log(error_msg)
                return None
            
            # Download model to memory buffer
            model_bytes = blob.download_as_bytes()
            buffer = io.BytesIO(model_bytes)
            
            # Load PyTorch model
            map_location = "cuda" if torch.cuda.is_available() else "cpu"
            model_state = torch.load(buffer, map_location=map_location)
            
            print(f"[GCP_STORAGE] ✅ Successfully loaded model from: gs://{self.artifacts_bucket_name}/{self.model_name}")
            self.__logger.log(f"[GCP_STORAGE] ✅ Successfully loaded model from: gs://{self.artifacts_bucket_name}/{self.model_name}")
            
            return model_state
            
        except Exception as e:
            error_msg = f"[GCP_STORAGE] ❌ Failed to load model: {e}"
            print(error_msg)
            self.__logger.log(error_msg)
            return None

    def get_image_from_link(self, public_url):
        """
        Download image from URL and return as numpy array
        Uses optimized TurboJPEG loader when possible
        
        Args:
            public_url: URL to download image from
            
        Returns:
            numpy.ndarray: Image as BGR numpy array (OpenCV format)
        """
        try:
            print(f"[GCP_STORAGE] Downloading image from: {public_url}")
            self.__logger.log(f"[GCP_STORAGE] Downloading image from: {public_url}")
            
            # Download image
            response = requests.get(public_url, timeout=30)
            response.raise_for_status()
            
            # Try TurboJPEG first for JPEG images
            if public_url.lower().endswith(('.jpg', '.jpeg')):
                try:
                    image_bgr = turbojpeg_loader.load_from_bytes(response.content)
                    if image_bgr is not None:
                        print(f"[GCP_STORAGE] ✅ Image loaded with TurboJPEG: {image_bgr.shape}")
                        self.__logger.log(f"[GCP_STORAGE] ✅ Image loaded with TurboJPEG: {image_bgr.shape}")
                        return image_bgr
                except Exception as turbo_error:
                    print(f"[GCP_STORAGE] TurboJPEG failed, falling back to OpenCV: {turbo_error}")
                    self.__logger.log(f"[GCP_STORAGE] TurboJPEG failed, falling back to OpenCV: {turbo_error}")
            
            # Fallback to OpenCV
            image_array = np.frombuffer(response.content, np.uint8)
            image_bgr = cv2.imdecode(image_array, cv2.IMREAD_COLOR)
            
            if image_bgr is None:
                raise Exception("Failed to decode image with OpenCV")
            
            print(f"[GCP_STORAGE] ✅ Image loaded with OpenCV: {image_bgr.shape}")
            self.__logger.log(f"[GCP_STORAGE] ✅ Image loaded with OpenCV: {image_bgr.shape}")
            
            return image_bgr
            
        except Exception as e:
            error_msg = f"[GCP_STORAGE] ❌ Failed to download image: {e}"
            print(error_msg)
            self.__logger.log(error_msg)
            return None

    def get_pil_image_from_url(self, public_url, return_bgr=False):
        """
        Download image from URL and return as PIL Image.
        Optionally return the OpenCV BGR numpy array as well.
        """
        try:
            self.__logger.log(f"[GCP_STORAGE] get_pil_image_from_url: {public_url}")
            response = requests.get(public_url, timeout=30)
            response.raise_for_status()
            img = Image.open(io.BytesIO(response.content)).convert("RGB")
            if not return_bgr:
                return img
            # Also produce BGR array if requested
            rgb = np.array(img)
            bgr = cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)
            return img, bgr
        except Exception as e:
            self.__logger.log(f"[GCP_STORAGE] ❌ get_pil_image_from_url failed: {e}")
            return None

    def upload_image_data(self, image_data, predicted=False):
        """
        Upload raw image data to GCP Cloud Storage
        
        Args:
            image_data: numpy array (BGR format)
            predicted: whether this is a processed image
            
        Returns:
            str: Public URL of uploaded image
        """
        return self.upload_s3_image(image_data=image_data, predicted_image=predicted)

    def download_blob_to_file(self, blob_name, destination_path):
        """
        Download a blob to local file
        
        Args:
            blob_name: Name of the blob in the bucket
            destination_path: Local path to save the file
        """
        try:
            blob = self.images_bucket.blob(blob_name)
            blob.download_to_filename(destination_path)
            
            print(f"[GCP_STORAGE] ✅ Downloaded {blob_name} to {destination_path}")
            self.__logger.log(f"[GCP_STORAGE] ✅ Downloaded {blob_name} to {destination_path}")
            return True
            
        except Exception as e:
            error_msg = f"[GCP_STORAGE] ❌ Download failed: {e}"
            print(error_msg)
            self.__logger.log(error_msg)
            return False

    def list_blobs(self, prefix="", bucket_type="images"):
        """
        List blobs in bucket with optional prefix
        
        Args:
            prefix: Blob name prefix filter
            bucket_type: "images" or "artifacts"
            
        Returns:
            list: List of blob names
        """
        try:
            if bucket_type == "artifacts":
                bucket = self.artifacts_bucket
            else:
                bucket = self.images_bucket
                
            blobs = bucket.list_blobs(prefix=prefix)
            blob_names = [blob.name for blob in blobs]
            
            print(f"[GCP_STORAGE] Found {len(blob_names)} blobs with prefix '{prefix}'")
            self.__logger.log(f"[GCP_STORAGE] Found {len(blob_names)} blobs with prefix '{prefix}'")
            
            return blob_names
            
        except Exception as e:
            error_msg = f"[GCP_STORAGE] ❌ List blobs failed: {e}"
            print(error_msg)
            self.__logger.log(error_msg)
            return [] 

    def save_image_to_gcp_random(self, img, prefix: str = ""):
        """
        Save a PIL Image or numpy array to GCP under predictions folder and return public URL.
        """
        try:
            # Normalize to numpy BGR for upload_s3_image
            if isinstance(img, Image.Image):
                rgb = np.array(img)
                img_bgr = cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)
            elif isinstance(img, np.ndarray):
                img_bgr = img
            else:
                raise ValueError("Unsupported image type for save_image_to_gcp_random")
            url = self.upload_s3_image(image_data=img_bgr, predicted_image=True)
            if url and prefix:
                # If prefix requested, rewrite path to include prefix marker (best-effort)
                return url.replace("/predictions/", f"/predictions/{prefix}")
            return url
        except Exception as e:
            self.__logger.log(f"[GCP_STORAGE] ❌ save_image_to_gcp_random failed: {e}")
            return None

    def save_text_to_gcp(self, text_data: str, object_path: str):
        """
        Save arbitrary text to GCP Storage under Remix_data/<object_path>.
        """
        try:
            if self.storage_client is None or self.images_bucket is None:
                # Fallback: write to local logs dir
                os.makedirs("logs", exist_ok=True)
                local_path = os.path.join("logs", os.path.basename(object_path))
                with open(local_path, "w", encoding="utf-8") as f:
                    f.write(text_data)
                self.__logger.log(f"[GCP_STORAGE] MOCK saved text locally: {local_path}")
                return local_path
            blob_name = f"Remix_data/{object_path}"
            blob = self.images_bucket.blob(blob_name)
            blob.upload_from_string(text_data, content_type='application/json; charset=utf-8')
            self.__logger.log(f"[GCP_STORAGE] ✅ Text saved to gs://{self.images_bucket_name}/{blob_name}")
            return f"gs://{self.images_bucket_name}/{blob_name}"
        except Exception as e:
            self.__logger.log(f"[GCP_STORAGE] ❌ save_text_to_gcp failed: {e}")
            return None

    def download_artifact_to_local(self, object_name: str, destination_path: str) -> bool:
        """
        Download an artifact from the artifacts bucket to a local file path.

        Args:
            object_name: Path of the object inside the artifacts bucket (e.g. "models/…/checkpoint.pt")
            destination_path: Local filesystem path to save to
        Returns:
            True on success, False otherwise
        """
        try:
            if self.storage_client is None or self.artifacts_bucket is None:
                self.__logger.log("[GCP_STORAGE] download_artifact_to_local: no client/bucket available")
                return False
            os.makedirs(os.path.dirname(destination_path) or ".", exist_ok=True)
            blob = self.artifacts_bucket.blob(object_name)
            if not blob.exists():
                self.__logger.log(f"[GCP_STORAGE] ❌ Artifact not found: gs://{self.artifacts_bucket_name}/{object_name}")
                return False
            blob.download_to_filename(destination_path)
            self.__logger.log(f"[GCP_STORAGE] ✅ Downloaded artifact to {destination_path}")
            return True
        except Exception as e:
            self.__logger.log(f"[GCP_STORAGE] ❌ download_artifact_to_local failed: {e}")
            return False 