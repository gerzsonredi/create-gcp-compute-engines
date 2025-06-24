import boto3, json, io, requests, time, os, torch
from PIL import Image

class S3Loader():
    def __init__(self):
        CONFIG_FILE = "configs/config_general_aws.json"
        with open(CONFIG_FILE, "r") as jf:
            self.__config = json.load(jf)
    

    def upload_s3_image(self, public_url="", image_path="", predicted_image=False):
        """
        Takes a public url as argument, and uploads image to AWS S3 bucket.
        Returns public s3 url
        """
        AWS_ACCESS_KEY_ID       = self.__config.get("ACCESS_KEY", "")
        AWS_SECRET_ACCESS_KEY   = self.__config.get("SECRET_KEY", "")
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
                image_data = io.BytesIO(response.content)
                
                # Generate unique filename using timestamp
                filename = public_url.split("/")[-1]

                if not filename:
                    filename = f"image_{time.time()}.jpg"
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
                    filename,
                    ExtraArgs={'ACL': 'public-read'}
                )
                
                # Generate and return public S3 URL
                s3_url = f"https://{BUCKET_NAME}.s3.{REGION}.amazonaws.com/{filename}"
                print("SUCCESS: uploaded image to s3!")
                print(s3_url)
                return s3_url
            
            except Exception as e:
                print("ERROR while uploading image to s3")
                print(e)
                return None
            
        elif image_path:
            try:
                # Open and read the local image file
                with open(image_path, 'rb') as f:
                    image_data = io.BytesIO(f.read())
                
                # Generate filename from the original path
                filename = os.path.basename(image_path)
                
                if not filename:
                    filename = f"image_{time.time()}.jpg"
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
                    filename,
                    ExtraArgs={'ACL': 'public-read'}
                )
                
                # Generate and return public S3 URL
                s3_url = f"https://{BUCKET_NAME}.s3.{REGION}.amazonaws.com/{filename}"
                print("SUCCESS: uploaded image to s3!")
                print(s3_url)
                return s3_url
                
            except Exception as e:
                print("ERROR while uploading image to s3")
                print(e)
                return None
    
    def load_hrnet_model(self):
        """
        Helper function to load HRNet model from S3.
        """
        AWS_ACCESS_KEY_ID       = self.__config.get("ACCES_KEY_ARTIFACTS", "")
        AWS_SECRET_ACCESS_KEY   = self.__config.get("SECRET_KEY_ARTIFACTS", "")
        BUCKET_NAME             = self.__config.get("BUCKET_NAME_ARTIFACTS", "")
        REGION                  = self.__config.get("REGION", "")
        MODEL_KEY               = self.__config.get("MODEL_NAME", "")
        map_location            = "cuda" if torch.cuda.is_available() else "cpu"

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
            return None
        
    def get_image_from_link(self, public_url):
        """
        Helper function that loads image from public_url
        Returns PIL Image object
        """
        try:
            r = requests.get(public_url, timeout=10)
            r.raise_for_status()
            return Image.open(io.BytesIO(r.content)).convert("RGB") 
        except Exception as e:
            print("ERROR while loading image ")
            print(e)
            return None