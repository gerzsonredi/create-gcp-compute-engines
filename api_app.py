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
                print("Initializing ParallelPredictor for simultaneous processing...")
                self.__logger.log("Initializing ParallelPredictor for simultaneous processing...")
                self.__parallel_predictor = ParallelPredictor(
                    landmark_predictor=self.__landmark_predictor,
                    category_predictor=self.__category_predictor,
                    logger=self.__logger
                )

            # Set up routes (simplified for testing)
            self.__app.add_url_rule('/health', 'health', self.health_check, methods=['GET'])
            self.__app.add_url_rule('/measurements', 'measurements', self.get_measurements, methods=['POST'])
            self.__app.add_url_rule('/benchmark', 'benchmark', self.benchmark_parallel, methods=['POST'])

            print("✅ API initialization completed with parallel processing!")
            self.__logger.log("✅ API initialization completed with parallel processing!")
            
        except Exception as e:
            error_msg = f"Failed to initialize ApiApp: {str(e)}"
            print(error_msg)
            if hasattr(self, '_ApiApp__logger'):
                self.__logger.log(error_msg)
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
        print("Health check endpoint called")
        self.__logger.log("Health check endpoint called")
        return jsonify({'status': 'healthy', 'message': 'API is running'}), 200
    
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
