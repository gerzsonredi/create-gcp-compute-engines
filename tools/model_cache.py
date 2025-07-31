import pickle
import os
import hashlib
import time
from pathlib import Path
from typing import Any, Optional
import threading

class SharedModelCache:
    """
    Shared memory cache for ML models across multiple processes
    Avoids caching non-serializable objects like ONNX sessions
    """
    
    def __init__(self, cache_dir: str = "/tmp/model_cache", max_size_gb: float = 2.0):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(exist_ok=True)
        self.max_size_bytes = int(max_size_gb * 1024 * 1024 * 1024)
        self.lock = threading.Lock()
        
    def _get_cache_key(self, model_path: str, model_type: str) -> str:
        """Generate cache key from model path and type"""
        cache_str = f"{model_path}:{model_type}:{os.path.getmtime(model_path) if os.path.exists(model_path) else int(time.time())}"
        return hashlib.md5(cache_str.encode()).hexdigest()
    
    def _get_cache_file(self, cache_key: str) -> Path:
        """Get cache file path for given key"""
        return self.cache_dir / f"{cache_key}.cache"
    
    def _get_metadata_file(self, cache_key: str) -> Path:
        """Get metadata file path for given key"""
        return self.cache_dir / f"{cache_key}.meta"
    
    def _cleanup_old_caches(self):
        """Remove old cache files to stay within size limit"""
        cache_files = list(self.cache_dir.glob("*.cache"))
        if not cache_files:
            return
            
        # Sort by modification time (oldest first)
        cache_files.sort(key=lambda f: f.stat().st_mtime)
        
        total_size = sum(f.stat().st_size for f in cache_files)
        
        while total_size > self.max_size_bytes and cache_files:
            old_file = cache_files.pop(0)
            meta_file = old_file.with_suffix('.meta')
            
            try:
                size = old_file.stat().st_size
                old_file.unlink()
                if meta_file.exists():
                    meta_file.unlink()
                total_size -= size
                print(f"[CACHE] Removed old cache file: {old_file.name}")
            except OSError:
                pass
    
    def _filter_serializable(self, obj: Any) -> Any:
        """Filter out non-serializable objects from cache data"""
        if isinstance(obj, dict):
            filtered = {}
            for key, value in obj.items():
                try:
                    # Test if value is serializable
                    pickle.dumps(value)
                    filtered[key] = value
                except (pickle.PicklingError, TypeError) as e:
                    print(f"[CACHE] Skipping non-serializable object {key}: {type(value).__name__}")
            return filtered
        else:
            try:
                pickle.dumps(obj)
                return obj
            except (pickle.PicklingError, TypeError):
                print(f"[CACHE] Cannot serialize object of type: {type(obj).__name__}")
                return None
    
    def put(self, model_path: str, model_type: str, model_object: Any) -> bool:
        """
        Store model in shared cache
        
        Args:
            model_path: Path to model file
            model_type: Type of model (e.g., 'hrnet', 'category_predictor')
            model_object: The model object to cache
            
        Returns:
            True if successfully cached, False otherwise
        """
        cache_key = self._get_cache_key(model_path, model_type)
        cache_file = self._get_cache_file(cache_key)
        meta_file = self._get_metadata_file(cache_key)
        
        try:
            with self.lock:
                # Filter out non-serializable objects
                filtered_object = self._filter_serializable(model_object)
                
                if filtered_object is None:
                    print(f"[CACHE] Cannot cache {model_type}: no serializable data")
                    return False
                
                # Serialize model
                serialized_data = pickle.dumps(filtered_object)
                
                # Check if we have space
                if len(serialized_data) > self.max_size_bytes:
                    print(f"[CACHE] Model too large to cache: {len(serialized_data)} bytes")
                    return False
                
                # Cleanup old caches if needed  
                self._cleanup_old_caches()
                
                # Write cache file
                with open(cache_file, 'wb') as f:
                    f.write(serialized_data)
                
                # Write metadata
                metadata = {
                    'model_path': model_path,
                    'model_type': model_type,
                    'cache_key': cache_key,
                    'cached_at': time.time(),
                    'size_bytes': len(serialized_data),
                    'process_id': os.getpid()
                }
                
                with open(meta_file, 'wb') as f:
                    pickle.dump(metadata, f)
                
                print(f"[CACHE] Cached {model_type} model: {len(serialized_data)/1024/1024:.1f}MB")
                return True
                
        except Exception as e:
            print(f"[CACHE] Failed to cache model: {e}")
            return False
    
    def get(self, model_path: str, model_type: str) -> Optional[Any]:
        """
        Retrieve model from shared cache
        
        Args:
            model_path: Path to model file
            model_type: Type of model
            
        Returns:
            Model object if found, None otherwise
        """
        cache_key = self._get_cache_key(model_path, model_type)
        cache_file = self._get_cache_file(cache_key)
        meta_file = self._get_metadata_file(cache_key)
        
        if not cache_file.exists() or not meta_file.exists():
            return None
        
        try:
            # Check if cache is still valid
            with open(meta_file, 'rb') as f:
                metadata = pickle.load(f)
            
            # Load cached model
            with open(cache_file, 'rb') as f:
                model_object = pickle.load(f)
            
            print(f"[CACHE] Loaded {model_type} from cache: {metadata['size_bytes']/1024/1024:.1f}MB")
            return model_object
            
        except Exception as e:
            print(f"[CACHE] Failed to load cached model: {e}")
            # Remove corrupted cache
            try:
                cache_file.unlink()
                meta_file.unlink()
            except:
                pass
            return None
    
    def exists(self, model_path: str, model_type: str) -> bool:
        """Check if model exists in cache"""
        cache_key = self._get_cache_key(model_path, model_type)
        cache_file = self._get_cache_file(cache_key)
        return cache_file.exists()
    
    def clear(self):
        """Clear all cached models"""
        with self.lock:
            for cache_file in self.cache_dir.glob("*.cache"):
                cache_file.unlink()
            for meta_file in self.cache_dir.glob("*.meta"):
                meta_file.unlink()
            print("[CACHE] Cleared all cached models")
    
    def get_stats(self) -> dict:
        """Get cache statistics"""
        cache_files = list(self.cache_dir.glob("*.cache"))
        total_size = sum(f.stat().st_size for f in cache_files)
        
        return {
            'cache_count': len(cache_files),
            'total_size_mb': total_size / 1024 / 1024,
            'max_size_gb': self.max_size_bytes / 1024 / 1024 / 1024,
            'utilization_percent': (total_size / self.max_size_bytes) * 100 if self.max_size_bytes > 0 else 0
        }

# Global cache instance
model_cache = SharedModelCache() 