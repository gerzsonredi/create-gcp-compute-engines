import torch
import json
import tempfile
import os
from PIL import Image
from tools.SubcategoryDetector import SubcategoryDetector
from tools.constants import CATEGORY_LABELS
from google.cloud import storage


class ClothingCategoryPredictor:
    def __init__(self, logger):
        self.__logger = logger
        self.__device = 'cuda' if torch.cuda.is_available() else 'cpu'
        
        # Model configuration for SubCategoryViT
        self.__backbone = "WinKawaks/vit-tiny-patch16-224"  # Hidden size = 192 to match saved model
        self.__model_path = "models/category_predictor/SubCategoryViT/model_epoch_5.pt" 
        self.__bucket_name = "artifactsredi"
        
        # Load category mappings from label_maps.json
        self.__load_category_mappings()
        
        # Load and initialize SubCategoryViT model
        self.__load_model()
        
    def __load_category_mappings(self):
        """Load the 661 category mappings from label_maps.json"""
        try:
            label_maps_path = os.path.join("tools", "label_maps.json")
            with open(label_maps_path, 'r') as f:
                label_data = json.load(f)
            
            self.__category_maps = label_data["sub"]
            self.__logger.log(f"✅ Loaded {len(self.__category_maps)} categories from label_maps.json")
            
        except Exception as e:
            self.__logger.log(f"❌ Failed to load label mappings: {str(e)}")
            raise e
    
    def __load_model(self):
        """Load SubCategoryViT model from GCP Storage"""
        try:
            self.__logger.log(f"🔄 Loading SubCategoryViT model from GCP: {self.__model_path}")
            
            # Download model file to temporary location
            with tempfile.NamedTemporaryFile(suffix='.pt', delete=False) as tmp_file:
                tmp_path = tmp_file.name
                
            # Use GCP Storage Client directly for model download
            storage_client = storage.Client()
            bucket = storage_client.bucket(self.__bucket_name)
            blob = bucket.blob(self.__model_path)
            blob.download_to_filename(tmp_path)
            
            self.__logger.log(f"✅ Model downloaded to {tmp_path}")
            
            # Load state dict
            state_dict = torch.load(tmp_path, map_location=self.__device, weights_only=True)
            
            # Initialize SubcategoryDetector with the loaded model
            self.__model = SubcategoryDetector(
                backbone=self.__backbone,
                maps=self.__category_maps,
                state_dict=state_dict,
                logger=self.__logger
            )
            
            # Clean up temporary file
            os.unlink(tmp_path)
            
            self.__logger.log(f"✅ SubCategoryViT model loaded successfully on {self.__device}")
            
        except Exception as e:
            self.__logger.log(f"❌ Failed to load SubCategoryViT model: {str(e)}")
            raise e
    
    def pred(self, img, return_idx=False):
        """
        Receives an image in PIL Image format and returns the category name and probability.
        Compatible with existing API but uses SubCategoryViT internally.
        """
        try:
            # Get predictions using SubcategoryDetector
            predictions = self.__model.predict_topx(img, k=3)
            
            if not predictions:
                # Fallback
                category_name = "other"
                probability = 0.0
                category_id = 0
            else:
                # Get top prediction
                category_name, probability = predictions[0]
                
                # Map to original category system for compatibility  
                category_id = self.__map_to_original_categories(category_name)
            
            # Log prediction
            self.__logger.log(f"Predicted category: {category_name}, with certainty: {probability:.1%}")
            print(f"Predicted category: {category_name}, with certainty: {probability:.1%}")
            
            if return_idx:
                return category_id, probability
            
            # Return category_name, probability, category_id (compatible with original API)
            return category_name, probability, category_id
            
        except Exception as e:
            self.__logger.log(f"❌ Category prediction failed: {str(e)}")
            # Fallback to safe defaults
            if return_idx:
                return 0, 0.0
            return "other", 0.0, 0
    
    def predict_category(self, pil_image):
        """
        Legacy method for backward compatibility
        Returns: (category_id, category_name, confidence)
        """
        category_name, probability, category_id = self.pred(pil_image, return_idx=False)
        return category_id, category_name, probability
    
    def __map_to_original_categories(self, new_category_name: str) -> int:
        """Map new SubCategoryViT categories to original category IDs for compatibility"""
        # Mapping from new categories to original CATEGORY_LABELS indices
        mapping = {
            'tops': 1,           # short-sleeve top
            'blouses': 1,        # short-sleeve top  
            't-shirts': 1,       # short-sleeve top
            'shirts': 2,         # long-sleeve top
            'sweaters': 2,       # long-sleeve top
            'jackets': 3,        # short-sleeve outwear
            'coats': 4,          # long-sleeve outwear
            'leather': 4,        # long-sleeve outwear
            'cardigans': 5,      # vest
            'clothing': 5,       # vest
            'shorts': 7,         # shorts
            'trousers': 8,       # trousers
            'skirts': 9,         # skirt
            'dresses': 10,       # short-sleeve dress
            'jumpsuits': 10,     # short-sleeve dress
            'other': 0,          # other
        }
        
        # Convert to lowercase for comparison
        category_key = new_category_name.lower()
        return mapping.get(category_key, 0)  # Default to "other" if not found
