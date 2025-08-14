from typing import Any, Mapping, Union
import torch, os, json, random
import torch.nn as nn
from transformers import ViTModel, AutoFeatureExtractor
from transformers.modeling_outputs import ImageClassifierOutput
from safetensors.torch import load_file
from PIL import Image
import torch.nn.functional as F
from io import BytesIO
from urllib.parse import urlparse
from PIL import Image
import requests
from requests.exceptions import HTTPError, RequestException

class SubCategoryViT(nn.Module):
    def __init__(self, backbone: str, n_sub: int):
        super().__init__()
        self.vit = ViTModel.from_pretrained(backbone)
        h = self.vit.config.hidden_size
        self.head_sub    = nn.Linear(h, n_sub)
        self.ce = nn.CrossEntropyLoss()

    def forward(
        self,
        pixel_values: torch.Tensor,
        sub_labels: Union[torch.Tensor, None] = None,
    ) -> ImageClassifierOutput:
        pooled = self.vit(pixel_values).pooler_output
        logit_sub    = self.head_sub(pooled)

        loss = None
        if sub_labels is not None:
            loss = self.ce(logit_sub, sub_labels)

        return ImageClassifierOutput(
            loss   = loss,
            logits = logit_sub,
        )
    
class SubcategoryDetector():
    def __init__(self, backbone:str, maps:int, state_dict:Mapping[str, Any], logger):
        self.__model = SubCategoryViT(
            backbone=backbone,
            n_sub=len(maps),
        )

        self.__model.load_state_dict(state_dict)
        self.__model.eval()

        self.__feature_extractor = AutoFeatureExtractor.from_pretrained(backbone)

        # Inverse sub-category map
        self.__inv_sub_map = {idx: label for label, idx in maps.items()}

        # Renaming rules
        self.__rename_map = {
            'clothing': 'Sportswear',
            'tops':     'Blouses',
            'leather': 'Leather Jackets'
        }

        # categories to zero-out entirely
        self.__zero_conf_categories = {'sweatshirts', 'cardigans', 'boleros', 'unbranded'}
        self.__logger = logger

    def __normalize_and_select(self, raw_preds):
        """
        raw_preds: list of (label, confidence) in original form, e.g. [('tops',0.9),('sweaters',0.05),('...')]
        returns: list of (renamed_label, adjusted_confidence) after applying all rules
        """
        # 1) rename & initial zeroing
        preds = []
        for label, conf in raw_preds:
            key = label.lower()
            # rename
            if key in self.__rename_map:
                new_label = self.__rename_map[key]
            else:
                new_label = label.capitalize()
            # if in zero‐out list, set conf to 0
            if key in self.__zero_conf_categories:
                conf = 0.0
            preds.append((new_label, conf))

        # unpack top predictions
        top = preds[0]
        rest = preds[1:]
        label1, conf1 = top

        # RULE A: if first is one of the zero‐out cats, return all with 0
        if label1.lower() in self.__zero_conf_categories:
            return [(lbl, 0.0) for lbl, _ in preds]

        # RULE B: Blouses (<0.99) + Sweaters second → return top2
        if label1 == 'Blouses' and conf1 < 0.99:
            if len(preds) > 1 and preds[1][0] == 'Sweaters':
                return preds[:2]

        # RULE C: Jumpsuits (<1.0) → return top2
        if label1 == 'Jumpsuits' and conf1 < 1.0:
            if len(preds) > 1:
                return preds[:2]

        if label1 == 'Shirts':
            return ('Shirts', preds[0][1]), ('T-Shirts', preds[0][1])

        # RULE D: if first conf <0.85 → return top3
        if conf1 < 0.85:
            return preds[:3]

        # RULE E: if first conf ≥0.85 and not Blouses/Sweaters/Jumpsuits → only top1
        if conf1 >= 0.85 and label1 not in {'Blouses', 'Sweaters', 'Jumpsuits'}:
            return [top]

        if label1 == 'Skirts':
            if conf1 < 0.95:
                return ('Skirts', preds[0][1]), ('Shorts', 1-preds[0][1])

        if label1 == 'Shorts':
            if conf1 < 0.95:
                return ('Shorts', preds[0][1]), ('Skirts', 1-preds[0][1])

        # fallback: return top2
        return preds[:2] 
    
    def predict_topx(self, image: Image.Image, k: int = 3):
        # Load & preprocess
        inputs = self.__feature_extractor(images=image, return_tensors="pt")
        device = next(self.__model.parameters()).device
        inputs = {k: v.to(device) for k, v in inputs.items()}
        self.__model.to(device)

        # Forward + softmax
        with torch.no_grad():
            logits = self.__model(pixel_values=inputs["pixel_values"]).logits  # [1, n_sub]
            probs  = F.softmax(logits, dim=-1)                         # [1, n_sub]

        # Top-k
        top_probs, top_idxs = probs.topk(k, dim=-1)
        top_probs = top_probs[0].tolist()
        top_idxs  = top_idxs[0].tolist()

        # Decode then normalize & select per rules
        raw_preds = [(self.__inv_sub_map[idx], prob) for idx, prob in zip(top_idxs, top_probs)]
        return self.__normalize_and_select(raw_preds)
    

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