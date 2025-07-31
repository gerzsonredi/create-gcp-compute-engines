import multiprocessing as mp
import numpy as np
import cv2
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor, as_completed
from typing import List, Callable, Any, Tuple
import time

class ParallelImageProcessor:
    """
    Utility class for parallel processing of image operations
    """
    
    def __init__(self, max_workers: int = None):
        self.max_workers = max_workers or min(mp.cpu_count(), 8)
        print(f"ParallelImageProcessor initialized with {self.max_workers} max workers")
    
    def process_image_regions(self, image: np.ndarray, regions: List[Tuple], 
                            operation: Callable, use_processes: bool = False) -> List[Any]:
        """
        Process multiple regions of an image in parallel
        
        Args:
            image: Input image
            regions: List of (x, y, w, h) tuples defining regions
            operation: Function to apply to each region
            use_processes: Whether to use processes (True) or threads (False)
        
        Returns:
            List of results from processing each region
        """
        executor_class = ProcessPoolExecutor if use_processes else ThreadPoolExecutor
        
        with executor_class(max_workers=self.max_workers) as executor:
            futures = []
            for region in regions:
                x, y, w, h = region
                roi = image[y:y+h, x:x+w]
                futures.append(executor.submit(operation, roi, region))
            
            results = []
            for future in as_completed(futures):
                try:
                    result = future.result(timeout=30)  # 30 second timeout
                    results.append(result)
                except Exception as e:
                    print(f"Error processing region: {e}")
                    results.append(None)
            
            return results
    
    def parallel_contour_analysis(self, contours: List[np.ndarray]) -> dict:
        """
        Analyze multiple contours in parallel
        
        Args:
            contours: List of contour arrays
            
        Returns:
            Dictionary with areas, perimeters, and bounding boxes
        """
        start_time = time.time()
        
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # Submit all tasks
            area_futures = [executor.submit(cv2.contourArea, contour) for contour in contours]
            perimeter_futures = [executor.submit(cv2.arcLength, contour, True) for contour in contours]
            bbox_futures = [executor.submit(cv2.boundingRect, contour) for contour in contours]
            
            # Collect results
            areas = [future.result() for future in area_futures]
            perimeters = [future.result() for future in perimeter_futures]
            bboxes = [future.result() for future in bbox_futures]
        
        end_time = time.time()
        print(f"Parallel contour analysis of {len(contours)} contours took {end_time - start_time:.3f}s")
        
        return {
            'areas': areas,
            'perimeters': perimeters,
            'bounding_boxes': bboxes,
            'processing_time': end_time - start_time
        }
    
    def parallel_morphological_operations(self, image: np.ndarray, 
                                        operations: List[Tuple[int, tuple]]) -> List[np.ndarray]:
        """
        Apply multiple morphological operations in parallel
        
        Args:
            image: Input image
            operations: List of (operation_type, kernel_size) tuples
            
        Returns:
            List of processed images
        """
        def apply_morph_op(img_and_op):
            img, (op_type, kernel_size) = img_and_op
            kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, kernel_size)
            return cv2.morphologyEx(img, op_type, kernel)
        
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures = [executor.submit(apply_morph_op, (image.copy(), op)) for op in operations]
            results = [future.result() for future in futures]
        
        return results
    
    def parallel_threshold_analysis(self, image: np.ndarray, 
                                  threshold_values: List[int]) -> List[Tuple[np.ndarray, float]]:
        """
        Test multiple threshold values in parallel
        
        Args:
            image: Input grayscale image
            threshold_values: List of threshold values to test
            
        Returns:
            List of (thresholded_image, quality_score) tuples
        """
        def threshold_and_score(img_and_thresh):
            img, thresh_val = img_and_thresh
            _, binary = cv2.threshold(img, thresh_val, 255, cv2.THRESH_BINARY)
            
            # Simple quality score based on edge preservation
            edges = cv2.Canny(binary, 50, 150)
            score = np.sum(edges) / (img.shape[0] * img.shape[1])
            
            return binary, score
        
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures = [executor.submit(threshold_and_score, (image, thresh)) 
                      for thresh in threshold_values]
            results = [future.result() for future in futures]
        
        return results
    
    def batch_image_preprocessing(self, images: List[np.ndarray], 
                                preprocessing_pipeline: Callable) -> List[np.ndarray]:
        """
        Apply preprocessing pipeline to multiple images in parallel
        
        Args:
            images: List of input images
            preprocessing_pipeline: Function that takes an image and returns processed image
            
        Returns:
            List of preprocessed images
        """
        with ProcessPoolExecutor(max_workers=self.max_workers) as executor:
            futures = [executor.submit(preprocessing_pipeline, img) for img in images]
            results = [future.result() for future in futures]
        
        return results

# Global instance for easy access
parallel_processor = ParallelImageProcessor() 