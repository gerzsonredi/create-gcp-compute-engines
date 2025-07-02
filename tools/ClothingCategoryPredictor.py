from transformers import AutoProcessor, AutoModel
from PIL import Image
import torch, os, torch.nn.functional as F
from tools.constants import CATEGORY_MODEL_NAME, CATEGORY_LABELS


class ClothingCategoryPredictor:
    def __init__(self, logger):
        self.__logger = logger
        
        self.__DEVICE = 'cuda' if torch.cuda.is_available() else 'cpu'
        self.__proc   = AutoProcessor.from_pretrained(CATEGORY_MODEL_NAME)
        self.__model  = AutoModel.from_pretrained(CATEGORY_MODEL_NAME).eval().to(self.__DEVICE)
        self.__logger.log(f"✔️ {CATEGORY_MODEL_NAME} ready on {self.__DEVICE}")

        # --- encode all label strings ---
        self.__text_feats = self.__proc(text=CATEGORY_LABELS, padding=True, return_tensors="pt").to(self.__model.device)
        with torch.no_grad():
            self.__text_feats = F.normalize(self.__model.get_text_features(**self.__text_feats), dim=-1)

    def pred(self, img, return_idx=False):
        """
        Receives an image in PIL Image format and returns the name of the category name and probability.
        """
        image_inputs = self.__proc(images=img, return_tensors="pt").to(self.__model.device)
        with torch.no_grad():
            image_feat = self.__model.get_image_features(**image_inputs)

        # normalise & cosine-similarity
        image_feat = F.normalize(image_feat, dim=-1)

        sims  = (image_feat @ self.__text_feats.T).squeeze(0)
        pred  = CATEGORY_LABELS[int(sims.argmax())]
        print(f"Predicted category: {pred}, with certainty: {(sims.max().item()):.1%}")
        self.__logger.log(f"Predicted category: {pred}, with certainty: {(sims.max().item()):.1%}")

        if return_idx:
            return int(sims.argmax()), sims.max().item()

        return pred, sims.max().item()
