import os
import sys
import cv2
import numpy as np
import torch
import torch.nn.functional as F
from typing import Optional
from PIL import Image
from torchvision import transforms
from io import BytesIO


class LocalBiSeNetSegmenter:
    def __init__(
        self,
        *,
        checkpoint_path: Optional[str] = None,
        image_size: int = 512,
        precision: str = "fp32",
    ) -> None:
        self.image_size = int(image_size)
        self.precision = precision
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        if self.device.type == "cpu":
            cpu_count = os.cpu_count() or 2
            torch.set_num_threads(cpu_count)
            os.environ['OMP_NUM_THREADS'] = str(cpu_count)
            os.environ['MKL_NUM_THREADS'] = str(cpu_count)
        self._setup_bisenet_repo()
        from lib.models.bisenetv1 import BiSeNetV1 as _BiSeNetV1
        self.model = _BiSeNetV1(n_classes=2).to(self.device)
        if checkpoint_path and os.path.exists(checkpoint_path):
            state = torch.load(checkpoint_path, map_location=self.device)
            if isinstance(state, dict) and 'model_state_dict' in state:
                state = state['model_state_dict']
            self.model.load_state_dict(state, strict=False)
        self.model.eval()
        if self.device.type == 'cpu':
            self.model = self.model.to(memory_format=torch.channels_last)
        self.transform = transforms.Compose([
            transforms.Resize((self.image_size, self.image_size)),
            transforms.ToTensor(),
        ])

    def _setup_bisenet_repo(self) -> None:
        repo_dir = "BiSeNet"
        if not os.path.exists(repo_dir):
            import subprocess
            subprocess.run(["git", "clone", "https://github.com/CoinCheung/BiSeNet.git"], check=True)
        if repo_dir not in sys.path:
            sys.path.append(repo_dir)

    def _preprocess(self, pil_img: Image.Image) -> torch.Tensor:
        if pil_img.mode != 'RGB':
            pil_img = pil_img.convert('RGB')
        t = self.transform(pil_img).unsqueeze(0).to(self.device)
        if self.device.type == 'cpu':
            t = t.to(memory_format=torch.channels_last)
        return t

    def _infer(self, x: torch.Tensor) -> np.ndarray:
        with torch.no_grad():
            logits = self.model(x)[0]
            logits_up = F.interpolate(logits, size=(self.image_size, self.image_size), mode="bilinear", align_corners=False)
            pred = torch.argmax(logits_up, dim=1).squeeze().cpu().numpy()
            return pred

    def _mask_to_bgr(self, pil_img: Image.Image, mask_arr: np.ndarray) -> np.ndarray:
        orig_w, orig_h = pil_img.size
        mask_pil = Image.fromarray(((mask_arr > 0).astype(np.uint8) * 255), mode='L')
        mask_resized = mask_pil.resize((orig_w, orig_h), Image.LANCZOS)
        img_np = np.array(pil_img.convert('RGB'))
        mask_np = np.array(mask_resized) > 0
        bgr = cv2.cvtColor(img_np, cv2.COLOR_RGB2BGR)
        bgr[mask_np] = [255, 255, 255]
        return bgr

    def process_image_url(self, url: str) -> Optional[np.ndarray]:
        try:
            import requests
            r = requests.get(url, timeout=20)
            r.raise_for_status()
            pil = Image.open(BytesIO(r.content))
        except Exception:
            # Fallback via cv2 decoding
            arr = np.frombuffer(r.content, np.uint8)
            img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
            if img is None:
                return None
            pil = Image.fromarray(cv2.cvtColor(img, cv2.COLOR_BGR2RGB))
        x = self._preprocess(pil)
        mask = self._infer(x)
        return self._mask_to_bgr(pil, mask)

    def process_image_array(self, img_bgr: np.ndarray) -> Optional[np.ndarray]:
        pil = Image.fromarray(cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB))
        x = self._preprocess(pil)
        mask = self._infer(x)
        return self._mask_to_bgr(pil, mask) 