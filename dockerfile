# Use Python 3.9 as base image
FROM python:3.9-slim

# Set working directory
WORKDIR /app

# Install system dependencies for OpenCV, TurboJPEG, and build tools
RUN apt-get update && apt-get install -y \
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
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies including optimization packages
RUN pip install flask yacs boto3 pillow requests gunicorn psutil==5.9.5 && \
    pip install --default-timeout=600 torch torchvision transformers && \
    pip install onnx onnxruntime onnxruntime-tools && \
    pip install PyTurboJPEG

# Install HRNet specific dependencies directly
RUN pip install --no-cache-dir \
    opencv-python \
    scipy \
    matplotlib \
    easydict \
    tensorboardX \
    Cython \
    pycocotools

# 🚀 COPY HRNet DIRECTORY FIRST (CRITICAL FIX!)
COPY HRNet/ /app/HRNet/

# Copy application files
COPY tools/ /app/tools/
COPY configs/ /app/configs/
COPY api_app.py /app/

# Create necessary directories
RUN mkdir -p /app/artifacts

# Set environment variables for optimization
ENV PYTHONPATH=/app
ENV OMP_NUM_THREADS=4
ENV MKL_NUM_THREADS=4

# Expose port
EXPOSE 5003

# Start the application with gunicorn
CMD ["gunicorn", "--config", "configs/gunicorn.conf.py", "api_app:app"]