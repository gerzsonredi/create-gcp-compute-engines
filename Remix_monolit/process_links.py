import json
import requests
import re
from collections import defaultdict
import random

def process_items_and_call_api():
    # Read the JSON file
    with open('items_photos_links.json', 'r', encoding='utf-8') as file:
        data = json.load(file)
    
    # Extract the items array (assuming there's only one key in the root object)
    items = list(data.values())[0]
    
    # Group items by SKU
    sku_groups = defaultdict(list)
    
    for item in items:
        sku = item['sku']
        image_url = item['image_url']
        sku_groups[sku].append(image_url)
    
    # Process each SKU group to order URLs as b, c, a
    garment_groups = []
    
    for sku, urls in sku_groups.items():
        # Create a dictionary to store URLs by their suffix letter
        url_dict = {'a': None, 'b': None, 'c': None}
        
        for url in urls:
            # Extract the letter suffix (a, b, or c) from the URL
            # URLs end with format: SKU_NUMBER + LETTER + .jpg
            match = re.search(rf'{sku}([abc])\.jpg$', url)
            if match:
                letter = match.group(1)
                url_dict[letter] = url
        
        # Create ordered group: b, c, a
        ordered_group = []
        for letter in ['b', 'c', 'a']:
            if url_dict[letter]:
                ordered_group.append(url_dict[letter])
        
        # Only add groups that have at least one URL
        if ordered_group:
            garment_groups.append(ordered_group)
    
    # random.shuffle(garment_groups)
    # Prepare the API request payload
    payload = {
        "garment_groups": garment_groups,
        "output_filename": "final_final_final.pdf"
    }
    
    # Print some statistics
    print(f"Total SKUs processed: {len(sku_groups)}")
    print(f"Total garment groups created: {len(garment_groups)}")
    print(f"Sample groups (first 3):")
    for i, group in enumerate(garment_groups[:3]):
        print(f"  Group {i+1}: {len(group)} images")
        for j, url in enumerate(group):
            print(f"    {j+1}. {url}")
    
    # Make the API call
    try:
        print("\nMaking API call to batch-analysis endpoint...")
        response = requests.post(
            'http://localhost:5000/batch-analysis',
            headers={'Content-Type': 'application/json'},
            json=payload,
            timeout=3000  # 5 minute timeout for batch processing
        )
        
        if response.status_code == 200:
            print("✅ API call successful!")
            print(f"Response: {response.json()}")
        else:
            print(f"❌ API call failed with status code: {response.status_code}")
            print(f"Response: {response.text}")
            
    except requests.exceptions.RequestException as e:
        print(f"❌ Error making API call: {str(e)}")
    
    return payload

def save_payload_to_file(payload, filename="batch_analysis_payload.json"):
    """Save the generated payload to a file for inspection"""
    with open(filename, 'w', encoding='utf-8') as file:
        json.dump(payload, file, indent=2, ensure_ascii=False)
    print(f"Payload saved to {filename}")

if __name__ == "__main__":
    # Process items and make API call
    payload = process_items_and_call_api()
    
    # Optionally save the payload to a file for inspection
    save_payload_to_file(payload, filename="test.pdf")