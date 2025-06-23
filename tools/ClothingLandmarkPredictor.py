import torch, cv2, numpy as np
from pathlib import Path
from HRNet.lib.config import cfg, update_config
from HRNet.lib.models.pose_hrnet import get_pose_net
from HRNet.lib.core.inference import get_final_preds, get_max_preds         # heatmap --> (x,y)
from HRNet.lib.utils.transforms import get_affine_transform, affine_transform
from torchvision import transforms
from argparse import Namespace
from tools.constants import CAT_SPEC_NODES, CFG_FILE, WEIGHTS


class ClothingLandmarkPredictor():
    def __init__(self):
        self.__CFG_FILE   = CFG_FILE
        self.__WEIGHTS    = WEIGHTS
        self.__DEVICE     = 'cuda' if torch.cuda.is_available() else 'cpu'
    

        args = Namespace(
            cfg=self.__CFG_FILE,
            opts=[],        # no CLI overrides
            modelDir='',    # no training ⇒ leave blank
            logDir='',
            dataDir=''
        )


        update_config(cfg, args)
        self.model = get_pose_net(cfg, is_train=False)       # build HRNet
        self.state = torch.load(self.__WEIGHTS, map_location=self.__DEVICE)
        self.model.load_state_dict(self.state['state_dict'] if 'state_dict' in self.state else self.state)
        self.model.to(self.__DEVICE).eval()

        self.__MEAN = np.array([0.485, 0.456, 0.406], dtype=np.float32)
        self.__STD  = np.array([0.229, 0.224, 0.225], dtype=np.float32)

        self.__to_tensor = transforms.Compose([
            transforms.ToTensor(),
            transforms.Normalize(mean=self.__MEAN, std=self.__STD)
        ])
        print("HRNet model loaded!")

    def __crop_and_warp(self, img_bgr, bbox):
        """
        bbox : (x1, y1, w, h) in the *original* image
        Returns the network-ready tensor, plus (center, scale) for back-projection.
        """
        x, y, w, h = bbox
        center = np.array([x + w * 0.5, y + h * 0.5], dtype=np.float32)
        # HRNet code defines 'scale' as size / 200
        scale  = np.array([w, h], dtype=np.float32) / 200.0
        rot    = 0

        trans  = get_affine_transform(center, scale, rot, cfg.MODEL.IMAGE_SIZE)
        crop   = cv2.warpAffine(img_bgr, trans,
                                (int(cfg.MODEL.IMAGE_SIZE[0]),
                                int(cfg.MODEL.IMAGE_SIZE[1])),
                                flags=cv2.INTER_LINEAR)
        crop_rgb = cv2.cvtColor(crop, cv2.COLOR_BGR2RGB)
        return self.__to_tensor(crop_rgb).unsqueeze(0), center, scale

    def __heatmap_to_image(self, coords_hm, center, scale,
                        heatmap_size=cfg.MODEL.HEATMAP_SIZE):
        """
        coords_hm : (K,2) landmark locations in heat-map space (e.g. 64x64)
        center    : (2,) same one you sent to _crop_and_warp
        scale     : (2,) same one you sent to _crop_and_warp
        returns   : (K,2) absolute pixel coords in the original image.
        """
        # build the forward affine transform (orig → heatmap)…
        trans = get_affine_transform(center, scale, 0, heatmap_size)
        # …invert it so we can go back
        trans_inv = cv2.invertAffineTransform(trans)

        K = coords_hm.shape[0]
        hm_homo = np.concatenate([coords_hm, np.ones((K,1))], axis=1)  # K×3
        img_xy  = (trans_inv @ hm_homo.T).T                            # K×2
        return img_xy


    @torch.no_grad()
    def predict_landmarks(self, img_path, bbox=None):
        """
        img_path : str / Path to an image.
        bbox     : (x1, y1, w, h) or None.  If None, the full frame is used.
        Returns  : ndarray of shape (num_landmarks, 2) in original-image coords.
        """
        img = cv2.imread(str(img_path))
        # if bbox is None:
        bbox = [0, 0, img.shape[1], img.shape[0]]

        net_in, center, scale = self.__crop_and_warp(img, bbox)
        net_in = net_in.to(self.__DEVICE)

        out  = self.model(net_in)                     # B×C×H×W heat-maps
        coords_hm, _ = get_max_preds(out.cpu().numpy())
        coords_img   = self.__heatmap_to_image(
                    coords_hm[0],
                    center, scale,          # from _crop_and_warp
                    cfg.MODEL.HEATMAP_SIZE)
        
        return coords_img


    def filter_by_category(self, coords_294, category_id):
        """
        coords_294 : (294, 2) array from `predict_landmarks`.
        category_id: 1-13 as defined by DeepFashion2.
        Returns    : (K, 2) array with only the landmarks for that garment.
        """
        return coords_294[CAT_SPEC_NODES[category_id]]

    