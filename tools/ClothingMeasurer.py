from __future__ import annotations
import cv2
import numpy as np
from numpy.typing import NDArray
from tools.constants import CATEGORY_TO_COORDS
from typing import TypedDict


class MeasurementResult(TypedDict):
    width:          float
    length:         float
    w1:             tuple[int, int]
    w2:             tuple[int, int]
    l1:             tuple[int, int]
    l2:             tuple[int, int]
    measuring_mode: str


class ClothingMeasurer:
    def __init__(self, logger):
        self.__logger = logger
        print("ClothingMeasurer initialized successfully!")
        self.__logger.log("ClothingMeasurer initialized successfully!")

    def dumb_measure(
    self,
    mask:    NDArray[np.uint]
) -> MeasurementResult:
        """
        If the category is skirt or shorts or long sleeve dress measure the length of the clothing item based on mask
        """
        # Convert to grayscale if needed
        if mask.ndim == 3:
            mask = cv2.cvtColor(mask, cv2.COLOR_RGB2GRAY)
        
        # Find non-white pixels (clothing pixels)
        non_white_area = mask < 255
        print("Two dimensional color channel!")
        
        # Find all coordinates where clothing pixels exist
        y_coords, x_coords = np.where(non_white_area)
        
        if len(y_coords) == 0:
            # No clothing pixels found
            return {
                "width": 0.0,
                "length": 0.0,
                "w1": (0, 0),
                "w2": (0, 0),
                "l1": (0, 0),
                "l2": (0, 0)
            }
        
        # Configuration for thickness tolerance
        top_thickness = 10  # Consider top 10 rows for upper left corner
        waist_thickness = 5  # Consider 5 rows around waist for width measurement
        bottom_thickness = 10  # Consider bottom 10 rows for length measurement
        x_tolerance = 15  # Allow some horizontal tolerance for bottom left corner
        
        # STEP 1: Find the upper left corner with thickness tolerance
        min_y = int(np.min(y_coords))  # Topmost row with clothing
        max_y = int(np.max(y_coords))  # Bottommost row with clothing
        
        # Look at top area (min_y to min_y + top_thickness)
        top_end = min(min_y + top_thickness, max_y)
        top_area_mask = non_white_area[min_y:top_end + 1]
        
        # Find leftmost pixel in the top area
        top_area_coords = np.where(top_area_mask)
        if len(top_area_coords[0]) > 0:
            # Adjust coordinates back to original image space
            top_area_y = top_area_coords[0] + min_y
            top_area_x = top_area_coords[1]
            
            # Find the leftmost pixel in the top area
            leftmost_idx = np.argmin(top_area_x)
            upper_left_x = int(top_area_x[leftmost_idx])
            upper_left_y = int(top_area_y[leftmost_idx])
        else:
            # Fallback: overall leftmost x coordinate
            upper_left_x = int(np.min(x_coords))
            upper_left_y = min_y
        
        upper_left_corner = (upper_left_x, upper_left_y)
        print(f"Upper left corner found at: {upper_left_corner}")
        
        # STEP 2: Calculate waist size with thickness tolerance
        # Look at rows around the upper left corner
        waist_start = max(0, upper_left_y - waist_thickness // 2)
        waist_end = min(non_white_area.shape[0] - 1, upper_left_y + waist_thickness // 2)
        
        waist_area_mask = non_white_area[waist_start:waist_end + 1]
        waist_area_coords = np.where(waist_area_mask)
        
        if len(waist_area_coords[0]) > 0:
            # Adjust coordinates back to original image space
            waist_area_y = waist_area_coords[0] + waist_start
            waist_area_x = waist_area_coords[1]
            
            # Find leftmost and rightmost pixels in waist area
            waist_left_x = int(np.min(waist_area_x))
            waist_right_x = int(np.max(waist_area_x))
            
            # Use the upper_left_y as the reference y-coordinate for waist measurement
            w1 = (waist_left_x, upper_left_y)
            w2 = (waist_right_x, upper_left_y)
            width_px = float(waist_right_x - waist_left_x)
        else:
            # Fallback
            w1 = (upper_left_x, upper_left_y)
            w2 = (upper_left_x, upper_left_y)
            width_px = 0.0
        
        print(f"Waist measurement: from {w1} to {w2}, width: {width_px:.2f}px")
        
        # STEP 3: Calculate skirt length
        # Find bottom left corner: larger y value and x <= upper_left_x
        bottom_left_x = upper_left_x
        bottom_left_y = upper_left_y
        
        # Look for pixels with y > upper_left_y and x <= upper_left_x
        valid_bottom_indices = np.where(
            (y_coords > upper_left_y) & (x_coords <= upper_left_x)
        )[0]
        
        if len(valid_bottom_indices) > 0:
            # Find the bottommost point among valid candidates
            valid_y_coords = y_coords[valid_bottom_indices]
            valid_x_coords = x_coords[valid_bottom_indices]
            
            max_y_idx = np.argmax(valid_y_coords)
            bottom_left_y = int(valid_y_coords[max_y_idx])
            bottom_left_x = int(valid_x_coords[max_y_idx])
        else:
            # Fallback: find bottommost pixel overall
            max_y = int(np.max(y_coords))
            bottom_row = non_white_area[max_y]
            if np.any(bottom_row):
                bottom_left_x = int(np.min(np.where(bottom_row)[0]))
                bottom_left_y = max_y
        
        # Calculate length (vertical distance between upper and lower left corners)
        length_px = float(abs(bottom_left_y - upper_left_y))
        
        # Length coordinates (upper left and bottom left corners)
        l1 = (upper_left_x, upper_left_y)
        l2 = (bottom_left_x, bottom_left_y)
        
        print(f"Skirt length measurement: from {l1} to {l2}, length: {length_px:.2f}px")
        self.__logger.log(f"Dumb measurement - length: {length_px:.2f}px, upper left: {l1}, bottom left: {l2}")
        
        return {
            "width": width_px,
            "length": length_px,
            "w1": w1,
            "w2": w2,
            "l1": l1,
            "l2": l2
        }
    


    def dumb_calculate_length(
            self,
            img_bgr: NDArray[np.uint8], 
            l1: NDArray
    ) -> MeasurementResult:
        """
        Calculate length by finding the bottommost point in the same column as the upper left corner
        """
        # Convert to grayscale if needed
        if img_bgr.ndim == 3:
            mask = cv2.cvtColor(img_bgr, cv2.COLOR_RGB2GRAY)
        else:
            mask = img_bgr
        
        # Find non-white pixels (clothing pixels)
        non_white_area = mask < 255
        print("Calculating length from upper left corner")
        
        # Extract coordinates from l1 (upper left corner)
        if isinstance(l1, (tuple, list)):
            upper_left_x, upper_left_y = int(l1[0]), int(l1[1])
        else:
            upper_left_x, upper_left_y = int(l1[0]), int(l1[1])
        
        # Find all coordinates where clothing pixels exist
        y_coords, x_coords = np.where(non_white_area)
        
        if len(y_coords) == 0:
            # No clothing pixels found
            return {
                "width": 0.0,
                "length": 0.0,
                "w1": (0, 0),
                "w2": (0, 0),
                "l1": (upper_left_x, upper_left_y),
                "l2": (upper_left_x, upper_left_y),
                "measuring_mode": "fail"
            }
        
        # Configuration for column tolerance
        x_tolerance = 5  # Allow some horizontal tolerance for finding bottom point

        # Find pixels in the same column (with tolerance) as the upper left corner
        column_mask = np.abs(x_coords - upper_left_x) <= x_tolerance

        if np.any(column_mask):
            # Filter coordinates to those in the target column
            column_y_coords = y_coords[column_mask]
            column_x_coords = x_coords[column_mask]
            
            # Find pixels below the upper left corner
            below_mask = column_y_coords > upper_left_y
            
            if np.any(below_mask):
                below_y_coords = column_y_coords[below_mask]
                below_x_coords = column_x_coords[below_mask]
                
                # Find the bottommost point
                bottommost_idx = np.argmax(below_y_coords)
                bottom_left_y = int(below_y_coords[bottommost_idx])
                bottom_left_x = int(below_x_coords[bottommost_idx])
            else:
                # No pixels below the upper left corner in this column
                bottom_left_x = upper_left_x
                bottom_left_y = upper_left_y
        else:
            # No pixels found in the target column, fallback to overall bottommost
            max_y = int(np.max(y_coords))
            bottom_row = non_white_area[max_y]
            if np.any(bottom_row):
                bottom_left_x = int(np.min(np.where(bottom_row)[0]))
                bottom_left_y = max_y
            else:
                bottom_left_x = upper_left_x
                bottom_left_y = upper_left_y

        # Calculate length (vertical distance)
        length_px = float(abs(bottom_left_y - upper_left_y))
        l2_result = (bottom_left_x, bottom_left_y)
    
        return length_px, l2_result
    
    def find_skirt_corners(
            self,
            img_bgr,
            went_back=False,
            top_band_px=75,
            bottom_fraction=0.10) -> MeasurementResult:
        """
        Returns dict(tl, tr, bl, waist_px, length_px)

        Parameters
        ----------
        top_band_px : int
            Vertical tolerance used to aggregate waistband contour points.
        bottom_fraction : float  (0 < f ≤ 0.5)
            Treat the lowest f·100 % of the contour’s y-range as the
            “bottom strip”; the left-most point in that strip is bl.
            0.10 ( = lowest 10 %) works well for heels/skirts 300–600 px tall.
        """
        # -- binary mask of foreground ------------------------------------------------
        gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
        _, mask = cv2.threshold(gray, 250, 255, cv2.THRESH_BINARY_INV)
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE,
                                cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5)),
                                iterations=2)

        # -- largest contour ----------------------------------------------------------
        cnts, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if not cnts:
            raise ValueError("No contour found.")
        pts = cnts[np.argmax([cv2.contourArea(c) for c in cnts])].reshape(-1, 2)

        # -- waistband corners --------------------------------------------------------
        y_top = pts[:, 1].min()
        top_band = pts[pts[:, 1] <= y_top + top_band_px]
        tl = tuple(int(x) for x in top_band[top_band[:, 0].argmin()])
        tr = tuple(int(x) for x in top_band[top_band[:, 0].argmax()])

        # -- bottom-left corner -------------------------------------------------------
        y_bot  = pts[:, 1].max()
        band_y = y_top + (y_bot - y_top) * (1 - bottom_fraction)
        bottom_strip = pts[pts[:, 1] >= band_y]
        bl = tuple(int(x) for x in bottom_strip[bottom_strip[:, 0].argmin()])

        # -- distances ----------------------------------------------------------------
        waist_px  = float(np.hypot(tr[0] - tl[0], tr[1] - tl[1]))
        length_px = float(np.hypot(bl[0] - tl[0], bl[1] - tl[1]))

        # return dict(tl=tl, tr=tr, bl=bl,
                    # waist_px=waist_px, length_px=length_px)

        if went_back:
            measuring_mode = "recalculated"
        else:
            measuring_mode = "skirt_and_shorts"
        
        return {
            "width": waist_px,
            "length": length_px,
            "w1": tl,
            "w2": tr,
            "l1": tl,
            "l2": bl,
            "measuring_mode": measuring_mode
        }
    
    def filter_components(
        self,
        img: np.ndarray,
        min_size: int = 400,
        keep_largest: bool = False,
        connectivity: int = 8,
    ) -> np.ndarray:
        """
        Remove small connected components *or* keep only the largest one.

        Args:
            img: we will turn it into a binary mask (bool / 0-1) where True==foreground.
            min_size: minimum pixel area to keep (ignored if keep_largest=True).
            keep_largest: if True keep only the biggest component, otherwise drop
                          everything smaller than min_size.
            connectivity: 4 or 8 (8 gives diagonals connectivity).

        Returns:
            Cleaned binary mask (same shape as input).
        """
        if img.ndim == 3:
            non_white_mask = ~np.all(img == [255, 255, 255], axis=2)
        else:
            non_white_mask = img != 255
        # Make sure we have uint8 {0,1} for OpenCV
        mask_uint8 = non_white_mask.astype(np.uint8)

        num_labels, labels, stats, _ = cv2.connectedComponentsWithStats(
            mask_uint8, connectivity=connectivity
        )

        # stats[:, cv2.CC_STAT_AREA] => pixel count per label (label 0 is background)
        if keep_largest and num_labels > 1:
            # Choose foreground label with largest area
            largest_label = 1 + np.argmax(stats[1:, cv2.CC_STAT_AREA])
            cleaned = labels == largest_label
        else:
            # Keep everything >= min_size
            keep = stats[:, cv2.CC_STAT_AREA] >= min_size
            keep[0] = False  # never keep background
            cleaned = keep[labels]

        cleaned = cleaned.astype(bool)
        if img.ndim == 3:
            img[~cleaned] = [255, 255, 255]
        else:
            img[~cleaned] = 255

        return img

    def calculate_measurements(
            self,
            img_bgr: NDArray[np.uint8],
            pts: NDArray[np.float32] | NDArray[np.int_],
            *,
            
            category_id: int = 1,
        ) -> MeasurementResult:
        """
        Calculate "width" and "length" guide lines for a set of landmarks and
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
        cleaned_img = self.filter_components(img_bgr, keep_largest=True)
        if category_id in (7,9):
            return self.find_skirt_corners(cleaned_img)
        try:
            indices = CATEGORY_TO_COORDS[category_id]
        except KeyError as exc:
            error_msg = f"Unknown category_id {category_id}"
            print(f"ERROR: {error_msg}")
            self.__logger.log(f"ERROR: {error_msg}")
            raise ValueError(error_msg) from exc

        # --- Width -------------------------------------------------------------
        w_idx1, w_idx2 = indices["width"]
        w1, w2 = pts[[w_idx1, w_idx2]].astype(int)

        # y_mid = int(np.mean((w1[1], w2[1]))) 
        w1 = (int(w1[0]), int(w1[1]))
        w2 = (int(w2[0]), int(w2[1]))

        width_px: float = float(np.linalg.norm(np.subtract(w1, w2)))

        # --- Length ------------------------------------------------------------
        l_idx1, l_idx2 = indices["length"]
        l1, l2 = pts[[l_idx1, l_idx2]].astype(int)

        measurement_mode = "landmark"
        if category_id in (7, 8, 9):
            length_px = float(np.linalg.norm(l1 - l2))
        elif category_id in (4, 10, 11, 12, 13):
            length_px, l2 = self.dumb_calculate_length(cleaned_img, l1)
            measurement_mode = "dresses_length"
        else:
            # Draw strictly vertical segment
            length_px: float = float(abs(l2[1] - l1[1]))

        print(f"Calculated measurements - width: {width_px:.2f}px, length: {length_px:.2f}px")
        self.__logger.log(f"Calculated measurements - width: {width_px:.2f}px, length: {length_px:.2f}px")
        if width_px < 300 or length_px < 300:
            return self.find_skirt_corners(cleaned_img, went_back=True)
        result = {
            "width": width_px,
            "length": length_px,
            "w1": w1,
            "w2": w2,
            "l1": (int(l1[0]), int(l1[1])),  # Convert numpy integers to Python integers
            "l2": (int(l2[0]), int(l2[1])),
            "measuring_mode": measurement_mode
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
        if category_id in (7,8,9):
            cv2.line(img_bgr, pts["l1"], pts["l2"], color, thickness=5)
        else:
            l2_projected = (int(pts["l1"][0]), int(pts["l2"][1]))
            cv2.line(img_bgr, pts["l1"], l2_projected, color, thickness=5)
        
        print("Successfully drew measurement lines on image")
        self.__logger.log("Successfully drew measurement lines on image")