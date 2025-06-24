from flask import Flask, request, jsonify
import cv2
from tools.ClothingLandmarkPredictor import ClothingLandmarkPredictor
from tools.ClothingMeasurer import ClothingMeasurer
from tools.S3Loader import S3Loader

class ApiApp():
    def __init__(self):
        print("Starting Flask app...")
        self.__app = Flask(__name__, static_folder='', static_url_path='')
        self.__app.secret_key = 'my-secret-key'

        print("Loading S3Loader...")
        self.__s3loader = S3Loader()
        print("Loading HRNet model...")
        state = self.__s3loader.load_hrnet_model()
        print("Initializing ClothingLandmarkPredictor...")
        self.__landmark_predictor = ClothingLandmarkPredictor(state=state)
        print("Initializing ClothingMeasurer...")
        self.__measurer = ClothingMeasurer()

        print("Setting up routes...")
        self.__app.route('/landmarks', methods=['POST'])(self.get_landmarks)
        self.__app.route('/measurements', methods=['POST'])(self.get_measurements)
        self.__app.route('/health', methods=['GET'])(self.health_check)
        print("Flask app initialized successfully!")

    def run_app(self):
        self.__app.run(host='0.0.0.0', port=5000, debug=True)

    # ----- HELPERS -----
    def get_image_from_s3_link(self, public_url):
        return self.__s3loader.get_image_from_link(public_url=public_url)

    def upload_image_to_s3(self, public_url="", image_path=""):
        """
        Calls S3Loader upload_s3_image function. 
        This function expects either a public url or a local image path, that it will upload to S3.
        Returns public S3 url.
        """
        return self.__s3loader.upload_s3_image(public_url=public_url, image_path=image_path)

    def __get_landmarks_helper(self, image_url="", image_path=""):
        try:
            s3_url = self.upload_image_to_s3(public_url=image_url, image_path=image_path)

            if s3_url:
                img = self.get_image_from_s3_link(public_url=s3_url)
                # Predict landmarks
                landmarks = self.__landmark_predictor.predict_landmarks(img=img)
            else:
                # failed to upload image to s3
                img = cv2.imread(str(image_path))
                landmarks = self.__landmark_predictor.predict_landmarks(img=img)
            
            return landmarks
            
        except Exception as e:
            print("ERROR getting landmarks")
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
            
            landmarks = self.__get_landmarks_helper(image_url=image_url, image_path=image_path)
            if not landmarks:
                return jsonify({'success': False, 'message': "Couldn't read landmarks!"}), 400
            return jsonify({
                'success': True,
                'landmarks': landmarks.tolist()  # Convert numpy array to list
            })
        except Exception as e:
            return jsonify({'error': str(e)}), 500

    def get_measurements(self):
        try:
            data = request.get_json()
            image_path  = data.get('image_path', '')
            image_url   = data.get('image_url', '')
            category_id = data.get('category_id', 1)
            
            if not image_path and not image_url:
                return jsonify({'error': 'image is required'}), 400
            
            landmarks = self.__get_landmarks_helper(image_url=image_url, image_path=image_path)
            
            # Filter by category
            category_landmarks = self.__landmark_predictor.filter_by_category(landmarks, category_id)
            
            # Calculate measurements (you'll need to load the image for this)

            img = cv2.imread(image_path)
            measurements = self.__measurer.calculate_measurements(img, category_landmarks, category_id=category_id)
            
            return jsonify({
                'success': True,
                'measurements': measurements
            })
        except Exception as e:
            return jsonify({'error': str(e)}), 500

    def health_check(self):
        return jsonify({'status': 'healthy', 'message': 'API is running'}), 200
    
if __name__ == '__main__':
    api_app = ApiApp()
    api_app.run_app()