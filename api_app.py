from flask import Flask, request, jsonify
import cv2, sys, traceback
from tools.ClothingLandmarkPredictor import ClothingLandmarkPredictor
from tools.ClothingMeasurer import ClothingMeasurer
from tools.ClothingCategoryPredictor import ClothingCategoryPredictor
from tools.GCPStorageLoader import GCPStorageLoader
from tools.logger import EVFSAMLogger
from tools.performance_monitor import PerformanceMonitor, perf_monitor
from tools.turbojpeg_loader import turbojpeg_loader
from tools.parallel_predictor import ParallelPredictor
from tools.batch_processor import BatchProcessor
import json


class ApiApp:
    def __init__(self):
        try:
            self.__logger = EVFSAMLogger()
            self.__perf_monitor = PerformanceMonitor(self.__logger)
            
            print("Starting Flask app...")
            self.__logger.log("Starting Flask app...")
            
            self.__app = Flask(__name__, static_folder='', static_url_path='')
            self.__app.secret_key = 'my-secret-key'

            with self.__perf_monitor.timer("GCPStorageLoader_initialization"):
                print("Loading GCPStorageLoader...")
                self.__logger.log("Loading GCPStorageLoader...")
                self.__s3loader = GCPStorageLoader(logger=self.__logger)
            
            with self.__perf_monitor.timer("HRNet_model_download"):
                print("Loading HRNet model...")
                self.__logger.log("Loading HRNet model...")
                state = self.__s3loader.load_hrnet_model()
            
            with self.__perf_monitor.timer("ClothingLandmarkPredictor_initialization"):
                print("Initializing ClothingLandmarkPredictor...")
                self.__logger.log("Initializing ClothingLandmarkPredictor...")
                self.__landmark_predictor = ClothingLandmarkPredictor(logger=self.__logger, state=state)
            
            with self.__perf_monitor.timer("ClothingMeasurer_initialization"):
                print("Initializing ClothingMeasurer...")
                self.__logger.log("Initializing ClothingMeasurer...")
                self.__measurer = ClothingMeasurer(logger=self.__logger)

            with self.__perf_monitor.timer("ClothingCategoryPredictor_initialization"):
                print("Initializing ClothingCategoryPredictor...")
                self.__logger.log("Initializing ClothingCategoryPredictor...")
                self.__category_predictor = ClothingCategoryPredictor(logger=self.__logger)
            
            # Initialize Parallel Predictor for simultaneous landmark and category detection
            with self.__perf_monitor.timer("ParallelPredictor_initialization"):
                print("Initializing Parallel Predictor...")
                self.__logger.log("Initializing Parallel Predictor...")
                self.__parallel_predictor = ParallelPredictor(
                    landmark_predictor=self.__landmark_predictor,
                    category_predictor=self.__category_predictor,
                    logger=self.__logger
                )
            
            # Initialize Batch Processor for advanced batch operations
            with self.__perf_monitor.timer("BatchProcessor_initialization"):
                print("Initializing Batch Processor...")
                self.__logger.log("Initializing Batch Processor...")
                self.__batch_processor = BatchProcessor(logger=self.__logger)

            # Set up routes (simplified for testing)
            # Original endpoints
            self.__app.add_url_rule('/health', 'health', self.health_check, methods=['GET'])
            self.__app.add_url_rule('/measurements', 'measurements', self.get_measurements, methods=['POST']) 
            self.__app.add_url_rule('/benchmark', 'benchmark', self.benchmark_parallel, methods=['POST'])
            
            # Additional existing endpoints
            self.__app.add_url_rule('/landmarks', 'landmarks', self.get_landmarks, methods=['POST'])
            self.__app.add_url_rule('/category', 'category', self.get_category, methods=['POST'])
            self.__app.add_url_rule('/upload_image', 'upload_image', self.upload_image, methods=['POST'])
            
            # NEW ORCHESTRATOR ENDPOINTS - Advanced functionality
            self.__app.add_url_rule('/full-analysis', 'full_analysis', self.full_analysis, methods=['POST'])
            self.__app.add_url_rule('/predict-category', 'predict_category_endpoint', self.predict_category_endpoint, methods=['POST'])
            self.__app.add_url_rule('/batch-analysis', 'batch_analysis', self.batch_analysis, methods=['POST'])
            self.__app.add_url_rule('/batch-analysis-sku', 'batch_analysis_sku', self.batch_analysis_sku, methods=['POST'])
            self.__app.add_url_rule('/process-garment', 'process_garment', self.process_garment, methods=['POST'])
            
            print("All endpoints registered!")
            self.__logger.log("All endpoints registered!")
            
        except Exception as e:
            self.__logger.log(f"Failed to initialize ApiApp: {e}")
            self.__logger.log(f"Traceback: {traceback.format_exc()}")
            
            print(f"Failed to initialize ApiApp: {e}")
            print(f"Traceback: {traceback.format_exc()}")
            raise e

    def run_app(self):
        """
        DEPRECATED: Only for local development!
        In production, use Gunicorn to start the app.
        """
        try:
            print("⚠️ WARNING: Running Flask development server - use only for local testing!")
            print("🚀 For production, use: gunicorn --config configs/gunicorn.conf.py api_app:app")
            sys.stdout.reconfigure(line_buffering=True)
            self.__app.run(host='0.0.0.0', port=5003, debug=False)  # Debug=False for security
        except Exception as e:
            error_msg = f"Failed to start Flask app: {str(e)}"
            print(error_msg)
            self.__logger.log(error_msg)
            raise

    # ----- HELPERS -----
    def __get_image_from_gcp_link(self, public_url):
        try:
            return self.__s3loader.get_image_from_link(public_url=public_url)
        except Exception as e:
            error_msg = f"Failed to get image from GCP Storage link {public_url}: {str(e)}"
            print(error_msg)
            self.__logger.log(error_msg)
            return None

    def __upload_image_to_gcp(self, public_url="", image_path="", image_data=None, predicted=False):
        """
        Calls GCPStorageLoader upload_s3_image function (kept method name for compatibility). 
        This function expects either a public url or a local image path, that it will upload to GCP Cloud Storage.
        Returns public GCP Storage url.
        """
        try:
            return self.__s3loader.upload_s3_image(
                public_url=public_url, 
                image_path=image_path, 
                image_data=image_data, 
                predicted_image=predicted
            )
        except Exception as e:
            error_msg = f"Failed to upload image to GCP Storage: {str(e)}"
            print(error_msg)
            self.__logger.log(error_msg)
            return None

    def __get_landmarks_helper(self, image_url="", image_path=""):
        try:
            print(f"Attempting GCP Storage upload with image_url: {image_url}, image_path: {image_path}")
            self.__logger.log(f"Attempting GCP Storage upload with image_url: {image_url}, image_path: {image_path}")
            
            gcp_url = self.__upload_image_to_gcp(public_url=image_url, image_path=image_path)
            print(f"GCP Storage upload result: {gcp_url}")
            self.__logger.log(f"GCP Storage upload result: {gcp_url}")

            img = None
            if gcp_url or image_url:
                img = self.__get_image_from_gcp_link(public_url=gcp_url)
                if img is None:
                    img = self.__get_image_from_gcp_link(public_url=image_url)
            else:
                if image_path:
                    print(f"Falling back to local file: {image_path}")
                    self.__logger.log(f"Falling back to local file: {image_path}")
                    try:
                        img = cv2.imread(str(image_path))
                        if img is None:
                            raise ValueError(f"Could not read image from path: {image_path}")
                    except Exception as e:
                        error_msg = f"Failed to read local image {image_path}: {str(e)}"
                        print(error_msg)
                        self.__logger.log(error_msg)
                        return None
                else:
                    error_msg = "ERROR: No valid image source available"
                    print(error_msg)
                    self.__logger.log(error_msg)
                    return None
            
            if img is None:
                error_msg = "Failed to load image from any source"
                print(error_msg)
                self.__logger.log(error_msg)
                return None
            
            try:
                landmarks = self.__landmark_predictor.predict_landmarks(img=img)
                return landmarks, gcp_url
            except Exception as e:
                error_msg = f"Failed to predict landmarks: {str(e)}"
                print(error_msg)
                self.__logger.log(error_msg)
                return None
            
        except Exception as e:
            error_msg = f"ERROR getting landmarks: {str(e)}"
            print(error_msg)
            self.__logger.log(error_msg)
            return None
        
    def __get_category_helper(self, image_url=""):
        try:
            img = self.__get_image_from_gcp_link(public_url=image_url)
            
            if img is None:
                error_msg = "Failed to load image from any source"
                print(error_msg)
                self.__logger.log(error_msg)
                return None
            
            try:
                category_id, category_name, confidence = self.__category_predictor.predict_category(img)
                return category_id
            except Exception as e:
                error_msg = f"Failed to predict category: {str(e)}"
                print(error_msg)
                self.__logger.log(error_msg)
                return None
            
        except Exception as e:
            error_msg = f"ERROR getting category: {str(e)}"
            print(error_msg)
            self.__logger.log(error_msg)
            return None

    # ----- ENDPOINTS -----
    def get_category(self):
        try:
            try:
                data = request.get_json()
                if data is None:
                    return jsonify({'error': 'Invalid JSON or Content-Type not set to application/json'}), 400
            except Exception as e:
                error_msg = f"Failed to parse JSON: {str(e)}"
                print(error_msg)
                self.__logger.log(error_msg)
                return jsonify({'error': 'Invalid JSON format'}), 400
            
            image_url = data.get('image_url', '')
            if not image_url:
                return jsonify({'error': 'image_url is required'}), 400

            category_id = self.__get_category_helper(image_url=image_url)

            return jsonify(category_id), 200

        except Exception as e:
            error_msg = f"Unexpected error in get_category: {str(e)}"
            print(error_msg)
            self.__logger.log(error_msg)
            print(f"Traceback: {traceback.format_exc()}")
            self.__logger.log(f"Traceback: {traceback.format_exc()}")
            return jsonify({'error': 'Internal server error'}), 500

    def get_landmarks(self):
        try:
            # Parse JSON with error handling
            try:
                data = request.get_json()
                if data is None:
                    return jsonify({'error': 'Invalid JSON or Content-Type not set to application/json'}), 400
            except Exception as e:
                error_msg = f"Failed to parse JSON: {str(e)}"
                print(error_msg)
                self.__logger.log(error_msg)
                return jsonify({'error': 'Invalid JSON format'}), 400
            
            image_path = data.get('image_path', '')
            image_url  = data.get('image_url', '')
            
            if not image_path and not image_url:
                return jsonify({'error': 'Either image_path or image_url is required'}), 400
            
            result = self.__get_landmarks_helper(image_url=image_url, image_path=image_path)
            if result is None:
                return jsonify({'success': False, 'error': "Failed to get landmarks"}), 500
                
            landmarks, _ = result
            if landmarks is None:
                return jsonify({'success': False, 'error': "Could not detect landmarks in image"}), 400
                
            try:
                landmarks_list = landmarks.tolist()  # Convert numpy array to list
            except Exception as e:
                error_msg = f"Failed to convert landmarks to list: {str(e)}"
                print(error_msg)
                self.__logger.log(error_msg)
                return jsonify({'success': False, 'error': "Failed to process landmarks"}), 500
                
            return jsonify({
                'success': True,
                'landmarks': landmarks_list
            })
            
        except Exception as e:
            error_msg = f"Unexpected error in get_landmarks: {str(e)}"
            print(error_msg)
            self.__logger.log(error_msg)
            print(f"Traceback: {traceback.format_exc()}")
            self.__logger.log(f"Traceback: {traceback.format_exc()}")
            return jsonify({'error': 'Internal server error'}), 500
        
    def draw_measurements(self):
        try:
            # Parse JSON with error handling
            try:
                data = request.get_json()
                if data is None:
                    return jsonify({'error': 'Invalid JSON or Content-Type not set to application/json'}), 400
            except Exception as e:
                error_msg = f"Failed to parse JSON: {str(e)}"
                print(error_msg)
                self.__logger.log(error_msg)
                return jsonify({'error': 'Invalid JSON format'}), 400
            
            landmarks = data.get('landmarks')
            image_url_bg = data.get('image_url_bg', '')
            category_id = data.get('category_id', 1)
            
            # Validate required parameters
            if landmarks is None:
                return jsonify({'error': 'landmarks parameter is required'}), 400
            
            if not image_url_bg:
                return jsonify({'error': 'image_url_bg parameter is required'}), 400
            
            # Validate category_id
            try:
                category_id = int(category_id)
            except (ValueError, TypeError):
                return jsonify({'error': 'category_id must be an integer'}), 400
            
            # Convert landmarks back to numpy array if needed
            try:
                import numpy as np
                if isinstance(landmarks, list):
                    landmarks = np.array(landmarks)
            except Exception as e:
                error_msg = f"Failed to process landmarks: {str(e)}"
                print(error_msg)
                self.__logger.log(error_msg)
                return jsonify({'error': 'Invalid landmarks format'}), 400
            
            # Get background image
            bg_img = self.__get_image_from_s3_link(public_url=image_url_bg)
            if bg_img is None:
                return jsonify({'success': False, 'error': "Could not load background image"}), 500
            
            # Filter landmarks by category
            try:
                category_landmarks = self.__landmark_predictor.filter_by_category(landmarks, category_id)
            except Exception as e:
                error_msg = f"Failed to filter landmarks by category {category_id}: {str(e)}"
                print(error_msg)
                self.__logger.log(error_msg)
                return jsonify({'success': False, 'error': f"Invalid category_id: {category_id}"}), 400
            
            # Calculate measurements
            try:
                measurements = self.__measurer.calculate_measurements(bg_img, category_landmarks, category_id=category_id)
            except Exception as e:
                error_msg = f"Failed to calculate measurements: {str(e)}"
                print(error_msg)
                self.__logger.log(error_msg)
                return jsonify({'success': False, 'error': "Failed to calculate measurements"}), 500
            
            if measurements is None:
                return jsonify({'success': False, 'error': "Could not calculate measurements from landmarks"}), 400
            
            print(f"Drawing measurements on background image. Measurement keys: {list(measurements.keys())}")
            self.__logger.log(f"Drawing measurements on background image. Measurement keys: {list(measurements.keys())}")

            # Draw measurement lines on background image
            try:
                self.__measurer.draw_lines(bg_img, measurements, category_id=category_id)
            except Exception as e:
                error_msg = f"Failed to draw measurement lines: {str(e)}"
                print(error_msg)
                self.__logger.log(error_msg)
                return jsonify({'success': False, 'error': "Failed to draw measurement lines"}), 500

            # Upload result image to S3
            result_s3_url = self.__upload_image_to_s3(image_data=bg_img, predicted=True)
            if result_s3_url is None:
                self.__logger.log("Failed to upload result image to S3")
                return jsonify({'success': False, 'error': "Failed to upload result image"}), 500

            return jsonify({
                'success': True,
                'message': 'Measurements drawn successfully',
                'url': result_s3_url,
                'measurements': measurements
            })
        
        except Exception as e:
            error_msg = f"Unexpected error in draw_measurements: {str(e)}"
            print(error_msg)
            self.__logger.log(error_msg)
            print(f"Traceback: {traceback.format_exc()}")
            self.__logger.log(f"Traceback: {traceback.format_exc()}")
            return jsonify({'error': 'Internal server error'}), 500

    def get_measurements(self):
        try:
            # Reset session for new measurement request
            self.__perf_monitor.reset_session()
            
            with self.__perf_monitor.timer("total_request_processing"):
                # Parse JSON with error handling
                with self.__perf_monitor.timer("json_parsing"):
                    try:
                        data = request.get_json()
                        if data is None:
                            return jsonify({'error': 'Invalid JSON or Content-Type not set to application/json'}), 400
                    except Exception as e:
                        error_msg = f"Failed to parse JSON: {str(e)}"
                        print(error_msg)
                        self.__logger.log(error_msg)
                        return jsonify({'error': 'Invalid JSON format'}), 400
                
                image_path  = data.get('image_path', '')
                image_url   = data.get('image_url', '')     # the removed mannequin image used to calculate measurements
                bg_img_url  = data.get('bg_img_url', '')    # original image to use as background, to draw the measurements
                
                if not image_path and not image_url:
                    return jsonify({'error': 'Either image_path or image_url is required'}), 400
                
                # Initialize s3_url for image processing
                s3_url = image_url  # Use image_url as fallback for s3_url
                
                # Get image for parallel processing with timing
                with self.__perf_monitor.timer("image_loading"):
                    img = None
                    if s3_url:
                        img = self.__get_image_from_gcp_link(s3_url)
                    if img is None and image_url:
                        img = self.__get_image_from_gcp_link(public_url=image_url)
                    
                    if img is None:
                        return jsonify({'success': False, 'error': "Could not load image for measurements"}), 500

                # 🚀 PARALLEL PREDICTION: Landmark detection + Category prediction simultaneously
                with self.__perf_monitor.timer("parallel_prediction"):
                    received_category_id = data.get('category_id', 0)
                    
                    try:
                        landmarks, category_id, category_name, confidence = self.__parallel_predictor.predict_parallel(
                            img=img,
                            image_url=image_url,
                            received_category_id=received_category_id
                        )
                        
                        if landmarks is None:
                            return jsonify({'success': False, 'error': "Could not detect landmarks in image"}), 400
                        
                        msg = f"Parallel prediction completed: category={category_name} (confidence: {confidence:.3f}), landmarks shape={landmarks.shape}"
                        print(msg)
                        self.__logger.log(msg)
                        
                        # Handle category-specific logic
                        if category_id == 0:
                            msg = "Category predictor predicted the category \"other\"."
                            print(msg)
                            self.__logger.log(msg)
                            return jsonify({'success': True, 'message': msg, "url": image_url}), 200
                            
                    except Exception as e:
                        error_msg = f"Failed parallel prediction: {str(e)}"
                        print(error_msg)
                        self.__logger.log(error_msg)
                        return jsonify({'success': False, 'error': "Failed to detect landmarks or category!"}), 400

                # Filter landmarks by category with timing
                with self.__perf_monitor.timer("landmark_filtering"):
                    try:
                        category_landmarks = self.__landmark_predictor.filter_by_category(landmarks, category_id)
                    except Exception as e:
                        error_msg = f"Failed to filter landmarks by category {category_id}: {str(e)}"
                        print(error_msg)
                        self.__logger.log(error_msg)
                        return jsonify({'success': False, 'error': f"Invalid category_id: {category_id}"}), 400
                
                # Calculate measurements with timing
                with self.__perf_monitor.timer("measurement_calculation"):
                    try:
                        measurements = self.__measurer.calculate_measurements(img, category_landmarks, category_id=category_id)
                    except Exception as e:
                        error_msg = f"Failed to calculate measurements: {str(e)}"
                        print(error_msg)
                        self.__logger.log(error_msg)
                        return jsonify({'success': False, 'error': "Failed to calculate measurements"}), 500
                    
                    if measurements is None:
                        return jsonify({'success': False, 'error': "Could not calculate measurements from landmarks"}), 400
                    
                    print(f"Measurement keys: {list(measurements.keys())}")
                    self.__logger.log(f"Measurement keys: {list(measurements.keys())}")

                # Background image loading and line drawing with timing
                with self.__perf_monitor.timer("background_image_processing"):
                    bg_img = None
                    try:
                        if bg_img_url:
                            bg_img = self.__get_image_from_gcp_link(bg_img_url)
                        if bg_img is None and s3_url:
                            bg_img = self.__get_image_from_gcp_link(public_url=s3_url)
                            warning_msg = f"No background image provided, using removed mannequin image"
                            print(warning_msg)
                            self.__logger.log(warning_msg)
                        if bg_img is None and image_url:
                            bg_img = self.__get_image_from_gcp_link(public_url=image_url)
                            warning_msg = f"No background image provided, using removed mannequin image"
                            print(warning_msg)
                            self.__logger.log(warning_msg)
                        if bg_img is None and not img is None:
                            bg_img = img
                            warning_msg = f"No background image provided, using removed mannequin image"
                            print(warning_msg)
                            self.__logger.log(warning_msg)
                        
                        if bg_img is None: 
                            return jsonify({'success': False, 'error': "Could not load image for drawing"}), 500
                        
                    except:
                        error_msg = f"Failed to load background image, using removed mannequin image"
                        print(error_msg)
                        self.__logger.log(error_msg)
                        bg_img = img

                # Draw measurement lines with timing
                with self.__perf_monitor.timer("measurement_line_drawing"):
                    try:
                        self.__measurer.draw_lines(bg_img, measurements, category_id=category_id)
                    except Exception as e:
                        error_msg = f"Failed to draw measurement lines: {str(e)}"
                        print(error_msg)
                        self.__logger.log(error_msg)
                        # Continue without drawing - not critical

                # Upload result image with timing
                with self.__perf_monitor.timer("result_image_upload"):
                    new_gcp_link = self.__upload_image_to_gcp(image_data=bg_img, predicted=True)
                    if new_gcp_link is None:
                        self.__logger.log("Failed to upload result image to GCP Storage, continuing without URL")

            # Print performance report
            self.__perf_monitor.print_performance_report()
            
            # Get performance summary for response
            perf_summary = self.__perf_monitor.get_current_session_summary()

            return jsonify({
                'success': True,
                'measurements': measurements,
                'url': new_gcp_link,
                "category_name": category_name,
                'performance_timing': {
                    'total_time_seconds': perf_summary['total_session_time'],
                    'subtask_timings': perf_summary['subtasks'],
                    'subtask_percentages': perf_summary['subtask_percentages']
                }
            }), 200
        
        except Exception as e:
            error_msg = f"Unexpected error in get_measurements: {str(e)}"
            print(error_msg)
            self.__logger.log(error_msg)
            print(f"Traceback: {traceback.format_exc()}")
            self.__logger.log(f"Traceback: {traceback.format_exc()}")
            return jsonify({'error': 'Internal server error'}), 500

    def health_check(self):
        """Enhanced health check with service status"""
        try:
            from datetime import datetime
            
            health_info = {
                "status": "healthy",
                "timestamp": datetime.utcnow().isoformat(),
                "service": "garment-measuring-hpe-orchestrator",
                "version": "2.0.0-subcategoryvit",
                "components": {
                    "category_predictor": "SubCategoryViT (661 categories)",
                    "landmark_predictor": "HRNet (optimized)",
                    "storage": "GCP Cloud Storage",
                    "category_mapper": "Advanced 14-category mapping"
                },
                "endpoints": [
                    "/health", "/measurements", "/landmarks", "/category", 
                    "/upload_image", "/full-analysis", "/predict-category", 
                    "/batch-analysis", "/process-garment", "/benchmark"
                ]
            }
            
            return jsonify(health_info), 200
            
        except Exception as e:
            error_msg = f"Health check failed: {str(e)}"
            self.__logger.log(f"❌ {error_msg}")
            return jsonify({"status": "unhealthy", "error": error_msg}), 500
    
    # ----- PERFORMANCE MONITORING -----
    def get_performance_stats(self):
        """New endpoint to get performance statistics"""
        try:
            stats = self.__perf_monitor.get_stats()
            current_session = self.__perf_monitor.get_current_session_summary()
            
            # Add model cache statistics to performance endpoint
            from tools.model_cache import model_cache
            cache_stats = model_cache.get_stats()
            
            performance_data = {
                'success': True,
                'overall_stats': stats,
                'current_session': current_session,
                'message': 'Performance statistics retrieved successfully'
            }
            
            performance_data['model_cache'] = {
                'cache_count': cache_stats['cache_count'],
                'total_size_mb': round(cache_stats['total_size_mb'], 2),
                'max_size_gb': cache_stats['max_size_gb'],
                'utilization_percent': round(cache_stats['utilization_percent'], 1)
            }
            
            return jsonify(performance_data)
            
        except Exception as e:
            error_msg = f"Failed to get performance stats: {str(e)}"
            print(error_msg)
            self.__logger.log(error_msg)
            return jsonify({'error': 'Failed to retrieve performance stats'}), 500

    def benchmark_parallel(self):
        """
        Benchmark parallel vs sequential prediction performance
        """
        try:
            data = request.get_json()
            if data is None:
                return jsonify({'error': 'Invalid JSON or Content-Type not set to application/json'}), 400
            
            image_url = data.get('image_url', '')
            num_runs = data.get('num_runs', 3)
            
            if not image_url:
                return jsonify({'error': 'image_url is required for benchmarking'}), 400
            
            # Load test image
            img = self.__get_image_from_s3_link(public_url=image_url)
            if img is None:
                return jsonify({'error': 'Could not load image for benchmarking'}), 400
            
            print(f"🔥 Starting parallel vs sequential benchmark with {num_runs} runs...")
            self.__logger.log(f"🔥 Starting parallel vs sequential benchmark with {num_runs} runs...")
            
            # Run benchmark
            benchmark_results = self.__parallel_predictor.benchmark_parallel_vs_sequential(
                img=img, 
                num_runs=num_runs
            )
            
            return jsonify({
                'success': True,
                'benchmark_results': benchmark_results,
                'image_url': image_url,
                'num_runs': num_runs,
                'summary': {
                    'sequential_avg': f"{benchmark_results['sequential_avg_time']:.3f}s",
                    'parallel_avg': f"{benchmark_results['parallel_avg_time']:.3f}s", 
                    'speedup': f"{benchmark_results['speedup_factor']:.2f}x",
                    'time_saved': f"{benchmark_results['time_saved_seconds']:.3f}s",
                    'speedup_percentage': f"{benchmark_results['speedup_percentage']:.1f}%"
                }
            })
            
        except Exception as e:
            error_msg = f"Benchmark failed: {str(e)}"
            print(error_msg)
            self.__logger.log(error_msg)
            return jsonify({'success': False, 'error': error_msg}), 500

    def full_analysis(self):
        """
        Complete garment analysis pipeline with intelligent category mapping:
        1. Detect category using SubCategoryViT + CategoryMapper
        2. Get measurements with landmarks  
        3. Return comprehensive analysis
        """
        try:
            self.__logger.log("🔄 Starting full garment analysis pipeline")
            
            data = request.get_json()
            if not data or 'image_url' not in data:
                return jsonify({"error": "image_url is required"}), 400
            
            image_url = data['image_url'].replace("\\", "")
            
            results = {
                "success": True,
                "original_image": image_url,
                "processing_timestamp": self.__get_current_time()
            }
            
            # Step 1: Predict category using SubCategoryViT + CategoryMapper
            self.__logger.log("🔍 Step 1: Advanced category prediction...")
            try:
                image = self.__s3loader.get_pil_image_from_url(image_url)
                if image is None:
                    return jsonify({"error": "Failed to load image from URL"}), 400
                
                # Get SubCategoryViT predictions
                category_name, probability, category_id = self.__category_predictor.pred(image, return_idx=False)
                
                # Get additional top predictions for better analysis
                predictions = self.__category_predictor._ClothingCategoryPredictor__model.predict_topx(image, k=5)
                
                category_result = {
                    "success": True,
                    "primary_category": {
                        "name": category_name,
                        "category_id": category_id, 
                        "confidence": probability
                    },
                    "topx": [(pred[0], pred[1]) for pred in predictions],
                    "category_mapper_name": self.__category_predictor.get_category_mapper().get_category_name(category_id)
                }
                
                results['category_prediction'] = category_result
                self.__logger.log(f"✅ Category: {category_name} → ID: {category_id} (confidence: {probability:.1%})")
                
            except Exception as e:
                self.__logger.log(f"❌ Category prediction failed: {str(e)}")
                category_id = 1  # Default fallback
                results['category_error'] = str(e)
            
            # Check if category should skip measurements
            skip_categories = ["calvin", "belts", "other", "scarfs", "swimwear", "socks", "hats", "backpacks", "gloves", "unbranded", "tommy", "sorel", "graceland", "adidas", "swiss", "underwear"]
            
            should_skip = False
            if 'category_prediction' in results and results['category_prediction'].get('success'):
                for pred_name, pred_conf in results['category_prediction']['topx']:
                    if pred_name.lower() in skip_categories and pred_conf > 0.1:
                        should_skip = True
                        break
            
            if should_skip:
                self.__logger.log(f"⏭️ Skipping measurements for category: {category_name}")
                results['measurements'] = {"message": "Measurements not applicable for this category"}
                return jsonify(results)
            
            # Step 2: Get measurements using determined category_id
            self.__logger.log("📏 Step 2: Getting measurements...")
            try:
                measurements_result = self.measurements_internal(image_url, category_id)
                results['measurements'] = measurements_result
                self.__logger.log("✅ Measurements completed successfully")
                
            except Exception as e:
                self.__logger.log(f"❌ Measurements failed: {str(e)}")
                results['measurements_error'] = str(e)
            
            self.__logger.log("🎉 Full analysis pipeline completed")
            return jsonify(results)
            
        except Exception as e:
            error_msg = f"Unexpected error in full analysis pipeline: {str(e)}"
            self.__logger.log(f"❌ {error_msg}")
            return jsonify({"error": "Internal server error"}), 500
    
    def predict_category_endpoint(self):
        """Standalone category prediction endpoint"""
        try:
            self.__logger.log("🔍 Category prediction requested")
            
            data = request.get_json()
            if not data or 'image_url' not in data:
                return jsonify({"error": "image_url is required"}), 400
            
            image_url = data['image_url']
            image = self.__s3loader.get_pil_image_from_url(image_url)
            
            if image is None:
                return jsonify({"error": "Failed to load image from URL"}), 400
            
            # Get predictions
            category_name, probability, category_id = self.__category_predictor.pred(image, return_idx=False)
            predictions = self.__category_predictor._ClothingCategoryPredictor__model.predict_topx(image, k=5)
            
            result = {
                "success": True,
                "primary_category": {
                    "name": category_name,
                    "category_id": category_id,
                    "confidence": probability
                },
                "topx": [(pred[0], pred[1]) for pred in predictions],
                "category_mapper_name": self.__category_predictor.get_category_mapper().get_category_name(category_id),
                "processing_timestamp": self.__get_current_time()
            }
            
            return jsonify(result)
            
        except Exception as e:
            error_msg = f"Category prediction failed: {str(e)}"
            self.__logger.log(f"❌ {error_msg}")
            return jsonify({"error": error_msg}), 500
    
    def batch_analysis(self):
        """
        Enhanced batch analysis endpoint with SKU processing and advanced analytics
        Supports both direct garment groups and SKU-based item processing
        """
        try:
            self.__logger.log("📦 Starting enhanced batch analysis...")
            
            data = request.get_json()
            if not data:
                return jsonify({"error": "JSON data is required"}), 400
            
            # Support multiple input formats
            garment_groups = None
            
            # Format 1: Direct garment groups
            if 'garment_groups' in data:
                garment_groups = data['garment_groups']
                processing_mode = "direct_groups"
                
            # Format 2: SKU-based items (from process_links.py style)
            elif 'items_data' in data:
                self.__logger.log("🔄 Processing SKU-based items...")
                sku_result = self.__batch_processor.process_sku_items(data['items_data'])
                garment_groups = sku_result['garment_groups']
                processing_mode = "sku_grouped"
                
                # Add SKU processing stats to response
                sku_stats = sku_result['processing_stats']
                
            else:
                return jsonify({"error": "Either 'garment_groups' or 'items_data' is required"}), 400
            
            if not garment_groups:
                return jsonify({"error": "No valid garment groups found"}), 400
            
            # Batch processing options
            output_filename = data.get('output_filename', f"batch_analysis_{self.__get_current_time().replace(':', '-')}.json")
            sample_size = data.get('sample_size', None)  # Optional sampling
            shuffle_groups = data.get('shuffle', False)  # Optional shuffling
            
            # Apply sampling if requested
            if sample_size and sample_size < len(garment_groups):
                garment_groups = self.__batch_processor.sample_groups(garment_groups, sample_size)
                self.__logger.log(f"📝 Sampled {len(garment_groups)} groups for processing")
            
            # Apply shuffling if requested
            if shuffle_groups:
                garment_groups = self.__batch_processor.shuffle_groups(garment_groups)
            
            self.__logger.log(f"📊 Processing {len(garment_groups)} garment groups...")
            
            results = []
            successful_count = 0
            processing_times = []
            
            for idx, image_group in enumerate(garment_groups, 1):
                if not image_group:
                    continue
                
                # Use first image as primary image for analysis
                primary_image_url = image_group[0]
                additional_images = image_group[1:] if len(image_group) > 1 else []
                
                start_time = self.__get_current_time()
                
                try:
                    self.__logger.log(f"🔄 Processing group {idx}/{len(garment_groups)}: {primary_image_url}")
                    
                    # Perform full analysis on primary image
                    analysis_data = {
                        'image_url': primary_image_url,
                        'additional_image_urls': additional_images
                    }
                    
                    # Call full_analysis internally
                    with self.__app.test_request_context(json=analysis_data, method='POST'):
                        analysis_result = self.full_analysis()
                        result_data = analysis_result.get_json()
                    
                    # Add batch-specific metadata
                    result_data['batch_metadata'] = {
                        'group_index': idx,
                        'primary_image': primary_image_url,
                        'additional_images': additional_images,
                        'processing_start': start_time,
                        'processing_end': self.__get_current_time()
                    }
                    
                    results.append(result_data)
                    
                    if result_data.get('success'):
                        successful_count += 1
                    
                    self.__logger.log(f"✅ Group {idx} processed successfully")
                    
                except Exception as e:
                    error_result = {
                        'batch_metadata': {
                            'group_index': idx,
                            'primary_image': primary_image_url,
                            'additional_images': additional_images,
                            'processing_start': start_time,
                            'processing_end': self.__get_current_time()
                        },
                        'error': str(e),
                        'success': False,
                        'processing_timestamp': self.__get_current_time()
                    }
                    results.append(error_result)
                    self.__logger.log(f"❌ Group {idx} failed: {str(e)}")
            
            # Analyze batch results using BatchProcessor
            batch_analysis = self.__batch_processor.analyze_batch_results(results)
            
            # Save results to GCP Storage
            try:
                results_json = {
                    'batch_info': {
                        'total_groups': len(garment_groups),
                        'successful': successful_count,
                        'failed': len(garment_groups) - successful_count,
                        'processing_timestamp': self.__get_current_time(),
                        'output_filename': output_filename,
                        'processing_mode': processing_mode,
                        'options': {
                            'sample_size': sample_size,
                            'shuffled': shuffle_groups
                        }
                    },
                    'batch_analysis': batch_analysis,
                    'results': results
                }
                
                # Add SKU stats if available
                if processing_mode == "sku_grouped" and 'sku_stats' in locals():
                    results_json['batch_info']['sku_processing'] = sku_stats
                
                # Upload to GCP Storage
                self.__s3loader.save_text_to_gcp(
                    json.dumps(results_json, indent=2, ensure_ascii=False),
                    f"batch_results/{output_filename}"
                )
                
                return jsonify({
                    "success": True,
                    "batch_results_file": f"batch_results/{output_filename}",
                    "processing_summary": {
                        "total_processed": len(garment_groups),
                        "successful": successful_count,
                        "failed": len(garment_groups) - successful_count,
                        "success_rate": (successful_count / len(garment_groups) * 100) if len(garment_groups) > 0 else 0,
                        "processing_mode": processing_mode
                    },
                    "batch_analysis": batch_analysis,
                    "processing_timestamp": self.__get_current_time()
                })
                
            except Exception as e:
                self.__logger.log(f"❌ Failed to save batch results: {str(e)}")
                return jsonify({
                    "success": False,
                    "error": f"Batch processing completed but failed to save results: {str(e)}",
                    "processing_summary": {
                        "total_processed": len(garment_groups),
                        "successful": successful_count,
                        "failed": len(garment_groups) - successful_count
                    },
                    "batch_analysis": batch_analysis,
                    "results": results[:10]  # Return first 10 results only due to size
                })
                
        except Exception as e:
            error_msg = f"Enhanced batch analysis failed: {str(e)}"
            self.__logger.log(f"❌ {error_msg}")
            return jsonify({"error": error_msg}), 500
    
    def batch_analysis_sku(self):
        """
        Specialized endpoint for SKU-based batch processing (process_links.py style)
        Expects JSON file with items grouped by SKU
        """
        try:
            self.__logger.log("📦 Starting SKU-based batch analysis...")
            
            data = request.get_json()
            if not data:
                return jsonify({"error": "JSON data is required"}), 400
            
            # Check for items_photos_links.json style data
            items_data = data.get('items_data', {})
            if not items_data:
                return jsonify({"error": "items_data is required (from items_photos_links.json)"}), 400
            
            # Process SKU items
            self.__logger.log("🔄 Processing SKU items...")
            sku_result = self.__batch_processor.process_sku_items(items_data)
            
            if not sku_result['garment_groups']:
                return jsonify({"error": "No valid SKU groups found in items_data"}), 400
            
            # Get processing options
            output_filename = data.get('output_filename', "sku_batch_analysis.json")
            sample_size = data.get('sample_size', None)
            shuffle = data.get('shuffle', False)
            
            # Create payload for batch processing
            batch_payload = self.__batch_processor.create_batch_payload(
                sku_result['garment_groups'], 
                output_filename
            )
            
            # Add processing options
            if sample_size:
                batch_payload['sample_size'] = sample_size
            if shuffle:
                batch_payload['shuffle'] = shuffle
            
            # Call main batch analysis internally
            with self.__app.test_request_context(json=batch_payload, method='POST'):
                batch_result = self.batch_analysis()
                result_data = batch_result.get_json()
            
            # Add SKU-specific metadata
            result_data['sku_processing'] = {
                'total_skus_processed': sku_result['total_skus'],
                'total_items_in_source': sku_result['processing_stats']['items_processed'],
                'sku_groups_created': sku_result['total_groups'],
                'processing_mode': 'sku_grouped_specialized'
            }
            
            self.__logger.log(f"✅ SKU batch processing completed: {sku_result['total_skus']} SKUs → {sku_result['total_groups']} groups")
            
            return jsonify(result_data)
            
        except Exception as e:
            error_msg = f"SKU batch analysis failed: {str(e)}"
            self.__logger.log(f"❌ {error_msg}")
            return jsonify({"error": error_msg}), 500
    
    def process_garment(self):
        """
        Simple garment processing pipeline (measurements only)
        """
        try:
            self.__logger.log("🔄 Starting garment processing pipeline")
            
            data = request.get_json()
            if not data or 'image_url' not in data:
                return jsonify({"error": "image_url is required"}), 400
            
            image_url = data['image_url']
            category_id = data.get('category_id', 1)  # Default to category 1
            
            self.__logger.log(f"📏 Processing measurements for: {image_url}")
            
            # Get measurements directly
            measurements_result = self.measurements_internal(image_url, category_id)
            
            return jsonify({
                "success": True,
                "original_image": image_url,
                "measurements": measurements_result.get('measurements'),
                "visualization_url": measurements_result.get('url'),
                "category_id": category_id,
                "processing_timestamp": self.__get_current_time()
            })
            
        except Exception as e:
            error_msg = f"Garment processing failed: {str(e)}"
            self.__logger.log(f"❌ {error_msg}")
            return jsonify({"error": error_msg}), 500
    
    def measurements_internal(self, image_url, category_id=1):
        """Internal method for measurements (used by orchestrator endpoints)"""
        try:
            # Load image
            image = self.__s3loader.get_pil_image_from_url(image_url)
            if image is None:
                raise ValueError("Failed to load image from URL")
            
            # Get measurements using existing logic
            with self.__perf_monitor.timer("measurements_processing"):
                landmarks = self.__landmark_predictor.pred(image)
                measurements = self.__measurer.get_measurements(landmarks, category=category_id)
                visualization = self.__measurer.get_measurements_visualization(image, landmarks, measurements, category=category_id)
                
                # Upload visualization to GCP
                result_url = self.__s3loader.save_image_to_gcp_random(visualization)
            
            return {
                "success": True,
                "measurements": measurements,
                "url": result_url,
                "landmarks": landmarks.tolist() if landmarks is not None else None
            }
            
        except Exception as e:
            self.__logger.log(f"❌ Internal measurements failed: {str(e)}")
            raise e
    
    def __get_current_time(self):
        """Helper method to get current timestamp"""
        from datetime import datetime
        return datetime.utcnow().isoformat()
    
    def health_check(self):
        """Enhanced health check with service status"""
        try:
            from datetime import datetime
            
            health_info = {
                "status": "healthy",
                "timestamp": datetime.utcnow().isoformat(),
                "service": "garment-measuring-hpe-orchestrator",
                "version": "2.0.0-subcategoryvit",
                "components": {
                    "category_predictor": "SubCategoryViT (661 categories)",
                    "landmark_predictor": "HRNet (optimized)",
                    "storage": "GCP Cloud Storage",
                    "category_mapper": "Advanced 14-category mapping"
                },
                "endpoints": [
                    "/health", "/measurements", "/landmarks", "/category", 
                    "/upload_image", "/full-analysis", "/predict-category", 
                    "/batch-analysis", "/process-garment", "/benchmark"
                ]
            }
            
            return jsonify(health_info), 200
            
        except Exception as e:
            error_msg = f"Health check failed: {str(e)}"
            self.__logger.log(f"❌ {error_msg}")
            return jsonify({"status": "unhealthy", "error": error_msg}), 500
    
    def get_landmarks(self):
        """Get clothing landmarks only (without measurements)"""
        try:
            data = request.get_json()
            if not data:
                return jsonify({'error': 'JSON data required'}), 400
            
            image_url = data.get('image_url', '')
            image_path = data.get('image_path', '')
            
            if not image_url and not image_path:
                return jsonify({'error': 'Either image_url or image_path is required'}), 400
            
            # Load image
            if image_url:
                img = self.__s3loader.get_pil_image_from_url(image_url)
            else:
                img = self.__get_image_from_gcp_link(image_path)
            
            if img is None:
                return jsonify({'error': 'Failed to load image'}), 400
            
            # Get landmarks
            landmarks = self.__landmark_predictor.pred(img)
            
            if landmarks is None:
                return jsonify({'error': 'Failed to detect landmarks'}), 400
            
            return jsonify({
                'success': True,
                'landmarks': landmarks.tolist(),
                'landmark_count': len(landmarks),
                'image_dimensions': img.size if hasattr(img, 'size') else None
            }), 200
            
        except Exception as e:
            error_msg = f"Landmark detection failed: {str(e)}"
            self.__logger.log(f"❌ {error_msg}")
            return jsonify({'error': error_msg}), 500
    
    def get_category(self):
        """Get clothing category prediction"""
        try:
            data = request.get_json()
            if not data:
                return jsonify({'error': 'JSON data required'}), 400
            
            image_url = data.get('image_url', '')
            if not image_url:
                return jsonify({'error': 'image_url is required'}), 400
            
            # Load image
            img = self.__s3loader.get_pil_image_from_url(image_url)
            if img is None:
                return jsonify({'error': 'Failed to load image'}), 400
            
            # Get category prediction
            category_name, probability, category_id = self.__category_predictor.pred(img, return_idx=False)
            
            # Get top predictions for additional context
            try:
                predictions = self.__category_predictor._ClothingCategoryPredictor__model.predict_topx(img, k=5)
                topx = [(pred[0], pred[1]) for pred in predictions]
            except:
                topx = [(category_name, probability)]
            
            return jsonify({
                'success': True,
                'category_id': category_id,
                'category_name': category_name,
                'confidence': probability,
                'topx': topx,
                'category_mapper_name': self.__category_predictor.get_category_mapper().get_category_name(category_id)
            }), 200
            
        except Exception as e:
            error_msg = f"Category prediction failed: {str(e)}"
            self.__logger.log(f"❌ {error_msg}")
            return jsonify({'error': error_msg}), 500
    
    def upload_image(self):
        """Upload image to GCP Storage and return public URL"""
        try:
            data = request.get_json()
            if not data:
                return jsonify({'error': 'JSON data required'}), 400
            
            image_data = data.get('image_data', '')
            cws_mode = data.get('CWS', 0)
            
            if not image_data:
                return jsonify({'error': 'image_data (base64) is required'}), 400
            
            try:
                import base64
                from PIL import Image
                from io import BytesIO
                
                # Decode base64 image
                img_bytes = base64.b64decode(image_data)
                img = Image.open(BytesIO(img_bytes))
                
                # Upload to GCP Storage
                if cws_mode:
                    # CWS mode - specific naming/handling
                    image_url = self.__s3loader.save_image_to_gcp_random(img, prefix="cws_")
                else:
                    # Standard mode
                    image_url = self.__s3loader.save_image_to_gcp_random(img)
                
                if image_url:
                    return jsonify({
                        'success': True,
                        'image_url': image_url,
                        'upload_timestamp': self.__get_current_time()
                    }), 200
                else:
                    return jsonify({'error': 'Failed to upload image to GCP Storage'}), 500
                    
            except Exception as e:
                return jsonify({'error': f'Failed to process image data: {str(e)}'}), 400
            
        except Exception as e:
            error_msg = f"Image upload failed: {str(e)}"
            self.__logger.log(f"❌ {error_msg}")
            return jsonify({'error': error_msg}), 500
    
    def measurements(self):
        try:
            # Reset session for new measurement request
            self.__perf_monitor.reset_session()
            
            with self.__perf_monitor.timer("total_request_processing"):
                # Parse JSON with error handling
                with self.__perf_monitor.timer("json_parsing"):
                    try:
                        data = request.get_json()
                        if data is None:
                            return jsonify({'error': 'Invalid JSON or Content-Type not set to application/json'}), 400
                    except Exception as e:
                        error_msg = f"Failed to parse JSON: {str(e)}"
                        print(error_msg)
                        self.__logger.log(error_msg)
                        return jsonify({'error': 'Invalid JSON format'}), 400
                
                image_path  = data.get('image_path', '')
                image_url   = data.get('image_url', '')     # the removed mannequin image used to calculate measurements
                bg_img_url  = data.get('bg_img_url', '')    # original image to use as background, to draw the measurements
                
                if not image_path and not image_url:
                    return jsonify({'error': 'Either image_path or image_url is required'}), 400
                
                # Initialize s3_url for image processing
                s3_url = image_url  # Use image_url as fallback for s3_url
                
                # Get image for parallel processing with timing
                with self.__perf_monitor.timer("image_loading"):
                    img = None
                    if s3_url:
                        img = self.__get_image_from_gcp_link(s3_url)
                    if img is None and image_url:
                        img = self.__get_image_from_gcp_link(public_url=image_url)
                    
                    if img is None:
                        return jsonify({'success': False, 'error': "Could not load image for measurements"}), 500

                # 🚀 PARALLEL PREDICTION: Landmark detection + Category prediction simultaneously
                with self.__perf_monitor.timer("parallel_prediction"):
                    received_category_id = data.get('category_id', 0)
                    
                    try:
                        landmarks, category_id, category_name, confidence = self.__parallel_predictor.predict_parallel(
                            img=img,
                            image_url=image_url,
                            received_category_id=received_category_id
                        )
                        
                        if landmarks is None:
                            return jsonify({'success': False, 'error': "Could not detect landmarks in image"}), 400
                        
                        msg = f"Parallel prediction completed: category={category_name} (confidence: {confidence:.3f}), landmarks shape={landmarks.shape}"
                        print(msg)
                        self.__logger.log(msg)
                        
                        # Handle category-specific logic
                        if category_id == 0:
                            msg = "Category predictor predicted the category \"other\"."
                            print(msg)
                            self.__logger.log(msg)
                            return jsonify({'success': True, 'message': msg, "url": image_url}), 200
                            
                    except Exception as e:
                        error_msg = f"Failed parallel prediction: {str(e)}"
                        print(error_msg)
                        self.__logger.log(error_msg)
                        return jsonify({'success': False, 'error': "Failed to detect landmarks or category!"}), 400

                # Filter landmarks by category with timing
                with self.__perf_monitor.timer("landmark_filtering"):
                    try:
                        category_landmarks = self.__landmark_predictor.filter_by_category(landmarks, category_id)
                    except Exception as e:
                        error_msg = f"Failed to filter landmarks by category {category_id}: {str(e)}"
                        print(error_msg)
                        self.__logger.log(error_msg)
                        return jsonify({'success': False, 'error': f"Invalid category_id: {category_id}"}), 400
                
                # Calculate measurements with timing
                with self.__perf_monitor.timer("measurement_calculation"):
                    try:
                        measurements = self.__measurer.calculate_measurements(img, category_landmarks, category_id=category_id)
                    except Exception as e:
                        error_msg = f"Failed to calculate measurements: {str(e)}"
                        print(error_msg)
                        self.__logger.log(error_msg)
                        return jsonify({'success': False, 'error': "Failed to calculate measurements"}), 500
                    
                    if measurements is None:
                        return jsonify({'success': False, 'error': "Could not calculate measurements from landmarks"}), 400
                    
                    print(f"Measurement keys: {list(measurements.keys())}")
                    self.__logger.log(f"Measurement keys: {list(measurements.keys())}")

                # Background image loading and line drawing with timing
                with self.__perf_monitor.timer("background_image_processing"):
                    bg_img = None
                    try:
                        if bg_img_url:
                            bg_img = self.__get_image_from_gcp_link(bg_img_url)
                        if bg_img is None and s3_url:
                            bg_img = self.__get_image_from_gcp_link(public_url=s3_url)
                            warning_msg = f"No background image provided, using removed mannequin image"
                            print(warning_msg)
                            self.__logger.log(warning_msg)
                        if bg_img is None and image_url:
                            bg_img = self.__get_image_from_gcp_link(public_url=image_url)
                            warning_msg = f"No background image provided, using removed mannequin image"
                            print(warning_msg)
                            self.__logger.log(warning_msg)
                        if bg_img is None and not img is None:
                            bg_img = img
                            warning_msg = f"No background image provided, using removed mannequin image"
                            print(warning_msg)
                            self.__logger.log(warning_msg)
                        
                        if bg_img is None: 
                            return jsonify({'success': False, 'error': "Could not load image for drawing"}), 500
                        
                    except:
                        error_msg = f"Failed to load background image, using removed mannequin image"
                        print(error_msg)
                        self.__logger.log(error_msg)
                        bg_img = img

                # Draw measurement lines with timing
                with self.__perf_monitor.timer("measurement_line_drawing"):
                    try:
                        self.__measurer.draw_lines(bg_img, measurements, category_id=category_id)
                    except Exception as e:
                        error_msg = f"Failed to draw measurement lines: {str(e)}"
                        print(error_msg)
                        self.__logger.log(error_msg)
                        # Continue without drawing - not critical

                # Upload result image with timing
                with self.__perf_monitor.timer("result_image_upload"):
                    new_gcp_link = self.__upload_image_to_gcp(image_data=bg_img, predicted=True)
                    if new_gcp_link is None:
                        self.__logger.log("Failed to upload result image to GCP Storage, continuing without URL")

            # Print performance report
            self.__perf_monitor.print_performance_report()
            
            # Get performance summary for response
            perf_summary = self.__perf_monitor.get_current_session_summary()

            return jsonify({
                'success': True,
                'measurements': measurements,
                'url': new_gcp_link,
                "category_name": category_name,
                'performance_timing': {
                    'total_time_seconds': perf_summary['total_session_time'],
                    'subtask_timings': perf_summary['subtasks'],
                    'subtask_percentages': perf_summary['subtask_percentages']
                }
            }), 200
        
        except Exception as e:
            error_msg = f"Unexpected error in get_measurements: {str(e)}"
            print(error_msg)
            self.__logger.log(error_msg)
            print(f"Traceback: {traceback.format_exc()}")
            self.__logger.log(f"Traceback: {traceback.format_exc()}")
            return jsonify({'error': 'Internal server error'}), 500

if __name__ == '__main__':
    try:
        api_app = ApiApp()
        api_app.run_app()
    except Exception as e:
        print(f"Failed to start application: {str(e)}")
        print(f"Traceback: {traceback.format_exc()}")
        sys.exit(1)

api_app_instance = ApiApp()
app = api_app_instance._ApiApp__app 
