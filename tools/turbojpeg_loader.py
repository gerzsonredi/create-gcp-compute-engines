import numpy as np
import cv2
import requests
from PIL import Image
import io
import time
from typing import Optional, Tuple, Union
import os

try:
    from turbojpeg import TurboJPEG
    TURBOJPEG_AVAILABLE = True
except ImportError:
    TURBOJPEG_AVAILABLE = False
    print("[TURBOJPEG] TurboJPEG not available, falling back to OpenCV")

class TurboJPEGLoader:
    """
    High-performance image loader using TurboJPEG for faster JPEG decoding
    Falls back to OpenCV if TurboJPEG is not available
    """
    
    def __init__(self, logger=None):
        self.logger = logger
        self.turbojpeg = None
        self.use_turbojpeg = TURBOJPEG_AVAILABLE
        
        if TURBOJPEG_AVAILABLE:
            try:
                self.turbojpeg = TurboJPEG()
                print("[TURBOJPEG] TurboJPEG initialized successfully")
                if self.logger:
                    self.logger.log("[TURBOJPEG] TurboJPEG initialized successfully")
            except Exception as e:
                print(f"[TURBOJPEG] Failed to initialize TurboJPEG: {e}")
                if self.logger:
                    self.logger.log(f"[TURBOJPEG] Failed to initialize TurboJPEG: {e}")
                self.use_turbojpeg = False
    
    def log(self, message: str):
        """Log message to both console and logger if available"""
        print(f"[TURBOJPEG] {message}")
        if self.logger:
            self.logger.log(f"[TURBOJPEG] {message}")
    
    def load_image_from_url(self, url: str, timeout: int = 10) -> Optional[np.ndarray]:
        """
        Load image from URL using TurboJPEG for faster decoding
        
        Args:
            url: Image URL
            timeout: Request timeout in seconds
            
        Returns:
            Image as numpy array (BGR format) or None if failed
        """
        start_time = time.time()
        
        try:
            # Download image data with optimized headers
            headers = {
                'User-Agent': 'Mozilla/5.0 (compatible; ImageLoader/1.0)',
                'Accept': 'image/jpeg,image/webp,image/png,image/*;q=0.8',
                'Accept-Encoding': 'gzip, deflate',
                'Connection': 'keep-alive'
            }
            
            response = requests.get(url, headers=headers, timeout=timeout, stream=True)
            response.raise_for_status()
            
            # Read image data
            image_data = response.content
            download_time = time.time() - start_time
            
            # Decode image
            decode_start = time.time()
            image = self._decode_image(image_data)
            decode_time = time.time() - decode_start
            
            total_time = time.time() - start_time
            
            if image is not None:
                self.log(f"Loaded image from URL: {image.shape} in {total_time:.3f}s (download: {download_time:.3f}s, decode: {decode_time:.3f}s)")
                return image
            else:
                self.log(f"Failed to decode image from URL: {url}")
                return None
                
        except requests.exceptions.Timeout:
            self.log(f"Timeout loading image from URL: {url}")
            return None
        except requests.exceptions.RequestException as e:
            self.log(f"Request error loading image from URL {url}: {e}")
            return None
        except Exception as e:
            self.log(f"Unexpected error loading image from URL {url}: {e}")
            return None
    
    def load_image_from_file(self, file_path: str) -> Optional[np.ndarray]:
        """
        Load image from file using TurboJPEG for faster decoding
        
        Args:
            file_path: Path to image file
            
        Returns:
            Image as numpy array (BGR format) or None if failed
        """
        start_time = time.time()
        
        try:
            if not os.path.exists(file_path):
                self.log(f"File not found: {file_path}")
                return None
            
            # Read file data
            with open(file_path, 'rb') as f:
                image_data = f.read()
            
            # Decode image
            image = self._decode_image(image_data)
            
            if image is not None:
                load_time = time.time() - start_time
                self.log(f"Loaded image from file: {image.shape} in {load_time:.3f}s")
                return image
            else:
                self.log(f"Failed to decode image from file: {file_path}")
                return None
                
        except Exception as e:
            self.log(f"Error loading image from file {file_path}: {e}")
            return None
    
    def _decode_image(self, image_data: bytes) -> Optional[np.ndarray]:
        """
        Decode image data using TurboJPEG or fallback to OpenCV/PIL
        
        Args:
            image_data: Raw image bytes
            
        Returns:
            Image as numpy array (BGR format) or None if failed
        """
        if not image_data:
            return None
        
        # Try TurboJPEG first (fastest for JPEG)
        if self.use_turbojpeg and self._is_jpeg(image_data):
            try:
                # Decode with TurboJPEG (returns RGB)
                rgb_array = self.turbojpeg.decode(image_data)
                # Convert RGB to BGR for OpenCV compatibility
                bgr_array = cv2.cvtColor(rgb_array, cv2.COLOR_RGB2BGR)
                return bgr_array
            except Exception as e:
                self.log(f"TurboJPEG decode failed, falling back to OpenCV: {e}")
        
        # Fallback to OpenCV
        try:
            nparr = np.frombuffer(image_data, np.uint8)
            image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            if image is not None:
                return image
        except Exception as e:
            self.log(f"OpenCV decode failed, trying PIL: {e}")
        
        # Final fallback to PIL
        try:
            pil_image = Image.open(io.BytesIO(image_data))
            if pil_image.mode != 'RGB':
                pil_image = pil_image.convert('RGB')
            # Convert to numpy array and then to BGR
            rgb_array = np.array(pil_image)
            bgr_array = cv2.cvtColor(rgb_array, cv2.COLOR_RGB2BGR)
            return bgr_array
        except Exception as e:
            self.log(f"PIL decode also failed: {e}")
            return None
    
    def _is_jpeg(self, image_data: bytes) -> bool:
        """Check if image data is JPEG format"""
        if len(image_data) < 4:
            return False
        # Check JPEG magic bytes
        return (image_data[:2] == b'\xff\xd8' and 
                image_data[-2:] == b'\xff\xd9') or \
               image_data[:4] == b'\xff\xd8\xff\xe0' or \
               image_data[:4] == b'\xff\xd8\xff\xe1'
    
    def resize_image(self, image: np.ndarray, target_size: Tuple[int, int], 
                    interpolation: int = cv2.INTER_LINEAR) -> np.ndarray:
        """
        Resize image with optimized settings
        
        Args:
            image: Input image
            target_size: Target size as (width, height)
            interpolation: Interpolation method
            
        Returns:
            Resized image
        """
        start_time = time.time()
        
        # Use optimized resize settings
        resized = cv2.resize(image, target_size, interpolation=interpolation)
        
        resize_time = time.time() - start_time
        self.log(f"Resized image from {image.shape[:2][::-1]} to {target_size} in {resize_time:.3f}s")
        
        return resized
    
    def benchmark_loading(self, url: str, num_runs: int = 5) -> dict:
        """
        Benchmark different loading methods
        
        Args:
            url: Test image URL
            num_runs: Number of benchmark runs
            
        Returns:
            Benchmark results
        """
        self.log(f"Benchmarking image loading with {num_runs} runs")
        
        # Download once to get the data
        try:
            response = requests.get(url, timeout=10)
            image_data = response.content
        except Exception as e:
            self.log(f"Failed to download test image: {e}")
            return {}
        
        results = {}
        
        # Benchmark TurboJPEG
        if self.use_turbojpeg and self._is_jpeg(image_data):
            times = []
            for _ in range(num_runs):
                start = time.time()
                try:
                    rgb_array = self.turbojpeg.decode(image_data)
                    bgr_array = cv2.cvtColor(rgb_array, cv2.COLOR_RGB2BGR)
                    times.append(time.time() - start)
                except:
                    times.append(float('inf'))
            
            if times and min(times) != float('inf'):
                results['turbojpeg'] = {
                    'avg_time': np.mean(times),
                    'min_time': min(times),
                    'max_time': max(times)
                }
        
        # Benchmark OpenCV
        times = []
        for _ in range(num_runs):
            start = time.time()
            try:
                nparr = np.frombuffer(image_data, np.uint8)
                image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
                times.append(time.time() - start)
            except:
                times.append(float('inf'))
        
        if times and min(times) != float('inf'):
            results['opencv'] = {
                'avg_time': np.mean(times),
                'min_time': min(times),
                'max_time': max(times)
            }
        
        # Calculate speedup
        if 'turbojpeg' in results and 'opencv' in results:
            speedup = results['opencv']['avg_time'] / results['turbojpeg']['avg_time']
            results['speedup'] = speedup
            self.log(f"TurboJPEG is {speedup:.2f}x faster than OpenCV")
        
        return results

# Global instance
turbojpeg_loader = TurboJPEGLoader() 