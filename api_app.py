from flask import Flask, request, jsonify
import cv2, sys
from tools.ClothingLandmarkPredictor import ClothingLandmarkPredictor
from tools.ClothingMeasurer import ClothingMeasurer
from tools.S3Loader import S3Loader
from tools.logger import EVFSAMLogger

class ApiApp:
    def __init__(self):
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
        self.__app.route('/health', methods=['GET'])(self.health_check)
        print("Flask app initialized successfully!")
        self.__logger.log("Flask app initialized successfully!")

    def run_app(self):
        sys.stdout.reconfigure(line_buffering=True)
        self.__app.run(host='0.0.0.0', port=5000, debug=True)

    # ----- HELPERS -----
    def __get_image_from_s3_link(self, public_url):
        return self.__s3loader.get_image_from_link(public_url=public_url)

    def __upload_image_to_s3(self, public_url="", image_path="", image_data=None, predicted=False):
        """
        Calls S3Loader upload_s3_image function. 
        This function expects either a public url or a local image path, that it will upload to S3.
        Returns public S3 url.
        """
        return self.__s3loader.upload_s3_image(public_url=public_url, image_path=image_path, image_data=image_data, predicted_image=predicted)

    def __get_landmarks_helper(self, image_url="", image_path=""):
        try:
            print(f"Attempting S3 upload with image_url: {image_url}, image_path: {image_path}")
            self.__logger.log(f"Attempting S3 upload with image_url: {image_url}, image_path: {image_path}")
            s3_url = self.__upload_image_to_s3(public_url=image_url, image_path=image_path)
            print(f"S3 upload result: {s3_url}")
            self.__logger.log(f"S3 upload result: {s3_url}")

            if s3_url:
                img = self.__get_image_from_s3_link(public_url=s3_url)
                if img is None:
                    img = self.__get_image_from_s3_link(public_url=image_url)
                landmarks = self.__landmark_predictor.predict_landmarks(img=img)
            else:
                if image_path:
                    print(f"Falling back to local file: {image_path}")
                    self.__logger.log(f"Falling back to local file: {image_path}")
                    img = cv2.imread(str(image_path))
                    landmarks = self.__landmark_predictor.predict_landmarks(img=img)
                else:
                    print("ERROR: No valid image source available")
                    self.__logger.log("ERROR: No valid image source available")
                    return None
            
            return landmarks, s3_url
            
        except Exception as e:
            print(f"ERROR getting landmarks: {e}")
            self.__logger.log(f"ERROR getting landmarks: {e}")
            return None


    # ----- ENDPOINTS -----
    def get_landmarks(self):
        try:
            # Get image path from request
            data = request.get_json()
            image_path = data.get('image_path', '')
            image_url  = data.get('image_url', '')
            
            if not image_path and not image_url:
                return jsonify({'error': 'image is required'}), 400
            
            landmarks, _ = self.__get_landmarks_helper(image_url=image_url, image_path=image_path)
            if landmarks is None:
                return jsonify({'success': False, 'message': "Couldn't read landmarks!"}), 400
            return jsonify({
                'success': True,
                'landmarks': landmarks.tolist()  # Convert numpy array to list
            })
        except Exception as e:
            print(f"Error in get_landmarks: {str(e)}")
            self.__logger.log(f"Error in get_landmarks: {str(e)}")
            return jsonify({'error': str(e)}), 500

    def get_measurements(self):
        try:
            data = request.get_json()
            image_path  = data.get('image_path', '')
            image_url   = data.get('image_url', '')
            category_id = data.get('category_id', 1)
            
            if not image_path and not image_url:
                return jsonify({'error': 'image is required'}), 400
            
            landmarks, s3_url = self.__get_landmarks_helper(image_url=image_url, image_path=image_path)
            
            if landmarks is None:
                return jsonify({'success': False, 'message': "Couldn't read landmarks!"}), 400
            # Filter by category
            category_landmarks = self.__landmark_predictor.filter_by_category(landmarks, category_id)
            
            img = self.__get_image_from_s3_link(s3_url)
            if img is None:
                img = self.__get_image_from_s3_link(public_url=image_url)
            measurements = self.__measurer.calculate_measurements(img, category_landmarks, category_id=category_id)
            
            if measurements is None:
                return jsonify({'success': False, 'message': "Failed to calculate measurements"}), 400
            print(f"Measurement keys: {list(measurements.keys())}")
            self.__logger.log(f"Measurement keys: {list(measurements.keys())}")

            # draw the lines on the image
            self.__measurer.draw_lines(img, measurements, category_id=category_id)

            new_s3_link = self.__upload_image_to_s3(image_data=img, predicted=True)

            return jsonify({
                'success': True,
                'measurements': measurements,
                'url': new_s3_link
            })
        
        except Exception as e:
            print(f"Error in get_measurements: {str(e)}")
            self.__logger.log(f"Error in get_measurements: {str(e)}")
            print(e.with_traceback())
            return jsonify({'error': str(e)}), 500

    def health_check(self):
        print("Health check endpoint called")
        self.__logger.log("Health check endpoint called")
        return jsonify({'status': 'healthy', 'message': 'API is running'}), 200
    
if __name__ == '__main__':
    api_app = ApiApp()
    api_app.run_app()

# For gunicorn
api_app_instance = ApiApp()
app = api_app_instance._ApiApp__app 