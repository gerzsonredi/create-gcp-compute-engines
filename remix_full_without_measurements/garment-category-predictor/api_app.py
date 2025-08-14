from flask import Flask, request, jsonify
import sys
from tools.S3Loader import S3Loader
from tools.logger import EVFSAMLogger

class ApiApp():
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
            
            print("Loading SubcategoryDetector...")
            self.__logger.log("Loading SubcategoryDetector...")
            self.__subcategory_detector = self.__s3loader.load_category_model()
            
            if self.__subcategory_detector is None:
                error_msg = "Failed to load SubcategoryDetector - model returned None"
                print(f"ERROR: {error_msg}")
                self.__logger.log(f"ERROR: {error_msg}")
                exit(1)
                
            print("Setting up routes...")
            self.__logger.log("Setting up routes...")
            self.__app.route('/category', methods=['POST'])(self.get_category)
            self.__app.route('/health', methods=['GET'])(self.health_check)
            
            print("Flask app initialized successfully!")
            self.__logger.log("Flask app initialized successfully!")
            
        except Exception as e:
            error_msg = f"Failed to initialize ApiApp: {str(e)}"
            print(f"CRITICAL ERROR: {error_msg}")
            if hasattr(self, '_ApiApp__logger'):
                self.__logger.log(f"CRITICAL ERROR: {error_msg}")
            exit(1)

    def run_app(self):
        try:
            sys.stdout.reconfigure(line_buffering=True)
            self.__app.run(host='0.0.0.0', port=5002, debug=True)
        except Exception as e:
            error_msg = f"Failed to start Flask application: {str(e)}"
            print(f"ERROR: {error_msg}")
            self.__logger.log(f"ERROR: {error_msg}")
            raise

    def get_category(self):
        try:
            # Get JSON data from request
            try:
                data = request.get_json()
                if data is None:
                    error_msg = "Invalid JSON in request body"
                    self.__logger.log(f"Bad Request: {error_msg}")
                    return jsonify({'error': error_msg}), 400
            except Exception as e:
                error_msg = f"Failed to parse JSON: {str(e)}"
                self.__logger.log(f"Bad Request: {error_msg}")
                return jsonify({'error': error_msg}), 400
            
            # Extract image URL
            image_url = data.get('image_url', '')
            
            if not image_url:
                error_msg = "image_url is required"
                self.__logger.log(f"Bad Request: {error_msg}")
                return jsonify({'error': error_msg}), 400
            
            # Load image from URL
            try:
                # image = self.__subcategory_detector.load_image_from_url(image_url)
                image = self.__s3loader.get_image_from_link(image_url)
            except Exception as e:
                error_msg = f"Failed to load image from URL '{image_url}': {str(e)}"
                self.__logger.log(f"Image Loading Error: {error_msg}")
                return jsonify({
                    'success': False,
                    'error': 'Failed to load image from provided URL'
                }), 400

            if image is None:
                error_msg = f"Image loading returned None for URL: {image_url}"
                self.__logger.log(f"Image Loading Error: {error_msg}")
                return jsonify({
                    'success': False,
                    'error': 'Failed to load image - invalid URL or unsupported format'
                }), 400

            # Make prediction
            try:
                topx = self.__subcategory_detector.predict_topx(image)
            except Exception as e:
                error_msg = f"Prediction failed for image: {str(e)}"
                self.__logger.log(f"Prediction Error: {error_msg}")
                return jsonify({
                    'success': False,
                    'error': 'Failed to predict category - model error'
                }), 500
            
            # Log successful prediction
            self.__logger.log(f"Successful prediction for URL: {image_url}")
            
            return jsonify({
                'success': True,
                'topx': topx
            })
            
        except Exception as e:
            # Catch-all for any unexpected errors
            error_msg = f"Unexpected error in get_category: {str(e)}"
            print(f"ERROR: {error_msg}")
            self.__logger.log(f"Unexpected Error: {error_msg}")
            return jsonify({
                'success': False,
                'error': 'Internal server error occurred'
            }), 500
        
    def health_check(self):
        print("Health check endpoint called")
        self.__logger.log("Health check endpoint called")
        return jsonify({'status': 'healthy', 'message': 'API is running'}), 200
        
    
if __name__ == '__main__':
    try:
        api_app = ApiApp()
        api_app.run_app()
    except Exception as e:
        print(f"CRITICAL ERROR: Application failed to start: {str(e)}")
        exit(1)

api_app_instance = ApiApp()
app = api_app_instance._ApiApp__app 