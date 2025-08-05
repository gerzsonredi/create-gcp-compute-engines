# 🚀 OPTIMIZED DOCKERFILE FOR FASTER BUILDS
# Pin exact Python version for cache stability
FROM python:3.9.21-slim

# Set working directory
WORKDIR /app

# 📦 INSTALL SYSTEM DEPENDENCIES (cached layer)
# Combine all apt operations for better caching
RUN apt-get update && apt-get install -y --no-install-recommends \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    libgomp1 \
    libgl1-mesa-glx \
    gcc \
    python3-dev \
    libjpeg-dev \
    zlib1g-dev \
    libturbojpeg0-dev \
    libturbojpeg0 \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*

# 🏗️ COPY REQUIREMENTS FIRST (for better caching)
COPY requirements.txt /app/requirements.txt

# Install Python dependencies (well-cached layer)
RUN pip install --no-cache-dir -r requirements.txt

# 📁 COPY APPLICATION FILES (most frequently changed - at the end)
# Copy HRNet first (changes less frequently)
COPY HRNet/ /app/HRNet/

# Copy tools (medium frequency changes)
COPY tools/ /app/tools/

# Copy configs and main app (most frequent changes)
COPY configs/ /app/configs/
COPY api_app.py /app/

# Create necessary directories
RUN mkdir -p /app/artifacts /app/logs

# 🔧 ENVIRONMENT VARIABLES
ENV PYTHONPATH=/app \
    PYTHONUNBUFFERED=1 \
    OMP_NUM_THREADS=8 \
    MKL_NUM_THREADS=8 \
    PYTHONDONTWRITEBYTECODE=1

# Expose port (Cloud Run will set PORT environment variable dynamically)
EXPOSE 8080

# Start the application with gunicorn - explicit port binding for Cloud Run  
CMD ["sh", "-c", "gunicorn --bind 0.0.0.0:${PORT:-8080} --workers 1 api_app:app"]