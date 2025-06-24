from __future__ import annotations
import cv2
import numpy as np
from numpy.typing import NDArray
from tools.constants import CATEGORY_TO_COORDS
from typing import TypedDict


class MeasurementResult(TypedDict):
    width:  float
    length: float
    w1:     tuple[int, int]
    w2:     tuple[int, int]
    l1:     tuple[int, int]
    l2:     tuple[int, int]


class ClothingMeasurer():
    def __init__(self):
        self.__category_to_coordinates = {
            1: {    # short-sleeved tops
                "width": [11, 19],  
                "length": [1, 14]
            },
            7: {    # shorts
                "width": [2, 4],
                "length": [7, 8]
            },
            8: {    # trousers
                "width": [3, 5],
                "length": [20, 22]
            }
        }


    def calculate_measurements(
            self,
            img_bgr: NDArray[np.uint8],
            pts: NDArray[np.float32] | NDArray[np.int_],
            *,
            
            category_id: int = 1,
        ) -> MeasurementResult:
        """
        Calculate “width” and “length” guide lines for a set of landmarks and
        return their pixel distances.

        Parameters
        ----------
        img_bgr
            Image (BGR) to draw on. Modified in place & returned for convenience.
        pts
            (N, 2) array of landmark coordinates.
        
        category_id
            Key in ``CATEGORY_TO_COORDS`` that chooses which landmark indices
            define the width and length.

        Returns
        -------
        dict
            (width_in_px, length_in_px, width coordinates, length coordinates)
        """
        try:
            indices = CATEGORY_TO_COORDS[category_id]
        except KeyError as exc:
            raise ValueError(f"Unknown category_id {category_id}") from exc

        # --- Width -------------------------------------------------------------
        w_idx1, w_idx2 = indices["width"]
        w1, w2 = pts[[w_idx1, w_idx2]].astype(int)

        y_mid = int(np.mean((w1[1], w2[1])))      # horizontal line at average y
        w1 = (int(w1[0]), y_mid)
        w2 = (int(w2[0]), y_mid)

        width_px: float = float(np.linalg.norm(np.subtract(w1, w2)))

        # --- Length ------------------------------------------------------------
        l_idx1, l_idx2 = indices["length"]
        l1, l2 = pts[[l_idx1, l_idx2]].astype(int)

        if category_id == 1:
            # Draw strictly vertical segment
            length_px: float = float(abs(l2[1] - l1[1]))
        else:
            length_px = float(np.linalg.norm(l1 - l2))

        result = {
            "width": width_px,
            "length": length_px,
            "w1": w1,
            "w2": w2,
            "l1": l1,
            "l2": l2
        }
        return result

    def draw_lines(
            self,
            img_bgr: NDArray[np.uint8],
            pts: MeasurementResult,
            *,
            category_id: int = 1,
            color: tuple[int, int, int] = (0, 255, 0)
        ) -> None:
        """
        Parameters
        ----------
        img_bgr
            Image (BGR) to draw on. Modified in place & returned for convenience.
        pts
            Result points from previous measurements.
        category_id:
            Key in ``CATEGORY_TO_COORDS`` that chooses which lines do we want to display.
        color
            BGR colour of the guide lines.
        """

        cv2.line(img_bgr, pts["w1"], pts["w2"], color, thickness=5)
        # Draw strictly vertical segment
        if category_id == 1:
            l2_projected = (int(pts["l1"][0]), int(pts["l2"][1]))
            cv2.line(img_bgr, pts["l1"], l2_projected, color, thickness=5)
        else:
            cv2.line(img_bgr, pts["l1"], pts["l2"], color, thickness=5)