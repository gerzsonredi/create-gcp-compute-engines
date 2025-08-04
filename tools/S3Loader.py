import boto3, json, io, requests, time, os, torch, cv2
from PIL import Image
import numpy as np
from urllib.parse import urlparse


class S3Loader:
    def __init__(self, logger):
        self.__logger = logger
        
        # 🚀 CLOUD RUN FIX: Try environment variables first, fallback to config file
        self.aws_access_key_id = os.getenv("AWS_ACCESS_KEY_ID")
        self.aws_secret_access_key = os.getenv("AWS_SECRET_ACCESS_KEY")
        self.bucket_name = os.getenv("AWS_S3_BUCKET_NAME")
        self.aws_s3_region = os.getenv("AWS_S3_REGION")
        self.model_name = os.getenv("MODEL_NAME", "models/pose_hrnet-w48_384x288-deepfashion2_mAP_0.7017.pth")
        
        # Fallback to config file for local development
        if not all([self.aws_access_key_id, self.aws_secret_access_key, self.bucket_name, self.aws_s3_region]):
            CONFIG_FILE = "configs/config_general_aws.json"
            try:
                with open(CONFIG_FILE, "r") as jf:
                    config = json.load(jf)
                self.aws_access_key_id = self.aws_access_key_id or config.get("AWS_ACCESS_KEY_ID")
                self.aws_secret_access_key = self.aws_secret_access_key or config.get("AWS_SECRET_ACCESS_KEY")
                self.bucket_name = self.bucket_name or config.get("AWS_S3_BUCKET_NAME")
                self.aws_s3_region = self.aws_s3_region or config.get("AWS_S3_REGION")
                self.model_name = self.model_name or config.get("MODEL_NAME", "models/pose_hrnet-w48_384x288-deepfashion2_mAP_0.7017.pth")
                print(f"[S3LOADER] Loaded AWS config from file: {CONFIG_FILE}")
                self.__logger.log(f"[S3LOADER] Loaded AWS config from file: {CONFIG_FILE}")
            except FileNotFoundError:
                print(f"[S3LOADER] Config file {CONFIG_FILE} not found, using environment variables only")
                self.__logger.log(f"[S3LOADER] Config file {CONFIG_FILE} not found, using environment variables only")
            except Exception as e:
                print(f"[S3LOADER] Error reading config file: {e}")
                self.__logger.log(f"[S3LOADER] Error reading config file: {e}")
        else:
            print(f"[S3LOADER] Loaded AWS config from environment variables")
            self.__logger.log(f"[S3LOADER] Loaded AWS config from environment variables")
        
        # Validate configuration
        if not all([self.aws_access_key_id, self.aws_secret_access_key, self.bucket_name, self.aws_s3_region]):
            print(f"[S3LOADER] Warning: Missing AWS credentials, S3 operations may fail")
            self.__logger.log(f"[S3LOADER] Warning: Missing AWS credentials, S3 operations may fail")
        else:
            print(f"[S3LOADER] AWS config ready - Bucket: {self.bucket_name}, Region: {self.aws_s3_region}")
            self.__logger.log(f"[S3LOADER] AWS config ready - Bucket: {self.bucket_name}, Region: {self.aws_s3_region}")

    def upload_s3_image(self, public_url="", image_path="", image_data="", predicted_image=False):
        """
        Takes a public url as argument, and uploads image to AWS S3 bucket.
        Returns public s3 url
        """
        # Use instance variables instead of config dict
        AWS_ACCESS_KEY_ID = self.aws_access_key_id
        AWS_SECRET_ACCESS_KEY = self.aws_secret_access_key
        BUCKET_NAME = self.bucket_name
        REGION = self.aws_s3_region
        
        session = boto3.Session(
            aws_access_key_id=AWS_ACCESS_KEY_ID,
            aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
            region_name=REGION
        )

        s3_client = session.client('s3')
        
        if public_url:
            try:
                # Download image from public URL
                response = requests.get(public_url)
                response.raise_for_status()
                image_data = io.BytesIO(response.content)
                print("Read image data")
                self.__logger.log("Read image data")
                # Generate unique filename using timestamp
                filename = public_url.split("/")[-1]

                if not filename:
                    filename = f"image_{int(time.time())}.jpg"
                if not filename.lower().endswith(('.jpg', '.png', '.webp', 'jpeg')):
                    filename += ".jpg"
                if predicted_image:
                    filename = f"Remix_data/predictions/{filename}"
                else:
                    filename = f"Remix_data/{filename}"
                print(f"Using filename: {filename}")
                self.__logger.log(f"Using filename: {filename}")

                # Upload to S3
                s3_client.upload_fileobj(
                    image_data,
                    BUCKET_NAME,
                    filename
                )
                
                # Generate and return public S3 URL
                s3_url = f"https://{BUCKET_NAME}.s3.{REGION}.amazonaws.com/{filename}"

                print("SUCCESS: uploaded image to s3!")
                print(s3_url)
                self.__logger.log("SUCCESS: uploaded image to s3!")
                self.__logger.log(s3_url)
                return s3_url
            
            except Exception as e:
                print("ERROR while uploading image to s3")
                print(e)
                self.__logger.log("ERROR while uploading image to s3")
                self.__logger.log(str(e))
                return None
            
        elif image_path:
            try:
                # Open and read the local image file
                with open(image_path, 'rb') as f:
                    image_data = io.BytesIO(f.read())
                
                # Generate filename from the original path
                filename = os.path.basename(image_path)
                
                if not filename:
                    filename = f"image_{int(time.time())}.jpg"
                if not filename.lower().endswith(('.jpg', '.png', '.webp', 'jpeg')):
                    filename += ".jpg"

                if predicted_image:
                    filename = f"Remix_data/predictions/{filename}"
                else:
                    filename = f"Remix_data/{filename}"
                
                # Upload to S3
                s3_client.upload_fileobj(
                    image_data,
                    BUCKET_NAME, 
                    filename
                )
                
                # Generate and return public S3 URL
                s3_url = f"https://{BUCKET_NAME}.s3.{REGION}.amazonaws.com/{filename}"
                print("SUCCESS: uploaded image to s3!")
                print(s3_url)
                self.__logger.log("SUCCESS: uploaded image to s3!")
                self.__logger.log(s3_url)
                return s3_url
            
            except Exception as e:
                print("ERROR while uploading image to s3")
                print(e)
                self.__logger.log("ERROR while uploading image to s3")
                self.__logger.log(str(e))
                return None
            
        elif not image_data is None:
            try:
                filename = ""
                if not filename:
                    filename = f"image_{int(time.time())}.jpg"
                if not filename.lower().endswith(('.jpg', '.png', '.webp', 'jpeg')):
                    filename += ".jpg"

                if predicted_image:
                    filename = f"Remix_data/predictions/{filename}"
                else:
                    filename = f"Remix_data/{filename}"
                
                # Convert numpy array to bytes
                success, img_encoded = cv2.imencode('.jpg', image_data)
                if not success:
                    raise ValueError("Failed to encode image")
                img_bytes = io.BytesIO(img_encoded.tobytes())
                
                # Upload to S3
                s3_client.upload_fileobj(
                    img_bytes,
                    BUCKET_NAME,
                    filename
                )
                
                # Generate and return public S3 URL
                s3_url = f"https://{BUCKET_NAME}.s3.{REGION}.amazonaws.com/{filename}"
                print("SUCCESS: uploaded image to s3!")
                print(s3_url)
                self.__logger.log("SUCCESS: uploaded image to s3!")
                self.__logger.log(s3_url)
                return s3_url
            
            except Exception as e:
                print("ERROR while uploading image to s3")
                print(e)
                self.__logger.log("ERROR while uploading image to s3")
                self.__logger.log(str(e))
                return None
    
    def load_hrnet_model(self):
        """
        Helper function to load HRNet model from S3.
        """
        # Use instance variables instead of config dict
        AWS_ACCESS_KEY_ID = self.aws_access_key_id
        AWS_SECRET_ACCESS_KEY = self.aws_secret_access_key
        BUCKET_NAME = self.bucket_name
        REGION = self.aws_s3_region
        MODEL_KEY = self.model_name
        map_location = "cuda" if torch.cuda.is_available() else "cpu"

        session = boto3.Session(
            aws_access_key_id=AWS_ACCESS_KEY_ID,
            aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
            region_name=REGION
        )

        s3_client = session.client('s3')

        try:
            response = s3_client.get_object(Bucket=BUCKET_NAME, Key=MODEL_KEY)   # s3:GetObject required
            buffer   = io.BytesIO(response["Body"].read())            # keep it in RAM
            return torch.load(buffer, map_location=map_location)

        except Exception as e:
            print("ERROR while loading model from s3")
            print(e)
            self.__logger.log("ERROR while loading model from s3")
            self.__logger.log(str(e))
            return None
        
    def get_image_from_link(self, public_url):
        """
        Helper function that loads image from public_url or private S3 URL
        Returns numpy array
        """
        try:
            # Check if it's an S3 URL that might require credentials
            if 's3' in public_url and 'amazonaws.com' in public_url:
                return self._get_image_from_s3_url(public_url)
            else:
                r = requests.get(public_url, timeout=10)
                r.raise_for_status()
                img = Image.open(io.BytesIO(r.content)) #.convert("RGB")
                img = np.array(img)
                img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
                return img
        except Exception as e:
            print("ERROR while loading image ")
            print(e)
            self.__logger.log("ERROR while loading image")
            self.__logger.log(str(e))
            return None
        
    def _get_image_from_s3_url(self, s3_url):
        """
        Helper function to get image from S3 URL using AWS credentials
        """
        try:
            # Parse the S3 URL to extract bucket and key
            # Format: https://bucket-name.s3.region.amazonaws.com/key
            # or: https://s3.region.amazonaws.com/bucket-name/key
            
            parsed_url = urlparse(s3_url)
            
            if parsed_url.hostname.startswith('s3.') or parsed_url.hostname.endswith('.amazonaws.com'):
                # Extract bucket and key from URL
                if parsed_url.hostname.endswith('.s3.amazonaws.com') or '.s3.' in parsed_url.hostname:
                    # Format: bucket-name.s3.region.amazonaws.com
                    bucket_name = parsed_url.hostname.split('.s3.')[0]
                    key = parsed_url.path.lstrip('/')
                else:
                    # Format: s3.region.amazonaws.com/bucket-name/key
                    path_parts = parsed_url.path.lstrip('/').split('/', 1)
                    bucket_name = path_parts[0]
                    key = path_parts[1] if len(path_parts) > 1 else ''
            else:
                raise ValueError(f"Unrecognized S3 URL format: {s3_url}")
            
            # Use instance variables instead of config dict
            AWS_ACCESS_KEY_ID = self.aws_access_key_id
            AWS_SECRET_ACCESS_KEY = self.aws_secret_access_key
            REGION = self.aws_s3_region
            
            session = boto3.Session(
                aws_access_key_id=AWS_ACCESS_KEY_ID,
                aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
                region_name=REGION
            )
            
            s3_client = session.client('s3')
            
            # Get the object from S3
            response = s3_client.get_object(Bucket=bucket_name, Key=key)
            image_data = response['Body'].read()
            
            # Convert to PIL Image and then numpy array
            img = Image.open(io.BytesIO(image_data)) #.convert("RGB")
            img = np.array(img)
            img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
            return img
            
        except Exception as e:
            print(f"ERROR while loading image from S3: {e}")
            self.__logger.log(f"ERROR while loading image from S3: {e}")
            return None