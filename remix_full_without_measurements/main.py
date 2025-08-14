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
    'category_predictor': {
        'host': os.getenv('CATEGORY_PREDICTOR_HOST', 'category-predictor'),
        'port': os.getenv('CATEGORY_PREDICTOR_PORT', '5002'),
        'endpoints': {
            'category': '/category',
            'health': '/health'
        }
    },
    'attribute_predictor': {
        'host': os.getenv('ATTRIBUTE_PREDICTOR_HOST', 'attribute-predictor'),
        'port': os.getenv('ATTRIBUTE_PREDICTOR_PORT', '5004'),
        'endpoints': {
            'condition': '/condition',
            'health': '/health',
            'get_attributes': '/get_attributes',
            'micro_prompt': '/micro_prompt'
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

@app.route('/debug', methods=['GET'])
def debug_check():
    """Debug endpoint to test connectivity."""
    try:
        log_message("Debug endpoint called")
        # Test category predictor
        cat_url = get_service_url('category_predictor', 'health')
        log_message(f"Trying to reach category predictor at: {cat_url}")
        
        # Test attribute predictor  
        attr_url = get_service_url('attribute_predictor', 'health')
        log_message(f"Trying to reach attribute predictor at: {attr_url}")
        
        return jsonify({
            "category_predictor_url": cat_url,
            "attribute_predictor_url": attr_url,
            "timestamp": datetime.utcnow().isoformat()
        })
    except Exception as e:
        log_message(f"Debug error: {str(e)}")
        return jsonify({"error": str(e)}), 500

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
    Simplified garment processing pipeline:
    1. Predict category
    2. Predict attributes (condition, etc.)
    """
    try:
        log_message("Starting simplified garment processing pipeline")
        
        # Parse request
        data = request.get_json()
        if not data or 'image_url' not in data:
            return jsonify({"error": "image_url is required"}), 400
        
        image_url = data['image_url']
        
        log_message(f"Processing image: {image_url}")
        
        # Step 1: Predict category
        log_message("Step 1: Predicting category...")
        category_result, error = call_microservice('category_predictor', 'category', {"image_url": image_url})
        
        if error:
            log_message(f"Category prediction failed: {error}")
            category_result = {"error": error}
        
        # Step 2: Get attributes
        log_message("Step 2: Getting attributes...")
        attributes_result, error = call_microservice('attribute_predictor', 'get_attributes', {"image_urls": [image_url]})
        
        if error:
            log_message(f"Attributes prediction failed: {error}")
            attributes_result = {"error": error}
        
        log_message("Simplified pipeline completed")
        
        # Return comprehensive result
        return jsonify({
            "success": True,
            "original_image": image_url,
            "category_prediction": category_result,
            "attributes": attributes_result,
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



@app.route('/full-analysis', methods=['POST'])
def full_analysis():
    """
    Simplified garment analysis pipeline:
    1. Predict category
    2. Predict attributes (condition, etc.)
    """
    try:
        log_message("Starting simplified full garment analysis pipeline")
        
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
            log_message(f"Category prediction failed: {error}")
            results['category_error'] = error
        else:
            results['category_prediction'] = category_result
        
        # Step 2: Predict attributes
        log_message("Step 2: Getting attributes...")
        all_images = [image_url] + additional_image_urls
        attributes_result, error = call_microservice('attribute_predictor', 'get_attributes', {"image_urls": all_images})
        if error:
            log_message(f"Attributes prediction failed: {error}")
            results['attributes_error'] = error
        else:
            results['attributes'] = attributes_result
        
        log_message("Simplified full analysis pipeline completed")

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




@app.route('/analyze-garment', methods=['POST'])
def analyze_garment():
    """
    Enhanced garment analysis that returns data in the required format.
    """
    try:
        log_message("Starting enhanced garment analysis")
        
        # Parse request
        data = request.get_json()
        if not data or 'image_urls' not in data:
            return jsonify({"error": "image_urls array is required"}), 400
        
        image_urls = data['image_urls']
        item_id = data.get('item_id', 'unknown')
        
        if not image_urls or len(image_urls) == 0:
            return jsonify({"error": "At least one image URL is required"}), 400
        
        main_image = image_urls[0]
        log_message(f"Processing item {item_id} with main image: {main_image}")
        
        # Step 1 & 2: Predict category and micro-attributes in parallel using asyncio
        log_message("Steps 1 & 2: Predicting category and micro-attributes in parallel...")
        
        import asyncio
        import aiohttp
        import json as json_lib
        
        async def call_openai_micro_prompt(prompt_name, system_msg, user_msg, schema):
            """Call OpenAI with micro prompts directly."""
            try:
                # This would call OpenAI API directly for micro prompts
                # For now, fall back to the existing attribute predictor
                url = get_service_url('attribute_predictor', 'get_attributes')
                log_message(f"Async calling micro-prompt {prompt_name}")
                
                timeout = aiohttp.ClientTimeout(total=30)
                async with aiohttp.ClientSession(timeout=timeout) as session:
                    async with session.post(url, json={"image_urls": image_urls}) as response:
                        response.raise_for_status()
                        result = await response.json()
                        return result, None
                        
            except Exception as e:
                error_msg = f"Error calling micro-prompt {prompt_name}: {str(e)}"
                log_message(f"ERROR: {error_msg}")
                return None, error_msg
        
        async def call_microservice_async(service_name, endpoint, data=None):
            """Async version of call_microservice."""
            try:
                url = get_service_url(service_name, endpoint)
                print(f"ASYNC DEBUG: Calling {service_name} at {url} with data: {data}")
                log_message(f"Async calling {service_name} at {url}")
                
                timeout = aiohttp.ClientTimeout(total=30)
                async with aiohttp.ClientSession(timeout=timeout) as session:
                    async with session.post(url, json=data) as response:
                        print(f"ASYNC DEBUG: Response status {response.status} from {url}")
                        response.raise_for_status()
                        result = await response.json()
                        print(f"ASYNC DEBUG: Got result from {url}: {result}")
                        return result, None
                        
            except asyncio.TimeoutError:
                error_msg = f"Timeout calling {service_name}/{endpoint}"
                print(f"ASYNC ERROR: {error_msg}")
                log_message(f"ERROR: {error_msg}")
                return None, error_msg
            except Exception as e:
                error_msg = f"Error calling {service_name}/{endpoint}: {str(e)}"
                print(f"ASYNC ERROR: {error_msg}")
                log_message(f"ERROR: {error_msg}")
                return None, error_msg
        
        async def call_micro_prompt_async(prompt_type):
            """Call micro-prompt endpoint asynchronously with optimized image selection."""
            try:
                url = get_service_url('attribute_predictor', 'micro_prompt')
                
                # Optimize image selection for each prompt type
                if prompt_type == 'brand':
                    # Brand: images 1, 3, 4 (index 0, 2, 3)
                    selected_images = [image_urls[i] for i in [0, 2, 3] if i < len(image_urls)]
                elif prompt_type == 'color':
                    # Color: only first image (index 0)
                    selected_images = [image_urls[0]] if len(image_urls) > 0 else []
                elif prompt_type == 'material' or prompt_type == 'size':
                    # Material & Size: images 3, 4 (index 2, 3)
                    selected_images = [image_urls[i] for i in [2, 3] if i < len(image_urls)]
                elif prompt_type == 'condition':
                    # Condition: images 1, 2 (index 0, 1)
                    selected_images = [image_urls[i] for i in [0, 1] if i < len(image_urls)]
                else:
                    # Fallback: all images
                    selected_images = image_urls
                
                data = {"prompt_type": prompt_type, "image_urls": selected_images}
                print(f"MICRO ASYNC DEBUG: Calling {url} with {prompt_type} using {len(selected_images)} images")
                
                timeout = aiohttp.ClientTimeout(total=30)
                async with aiohttp.ClientSession(timeout=timeout) as session:
                    async with session.post(url, json=data) as response:
                        print(f"MICRO ASYNC DEBUG: Response status {response.status} for {prompt_type}")
                        response.raise_for_status()
                        result = await response.json()
                        print(f"MICRO ASYNC DEBUG: Got result for {prompt_type}: {result}")
                        return result, None
                        
            except Exception as e:
                error_msg = f"Error calling micro-prompt {prompt_type}: {str(e)}"
                print(f"MICRO ASYNC ERROR: {error_msg}")
                log_message(f"ERROR: {error_msg}")
                return None, error_msg

        async def get_parallel_results():
            print("PARALLEL DEBUG: Starting parallel tasks")
            # Create tasks for parallel execution
            category_task = call_microservice_async('category_predictor', 'category', {"image_url": main_image})
            
            # Create simple micro-prompt tasks for parallel execution
            brand_task = call_micro_prompt_async('brand')
            color_task = call_micro_prompt_async('color')  
            material_task = call_micro_prompt_async('material')
            size_task = call_micro_prompt_async('size')
            condition_task = call_micro_prompt_async('condition')
            
            print("PARALLEL DEBUG: All tasks created, starting gather")
            # Run all tasks in parallel
            results = await asyncio.gather(
                category_task, 
                brand_task,
                color_task, 
                material_task,
                size_task,
                condition_task,
                return_exceptions=True
            )
            
            print(f"PARALLEL DEBUG: Gather completed with results: {len(results)} items")
            return results
        
        # Run the async function
        try:
            print("MAIN DEBUG: Starting async execution")
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            print("MAIN DEBUG: Event loop created")
            results = loop.run_until_complete(get_parallel_results())
            print(f"MAIN DEBUG: Got async results: {results}")
            loop.close()
            
            # Parse results
            (category_result, category_error) = results[0]
            (brand_result, brand_error) = results[1] 
            (color_result, color_error) = results[2]
            (material_result, material_error) = results[3]
            (size_result, size_error) = results[4]
            (condition_result, condition_error) = results[5]
            print("MAIN DEBUG: Results parsed successfully")
            
        except Exception as e:
            print(f"MAIN ERROR: Async execution failed: {str(e)}")
            log_message(f"Async execution failed: {str(e)}")
            # Fallback to synchronous calls
            category_result, category_error = call_microservice('category_predictor', 'category', {"image_url": main_image})
            brand_result = color_result = material_result = size_result = condition_result = None
            brand_error = color_error = material_error = size_error = condition_error = "Async fallback failed"
        
        # Extract category info
        main_category = "Unknown"
        category = "Unknown" 
        if not category_error and category_result.get('success') and category_result.get('topx'):
            top_prediction = category_result['topx'][0]
            category = top_prediction[0]
            # Map to main categories
            if category.lower() in ['trousers', 'jeans', 'shorts']:
                main_category = "Menswear" if "men" in main_image.lower() else "Womenswear"
            elif category.lower() in ['blouses', 'tops', 'shirts']:
                main_category = "Womenswear"
            else:
                main_category = "Unisex"
        
        # Extract attributes info from simple micro-prompts
        brand = "Unknown"
        color = "Unknown"
        material = "Unknown"
        size = ""
        condition_rating = "Unknown condition"
        condition_grade = 0
        
        # Extract brand
        print(f"DEBUG: brand_error={brand_error}, brand_result={brand_result}")
        log_message(f"DEBUG: brand_error={brand_error}, brand_result={brand_result}")
        if not brand_error and brand_result:
            brand = brand_result.get('brand', 'Unknown') or 'Unknown'
            log_message(f"DEBUG: Extracted brand: {brand}")
            
        # Extract size
        log_message(f"DEBUG: size_error={size_error}, size_result={size_result}")
        if not size_error and size_result:
            size = size_result.get('size_tag', '') or ''
            log_message(f"DEBUG: Extracted size: {size}")
            
        # Extract color
        log_message(f"DEBUG: color_error={color_error}, color_result={color_result}")
        if not color_error and color_result:
            color = color_result.get('primary_color', 'Unknown') or 'Unknown'
            log_message(f"DEBUG: Extracted color: {color}")
            
        # Extract material
        log_message(f"DEBUG: material_error={material_error}, material_result={material_result}")
        if not material_error and material_result:
            material = material_result.get('fabric_composition', 'Unknown') or 'Unknown'
            log_message(f"DEBUG: Extracted material: {material}")
            
        # Extract condition
        if not condition_error and condition_result:
            condition_grade = condition_result.get('condition_grade', 0)
            condition_note = condition_result.get('condition_note', '')
            
            if condition_grade >= 9:
                condition_rating = "This product has no signs of use."
            elif condition_grade >= 7:
                condition_rating = "This product shows minor signs of use."
            elif condition_grade >= 5:
                condition_rating = "This product shows moderate signs of use."
            else:
                condition_rating = "This product shows significant signs of use."
            
            if condition_note:
                condition_rating = condition_note


        
        # Generate name and description
        name = f"{brand} {color} {category}"
        description = f"A {color.lower()} {category.lower()} from {brand}."
        
        # Generate basic tags
        tags = f"{color.lower()}, {category.lower()}, {brand.lower()}, {main_category.lower()}"
        
        # Build response in required format
        result = {
            item_id: {
                "attributes": {
                    "brand": brand,
                    "main_category": main_category,
                    "category": category,
                    "sub_category": "",  # Not available from current services
                    "color": color,
                    "size": size,
                    "material": material,
                    "name": name,
                    "description": description,
                    "tags": tags
                },
                "images": image_urls,
                "condition_rating": condition_rating,
                "condition_description": "",
                "measurements": [],  # Not available without measurement service
                "generated_picture_url": ""  # Not available from current services
            }
        }
        
        log_message(f"Enhanced analysis completed for item {item_id}")
        return jsonify(result)
        
    except Exception as e:
        error_msg = f"Unexpected error in enhanced garment analysis: {str(e)}"
        log_message(f"ERROR: {error_msg}")
        return jsonify({"error": "Internal server error"}), 500

if __name__ == '__main__':
    log_message("Starting simplified main orchestrator API...")
    app.run(host='0.0.0.0', port=int(os.getenv('MAIN_API_PORT', '5000')), debug=True)
