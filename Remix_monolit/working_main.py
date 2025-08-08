#!/usr/bin/env python3
"""
Working Flask service for garment measuring API
This version starts without problematic dependencies
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
        "timestamp": datetime.utcnow().isoformat(),
        "mode": "working_service"
    })

@app.route('/measurements', methods=['POST'])
@app.route('/process-garment', methods=['POST'])
@app.route('/full-analysis', methods=['POST'])
def process_garment():
    """
    Main endpoint for processing garment images.
    Currently returns REST API calls to external services.
    """
    try:
        log_message("Processing garment request")
        
        data = request.get_json()
        if not data or 'image_url' not in data:
            return jsonify({"error": "image_url is required"}), 400
        
        image_url = data['image_url']
        log_message(f"Processing image: {image_url}")
        
        # Get external service URLs from environment
        mannequin_url = os.getenv("MANNEQUIN_SEGMENTER_BASE_URL")
        category_url = os.getenv("CATEGORY_PREDICTOR_BASE_URL") 
        measuring_url = os.getenv("MEASURING_HPE_BASE_URL")
        
        results = {
            "success": True,
            "original_image": image_url,
            "processing_timestamp": datetime.utcnow().isoformat(),
            "status": "external_services_mode"
        }
        
        # Step 1: Category prediction via external service
        if category_url:
            try:
                log_message("Calling external category predictor...")
                response = requests.post(f"{category_url}/category", 
                                       json={"image_url": image_url}, 
                                       timeout=30)
                if response.status_code == 200:
                    results['category_prediction'] = response.json()
                    log_message("Category prediction successful")
                else:
                    results['category_error'] = f"HTTP {response.status_code}"
            except Exception as e:
                results['category_error'] = str(e)
                log_message(f"Category prediction failed: {e}")
        
        # Step 2: Mannequin segmentation via external service
        if mannequin_url:
            try:
                log_message("Calling external mannequin segmenter...")
                response = requests.post(f"{mannequin_url}/infer", 
                                       json={"image_url": image_url}, 
                                       timeout=60)
                if response.status_code == 200:
                    seg_result = response.json()
                    results['segmented_image'] = seg_result.get('visualization_url', image_url)
                    log_message("Mannequin segmentation successful")
                else:
                    results['segmentation_error'] = f"HTTP {response.status_code}"
                    results['segmented_image'] = image_url
            except Exception as e:
                results['segmentation_error'] = str(e)
                results['segmented_image'] = image_url
                log_message(f"Mannequin segmentation failed: {e}")
        
        # Step 3: Measurements via external service
        if measuring_url:
            try:
                log_message("Calling external measuring service...")
                segmented_url = results.get('segmented_image', image_url)
                response = requests.post(f"{measuring_url}/measurements", 
                                       json={
                                           "image_url": segmented_url,
                                           "category_id": 1,
                                           "bg_img_url": image_url
                                       }, 
                                       timeout=60)
                if response.status_code == 200:
                    results['measurements'] = response.json()
                    log_message("Measurements successful")
                else:
                    results['measurements_error'] = f"HTTP {response.status_code}"
            except Exception as e:
                results['measurements_error'] = str(e)
                log_message(f"Measurements failed: {e}")
        
        log_message("Processing completed")
        return jsonify(results)
        
    except Exception as e:
        error_msg = f"Error in process_garment: {str(e)}"
        log_message(f"ERROR: {error_msg}")
        return jsonify({"error": "Internal server error", "details": str(e)}), 500

@app.route('/', methods=['GET'])
def root():
    """Root endpoint."""
    return jsonify({
        "service": "garment-measuring-api",
        "status": "running",
        "mode": "external_services",
        "endpoints": ["/health", "/measurements", "/process-garment", "/full-analysis"]
    })

if __name__ == '__main__':
    port = int(os.getenv('PORT', 5003))
    print(f"🚀 Starting working garment measuring API on port {port}")
    app.run(host='0.0.0.0', port=port, debug=False) 