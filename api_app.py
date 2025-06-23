from flask import Flask, request, jsonify
import cv2
from tools.ClothingLandmarkPredictor import ClothingLandmarkPredictor
from tools.ClothingMeasurer import ClothingMeasurer

"""
# Build the image
docker build -t clothing-api .

# Run the container
docker run -p 5000:5000 clothing-api
"""

class ApiApp():
    def __init__(self):
        app = Flask(__name__, static_folder='', static_url_path='')
        app.secret_key = 'my-secret-key'

        self.__landmark_predictor = ClothingLandmarkPredictor()
        self.__measurer = ClothingMeasurer()

        self.__app.route('/landmarks', methods=['POST'])(self.get_landmarks)
        self.__app.route('/measurements', methods=['POST'])(self.get_measurements)
        self.__app.route('/health', methods=['GET'])(self.health_check)


    def run_app(self):
        self.__app.run()


    def get_landmarks(self):
        try:
            # Get image path from request
            data = request.get_json()
            image_path = data.get('image_path')
            
            if not image_path:
                return jsonify({'error': 'image_path is required'}), 400
            
            # Predict landmarks
            landmarks = self.__landmark_predictor.predict_landmarks(image_path)
            
            return jsonify({
                'success': True,
                'landmarks': landmarks.tolist()  # Convert numpy array to list
            })
        except Exception as e:
            return jsonify({'error': str(e)}), 500

    def get_measurements(self):
        try:
            data = request.get_json()
            image_path = data.get('image_path')
            category_id = data.get('category_id', 1)
            
            if not image_path:
                return jsonify({'error': 'image_path is required'}), 400
            
            # Get landmarks first
            landmarks = self.__landmark_predictor.predict_landmarks(image_path)
            
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