"""
Category mapper for garment classification.
Maps clothing category names to category IDs used in CAT_SPEC_NODES.
"""

class CategoryMapper:
    def __init__(self):
        # Category mapping based on CAT_SPEC_NODES comments
        self.category_mapping = {
            # Category 1: short-sleeve top
            1: [
                'shirts', 'tops', 'tunics', 't-shirts', 'tank tops', 'blouses',
                'polo', 'tees', 'crop tops', 'halter tops', 'tube tops'
            ],
            
            # Category 2: long-sleeve top 
            2: [
                'sweaters', 'sweatshirts', 'cardigans', 'long-sleeve shirts',
                'long-sleeve tops', 'long-sleeve blouses', 'pullover', 'jumpers',
                'hoodies', 'long-sleeve tees', 'turtlenecks'
            ],
            
            # Category 3: short-sleeve outwear
            3: [
                'short-sleeve jackets', 'short-sleeve blazers', 'boleros',
                'short-sleeve coats', 'short-sleeve outerwear', 'kimonos',
                'short-sleeve cardigans', 'vests (open)', 'waistcoats'
            ],
            
            # Category 4: long-sleeve outwear
            4: [
                'coats', 'jackets', 'blazers', 'outerwear', 'long-sleeve blazers',
                'long-sleeve jackets', 'overcoats', 'parkas', 'windbreakers',
                'suit jackets', 'sport coats', 'trench coats', 'peacoats',
                'bomber jackets', 'denim jackets', 'leather jackets'
            ],
            
            # Category 5: vest
            5: [
                'vests', 'waistcoats', 'vest tops', 'sleeveless tops',
                'tank tops (fitted)', 'gilets'
            ],
            
            # Category 6: sling
            6: [
                'sling', 'camisoles', 'spaghetti straps', 'slip tops',
                'bandeau tops', 'strapless tops'
            ],
            
            # Category 7: shorts
            7: [
                'shorts', 'swim shorts', 'board shorts', 'cargo shorts',
                'denim shorts', 'athletic shorts', 'bermuda shorts',
                'hot pants', 'short shorts'
            ],
            
            # Category 8: trousers
            8: [
                'trousers', 'jeans', 'leggings', 'sweatpants', 'pants',
                'slacks', 'chinos', 'joggers', 'track pants', 'cargo pants',
                'dress pants', 'skinny jeans', 'bootcut jeans', 'straight jeans',
                'wide leg pants', 'palazzo pants', 'yoga pants'
            ],
            
            # Category 9: skirt
            9: [
                'skirts', 'mini skirts', 'midi skirts', 'maxi skirts',
                'a-line skirts', 'pencil skirts', 'pleated skirts',
                'wrap skirts', 'circle skirts'
            ],
            
            # Category 10: short-sleeve dress
            10: [
                'short-sleeve dresses', 'short-sleeve dress', 'summer dresses',
                't-shirt dresses', 'shift dresses', 'sundresses',
                'short-sleeve midi dress', 'short-sleeve maxi dress'
            ],
            
            # Category 11: long-sleeve dress
            11: [
                'long-sleeve dresses', 'long-sleeve dress', 'sweater dresses',
                'long-sleeve midi dress', 'long-sleeve maxi dress',
                'winter dresses', 'knit dresses'
            ],
            
            # Category 12: vest dress
            12: [
                'vest dresses', 'vest dress', 'sleeveless dresses',
                'tank dresses', 'pinafore dresses', 'jumper dresses'
            ],
            
            # Category 13: sling dress
            13: [
                'sling dresses', 'sling dress', 'slip dresses',
                'camisole dresses', 'spaghetti strap dresses'
            ]
        }
        
        # Create reverse mapping for faster lookup
        self.name_to_category = {}
        for category_id, names in self.category_mapping.items():
            for name in names:
                self.name_to_category[name.lower()] = category_id
        
        # Add label_maps.json specific mappings
        self.label_specific_mapping = {
            'blazers': 4,           # long-sleeve outwear
            'body': 1,              # short-sleeve top
            'boleros': 3,           # short-sleeve outwear
            'cardigans': 2,         # long-sleeve top
            'coats': 4,             # long-sleeve outwear
            'dresses': 10,          # default to short-sleeve dress
            'jackets': 4,           # long-sleeve outwear
            'jeans': 8,             # trousers
            'jumpsuits': 10,        # treat as dress category
            'leggings': 8,          # trousers
            'outerwear': 4,         # long-sleeve outwear
            'shirts': 1,            # short-sleeve top
            'shorts': 7,            # shorts
            'skirts': 9,            # skirt
            'suits': 4,             # long-sleeve outwear
            'sweaters': 2,          # long-sleeve top
            'sweatpants': 8,        # trousers
            'sweatshirts': 2,       # long-sleeve top
            'swimwear': 7,          # shorts (swimwear bottom)
            'tops': 1,              # short-sleeve top
            'trousers': 8,          # trousers
            'tunics': 1,            # short-sleeve top
            'underwear': 1,         # short-sleeve top
            'vests': 5,             # vest
        }
        
        # Merge label-specific mappings
        self.name_to_category.update(self.label_specific_mapping)

    def get_category_id(self, category_name):
        """
        Get category ID from category name.
        
        Args:
            category_name (str): Name of the clothing category
            
        Returns:
            int: Category ID (1-13) or 1 as default
        """
        if not category_name:
            return 1  # Default category
            
        category_name = category_name.lower().strip()
        
        # Direct lookup
        if category_name in self.name_to_category:
            return self.name_to_category[category_name]
        
        # Fuzzy matching for common variations
        for name, category_id in self.name_to_category.items():
            if category_name in name or name in category_name:
                return category_id
        
        # Special handling for compound words
        if 'dress' in category_name:
            if 'long' in category_name or 'sleeve' in category_name:
                return 11  # long-sleeve dress
            elif 'vest' in category_name or 'sleeveless' in category_name:
                return 12  # vest dress
            elif 'sling' in category_name or 'slip' in category_name:
                return 13  # sling dress
            else:
                return 10  # default to short-sleeve dress
        
        if 'top' in category_name:
            if 'long' in category_name:
                return 2  # long-sleeve top
            elif 'tank' in category_name or 'vest' in category_name:
                return 5  # vest
            else:
                return 1  # short-sleeve top
        
        if 'jacket' in category_name or 'coat' in category_name:
            return 4  # long-sleeve outwear
        
        if 'pant' in category_name or 'jean' in category_name:
            return 8  # trousers
        
        # Default to category 1 (short-sleeve top)
        return 1

    def get_category_name(self, category_id):
        """
        Get category name from category ID.
        
        Args:
            category_id (int): Category ID (1-13)
            
        Returns:
            str: Category name
        """
        category_names = {
            1: "short-sleeve top",
            2: "long-sleeve top", 
            3: "short-sleeve outwear",
            4: "long-sleeve outwear",
            5: "vest",
            6: "sling",
            7: "shorts",
            8: "trousers",
            9: "skirt",
            10: "short-sleeve dress",
            11: "long-sleeve dress",
            12: "vest dress",
            13: "sling dress"
        }
        
        return category_names.get(category_id, "unknown")

    def get_all_categories(self):
        """
        Get all available categories.
        
        Returns:
            dict: Mapping of category ID to category name
        """
        return {i: self.get_category_name(i) for i in range(1, 14)}

    def get_category_examples(self, category_id):
        """
        Get example items for a category.
        
        Args:
            category_id (int): Category ID (1-13)
            
        Returns:
            list: List of example category names
        """
        return self.category_mapping.get(category_id, [])


# Usage example and testing
if __name__ == "__main__":
    mapper = CategoryMapper()
    
    # Test some mappings
    test_items = [
        "dresses", "jackets", "jeans", "shorts", "skirts", 
        "sweaters", "tops", "vests", "blazers", "coats"
    ]
    
    print("Category Mapping Tests:")
    for item in test_items:
        category_id = mapper.get_category_id(item)
        category_name = mapper.get_category_name(category_id)
        print(f"{item:15} -> Category {category_id:2d}: {category_name}")
    
    print("\nAll Categories:")
    for cat_id, cat_name in mapper.get_all_categories().items():
        examples = mapper.get_category_examples(cat_id)[:3]  # Show first 3 examples 
        print(f"Category {cat_id:2d}: {cat_name:20} (examples: {', '.join(examples)})")