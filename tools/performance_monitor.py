import time
import functools
from contextlib import contextmanager
from typing import Dict, List, Optional
import threading
from collections import defaultdict
import psutil
import os

class PerformanceMonitor:
    """
    Performance monitoring utility to track timing of subtasks and overall performance
    """
    def __init__(self, logger=None):
        self.logger = logger
        self.timings: Dict[str, List[float]] = defaultdict(list)
        self.current_session: Dict[str, float] = {}
        self.cpu_usage: Dict[str, float] = {}
        self.memory_usage: Dict[str, float] = {}
        self.lock = threading.Lock()
        self.process = psutil.Process(os.getpid())
        
    def log(self, message: str):
        """Log message to both console and logger if available"""
        print(f"[PERF] {message}")
        if self.logger:
            self.logger.log(f"[PERF] {message}")
    
    @contextmanager
    def timer(self, task_name: str):
        """Context manager to time a specific task and monitor resource usage"""
        start_time = time.time()
        start_cpu = self.process.cpu_percent()
        start_memory = self.process.memory_info().rss / 1024 / 1024  # MB
        
        self.log(f"Starting task: {task_name}")
        try:
            yield
        finally:
            end_time = time.time()
            end_cpu = self.process.cpu_percent()
            end_memory = self.process.memory_info().rss / 1024 / 1024  # MB
            
            duration = end_time - start_time
            cpu_usage = (start_cpu + end_cpu) / 2  # Average CPU usage
            memory_delta = end_memory - start_memory
            
            with self.lock:
                self.timings[task_name].append(duration)
                self.current_session[task_name] = duration
                self.cpu_usage[task_name] = cpu_usage
                self.memory_usage[task_name] = memory_delta
                
            self.log(f"Completed task: {task_name} in {duration:.3f}s "
                    f"(CPU: {cpu_usage:.1f}%, Memory Δ: {memory_delta:+.1f}MB)")
    
    def time_function(self, task_name: str):
        """Decorator to time function execution"""
        def decorator(func):
            @functools.wraps(func)
            def wrapper(*args, **kwargs):
                with self.timer(task_name):
                    return func(*args, **kwargs)
            return wrapper
        return decorator
    
    def get_system_info(self) -> Dict:
        """Get current system resource information"""
        return {
            'cpu_count': psutil.cpu_count(),
            'cpu_percent': psutil.cpu_percent(interval=0.1),
            'memory_total_gb': psutil.virtual_memory().total / 1024 / 1024 / 1024,
            'memory_available_gb': psutil.virtual_memory().available / 1024 / 1024 / 1024,
            'memory_percent': psutil.virtual_memory().percent,
            'process_memory_mb': self.process.memory_info().rss / 1024 / 1024,
            'process_cpu_percent': self.process.cpu_percent()
        }
    
    def get_stats(self, task_name: str = None) -> Dict:
        """Get performance statistics for a specific task or all tasks"""
        with self.lock:
            if task_name:
                if task_name in self.timings:
                    times = self.timings[task_name]
                    return {
                        'task': task_name,
                        'count': len(times),
                        'total_time': sum(times),
                        'avg_time': sum(times) / len(times),
                        'min_time': min(times),
                        'max_time': max(times),
                        'last_time': times[-1] if times else 0,
                        'avg_cpu_usage': self.cpu_usage.get(task_name, 0),
                        'memory_delta': self.memory_usage.get(task_name, 0)
                    }
                return None
            
            # Return stats for all tasks
            stats = {}
            for task, times in self.timings.items():
                stats[task] = {
                    'count': len(times),
                    'total_time': sum(times),
                    'avg_time': sum(times) / len(times),
                    'min_time': min(times),
                    'max_time': max(times),
                    'last_time': times[-1] if times else 0,
                    'avg_cpu_usage': self.cpu_usage.get(task, 0),
                    'memory_delta': self.memory_usage.get(task, 0)
                }
            return stats
    
    def get_current_session_summary(self) -> Dict:
        """Get timing summary for the current processing session"""
        with self.lock:
            total_time = sum(self.current_session.values())
            summary = {
                'total_session_time': total_time,
                'subtasks': self.current_session.copy(),
                'subtask_percentages': {},
                'cpu_usage': self.cpu_usage.copy(),
                'memory_usage': self.memory_usage.copy(),
                'system_info': self.get_system_info()
            }
            
            if total_time > 0:
                for task, time_taken in self.current_session.items():
                    summary['subtask_percentages'][task] = (time_taken / total_time) * 100
            
            return summary
    
    def reset_session(self):
        """Reset current session timings"""
        with self.lock:
            self.current_session.clear()
            self.cpu_usage.clear()
            self.memory_usage.clear()
    
    def print_performance_report(self):
        """Print detailed performance report"""
        stats = self.get_stats()
        session = self.get_current_session_summary()
        
        self.log("=" * 80)
        self.log("PERFORMANCE REPORT")
        self.log("=" * 80)
        
        # System information
        sys_info = session['system_info']
        self.log(f"System: {sys_info['cpu_count']} CPUs, "
                f"{sys_info['memory_total_gb']:.1f}GB RAM, "
                f"CPU: {sys_info['cpu_percent']:.1f}%, "
                f"Memory: {sys_info['memory_percent']:.1f}%")
        self.log("-" * 80)
        
        # Current session summary
        if session['subtasks']:
            self.log(f"Current Session Total Time: {session['total_session_time']:.3f}s")
            self.log("-" * 80)
            self.log(f"{'Task':<25} {'Time':<10} {'%':<7} {'CPU%':<7} {'Mem MB':<8}")
            self.log("-" * 80)
            for task, time_taken in session['subtasks'].items():
                percentage = session['subtask_percentages'].get(task, 0)
                cpu_usage = session['cpu_usage'].get(task, 0)
                memory_delta = session['memory_usage'].get(task, 0)
                self.log(f"{task:<25} {time_taken:>8.3f}s {percentage:>5.1f}% "
                        f"{cpu_usage:>5.1f}% {memory_delta:>+6.1f}")
            self.log("-" * 80)
        
        # Overall statistics
        self.log("Overall Statistics:")
        for task, stat in stats.items():
            self.log(f"{task:<25} - Avg: {stat['avg_time']:.3f}s, Count: {stat['count']}, "
                    f"CPU: {stat['avg_cpu_usage']:.1f}%, Memory: {stat['memory_delta']:+.1f}MB")
        
        self.log("=" * 80)

# Global performance monitor instance
perf_monitor = PerformanceMonitor() 