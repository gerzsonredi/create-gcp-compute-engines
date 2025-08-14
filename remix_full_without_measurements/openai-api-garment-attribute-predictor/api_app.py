from flask import Flask, request, jsonify
import asyncio
import cv2, sys, traceback
from tools.S3Loader import S3Loader
from tools.logger import EVFSAMLogger
from tools.ConditionPredictor import ConditionPredictor
from tools.OpenAIAssistant import OpenAIAssistant
from dotenv import load_dotenv
import os
import tools.constants as c

load_dotenv()

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
            
            print("Creating openai helper instance")
            self.__logger.log("Creating openai helper instance")
            api_key = os.getenv("OPENAI_API_KEY", "")
            if not api_key:
                print("ERROR: Failed to load OpenAI API Key")
                self.__logger.log("ERROR: Failed to load OpenAI API Key")
                raise
            self.__openai_assistant = OpenAIAssistant(api_key)

            print("Creating condition predictor instance")
            self.__logger.log("Creating condition predictor instance")
            try:
                self.__condition_predictor = ConditionPredictor(self.__openai_assistant, self.__logger, self.__s3loader)
            except Exception as e:
                print(f"Error loading label predictor: {e}")
                self.__logger.log(f"Error loading label predictor: {e}")
                raise e


            print("Setting up routes...")
            self.__logger.log("Setting up routes...")
            self.__app.route('/condition', methods=['POST'])(self.get_condition)
            self.__app.route('/get_attributes', methods=['POST'])(self._sync_get_attributes)
            self.__app.route('/micro_prompt', methods=['POST'])(self._sync_micro_prompt)
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
            self.__app.run(host='0.0.0.0', port=5004, debug=True)
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
        
    def get_condition(self):
        try:
            # Get image URLs from request
            data = request.get_json()
            if not data or 'image_urls' not in data:
                return jsonify({'error': 'No image URLs provided'}), 400

            image_urls = data['image_urls']
            if not isinstance(image_urls, list):
                return jsonify({'error': 'image_urls must be a list'}), 400

            if not image_urls:
                return jsonify({'error': 'Empty list of image URLs provided'}), 400

            # Get condition assessment from predictor
            condition_result = self.__condition_predictor.get_condition(image_urls)
            
            if condition_result is None:
                return jsonify({'error': 'Failed to get condition assessment'}), 500

            return jsonify(condition_result), 200

        except Exception as e:
            error_msg = f"Failed to get condition assessment: {str(e)}"
            print(error_msg)
            self.__logger.log(error_msg)
            return jsonify({'error': error_msg}), 500

    async def get_attributes(self):
        print("/get_attributes POST endpoint called.")
        try:
            # Get image URLs from request
            data = request.get_json()
            if not data or 'image_urls' not in data:
                error_msg = 'No image URLs provided'
                print(error_msg)
                self.__logger.log(error_msg)
                return jsonify({'error': error_msg}), 400

            image_urls = data['image_urls']
            if not isinstance(image_urls, list):
                error_msg = 'image_urls must be a list'
                print(error_msg)
                self.__logger.log(error_msg)
                return jsonify({'error': error_msg}), 400

            if not image_urls:
                error_msg = 'Empty list of image URLs provided'
                print(error_msg)
                self.__logger.log(error_msg)
                return jsonify({'error': error_msg}), 400
            
            print(image_urls)

            isRomanian = 'romanian' in data and data['romanian']

            if isRomanian:
                attribute_result = self.__openai_assistant.extract_data_romanian(
                    image_urls=image_urls,
                    json_schema=c.json_schema3,
                    prompt_message=c.prompt_message3
                )
            else:
                # Get attributes from predictor
                attribute_result = await self.__openai_assistant.extract_work_clothing_info(
                    image_urls=image_urls,
                    json_schema=c.json_schema2,
                    prompt_message=c.prompt_message2
                )
            
            if attribute_result is None:
                return jsonify({'error': 'Failed to get attribute assessment'}), 500

            return jsonify(attribute_result), 200

        except Exception as e:
            error_msg = f"Failed to get clothing attributes: {str(e)}"
            print(error_msg)
            self.__logger.log(error_msg)
            return jsonify({'error': error_msg}), 500

    async def micro_prompt(self):
        """Handle micro-prompt requests for specific attributes."""
        try:
            data = request.get_json()
            if not data:
                return jsonify({'error': 'No JSON data provided'}), 400
            
            image_urls = data.get('image_urls', [])
            prompt_type = data.get('prompt_type', '')
            
            if not image_urls:
                return jsonify({'error': 'No image URLs provided'}), 400
            
            if not prompt_type:
                return jsonify({'error': 'No prompt_type specified'}), 400
            
            # Define micro prompts and schemas - SIMPLE VERSION FOR SPEED
            micro_prompts = {
                'brand': {
                    'prompt': "Identify the brand name of this clothing item. Look for labels, tags, or logos. If no brand is visible, return empty string.",
                    'schema': {
                        "name": "brand_identification",
                        "strict": True,
                        "schema": {
                            "type": "object",
                            "properties": {
                                "brand": {"type": "string"}
                            },
                            "required": ["brand"],
                            "additionalProperties": False
                        }
                    }
                },
                'color': {
                    'prompt': "Identify the primary and secondary colors of this clothing item.",
                    'schema': {
                        "name": "color_identification",
                        "strict": True,
                        "schema": {
                            "type": "object",
                            "properties": {
                                "primary_color": {"type": "string"},
                                "secondary_colors": {"type": "string"}
                            },
                            "required": ["primary_color", "secondary_colors"],
                            "additionalProperties": False
                        }
                    }
                },
                'material': {
                    'prompt': "Identify the fabric composition of this clothing item. Look for fabric labels or tags.",
                    'schema': {
                        "name": "material_identification",
                        "strict": True,
                        "schema": {
                            "type": "object",
                            "properties": {
                                "fabric_composition": {"type": "string"}
                            },
                            "required": ["fabric_composition"],
                            "additionalProperties": False
                        }
                    }
                },
                'size': {
                    'prompt': "Identify the size of this clothing item. Look for size tags or labels.",
                    'schema': {
                        "name": "size_identification",
                        "strict": True,
                        "schema": {
                            "type": "object",
                            "properties": {
                                "size_tag": {"type": "string"}
                            },
                            "required": ["size_tag"],
                            "additionalProperties": False
                        }
                    }
                },
                'condition': {
                    'prompt': "Rate the condition of this clothing item from 1-10 and provide a brief description of any defects or wear.",
                    'schema': {
                        "name": "condition_assessment",
                        "strict": True,
                        "schema": {
                            "type": "object",
                            "properties": {
                                "condition_grade": {"type": "number"},
                                "condition_note": {"type": "string"}
                            },
                            "required": ["condition_grade", "condition_note"],
                            "additionalProperties": False
                        }
                    }
                }
            }
            
            if prompt_type not in micro_prompts:
                return jsonify({'error': f'Unknown prompt_type: {prompt_type}'}), 400
            
            micro_prompt_config = micro_prompts[prompt_type]
            
            # Call OpenAI with the micro prompt
            result = await self.__openai_assistant.extract_work_clothing_info(
                image_urls=image_urls,
                json_schema=micro_prompt_config['schema'],
                prompt_message=micro_prompt_config['prompt']
            )
            
            if result is None:
                return jsonify({'error': f'Failed to get {prompt_type} assessment'}), 500
            
            return jsonify(result), 200
            
        except Exception as e:
            error_msg = f"Failed to process micro prompt {prompt_type}: {str(e)}"
            print(error_msg)
            self.__logger.log(error_msg)
            return jsonify({'error': error_msg}), 500
        
    def health_check(self):
        print("Health check endpoint called")
        self.__logger.log("Health check endpoint called")
        return jsonify({'status': 'healthy', 'message': 'API is running'}), 200
    
    def _sync_get_attributes(self):
        """Synchronous wrapper for async get_attributes method."""
        return asyncio.run(self.get_attributes())
    
    def _sync_micro_prompt(self):
        """Synchronous wrapper for async micro_prompt method."""
        return asyncio.run(self.micro_prompt())
    
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
