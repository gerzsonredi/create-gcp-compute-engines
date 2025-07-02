from flask import Flask, request, jsonify
import cv2, sys, traceback
from tools.ClothingLandmarkPredictor import ClothingLandmarkPredictor
from tools.ClothingMeasurer import ClothingMeasurer
from tools.S3Loader import S3Loader
from tools.logger import EVFSAMLogger

class ApiApp:
    def __init__(self):
        try:
            self.__logger = EVFSAMLogger()
            print("Starting Flask app...")
            self.__logger.log("Starting Flask app...")
            
            self.__app = Flask(__name__, static_folder='', static_url_path='')
            self.__app.secret_key = 'my-secret-key'

            print("Loading S3Loader...")
            self.__logger.log("Loading S3Loader...")
            self.__s3loader = S3Loader(logger=self.__logger)
            
            print("Loading HRNet model...")
            self.__logger.log("Loading HRNet model...")
            state = self.__s3loader.load_hrnet_model()
            
            print("Initializing ClothingLandmarkPredictor...")
            self.__logger.log("Initializing ClothingLandmarkPredictor...")
            self.__landmark_predictor = ClothingLandmarkPredictor(logger=self.__logger, state=state)
            
            print("Initializing ClothingMeasurer...")
            self.__logger.log("Initializing ClothingMeasurer...")
            self.__measurer = ClothingMeasurer(logger=self.__logger)

            print("Setting up routes...")
            self.__logger.log("Setting up routes...")
            self.__app.route('/landmarks', methods=['POST'])(self.get_landmarks)
            self.__app.route('/measurements', methods=['POST'])(self.get_measurements)
            self.__app.route('/draw_measurements', methods=['POST'])(self.draw_measurements)
            self.__app.route('/health', methods=['GET'])(self.health_check)
            
            print("Flask app initialized successfully!")
            self.__logger.log("Flask app initialized successfully!")
            
        except Exception as e:
            error_msg = f"Failed to initialize ApiApp: {str(e)}"
            print(error_msg)
            print(f"Traceback: {traceback.format_exc()}")
            if hasattr(self, '_ApiApp__logger'):
                self.__logger.log(error_msg)
                self.__logger.log(f"Traceback: {traceback.format_exc()}")
            raise

    def run_app(self):
        try:
            sys.stdout.reconfigure(line_buffering=True)
            self.__app.run(host='0.0.0.0', port=5003, debug=True)
        except Exception as e:
            error_msg = f"Failed to start Flask app: {str(e)}"
            print(error_msg)
            self.__logger.log(error_msg)
            raise

    # ----- HELPERS -----
    def __get_image_from_s3_link(self, public_url):
        try:
            return self.__s3loader.get_image_from_link(public_url=public_url)
        except Exception as e:
            error_msg = f"Failed to get image from S3 link {public_url}: {str(e)}"
            print(error_msg)
            self.__logger.log(error_msg)
            return None

    def __upload_image_to_s3(self, public_url="", image_path="", image_data=None, predicted=False):
        """
        Calls S3Loader upload_s3_image function. 
        This function expects either a public url or a local image path, that it will upload to S3.
        Returns public S3 url.
        """
        try:
            return self.__s3loader.upload_s3_image(
                public_url=public_url, 
                image_path=image_path, 
                image_data=image_data, 
                predicted_image=predicted
            )
        except Exception as e:
            error_msg = f"Failed to upload image to S3: {str(e)}"
            print(error_msg)
            self.__logger.log(error_msg)
            return None

    def __get_landmarks_helper(self, image_url="", image_path=""):
        try:
            print(f"Attempting S3 upload with image_url: {image_url}, image_path: {image_path}")
            self.__logger.log(f"Attempting S3 upload with image_url: {image_url}, image_path: {image_path}")
            
            s3_url = self.__upload_image_to_s3(public_url=image_url, image_path=image_path)
            print(f"S3 upload result: {s3_url}")
            self.__logger.log(f"S3 upload result: {s3_url}")

            img = None
            if s3_url or image_url:
                img = self.__get_image_from_s3_link(public_url=s3_url)
                if img is None:
                    img = self.__get_image_from_s3_link(public_url=image_url)
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
                return landmarks, s3_url
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

    # ----- ENDPOINTS -----
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
            
            image_path  = data.get('image_path', '')
            image_url   = data.get('image_url', '')     # the removed mannequin image used to calculate measurements
            category_id = data.get('category_id', 1)
            bg_img_url  = data.get('bg_img_url', '')    # original image to use as background, to draw the measurements
            
            # Validate category_id
            try:
                category_id = int(category_id)
            except (ValueError, TypeError):
                return jsonify({'error': 'category_id must be an integer'}), 400
            
            if not image_path and not image_url:
                return jsonify({'error': 'Either image_path or image_url is required'}), 400
            
            result = self.__get_landmarks_helper(image_url=image_url, image_path=image_path)
            if result is None:
                return jsonify({'success': False, 'error': "Failed to get landmarks"}), 500
                
            landmarks, s3_url = result
            if landmarks is None:
                return jsonify({'success': False, 'error': "Could not detect landmarks in image"}), 400
            
            # Filter by category with error handling
            try:
                category_landmarks = self.__landmark_predictor.filter_by_category(landmarks, category_id)
            except Exception as e:
                error_msg = f"Failed to filter landmarks by category {category_id}: {str(e)}"
                print(error_msg)
                self.__logger.log(error_msg)
                return jsonify({'success': False, 'error': f"Invalid category_id: {category_id}"}), 400
            
            # Get image for measurements
            img = None
            if s3_url:
                img = self.__get_image_from_s3_link(s3_url)
            if img is None and image_url:
                img = self.__get_image_from_s3_link(public_url=image_url)
            
            if img is None:
                return jsonify({'success': False, 'error': "Could not load image for measurements"}), 500
            
            # Calculate measurements with error handling
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

            # Draw lines on background image with error handling
            bg_img = None
            try:
                if bg_img_url:
                    bg_img = self.__get_image_from_s3_link(bg_img_url)
                if bg_img is None and s3_url:
                    bg_img = self.__get_image_from_s3_link(public_url=s3_url)
                if bg_img is None and image_url:
                    bg_img = self.__get_image_from_s3_link(public_url=image_url)
                if bg_img is None and not img is None:
                    bg_img = img
                
                if bg_img is None: 
                    return jsonify({'success': False, 'error': "Could not load image for drawing"}), 500
                
                warning_msg = f"No background image provided, using removed mannequin image"
                print(warning_msg)
                self.__logger.log(warning_msg)
            except:
                error_msg = f"Failed to load background image, using removed mannequin image"
                print(error_msg)
                self.__logger.log(error_msg)
                bg_img = img
                
            try:
                self.__measurer.draw_lines(bg_img, measurements, category_id=category_id)
            except Exception as e:
                error_msg = f"Failed to draw measurement lines: {str(e)}"
                print(error_msg)
                self.__logger.log(error_msg)
                # Continue without drawing - not critical

            # Upload result image with error handling
            new_s3_link = self.__upload_image_to_s3(image_data=bg_img, predicted=True)
            if new_s3_link is None:
                self.__logger.log("Failed to upload result image to S3, continuing without URL")

            return jsonify({
                'success': True,
                'measurements': measurements,
                'url': new_s3_link
            })
        
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
