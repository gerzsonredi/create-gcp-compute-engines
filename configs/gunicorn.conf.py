# Gunicorn configuration file
import multiprocessing
import os

# 🚀 OPTIMIZED FOR 4 CPU CORES + 8GB RAM

# Get available CPU count, but optimize for 4 cores in Cloud Run
cpu_count = int(os.getenv('CPU_COUNT', multiprocessing.cpu_count()))
print(f"Configuring gunicorn with {cpu_count} CPU cores")

# Worker configuration for 4 CPU cores + 8GB RAM
# With 8GB RAM, we can support more workers efficiently
workers = min(cpu_count, 4)  # Maximum 4 workers for 4 cores
worker_class = "sync"
worker_connections = 1000
max_requests = 1000
max_requests_jitter = 100
preload_app = True
timeout = 900  # 15 minutes for model loading
keepalive = 0  # Force connection close for better load balancing

# Memory optimization for 8GB RAM
worker_tmp_dir = "/dev/shm"  # Use shared memory for temp files

# Binding configuration - use Cloud Run PORT environment variable
port = int(os.getenv('PORT', 5003))  # Cloud Run sets PORT, fallback to 5003 for local
bind = f"0.0.0.0:{port}"
backlog = 2048

# Process naming
proc_name = "garment-measuring-api"

# Logging configuration
loglevel = "info"
accesslog = "-"  # stdout
errorlog = "-"   # stderr
access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s" %(D)s'

# Graceful timeout for shutdown
graceful_timeout = 120

# Enable automatic worker restarts for memory management
max_worker_memory = 2000000000  # 2GB per worker (with 8GB total)

# Environment variables
raw_env = [
    f"PYTHONPATH={os.getenv('PYTHONPATH', '/app')}",
    "OMP_NUM_THREADS=8",
    "MKL_NUM_THREADS=8",
]

def on_starting(server):
    server.log.info("🚀 Starting Garment Measuring API with optimized configuration")
    server.log.info(f"💾 Memory: 8GB | 🔧 CPU: 4 cores | 👥 Workers: {workers}")

def when_ready(server):
    server.log.info(f"Clothing Measurement API server ready with {workers} workers on {cpu_count} CPU cores")
    server.log.info(f"🔧 Configuration: 8GB RAM, 4 CPU cores, optimized for performance")

def worker_int(worker):
    worker.log.info("Worker received INT or QUIT signal")

def pre_fork(server, worker):
    server.log.info("Worker spawned (pid: %s)", worker.pid)

def post_fork(server, worker):
    server.log.info("Worker spawned (pid: %s)", worker.pid)

def worker_abort(worker):
    worker.log.info("Worker received SIGABRT signal")

def on_exit(server):
    server.log.info("Shutting down Garment Measuring API server")