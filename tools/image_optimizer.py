import numpy as np
import cv2
from PIL import Image, ImageOps
import io
from typing import Tuple, Union, Optional
import time

class ImageOptimizer:
    """
    Optimized image processing utilities using standard Pillow with performance improvements
    """
    
    def __init__(self, logger=None):
        self.logger = logger
        self.benchmark_results = {}
        
    def log(self, message: str):
        """Log message to both console and logger if available"""
        print(f"[IMG_OPT] {message}")
        if self.logger:
            self.logger.log(f"[IMG_OPT] {message}")
    
    def resize_pillow_optimized(self, image: np.ndarray, target_size: Tuple[int, int], 
                               resample: int = Image.LANCZOS) -> np.ndarray:
        """
        Resize image using optimized Pillow (faster than OpenCV for many operations)
        
        Args:
            image: Input image as numpy array (BGR or RGB)
            target_size: Target size as (width, height)
            resample: Resampling filter (Image.LANCZOS, Image.BILINEAR, etc.)
            
        Returns:
            Resized image as numpy array
        """
        # Convert BGR to RGB if needed (OpenCV uses BGR, PIL uses RGB)
        if len(image.shape) == 3 and image.shape[2] == 3:
            # Assume BGR from OpenCV, convert to RGB
            image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        else:
            image_rgb = image
        
        # Convert to PIL Image
        pil_image = Image.fromarray(image_rgb)
        
        # Resize using Pillow with optimized resampling
        resized_pil = pil_image.resize(target_size, resample=resample)
        
        # Convert back to numpy array
        resized_np = np.array(resized_pil)
        
        # Convert back to BGR if original was BGR
        if len(image.shape) == 3 and image.shape[2] == 3:
            resized_np = cv2.cvtColor(resized_np, cv2.COLOR_RGB2BGR)
        
        return resized_np
    
    def resize_with_aspect_ratio(self, image: np.ndarray, target_size: Tuple[int, int],
                               pad_color: Tuple[int, int, int] = (0, 0, 0)) -> np.ndarray:
        """
        Resize image maintaining aspect ratio with padding
        
        Args:
            image: Input image
            target_size: Target size as (width, height)
            pad_color: Color for padding areas
            
        Returns:
            Resized and padded image
        """
        h, w = image.shape[:2]
        target_w, target_h = target_size
        
        # Calculate aspect ratios
        aspect_ratio = w / h
        target_aspect = target_w / target_h
        
        if aspect_ratio > target_aspect:
            # Image is wider, fit to width
            new_w = target_w
            new_h = int(target_w / aspect_ratio)
        else:
            # Image is taller, fit to height
            new_h = target_h
            new_w = int(target_h * aspect_ratio)
        
        # Resize image
        resized = self.resize_pillow_optimized(image, (new_w, new_h))
        
        # Create padded image
        if len(image.shape) == 3:
            padded = np.full((target_h, target_w, image.shape[2]), pad_color, dtype=image.dtype)
        else:
            padded = np.full((target_h, target_w), pad_color[0], dtype=image.dtype)
        
        # Calculate padding offsets
        y_offset = (target_h - new_h) // 2
        x_offset = (target_w - new_w) // 2
        
        # Place resized image in center
        padded[y_offset:y_offset + new_h, x_offset:x_offset + new_w] = resized
        
        return padded
    
    def normalize_image_fast(self, image: np.ndarray, mean: np.ndarray, std: np.ndarray) -> np.ndarray:
        """
        Fast image normalization using vectorized operations
        
        Args:
            image: Input image (0-255 range)
            mean: Mean values for normalization
            std: Standard deviation values for normalization
            
        Returns:
            Normalized image
        """
        # Convert to float32 and normalize to 0-1 range
        normalized = image.astype(np.float32) / 255.0
        
        # Apply mean and std normalization
        normalized = (normalized - mean) / std
        
        return normalized
    
    def preprocess_batch(self, images: list, target_size: Tuple[int, int],
                        mean: np.ndarray, std: np.ndarray) -> np.ndarray:
        """
        Preprocess a batch of images efficiently
        
        Args:
            images: List of input images
            target_size: Target size for resizing
            mean: Mean values for normalization
            std: Standard deviation values for normalization
            
        Returns:
            Batch of preprocessed images as numpy array
        """
        batch_size = len(images)
        if len(images[0].shape) == 3:
            channels = images[0].shape[2]
            batch_array = np.zeros((batch_size, channels, target_size[1], target_size[0]), dtype=np.float32)
        else:
            batch_array = np.zeros((batch_size, 1, target_size[1], target_size[0]), dtype=np.float32)
        
        for i, image in enumerate(images):
            # Resize image
            resized = self.resize_pillow_optimized(image, target_size)
            
            # Normalize
            normalized = self.normalize_image_fast(resized, mean, std)
            
            # Convert to CHW format
            if len(normalized.shape) == 3:
                normalized = np.transpose(normalized, (2, 0, 1))
            else:
                normalized = np.expand_dims(normalized, axis=0)
            
            batch_array[i] = normalized
        
        return batch_array
    
    def benchmark_resize_methods(self, image: np.ndarray, target_size: Tuple[int, int],
                                num_runs: int = 100) -> dict:
        """
        Benchmark different resizing methods
        
        Args:
            image: Test image
            target_size: Target size for resizing
            num_runs: Number of benchmark runs
            
        Returns:
            Benchmark results
        """
        self.log(f"Benchmarking resize methods with {num_runs} runs")
        
        # Test OpenCV resize
        opencv_times = []
        for _ in range(num_runs):
            start_time = time.time()
            _ = cv2.resize(image, target_size, interpolation=cv2.INTER_LINEAR)
            opencv_times.append(time.time() - start_time)
        
        # Test optimized Pillow resize
        pillow_times = []
        for _ in range(num_runs):
            start_time = time.time()
            _ = self.resize_pillow_optimized(image, target_size, Image.BILINEAR)
            pillow_times.append(time.time() - start_time)
        
        # Calculate statistics
        opencv_avg = np.mean(opencv_times)
        pillow_avg = np.mean(pillow_times)
        speedup = opencv_avg / pillow_avg
        
        results = {
            'opencv_avg_time': opencv_avg,
            'pillow_optimized_avg_time': pillow_avg,
            'speedup_factor': speedup,
            'speedup_percentage': (speedup - 1) * 100,
            'opencv_std': np.std(opencv_times),
            'pillow_std': np.std(pillow_times)
        }
        
        self.log(f"Resize Benchmark Results:")
        self.log(f"  OpenCV avg: {opencv_avg:.4f}s (±{results['opencv_std']:.4f}s)")
        self.log(f"  Pillow-Optimized avg: {pillow_avg:.4f}s (±{results['pillow_std']:.4f}s)")
        
        if speedup > 1:
            self.log(f"  Pillow-Optimized is {speedup:.2f}x faster ({results['speedup_percentage']:.1f}% faster)")
        else:
            self.log(f"  OpenCV is {1/speedup:.2f}x faster ({-results['speedup_percentage']:.1f}% faster)")
        
        self.benchmark_results['resize'] = results
        return results

# Global image optimizer instance
image_optimizer = ImageOptimizer() 