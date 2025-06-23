# category_id: indices in the 0-based 294-vector
CAT_SPEC_NODES = {
     1: list(range(  0,  29)),   # short-sleeve top      (29)
     2: list(range( 29,  58)),   # long-sleeve  top      (29)
     3: list(range( 58,  87)),   # short-sleeve outwear  (29)
     4: list(range( 87, 126)),   # long-sleeve  outwear  (39)
     5: list(range(126, 141)),   # vest                 (15)
     6: list(range(141, 156)),   # sling                (15)
     7: list(range(156, 179)),   # shorts               (23)
     8: list(range(179, 202)),   # trousers             (23)
     9: list(range(202, 219)),   # skirt                (17)
    10: list(range(219, 244)),   # short-sleeve dress   (25)
    11: list(range(244, 269)),   # long-sleeve  dress   (25)
    12: list(range(269, 289)),   # vest dress           (20)
    13: list(range(289, 294)),   # sling dress          (5)  # pad to 294
}

CFG_FILE   = 'HRNet/experiments/deepfashion2/hrnet/w48_384x288_adam_lr1e-3.yaml'
WEIGHTS    = 'artifacts/pose_hrnet-w48_384x288-deepfashion2_mAP_0.7017.pth'

CATEGORY_TO_COORDS: dict[int, dict[str, list[int]]] = {
    1: {"width": [11, 19], "length": [1, 14]},
    7: {"width": [2, 4],  "length": [7, 8]},
    8: {"width": [3, 5],  "length": [20, 22]},
}