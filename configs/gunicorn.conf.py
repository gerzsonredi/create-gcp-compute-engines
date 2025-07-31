# Gunicorn configuration file
import multiprocessing
import os

# Server socket
bind = "0.0.0.0:5003"
backlog = 2048

# Worker processes - Updated to use multiple cores
cpu_count = multiprocessing.cpu_count()
workers = min(cpu_count, 8)  # Use up to 8 workers to balance memory usage
print(f"Configuring gunicorn with {workers} workers for {cpu_count} CPU cores")

worker_class = "sync"
worker_connections = 1000
timeout = 600  # 10 minutes for model inference (increased for CPU processing)
keepalive = 5

# Restart workers after fewer requests to prevent memory buildup
max_requests = 50  # Reduced to prevent memory issues with multiple workers
max_requests_jitter = 10

# Logging
accesslog = "-"  # Log to stdout
errorlog = "-"   # Log to stderr
loglevel = "info"
access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s" %(D)s [Worker: %(p)s]'

# Process naming
proc_name = "clothing-measurement-api"

# Server mechanics
daemon = False
pidfile = None
tmp_upload_dir = None

# Worker timeout for graceful shutdown
graceful_timeout = 60

# Preload application for better memory usage (disabled for model loading)
preload_app = False

# Environment variables
raw_env = [
    f"PYTHONPATH={os.getenv('PYTHONPATH', '/app')}",
    f"OMP_NUM_THREADS=2",  # Limit OpenMP threads per worker
    f"MKL_NUM_THREADS=2",  # Limit MKL threads per worker
]

def when_ready(server):
    server.log.info(f"Clothing Measurement API server ready with {workers} workers on {cpu_count} CPU cores")

def worker_int(worker):
    worker.log.info("Worker received INT or QUIT signal")

def pre_fork(server, worker):
    server.log.info("Worker spawned (pid: %s)", worker.pid)

def post_fork(server, worker):
    server.log.info("Worker spawned (pid: %s)", worker.pid)

def worker_abort(worker):
    worker.log.info("Worker received SIGABRT signal")