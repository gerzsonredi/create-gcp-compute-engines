import torch
from PIL import Image
from transformers import AutoImageProcessor
from pathlib import Path
from transformers import ViTModel
from io import BytesIO
from urllib.parse import urlparse
import requests
from requests.exceptions import HTTPError, RequestException
from tools.OpenAIAssistant import OpenAIAssistant
from tools.S3Loader import S3Loader
import tools.constants as c

class BinaryViTClassifier(torch.nn.Module):
    def __init__(self, backbone: str):
        super().__init__()
        self.vit = ViTModel.from_pretrained(backbone)
        h = self.vit.config.hidden_size
        self.head = torch.nn.Linear(h, 2)
        self.ce = torch.nn.CrossEntropyLoss()
    def forward(self, pixel_values: torch.Tensor, labels: torch.Tensor = None):
        pooled = self.vit(pixel_values).pooler_output
        logits = self.head(pooled)
        loss = None
        if labels is not None:
            loss = self.ce(logits, labels)
        return logits if loss is None else (loss, logits)
    

class LabelPredictor:
    def __init__(self, logger, state, model_name):
        self.__logger = logger
        
        self.__device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        print(f"Inference using device: {self.__device}")
        self.__logger.log(f"Inference using device: {self.__device}")

        self.__model = BinaryViTClassifier(model_name)
        self.__model.load_state_dict(state)
        self.__model.to(self.__device)
        self.__model.eval()

        self.__processor = AutoImageProcessor.from_pretrained(model_name)

    def load_image_from_url(self, url: str, timeout: int = 10) -> Image.Image:
        """Download an image and return it as a RGB PIL.Image."""
        try:
            # 1) Syntax check
            parsed = urlparse(url)
            if parsed.scheme not in {"http", "https"} or not parsed.netloc:
                raise ValueError(f"Invalid URL: {url}")

            # 2) Fetch
            resp = requests.get(url, timeout=timeout, headers={"User-Agent": "Mozilla/5.0"})
            resp.raise_for_status()                        # HTTP errors ⇒ exception

            # 3) Rudimentary content check
            if not resp.headers.get("Content-Type", "").startswith("image"):
                raise ValueError(f"URL does not point to an image "
                                f"(Content-Type = {resp.headers.get('Content-Type')!r})")

            # 4) Assemble PIL.Image
            return Image.open(BytesIO(resp.content)).convert("RGB")
        except (ValueError, HTTPError, RequestException) as e:
            print(f"Skipping {url!r}: {e}")
            self.__logger.log(f"Skipping {url!r}: {e}")
            return None
        

    def inference(self, img_url:str):
        try:
            img = self.load_image_from_url(img_url)
            inputs = self.__processor(img, return_tensors="pt")["pixel_values"].to(self.__device)

            with torch.no_grad():
                logits = self.__model(inputs)
                if isinstance(logits, tuple):
                    logits = logits[1]
                probs = torch.softmax(logits, dim=-1)
                pred = probs.argmax(dim=-1).item()
                confidence = probs.max().item()
            
            result = {
                "image_path": img_url,
                "predicted_label": pred,
                "confidence": confidence,
            }
            return result

        except Exception as e:
            print(f"Error during inference: {e}")
            self.__logger.log(f"Error during inference: {e}")
            return None

class ConditionPredictor:
    def __init__(self, openai_assistant:OpenAIAssistant, logger, s3_loader:S3Loader):
        self.__logger = logger
        self.__openai_assistant = openai_assistant

        # load state dict from s3
        try:
            state, model_name = s3_loader.load_label_predictor()
            if not state is None and not model_name is None:
                self.__label_predictor = LabelPredictor(logger, state, model_name)
        except Exception as e:
            print(f"Error loading label predictor: {e}")
            self.__logger.log(f"Error loading label predictor: {e}")
            raise e

    def get_condition(self, image_urls):
        try:
            last_image = sorted(image_urls)[-1]

            # find out if the product is new with tags
            try:
                pred_res = self.__label_predictor.inference(last_image)
                if not pred_res:
                    pred       = 0
                    confidence = 0
                else:
                    pred       = pred_res["predicted_label"]
                    confidence = pred_res["confidence"]
            except Exception as e:
                print(f"Error getting label prediction: {e}")
                self.__logger.log(f"Error getting label prediction: {e}")
                pred = 0
                confidence = 0

            confidence_benchmark = 0.995
            condition_result     = {}
            if pred == 1 and confidence >= confidence_benchmark:
                condition_result["condition_rating"] = "New product with tags."
                cond_desc = ""
            elif pred == 1 and confidence < confidence_benchmark:
                condition_result["condition_rating"] = "This product has no signs of use."
                cond_desc = ""
            else:
                try:
                    # Call openai helper
                    openai_res = self.__openai_assistant.extract_data(
                        image_urls=image_urls,
                        json_schema=c.json_schema,
                        prompt_message=c.prompt_message
                    )
                    cond_rating = int(openai_res.get("condition_rating", 0))
                    cond_desc = openai_res.get("condition_description", "")
                    if cond_rating in (8,9,10):
                        condition_result["condition_rating"] = "This product has no signs of use."
                        cond_desc = ""
                    else:
                        condition_result["condition_rating"] = "This product has barely noticeable signs of use."
                except Exception as e:
                    print(f"Error getting OpenAI condition assessment: {e}")
                    self.__logger.log(f"Error getting OpenAI condition assessment: {e}")
                    condition_result["condition_rating"] = "This product has barely noticeable signs of use."
                    cond_desc = ""

            condition_result["condition_description"] = cond_desc
            return condition_result

        except Exception as e:
            print(f"Error in get_condition: {e}")
            self.__logger.log(f"Error in get_condition: {e}")
            return {
                "condition_rating": "This product has barely noticeable signs of use.",
                "condition_description": ""
            }