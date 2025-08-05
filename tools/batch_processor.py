"""
Batch processor for garment analysis with SKU-based grouping.
Based on process_links.py logic.
"""

import json
import re
from collections import defaultdict
import random
from typing import List, Dict, Any


class BatchProcessor:
    """
    Handles batch processing of garment images with intelligent SKU grouping
    """
    
    def __init__(self, logger=None):
        self.logger = logger
    
    def process_sku_items(self, items_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process items from JSON file and group by SKU with intelligent ordering
        
        Args:
            items_data: Dictionary with items data from JSON file
            
        Returns:
            Dictionary with grouped garment data ready for batch processing
        """
        try:
            if self.logger:
                self.logger.log("🔄 Processing SKU items for batch analysis...")
            
            # Extract items array (assuming single key in root object)
            items = list(items_data.values())[0] if items_data else []
            
            # Group items by SKU
            sku_groups = defaultdict(list)
            
            for item in items:
                sku = item.get('sku', '')
                image_url = item.get('image_url', '')
                
                if sku and image_url:
                    sku_groups[sku].append(image_url)
            
            # Process each SKU group with intelligent ordering (b, c, a)
            garment_groups = []
            
            for sku, urls in sku_groups.items():
                # Create dictionary to store URLs by suffix letter
                url_dict = {'a': None, 'b': None, 'c': None}
                
                for url in urls:
                    # Extract letter suffix (a, b, or c) from URL
                    # URLs end with format: SKU_NUMBER + LETTER + .jpg
                    match = re.search(rf'{sku}([abc])\.jpg$', url)
                    if match:
                        letter = match.group(1)
                        url_dict[letter] = url
                
                # Create ordered group: b (main), c (side), a (detail)
                ordered_group = []
                for letter in ['b', 'c', 'a']:
                    if url_dict[letter]:
                        ordered_group.append(url_dict[letter])
                
                # Only add groups with at least one URL
                if ordered_group:
                    garment_groups.append(ordered_group)
            
            result = {
                'total_skus': len(sku_groups),
                'total_groups': len(garment_groups),
                'garment_groups': garment_groups,
                'processing_stats': {
                    'items_processed': len(items),
                    'skus_found': len(sku_groups),
                    'valid_groups': len(garment_groups)
                }
            }
            
            if self.logger:
                self.logger.log(f"✅ SKU processing complete: {len(sku_groups)} SKUs → {len(garment_groups)} groups")
            
            return result
            
        except Exception as e:
            error_msg = f"SKU processing failed: {str(e)}"
            if self.logger:
                self.logger.log(f"❌ {error_msg}")
            raise Exception(error_msg)
    
    def create_batch_payload(self, garment_groups: List[List[str]], output_filename: str = None) -> Dict[str, Any]:
        """
        Create batch analysis payload for API consumption
        
        Args:
            garment_groups: List of image URL groups
            output_filename: Optional custom filename
            
        Returns:
            API payload dictionary
        """
        from datetime import datetime
        
        if not output_filename:
            timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
            output_filename = f"batch_analysis_{timestamp}.json"
        
        payload = {
            "garment_groups": garment_groups,
            "output_filename": output_filename,
            "batch_info": {
                "total_groups": len(garment_groups),
                "created_timestamp": datetime.utcnow().isoformat(),
                "processing_mode": "sku_grouped"
            }
        }
        
        if self.logger:
            self.logger.log(f"📦 Batch payload created: {len(garment_groups)} groups")
        
        return payload
    
    def analyze_batch_results(self, results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Analyze batch processing results and provide statistics
        
        Args:
            results: List of individual processing results
            
        Returns:
            Analysis summary
        """
        try:
            total_processed = len(results)
            successful = sum(1 for r in results if r.get('success', False))
            failed = total_processed - successful
            
            # Analyze categories
            categories_found = defaultdict(int)
            confidence_scores = []
            
            for result in results:
                if result.get('success', False) and 'category_prediction' in result:
                    cat_pred = result['category_prediction']
                    if 'primary_category' in cat_pred:
                        category_name = cat_pred['primary_category'].get('name', 'unknown')
                        confidence = cat_pred['primary_category'].get('confidence', 0)
                        
                        categories_found[category_name] += 1
                        confidence_scores.append(confidence)
            
            # Calculate statistics
            avg_confidence = sum(confidence_scores) / len(confidence_scores) if confidence_scores else 0
            
            analysis = {
                'processing_summary': {
                    'total_processed': total_processed,
                    'successful': successful,
                    'failed': failed,
                    'success_rate': (successful / total_processed * 100) if total_processed > 0 else 0
                },
                'category_distribution': dict(categories_found),
                'confidence_stats': {
                    'average_confidence': avg_confidence,
                    'min_confidence': min(confidence_scores) if confidence_scores else 0,
                    'max_confidence': max(confidence_scores) if confidence_scores else 0,
                    'total_predictions': len(confidence_scores)
                },
                'top_categories': sorted(categories_found.items(), key=lambda x: x[1], reverse=True)[:5]
            }
            
            if self.logger:
                self.logger.log(f"📊 Batch analysis: {successful}/{total_processed} successful ({analysis['processing_summary']['success_rate']:.1f}%)")
                self.logger.log(f"🏷️ Top categories: {analysis['top_categories']}")
            
            return analysis
            
        except Exception as e:
            error_msg = f"Batch analysis failed: {str(e)}"
            if self.logger:
                self.logger.log(f"❌ {error_msg}")
            return {'error': error_msg}
    
    def shuffle_groups(self, garment_groups: List[List[str]], seed: int = None) -> List[List[str]]:
        """
        Shuffle garment groups for randomized processing
        
        Args:
            garment_groups: List of image groups
            seed: Optional random seed for reproducible shuffling
            
        Returns:
            Shuffled list of groups
        """
        if seed:
            random.seed(seed)
        
        shuffled = garment_groups.copy()
        random.shuffle(shuffled)
        
        if self.logger:
            self.logger.log(f"🔀 Shuffled {len(shuffled)} garment groups")
        
        return shuffled
    
    def sample_groups(self, garment_groups: List[List[str]], sample_size: int) -> List[List[str]]:
        """
        Sample a subset of garment groups for testing
        
        Args:
            garment_groups: List of image groups
            sample_size: Number of groups to sample
            
        Returns:
            Sampled subset of groups
        """
        if sample_size >= len(garment_groups):
            return garment_groups
        
        sampled = random.sample(garment_groups, sample_size)
        
        if self.logger:
            self.logger.log(f"📝 Sampled {len(sampled)} groups from {len(garment_groups)} total")
        
        return sampled


# Usage example and testing
if __name__ == "__main__":
    processor = BatchProcessor()
    
    # Example items data
    sample_data = {
        "items": [
            {"sku": "ABC123", "image_url": "https://example.com/ABC123a.jpg"},
            {"sku": "ABC123", "image_url": "https://example.com/ABC123b.jpg"},
            {"sku": "ABC123", "image_url": "https://example.com/ABC123c.jpg"},
            {"sku": "DEF456", "image_url": "https://example.com/DEF456b.jpg"},
            {"sku": "DEF456", "image_url": "https://example.com/DEF456c.jpg"},
        ]
    }
    
    # Process SKU items
    result = processor.process_sku_items(sample_data)
    print(f"Processed {result['total_groups']} groups from {result['total_skus']} SKUs")
    print("Sample groups:")
    for i, group in enumerate(result['garment_groups'][:2]):
        print(f"  Group {i+1}: {group}")
    
    # Create batch payload
    payload = processor.create_batch_payload(result['garment_groups'])
    print(f"\nBatch payload created with {len(payload['garment_groups'])} groups") 