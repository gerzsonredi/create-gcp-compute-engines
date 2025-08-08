#!/usr/bin/env python3
"""
Simple test service to verify deployment
"""

from flask import Flask, request, jsonify
from datetime import datetime
import traceback

app = Flask(__name__)

@app.route('/health', methods=['GET'])
def health_check():
    return jsonify({
        "status": "healthy",
        "service": "simple-test-service",
        "version": "1.0.0",
        "timestamp": datetime.utcnow().isoformat()
    })

@app.route('/test-analysis', methods=['POST'])
def test_analysis():
    try:
        data = request.get_json()
        if not data or 'image_url' not in data:
            return jsonify({"error": "image_url is required", "success": False}), 400
        
        image_url = data['image_url']
        
        return jsonify({
            "success": True,
            "message": "Test service is working!",
            "original_image": image_url,
            "processing_timestamp": datetime.utcnow().isoformat(),
            "test_mode": True,
            "status": "Service operational - models will be integrated next"
        })
        
    except Exception as e:
        return jsonify({
            "success": False,
            "error": "Test service error",
            "details": str(e),
            "traceback": traceback.format_exc()
        }), 500

@app.route('/', methods=['GET'])
def root():
    return jsonify({
        "service": "simple-test-service",
        "status": "running",
        "endpoints": ["/health", "/test-analysis"]
    })

if __name__ == '__main__':
    import os
    port = int(os.getenv('PORT', 5003))
    print(f"🚀 Starting simple test service on port {port}")
    app.run(host='0.0.0.0', port=port, debug=False) 