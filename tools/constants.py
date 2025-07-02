# category_id: indices in the 0-based 294-vector
CAT_SPEC_NODES = {
     1: list(range(  0,  25)),   # short-sleeve top      (25)
     2: list(range( 25,  58)),   # long-sleeve  top      (33)
     3: list(range( 58,  89)),   # short-sleeve outwear  (31)
     4: list(range( 89, 128)),   # long-sleeve  outwear  (39)
     5: list(range(128, 143)),   # vest                  (15)
     6: list(range(143, 158)),   # sling                 (15)
     7: list(range(158, 168)),   # shorts                (10)
     8: list(range(168, 182)),   # trousers              (14)
     9: list(range(182, 190)),   # skirt                 (8)
    10: list(range(190, 219)),   # short-sleeve dress    (29)
    11: list(range(219, 256)),   # long-sleeve  dress    (37)
    12: list(range(256, 275)),   # vest dress            (19)
    13: list(range(275, 294)),   # sling dress           (19)
}

CFG_FILE   = 'HRNet/experiments/deepfashion2/hrnet/w48_384x288_adam_lr1e-3.yaml'
WEIGHTS    = 'artifacts/pose_hrnet-w48_384x288-deepfashion2_mAP_0.7017.pth'

CATEGORY_TO_COORDS: dict[int, dict[str, list[int]]] = {
    1:  {"width": [11, 19], "length": [1, 14]},    # short-sleeve top
    2:  {"width": [15, 23], "length": [1, 18]},    # long-sleeve top
    3:  {"width": [11, 19], "length": [3, 15]},    # short-sleeve outwear
    4:  {"width": [15, 23], "length": [1, 18]},    # long-sleeve outwear
    5:  {"width": [7, 13],  "length": [1, 9]},     # vest
    6:  {"width": [7, 13],  "length": [1, 9]},     # sling
    7:  {"width": [0, 2],   "length": [5, 6]},     # shorts
    8:  {"width": [0, 2],   "length": [6, 8]},     # trousers
    9:  {"width": [0, 2],   "length": [0, 4]},     # skirt
    10: {"width": [11, 23], "length": [1, 16]},    # short-sleeve dress
    11: {"width": [15, 27], "length": [1, 20]},    # long-sleeve dress
    12: {"width": [7, 17],  "length": [1, 11]},    # vest dress
    13: {"width": [7, 17],  "length": [6, 11]},    # sling dress
}