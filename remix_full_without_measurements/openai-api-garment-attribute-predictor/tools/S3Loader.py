import boto3, json, io, requests, time, os, torch, cv2
from PIL import Image
import numpy as np
from urllib.parse import urlparse


class S3Loader:
    def __init__(self, logger):
        CONFIG_FILE = "configs/config_general_aws.json"
        with open(CONFIG_FILE, "r") as jf:
            self.__config = json.load(jf)
        self.__logger = logger

    def load_label_predictor(self):
        AWS_ACCESS_KEY_ID     = self.__config.get("ACCES_KEY_ARTIFACTS", "")
        AWS_SECRET_ACCESS_KEY = self.__config.get("SECRET_KEY_ARTIFACTS", "")
        BUCKET_NAME           = self.__config.get("BUCKET_NAME_ARTIFACTS", "")
        REGION                = self.__config.get("REGION", "")
        MODEL_NAME_CONDITION  = self.__config.get("MODEL_NAME_CONDITION", "")
        MODEL_PATH_CONDITION  = self.__config.get("MODEL_PATH_CONDITION", "")

        map_location          = "cuda" if torch.cuda.is_available() else "cpu"

        session = boto3.Session(
            aws_access_key_id=AWS_ACCESS_KEY_ID,
            aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
            region_name=REGION
        )

        s3_client = session.client('s3')

        try:
            response   = s3_client.get_object(Bucket=BUCKET_NAME, Key=MODEL_PATH_CONDITION)   # s3:GetObject required
            buffer     = io.BytesIO(response["Body"].read())            # keep it in RAM
            state_dict = torch.load(buffer, map_location=map_location)
            model_name = MODEL_NAME_CONDITION
            return state_dict, model_name
            
            # return SubcategoryDetector(
            #     backbone=MODEL_NAME_SUBCATEGORY,
            #     maps=maps["sub"],
            #     state_dict=state_dict,
            #     logger=self.__logger
            # )

        except Exception as e:
            print("ERROR while loading category model from s3")
            print(e.with_traceback())
            self.__logger.log("ERROR while loading category model from s3")
            self.__logger.log(str(e))
            return None, None

    def upload_s3_image(self, public_url="", image_path="", image_data="", predicted_image=False):
        """
        Takes a public url as argument, and uploads image to AWS S3 bucket.
        Returns public s3 url
        """
        AWS_ACCESS_KEY_ID       = self.__config.get("ACCES_KEY_ARTIFACTS", "")
        AWS_SECRET_ACCESS_KEY   = self.__config.get("SECRET_KEY_ARTIFACTS", "")
        BUCKET_NAME             = self.__config.get("BUCKET_NAME", "")
        REGION                  = self.__config.get("REGION", "")
        
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
                img = Image.open(io.BytesIO(r.content)).convert("RGB")
                return np.array(img)
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
            
            AWS_ACCESS_KEY_ID = self.__config.get("ACCES_KEY_ARTIFACTS", "")
            AWS_SECRET_ACCESS_KEY = self.__config.get("SECRET_KEY_ARTIFACTS", "")
            REGION = self.__config.get("REGION", "")
            
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
            img = Image.open(io.BytesIO(image_data)).convert("RGB")
            return np.array(img)
            
        except Exception as e:
            print(f"ERROR while loading image from S3: {e}")
            self.__logger.log(f"ERROR while loading image from S3: {e}")
            return None