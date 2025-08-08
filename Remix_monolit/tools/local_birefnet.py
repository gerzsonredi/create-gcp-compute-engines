import os
import cv2
import numpy as np
import torch
from typing import Optional
from PIL import Image
from torchvision.transforms import functional as F
from transformers import AutoModelForImageSegmentation


class LocalBiRefNetSegmenter:
    def __init__(
        self,
        *,
        model_name: str = "zhengpeng7/BiRefNet",
        checkpoint_path: Optional[str] = None,
        precision: str = "fp16",
        mask_threshold: float = 0.5,
        thickness_threshold: int = 200,
    ) -> None:
        os.environ["TRANSFORMERS_TRUST_REMOTE_CODE"] = "true"
        self.model_name = model_name
        self.mask_threshold = float(mask_threshold)
        self.thickness_threshold = int(thickness_threshold)
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.dtype = {
            "fp32": torch.float32,
            "fp16": torch.float16,
            "bf16": torch.bfloat16,
        }.get(precision, torch.float16)

        self.model = AutoModelForImageSegmentation.from_pretrained(
            model_name, trust_remote_code=True, config={"model_type": "custom_segmentation_model"}
        ).to(self.device)
        self.model.eval()
        if self.device.type == "cuda" and self.dtype == torch.float16:
            self.model.half()

        if checkpoint_path and os.path.exists(checkpoint_path):
            state = torch.load(checkpoint_path, map_location=self.device)
            if isinstance(state, dict):
                for key in ("model_state_dict", "state_dict"):
                    if key in state:
                        state = state[key]
                        break
            self.model.load_state_dict(state, strict=False)

    def _preprocess(self, img_bgr: np.ndarray) -> torch.Tensor:
        img_rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)
        pil = Image.fromarray(img_rgb).convert("RGB").resize((512, 512))
        t = F.to_tensor(pil).unsqueeze(0).to(self.device)
        if self.dtype == torch.float16 and self.device.type == "cuda":
            t = t.half()
        return t

    def _run(self, x: torch.Tensor) -> torch.Tensor:
        with torch.no_grad():
            outputs = self.model(x)
            def find_map(obj):
                if hasattr(obj, "shape") and len(obj.shape) >= 2 and obj.shape[-2:] == (512, 512):
                    return obj
                if isinstance(obj, (list, tuple)):
                    for it in obj:
                        r = find_map(it)
                        if r is not None:
                            return r
                return None
            m = find_map(outputs)
            if m is None and hasattr(outputs, "shape"):
                m = outputs
            if m is None:
                return torch.zeros((512, 512), device=self.device)
            if m.ndim > 2:
                while m.ndim > 2:
                    m = m.squeeze(0)
            return torch.sigmoid(m)

    def _mask_to_binary(self, mask: torch.Tensor, shape_hw: tuple) -> np.ndarray:
        if mask.dtype == torch.float16:
            mask_np = mask.detach().cpu().float().numpy()
        else:
            mask_np = mask.detach().cpu().numpy()
        while mask_np.ndim > 2:
            mask_np = mask_np.squeeze()
        h, w = shape_hw
        if mask_np.shape != (h, w):
            mask_np = cv2.resize(mask_np, (w, h), interpolation=cv2.INTER_LINEAR)
        mask_np = np.clip(mask_np, 0, 1)
        return mask_np > float(self.mask_threshold)

    def _apply_mask(self, img: np.ndarray, mask: np.ndarray) -> np.ndarray:
        out = img.copy()
        if out.ndim == 3:
            out[mask] = [255, 255, 255]
        else:
            out[mask] = 255
        return out

    def _remove_thin(self, img: np.ndarray) -> np.ndarray:
        cleaned = img.copy()
        if img.ndim == 3:
            non_white = ~np.all(img == [255, 255, 255], axis=2)
        else:
            non_white = img != 255
        k = max(1, self.thickness_threshold // 2)
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (k, k))
        opened = cv2.morphologyEx(non_white.astype(np.uint8), cv2.MORPH_OPEN, kernel)
        removed = non_white & ~opened.astype(bool)
        if cleaned.ndim == 3:
            cleaned[removed] = [255, 255, 255]
        else:
            cleaned[removed] = 255
        return cleaned

    def process_image_array(self, img_bgr: np.ndarray) -> np.ndarray:
        x = self._preprocess(img_bgr)
        mask = self._run(x)
        binary = self._mask_to_binary(mask, img_bgr.shape[:2])
        masked = self._apply_mask(img_bgr, binary)
        return self._remove_thin(masked)

    def process_image_url(self, url: str) -> Optional[np.ndarray]:
        try:
            import requests
            r = requests.get(url, timeout=20)
            r.raise_for_status()
            arr = np.frombuffer(r.content, np.uint8)
            img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
            if img is None:
                return None
            return self.process_image_array(img)
        except Exception:
            return None 