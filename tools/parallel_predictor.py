import concurrent.futures
import threading
import time
from typing import Tuple, Optional, Any
import numpy as np


class ParallelPredictor:
    """
    Parallel execution of landmark detection and category prediction
    for maximum performance optimization
    """
    
    def __init__(self, landmark_predictor, category_predictor, logger=None):
        self.landmark_predictor = landmark_predictor
        self.category_predictor = category_predictor
        self.logger = logger
        
        # Use ThreadPoolExecutor for I/O bound and model inference tasks
        self.max_workers = 2  # One for landmarks, one for category
        
    def log(self, message: str):
        """Log message to both console and logger if available"""
        print(f"[PARALLEL] {message}")
        if self.logger:
            self.logger.log(f"[PARALLEL] {message}")
    
    def predict_parallel(self, img: np.ndarray, image_url: str = "", received_category_id: int = 0) -> Tuple[Optional[np.ndarray], int, str, float]:
        """
        Execute landmark detection and category prediction in parallel
        
        Args:
            img: Image array for processing
            image_url: Image URL for logging purposes
            received_category_id: Optional received category ID for override
            
        Returns:
            Tuple of (landmarks, category_id, category_name, confidence)
        """
        self.log("Starting parallel prediction (landmarks + category)")
        start_time = time.time()
        
        # Use ThreadPoolExecutor for parallel execution
        with concurrent.futures.ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            
            # Submit both tasks simultaneously
            self.log("Submitting landmark detection task...")
            landmark_future = executor.submit(self._predict_landmarks_task, img)
            
            self.log("Submitting category prediction task...")
            category_future = executor.submit(self._predict_category_task, img)
            
            # Collect results as they complete
            results = {}
            
            # Wait for both tasks to complete
            for future in concurrent.futures.as_completed([landmark_future, category_future], timeout=30):
                try:
                    if future == landmark_future:
                        landmarks = future.result()
                        results['landmarks'] = landmarks
                        self.log(f"✅ Landmark detection completed: {landmarks.shape if landmarks is not None else 'None'}")
                    
                    elif future == category_future:
                        category_result = future.result()
                        results['category'] = category_result
                        category_id, category_name, confidence = category_result
                        self.log(f"✅ Category prediction completed: {category_name} (confidence: {confidence:.3f})")
                
                except Exception as e:
                    if future == landmark_future:
                        self.log(f"❌ Landmark detection failed: {e}")
                        results['landmarks'] = None
                    elif future == category_future:
                        self.log(f"❌ Category prediction failed: {e}")
                        results['category'] = (12, "sling dress", 0.0)  # Default fallback
        
        # Process results
        landmarks = results.get('landmarks')
        category_id, category_name, confidence = results.get('category', (12, "sling dress", 0.0))
        
        # Apply category ID override logic
        if received_category_id == 9:
            category_id = 9
        elif category_id == 0 and received_category_id in (1, 2):
            category_id = received_category_id
        
        total_time = time.time() - start_time
        self.log(f"Parallel prediction completed in {total_time:.3f}s")
        
        return landmarks, category_id, category_name, confidence
    
    def _predict_landmarks_task(self, img: np.ndarray) -> Optional[np.ndarray]:
        """
        Task wrapper for landmark detection
        """
        try:
            task_start = time.time()
            landmarks = self.landmark_predictor.predict_landmarks(img=img)
            task_time = time.time() - task_start
            self.log(f"Landmark detection task: {task_time:.3f}s")
            return landmarks
        except Exception as e:
            self.log(f"Landmark detection task failed: {e}")
            return None
    
    def _predict_category_task(self, img: np.ndarray) -> Tuple[int, str, float]:
        """
        Task wrapper for category prediction
        """
        try:
            task_start = time.time()
            category_id, category_name, confidence = self.category_predictor.predict_category(img)
            task_time = time.time() - task_start
            self.log(f"Category prediction task: {task_time:.3f}s")
            return category_id, category_name, confidence
        except Exception as e:
            self.log(f"Category prediction task failed: {e}")
            return 12, "sling dress", 0.0  # Default fallback
    
    def benchmark_parallel_vs_sequential(self, img: np.ndarray, num_runs: int = 3) -> dict:
        """
        Benchmark parallel vs sequential execution
        
        Args:
            img: Test image
            num_runs: Number of benchmark runs
            
        Returns:
            Performance comparison results
        """
        self.log(f"Benchmarking parallel vs sequential with {num_runs} runs")
        
        parallel_times = []
        sequential_times = []
        
        # Benchmark parallel execution
        for i in range(num_runs):
            start_time = time.time()
            self.predict_parallel(img)
            parallel_times.append(time.time() - start_time)
            self.log(f"Parallel run {i+1}/{num_runs}: {parallel_times[-1]:.3f}s")
        
        # Benchmark sequential execution  
        for i in range(num_runs):
            start_time = time.time()
            
            # Sequential: landmarks first, then category
            landmarks = self.landmark_predictor.predict_landmarks(img=img)
            category_id, category_name, confidence = self.category_predictor.predict_category(img)
            
            sequential_times.append(time.time() - start_time)
            self.log(f"Sequential run {i+1}/{num_runs}: {sequential_times[-1]:.3f}s")
        
        # Calculate statistics
        parallel_avg = np.mean(parallel_times)
        sequential_avg = np.mean(sequential_times)
        speedup = sequential_avg / parallel_avg
        time_saved = sequential_avg - parallel_avg
        
        results = {
            'parallel_avg_time': parallel_avg,
            'sequential_avg_time': sequential_avg,
            'speedup_factor': speedup,
            'time_saved_seconds': time_saved,
            'speedup_percentage': (speedup - 1) * 100,
            'parallel_times': parallel_times,
            'sequential_times': sequential_times
        }
        
        self.log(f"📊 Benchmark Results:")
        self.log(f"  Sequential avg: {sequential_avg:.3f}s")
        self.log(f"  Parallel avg: {parallel_avg:.3f}s")
        self.log(f"  Speedup: {speedup:.2f}x ({results['speedup_percentage']:.1f}% faster)")
        self.log(f"  Time saved: {time_saved:.3f}s per request")
        
        return results

# Global instance (will be initialized in API)
parallel_predictor = None 