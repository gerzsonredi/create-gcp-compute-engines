from flask import Flask, request, jsonify
import requests
import json
from datetime import datetime
import traceback
import os
from dotenv import load_dotenv
from category_mapper import CategoryMapper
from pdf_generator import create_batch_report_from_image_groups
import base64
from pathlib import Path
from natsort import os_sorted, ns, natsorted   

# Load environment variables
load_dotenv()

app = Flask(__name__)
mapper = CategoryMapper()

# Microservice configurations
SERVICES = {
    'mannequin_segmenter': {
        'host': os.getenv('MANNEQUIN_SEGMENTER_HOST', '127.0.0.1'),
        'port': os.getenv('MANNEQUIN_SEGMENTER_PORT', '5001'),
        'endpoints': {
            'infer': '/infer',
            'health': '/health'
        }
    },
    'category_predictor': {
        'host': os.getenv('CATEGORY_PREDICTOR_HOST', '127.0.0.1'),
        'port': os.getenv('CATEGORY_PREDICTOR_PORT', '5002'),
        'endpoints': {
            'category': '/category',
            'health': '/health'
        }
    },
    'measuring_hpe': {
        'host': os.getenv('MEASURING_HPE_HOST', '127.0.0.1'),
        'port': os.getenv('MEASURING_HPE_PORT', '5003'),
        'endpoints': {
            'landmarks': '/landmarks',
            'measurements': '/measurements',
            'health': '/health',
            'get_category': '/get_category',
            'upload_image': '/upload_image'
        }
    },
    'attribute_predictor': {
        'host': os.getenv('ATTRIBUTE_PREDICTOR_HOST', '127.0.0.1'),
        'port': os.getenv('ATTRIBUTE_PREDICTOR_PORT', '5004'),
        'endpoints': {
            'condition': '/condition',
            'health': '/health',
            'get_attributes': '/get_attributes'
        }
    }
}

def get_service_url(service_name, endpoint):
    """Construct the full URL for a microservice endpoint."""
    service = SERVICES[service_name]
    return f"http://{service['host']}:{service['port']}{service['endpoints'][endpoint]}"

def log_message(message):
    """Simple logging function."""
    timestamp = datetime.utcnow().isoformat()
    print(f"[{timestamp}] MAIN_API: {message}")

def call_microservice(service_name, endpoint, data=None, method='POST', timeout=300):
    """Make a request to a microservice with error handling."""
    try:
        url = get_service_url(service_name, endpoint)
        log_message(f"Calling {service_name} at {url}")
        
        if method == 'GET':
            response = requests.get(url, timeout=timeout)
        else:
            response = requests.post(url, json=data, timeout=timeout)
        
        response.raise_for_status()
        return response.json(), None
        
    except requests.exceptions.Timeout:
        error_msg = f"Timeout calling {service_name}/{endpoint}"
        log_message(f"ERROR: {error_msg}")
        return None, error_msg
    except requests.exceptions.ConnectionError:
        error_msg = f"Connection error calling {service_name}/{endpoint} - service may be down"
        log_message(f"ERROR: {error_msg}")
        return None, error_msg
    except requests.exceptions.HTTPError as e:
        error_msg = f"HTTP error calling {service_name}/{endpoint}: {e.response.status_code}"
        log_message(f"ERROR: {error_msg}")
        return None, error_msg
    except Exception as e:
        error_msg = f"Unexpected error calling {service_name}/{endpoint}: {str(e)}"
        log_message(f"ERROR: {error_msg}")
        return None, error_msg

@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint that also checks all microservices."""
    log_message("Health check requested")
    
    main_status = {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "service": "main-orchestrator",
        "version": "1.0.0"
    }
    
    # Check all microservices
    services_status = {}
    for service_name in SERVICES.keys():
        try:
            result, error = call_microservice(service_name, 'health', method='GET', timeout=10)
            if error:
                services_status[service_name] = {"status": "unhealthy", "error": error}
            else:
                services_status[service_name] = {"status": "healthy", "response": result}
        except Exception as e:
            services_status[service_name] = {"status": "unhealthy", "error": str(e)}
    
    return jsonify({
        "main": main_status,
        "microservices": services_status
    }), 200

@app.route('/process-garment', methods=['POST'])
def process_garment():
    """
    Main pipeline endpoint that processes a garment image through the full pipeline:
    1. Remove mannequin
    2. Get measurements with landmarks
    """
    try:
        log_message("Starting garment processing pipeline")
        
        # Parse request
        data = request.get_json()
        if not data or 'image_url' not in data:
            return jsonify({"error": "image_url is required"}), 400
        
        image_url = data['image_url']
        category_id = data.get('category_id', 1)  # Default to category 1
        
        log_message(f"Processing image: {image_url}")
        
        # Step 1: Remove mannequin
        log_message("Step 1: Removing mannequin...")
        segmenter_data = {"image_url": image_url}
        segmenter_result, error = call_microservice('mannequin_segmenter', 'infer', segmenter_data)
        
        if error:
            return jsonify({"error": f"Mannequin segmentation failed: {error}"}), 500
        
        if not segmenter_result or 'visualization_url' not in segmenter_result:
            return jsonify({"error": "Mannequin segmentation did not return visualization_url"}), 500
        
        segmented_image_url = segmenter_result['visualization_url']
        log_message(f"Mannequin removed, segmented image: {segmented_image_url}")
        
        # Step 2: Get measurements
        log_message("Step 2: Getting measurements...")
        measurements_data = {
            "image_url": segmented_image_url,
            "category_id": category_id
        }
        measurements_result, error = call_microservice('measuring_hpe', 'measurements', measurements_data)
        
        if error:
            return jsonify({"error": f"Measurements failed: {error}"}), 500
        
        if not measurements_result or not measurements_result.get('success'):
            error_msg = measurements_result.get('error', 'Unknown error') if measurements_result else 'No response'
            return jsonify({"error": f"Measurements failed: {error_msg}"}), 500
        
        log_message("Pipeline completed successfully")
        
        # Return comprehensive result
        return jsonify({
            "success": True,
            "pipeline_steps": {
                "1_original_image": image_url,
                "2_segmented_image": segmented_image_url,
                "3_measurements_image": measurements_result.get('url'),
            },
            "measurements": measurements_result.get('measurements'),
            "category_id": category_id,
            "processing_timestamp": datetime.utcnow().isoformat()
        })
        
    except Exception as e:
        error_msg = f"Unexpected error in garment processing pipeline: {str(e)}"
        log_message(f"ERROR: {error_msg}")
        log_message(f"Traceback: {traceback.format_exc()}")
        return jsonify({"error": "Internal server error"}), 500

@app.route('/predict-category', methods=['POST'])
def predict_category():
    """Endpoint to predict garment category."""
    try:
        log_message("Category prediction requested")
        
        data = request.get_json()
        if not data or 'image_url' not in data:
            return jsonify({"error": "image_url is required"}), 400
        
        result, error = call_microservice('category_predictor', 'category', data)
        
        if error:
            return jsonify({"error": f"Category prediction failed: {error}"}), 500
            
        return jsonify(result)
        
    except Exception as e:
        error_msg = f"Unexpected error in category prediction: {str(e)}"
        log_message(f"ERROR: {error_msg}")
        return jsonify({"error": "Internal server error"}), 500

@app.route('/predict-condition', methods=['POST'])
def predict_condition():
    """Endpoint to predict garment condition."""
    try:
        log_message("Condition prediction requested")
        
        data = request.get_json()
        if not data or 'image_urls' not in data:
            return jsonify({"error": "image_urls list is required"}), 400
        
        result, error = call_microservice('attribute_predictor', 'condition', data)
        
        if error:
            return jsonify({"error": f"Condition prediction failed: {error}"}), 500
            
        return jsonify(result)
        
    except Exception as e:
        error_msg = f"Unexpected error in condition prediction: {str(e)}"
        log_message(f"ERROR: {error_msg}")
        return jsonify({"error": "Internal server error"}), 500

@app.route('/get-landmarks', methods=['POST'])
def get_landmarks():
    """Endpoint to get garment landmarks only."""
    try:
        log_message("Landmarks prediction requested")
        
        data = request.get_json()
        if not data or ('image_url' not in data and 'image_path' not in data):
            return jsonify({"error": "image_url or image_path is required"}), 400
        
        result, error = call_microservice('measuring_hpe', 'landmarks', data)
        
        if error:
            return jsonify({"error": f"Landmarks prediction failed: {error}"}), 500
            
        return jsonify(result)
        
    except Exception as e:
        error_msg = f"Unexpected error in landmarks prediction: {str(e)}"
        log_message(f"ERROR: {error_msg}")
        return jsonify({"error": "Internal server error"}), 500

@app.route('/full-analysis', methods=['POST'])
def full_analysis():
    """
    Complete garment analysis pipeline:
    1. Remove mannequin
    2. Predict category
    3. Get measurements
    4. Predict condition (if multiple images provided)
    """
    try:
        log_message("Starting full garment analysis pipeline")
        
        data = request.get_json()
        if not data or 'image_url' not in data:
            return jsonify({"error": "image_url is required"}), 400
        
        image_url = data['image_url'].replace("\\", "")
        additional_image_urls = data.get('additional_image_urls', [])
        
        results = {
            "success": True,
            "original_image": image_url,
            "processing_timestamp": datetime.utcnow().isoformat()
        }
        
        # Step 1: Predict category
        log_message("Step 1: Predicting category...")
        category_result, error = call_microservice('category_predictor', 'category', {"image_url": image_url})
        if error:
            log_message(f"Category prediction failed: {error}, continuing with default category")
            category_id = -1
        else:
            results['category_prediction'] = category_result
            # Extract category_id from top prediction if available
            if category_result.get('success') and category_result.get('topx'):
                # category_id = category_result['topx'][0].get('category_id', 1)
                category_names = category_result['topx']

                log_message(f"Got category names: {category_names}")
                category_id = mapper.get_category_id(category_name=category_names[0][0])
                log_message(f"Determined category_id: {category_id}")
            else:
                category_id = 1
                log_message("Using default category_id: 1")
        
        # log_message("Step 1.1: Predicting DeepFashion2 category...")
        # deepf_cat_res, error = call_microservice('measuring_hpe', 'get_category', {'image_url': image_url})
        # if error:
        #     log_message(f"DeepFashion2 category prediction failed: {error}, continuing with default settings")
        #     skip_mannequin_removal = False
        # else:
        #     skip_mannequin_removal = False
        #     if deepf_cat_res == 13:
        #         log_message("DeepFashion2 category predictor predicted sling dress! Skipping mannequin removal!")
        #         skip_mannequin_removal = True
        
        skip_categories = ["calvin", "belts", "other", "scarfs", "swimwear", "socks", "hats", "backpacks", "gloves", "unbranded", "tommy", "sorel", "graceland", "adidas", "swiss"]
        for category_list in category_names:
            if category_list[0].lower() == "underwear" and category_list[1] > 0.1:
                log_message(f"Category {category_list[0].lower()} does not require measurements")
                results['measurements'] = {"message": "Measurements not applicable for this category"}
                return jsonify(results)
            if category_list[0].lower() in skip_categories:
        # if any(category[0][0].lower() in skip_categories for category in category_names):
                log_message(f"Category {category_list[0].lower()} in {category_names} does not require measurements")
                results['measurements'] = {"message": "Measurements not applicable for this category"}
                return jsonify(results)
        
        # Step 2: Remove mannequin
        skip_mannequin_removal = False
        if not skip_mannequin_removal:
            log_message("Step 2: Removing mannequin...")
            segmenter_result, error = call_microservice('mannequin_segmenter', 'infer', {"image_url": image_url})
            if error:
                return jsonify({"error": f"Mannequin segmentation failed: {error}"}), 500
            segmented_image_url = segmenter_result.get('visualization_url')
            log_message(f"Mannequin segmenter succesful: {segmented_image_url}")
            results['segmented_image'] = segmented_image_url
        else:
            segmented_image_url = image_url
            log_message("Skipping mannequin removal!")
        # Step 3: Get measurements
        log_message("Step 3: Getting measurements...")
        print(f"{category_id=}")
        measurements_result, error = call_microservice('measuring_hpe', 'measurements', {
            "image_url": segmented_image_url,
            "category_id": category_id,
            "bg_img_url": image_url
        })
        if error:
            log_message(f"Measurements failed: {error}")
            results['measurements_error'] = error
        else:
            results['measurements'] = measurements_result
        
        # # Step 4: Predict condition (if additional images provided)
        # if additional_image_urls:
        #     log_message("Step 4: Predicting condition...")
        #     all_images = [image_url] + additional_image_urls
        #     condition_result, error = call_microservice('attribute_predictor', 'condition', {"image_urls": all_images})
        #     if error:
        #         log_message(f"Condition prediction failed: {error}")
        #         results['condition_error'] = error
        #     else:
        #         results['condition_prediction'] = condition_result
        
        # log_message("Full analysis pipeline completed")

        return jsonify(results)
        
    except Exception as e:
        error_msg = f"Unexpected error in full analysis pipeline: {str(e)}"
        log_message(f"ERROR: {error_msg}")
        return jsonify({"error": "Internal server error"}), 500

@app.route('/batch-analysis', methods=['POST'])
def batch_analysis():
    """
    Endpoint to process multiple garments and create a batch PDF report.
    Expects: {"garment_groups": [["img1.jpg"], ["img2.jpg", "img3.jpg"], ...]}
    """
    try:
        data = request.get_json()
        if not data :
            log_message("data is required")
            return jsonify({"error": "data is required"}), 400
        elif 'garment_groups' not in data:
            log_message("garment_groups is required")
            return jsonify({"error": "garment_groups is required"}), 400
        
        garment_groups = data['garment_groups']
        output_filename = data.get('output_filename', f"batch_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf")
        
        # Create the batch report
        pdf_path = create_batch_report_from_image_groups(
            garment_groups,
            output_filename=f"reports/{output_filename}",
            api_base_url="http://localhost:5000"
        )
        
        if pdf_path:
            host_path = f"./reports/{os.path.basename(pdf_path)}"
            return jsonify({
                "success": True,
                "pdf_path": pdf_path,  # Container path
                "host_path": host_path,  # Host path for easy access
                "processed_garments": len(garment_groups),
                "timestamp": datetime.utcnow().isoformat()
            })
        else:
            log_message("Failed to create batch report")
            return jsonify({"error": "Failed to create batch report"}), 500
    
    except Exception as e:
        log_message(str(e))
        return jsonify({"error": str(e)}), 500

@app.route('/full-analysis_cws', methods=['POST'])
def full_analysis_cws():
    """
    Perform full analysis for CWS.
    Steps:
        1. Upload every image so that we can work with a public url. 
        2. Get measurements based on the first image.
        3. Get all other attributes.
    """
    try:
        log_message("Starting full garment analysis pipeline for CWS")
            
        data = request.get_json()
        if not data or 'image_path' not in data:
            return jsonify({"error": "image_path is required"}), 400
        
        image_path = data['image_path'].replace("\\", "")
        additional_image_paths = data.get('additional_image_paths', [])
        success = True
        results = {
            "processing_timestamp": datetime.utcnow().isoformat()
        }

        # 1st step
        # Read image and convert to base64
        print("1st step getting image urls...")
        try:
            with open(image_path, 'rb') as img_file:
                img_bytes = img_file.read()
                img_base64 = base64.b64encode(img_bytes).decode('utf-8')
        except Exception as e:
            error_msg = f"Failed to read and encode image: {str(e)}"
            log_message(f"ERROR: {error_msg}")
            return jsonify({"error": error_msg}), 500
        
        image_url, error = call_microservice('measuring_hpe', 'upload_image', {
            'image_data': img_base64,
            'CWS': 1
        })

        if error:
            log_message("Image upload failed!")
            log_message(error)
            results['image_url'] = "Failed"
            success = False
        else:
            main_image = image_url['image_url']
            results['image_url'] = main_image
        
        additional_urls = []
        for add_im in additional_image_paths:
            # Read image and convert to base64
            try:
                with open(add_im, 'rb') as img_file:
                    img_bytes = img_file.read()
                    img_base64 = base64.b64encode(img_bytes).decode('utf-8')
            except Exception as e:
                error_msg = f"Failed to read and encode image: {str(e)}"
                log_message(f"ERROR: {error_msg}")
                continue
            
            image_url, error = call_microservice('measuring_hpe', 'upload_image', {
                'image_data': img_base64,
                'CWS': 1
            })

            if error:
                log_message(f"Image upload failed for: {add_im}")
            else:
                additional_urls.append(image_url['image_url'])
            
        results['additional_image_urls'] = additional_urls

        # 2nd step
        # Call garment attribute predictor
        print("2nd step, getting attributes...")
        all_ims = [main_image]
        all_ims.extend(additional_urls)

        attributes, error = call_microservice('attribute_predictor', 'get_attributes', {
            'image_urls': all_ims
        })

        if error:
            log_message("Attribute prediction failed!")
            log_message(error)
            results['attributes'] = "Failed"
            success = False
        else:
            results['attributes'] = attributes

        
        results['success'] = success

        # 3rd step
        # call measuring hpe
        log_message("3rd step, calling measurin hpe")
        measurements_result, error = call_microservice('measuring_hpe', 'measurements', {
            "image_url": main_image
        })
        if error:
            log_message(f"Measurements failed: {error}")
            results['measurements_error'] = error
        else:
            results['measurements'] = measurements_result
        
        
        return jsonify(results)
        

    except Exception as e:
        error_msg = f"Unexpected error in full analysis pipeline for CWS: {str(e)}"
        log_message(f"ERROR: {error_msg}")
        return jsonify({"error": "Internal server error"}), 500

@app.route('/full-analysis_romanian', methods=['POST']) 
def full_analysis_romanian():
    try:
        log_message("Starting full garment analysis pipeline for CWS")
            
        data = request.get_json()
        if not data or 'image_paths' not in data:
            return jsonify({"error": "image_paths is required"}), 400
        
        image_paths = data.get('image_paths')

        success = True
        results = {
            "processing_timestamp": datetime.utcnow().isoformat()
        }

        log_message("1st step getting image urls...")
        image_urls = []
        for image_path in image_paths:
            # Read image and convert to base64
            try:
                with open(image_path, 'rb') as img_file:
                    img_bytes = img_file.read()
                    img_base64 = base64.b64encode(img_bytes).decode('utf-8')
            except Exception as e:
                error_msg = f"Failed to read and encode image: {str(e)}"
                log_message(f"ERROR: {error_msg}")
                continue
            
            image_url, error = call_microservice('measuring_hpe', 'upload_image', {
                'image_data': img_base64,
                'CWS': 1
            })

            if error:
                log_message(f"Image upload failed for: {image_path}")
            else:
                image_urls.append(image_url['image_url'])
            
        results['image_urls'] = image_urls

        image_for_measurement = image_urls[-1]

        print("2nd step, getting attributes...")

        attributes, error = call_microservice('attribute_predictor', 'get_attributes', {
            'image_urls': image_urls,
            'romanian': True
        })

        if error:
            log_message("Attribute prediction failed!")
            log_message(error)
            results['attributes'] = "Failed"
            success = False
        else:
            results['attributes'] = attributes

        
        results['success'] = success

        log_message("3rd step, calling measurin hpe")
        measurements_result, error = call_microservice('measuring_hpe', 'measurements', {
            "image_url": image_for_measurement
        })
        if error:
            log_message(f"Measurements failed: {error}")
            results['measurements_error'] = error
        else:
            results['measurements'] = measurements_result
        
        return jsonify(results), 200

    except Exception as e:
        error_msg = f"Unexpected error in full analysis pipeline for CWS: {str(e)}"
        log_message(f"ERROR: {error_msg}")
        return jsonify({"error": "Internal server error"}), 500
    
 
    
@app.route('/batch-analysis_romanian', methods=["GET"])
def batch_romanian():
    log_message("/batch-analysis_romanian GET endpoint called!")
    images = []
    images_dir = Path("/app/peteava")
    subdirs = [p for p in images_dir.iterdir() if p.is_dir()]
    subdirs = natsorted(
        subdirs,
        key=str,
        alg=ns.LOCALE | ns.IGNORECASE
    )
    for subdir in subdirs:
        if "rossz" in subdir.name:
            continue
        # subdir_path = os.path.join(images_dir, dir)
        # if not os.path.exists(subdir_path) or not os.path.isdir(subdir_path):
        #     log_message(f"{subdir_path=} doesn't exist!\nSkipping...")
        #     continue

        # # image_files = sorted(os.listdir(subdir_path), key=lambda x: int(x.split('-')[1].split('.')[0]))
        # image_files = sorted(os.listdir(subdir_path))
        # image_files = [os.path.join(subdir_path, image) for image in image_files if image.endswith('.jpg')]
        # images.append(image_files)
        # Collect *.jpg files inside this sub-directory
        image_files = sorted(
            str(f) for f in subdir.iterdir()
            if f.suffix.lower() == ".jpg"
        )
        # print(image_files)
        images.append(image_files) 

    results = []

    for idx, image_group in enumerate(images, 1):
        if not image_group:
            continue

        try:
            payload = {
                'image_paths': image_group
            }

            log_message(f"Processing image group {idx}/{len(images)} with main image: {image_group[0]}")
            
            response = requests.post(
                'http://localhost:5000/full-analysis_romanian',
                json=payload,
                timeout=3000
            )
            response.raise_for_status()
            
            result = response.json()
            results.append(result)

        except Exception as e:
            log_message(f"Error processing image group {idx}/20 ({image_group[0]}): {str(e)}")
            results.append({
                'error': str(e),
                'image_path': image_group[0],
                'success': False
            })

    # Save results to JSON file
    output_path = 'reports/batch_romanian_test_measure.json'
    try:
        os.makedirs('reports', exist_ok=True)
        with open(output_path, 'w') as f:
            json.dump(results, f, indent=2)
        log_message(f"Results saved to {output_path}")
        return jsonify({
            'success': True,
            'results_file': output_path,
            'total_processed': len(results)
        })
    except Exception as e:
        error_msg = f"Error saving results: {str(e)}"
        log_message(error_msg)
        return jsonify({'error': error_msg}), 500
    

@app.route('/batch-analysis_cws', methods=['GET'])
def batch_cws():
    log_message("/batch-analysis_cws GET endpoint called!")
    # 1-9; 10-15; 16-23; 24-26; 27-38; 39-43; 44-49; 50-53; 54-58; 59-67; 68-71; 72-75; 76-80; 81-84
    images = [
        [f"/app/CWS_Test/TEST {idx}.jpg" for idx in range(1,10)],
        [f"/app/CWS_Test/TEST {idx}.jpg" for idx in range(10,16)],
        [f"/app/CWS_Test/TEST {idx}.jpg" for idx in range(16,24)],
        [f"/app/CWS_Test/TEST {idx}.jpg" for idx in range(24,27)],
        [f"/app/CWS_Test/TEST {idx}.jpg" for idx in range(27,39)],
        [f"/app/CWS_Test/TEST {idx}.jpg" for idx in range(39,44)],
        [f"/app/CWS_Test/TEST {idx}.jpg" for idx in range(44,50)],
        [f"/app/CWS_Test/TEST {idx}.jpg" for idx in range(50,54)],
        [f"/app/CWS_Test/TEST {idx}.jpg" for idx in range(54,59)],
        [f"/app/CWS_Test/TEST {idx}.jpg" for idx in range(59,68)],
        [f"/app/CWS_Test/TEST {idx}.jpg" for idx in range(68,72)],
        [f"/app/CWS_Test/TEST {idx}.jpg" for idx in range(72,76)],
        [f"/app/CWS_Test/TEST {idx}.jpg" for idx in range(76,81)],
        [f"/app/CWS_Test/TEST {idx}.jpg" for idx in range(81,85)]
    ]

    results = []
    
    for image_group in images:
        if not image_group:
            continue
            
        # Use first image as main, rest as additional
        main_image = image_group[0]
        additional_images = image_group[1:] if len(image_group) > 1 else []
        
        try:
            # Call full analysis endpoint
            payload = {
                'image_path': main_image,
                'additional_image_paths': additional_images
            }
            
            log_message(f"Processing image group with main image: {main_image}")
            
            response = requests.post(
                'http://localhost:5000/full-analysis_cws',
                json=payload,
                timeout=300
            )
            response.raise_for_status()
            
            result = response.json()
            results.append(result)
            
        except Exception as e:
            log_message(f"Error processing image group {main_image}: {str(e)}")
            results.append({
                'error': str(e),
                'image_path': main_image,
                'success': False
            })
    
    # Save results to JSON file
    output_path = 'reports/batch_cws_results.json'
    try:
        os.makedirs('reports', exist_ok=True)
        with open(output_path, 'w') as f:
            json.dump(results, f, indent=2)
        log_message(f"Results saved to {output_path}")
        return jsonify({
            'success': True,
            'results_file': output_path,
            'total_processed': len(results)
        })
    except Exception as e:
        error_msg = f"Error saving results: {str(e)}"
        log_message(error_msg)
        return jsonify({'error': error_msg}), 500





if __name__ == '__main__':
    log_message("Starting main orchestrator API...")
    app.run(host='0.0.0.0', port=int(os.getenv('MAIN_API_PORT', '5000')), debug=True)
