# Use Python 3.9 as base image
FROM python:3.9-slim

# Set working directory
WORKDIR /app

# Install system dependencies for OpenCV and other libraries
RUN apt-get update && apt-get install -y \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    libgomp1 \
    libgl1-mesa-glx \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements files
COPY HRNet/requirements.txt /app/hrnet_requirements.txt

# Install Python dependencies
RUN pip install flask yacs boto3 pillow requests gunicorn && \
    pip install --default-timeout=600 torch torchvision

RUN pip install --no-cache-dir -r hrnet_requirements.txt

# Copy the entire application
COPY . /app/

# Create necessary directories if they don't exist
RUN mkdir -p /app/artifacts /app/tools /app/HRNet

# Set environment variables
ENV PYTHONPATH=/app
ENV FLASK_APP=api_app.py
ENV FLASK_RUN_HOST=0.0.0.0
ENV FLASK_RUN_PORT=5000

# Expose the port the app runs on
EXPOSE 5000

# Command to run the application
CMD ["gunicorn", "--config", "configs/gunicorn.conf.py", "api_app:app"]