#!/usr/bin/env python3
"""
Minimal Flask service for garment measuring API
This version starts without model dependencies for emergency deployment
"""

from flask import Flask, request, jsonify
import requests
import json
import os
from datetime import datetime
import traceback
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

app = Flask(__name__)

def log_message(message):
    """Simple logging function."""
    timestamp = datetime.utcnow().isoformat()
    print(f"[{timestamp}] {message}")

@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint."""
    return jsonify({
        "status": "healthy",
        "service": "garment-measuring-api",
        "version": "1.0.0",
        "timestamp": datetime.utcnow().isoformat()
    })

@app.route('/measurements', methods=['POST'])
@app.route('/process-garment', methods=['POST'])
@app.route('/full-analysis', methods=['POST'])
def process_garment():
    """
    Main endpoint for processing garment images.
    Returns a simple response for testing purposes.
    """
    try:
        log_message("Processing garment request")
        
        data = request.get_json()
        if not data or 'image_url' not in data:
            return jsonify({"error": "image_url is required"}), 400
        
        image_url = data['image_url']
        log_message(f"Processing image: {image_url}")
        
        # Simple response for testing
        return jsonify({
            "success": True,
            "message": "Service is working! Models will be integrated soon.",
            "original_image": image_url,
            "processing_timestamp": datetime.utcnow().isoformat(),
            "status": "minimal_service_active"
        })
        
    except Exception as e:
        error_msg = f"Error in process_garment: {str(e)}"
        log_message(f"ERROR: {error_msg}")
        return jsonify({"error": "Internal server error"}), 500

@app.route('/', methods=['GET'])
def root():
    """Root endpoint."""
    return jsonify({
        "service": "garment-measuring-api",
        "status": "running",
        "endpoints": ["/health", "/measurements", "/process-garment", "/full-analysis"]
    })

if __name__ == '__main__':
    port = int(os.getenv('PORT', 5003))
    print(f"🚀 Starting simple garment measuring API on port {port}")
    app.run(host='0.0.0.0', port=port, debug=False) 