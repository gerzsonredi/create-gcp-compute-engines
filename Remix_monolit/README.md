# Garment Analysis API

A comprehensive garment analysis API that orchestrates multiple microservices to provide:

- Mannequin removal from garment images
- Garment category prediction
- Measurement extraction with landmarks
- Condition assessment
- Batch processing with PDF report generation

## Quick Start

### Prerequisites

- Docker and Docker Compose installed
- All microservices running via docker-compose

### Initial Setup

1. **Create required directories:**
```bash
# Create directories for PDF reports
mkdir -p reports

# Set proper permissions
chmod 755 reports
```

2. **Environment Variables:**
Create a `.env` file in the root directory:
```env
# Main API Configuration
MAIN_API_PORT=5000

# Microservice configurations (use service names for internal communication)
MANNEQUIN_SEGMENTER_HOST=mannequin-segmenter
MANNEQUIN_SEGMENTER_PORT=5000

CATEGORY_PREDICTOR_HOST=category-predictor
CATEGORY_PREDICTOR_PORT=5000

MEASURING_HPE_HOST=measuring-hpe
MEASURING_HPE_PORT=5000

ATTRIBUTE_PREDICTOR_HOST=attribute-predictor
ATTRIBUTE_PREDICTOR_PORT=5000

# AWS credentials (if needed for S3 access)
AWS_ACCESS_KEY_ID=your_access_key
AWS_SECRET_ACCESS_KEY=your_secret_key
AWS_S3_BUCKET_NAME=your_bucket_name
AWS_S3_REGION=your_region
```

### Starting the Services

```bash
# Start all microservices
sudo docker compose up -d --build

# Check if all services are healthy
curl http://localhost:5000/health

# View logs
sudo docker compose logs -f
```

### Project Structure

After setup, your project structure should look like:
Remix/
├── docker-compose.yml
├── dockerfile
├── main.py
├── category_mapper.py
├── pdf_generator.py
├── requirements.txt
├── .env
├── reports/ # PDF reports saved here (volume mounted)
│ ├── batch_report_20250627_140825.pdf
│ └── ...
├── mannequin-segmenter/
├── garment-category-predictor/
├── garment-measuring-hpe/
├── openai-api-garment-attribute-predictor/
└── README.md

## API Endpoints****

### 1. Health Check

Check the status of the main orchestrator and all microservices.

**Endpoint:** `GET /health`

```bash
curl http://localhost:5000/health
```

**Response:**

```json
{
  "main": {
    "status": "healthy",
    "timestamp": "2025-06-27T14:38:18.756815",
    "service": "main-orchestrator",
    "version": "1.0.0"
  },
  "microservices": {
    "mannequin_segmenter": {"status": "healthy"},
    "category_predictor": {"status": "healthy"},
    "measuring_hpe": {"status": "healthy"},
    "attribute_predictor": {"status": "healthy"}
  }
}
```

### 2. Batch Analysis with PDF Report

Process multiple garments and generate a comprehensive PDF report with all results.

**Endpoint:** `POST /batch-analysis`

**Payload:**

```json
{
  "garment_groups": [
    ["https://example.com/dress1.jpg"],
    ["https://example.com/shirt1_front.jpg", "https://example.com/shirt1_back.jpg"],
    ["https://example.com/pants1.jpg", "https://example.com/pants1_detail.jpg"]
  ],
  "output_filename": "my_batch_report.pdf"  // Optional
}
```

**Example:**

```bash
curl -X POST http://localhost:5000/batch-analysis \
  -H "Content-Type: application/json" \
  -d '{
    "garment_groups": [
      [ 
      "https://media.remix.eu/files/20-2025/Majki-kas-pantalon-Samsoe---Samsoe-132036343b.jpg",
      "https://media.remix.eu/files/20-2025/Majki-kas-pantalon-Samsoe---Samsoe-132036343c.jpg", 
      "https://media.remix.eu/files/20-2025/Majki-kas-pantalon-Samsoe---Samsoe-132036343a.jpg"
      ],
      ["https://example.com/dress.jpg"],
      ["https://example.com/shirt_front.jpg", "https://example.com/shirt_back.jpg"],
      ["https://example.com/pants.jpg"]
    ],
    "output_filename": "fashion_analysis_batch.pdf"
  }'
```

**Response:**

```json
{
  "success": true,
  "pdf_path": "reports/fashion_analysis_batch.pdf",
  "processed_garments": 3,
  "timestamp": "2025-06-27T14:38:18.756815"
}
```

**Features:**

- Processes each garment group through the full analysis pipeline
- First image in each group is the primary image
- Additional images are used for condition assessment
- Generates a comprehensive PDF with:
  - Title page with overview
  - Summary page listing all garments
  - Individual pages for each garment with images and analysis
  - Error pages for any failed analyses


### 3. Process Garment (Main Pipeline)

Remove mannequin from image and extract measurements.

**Endpoint:** `POST /process-garment`

**Payload:**

```json
{
  "image_url": "https://example.com/garment.jpg",
  "category_id": 1  // Optional, defaults to 1
}
```

**Example:**

```bash
curl -X POST http://localhost:5000/process-garment \
  -H "Content-Type: application/json" \
  -d '{
    "image_url": "https://media.remix.eu/files/20-2025/Majki-kas-pantalon-Samsoe---Samsoe-132036343b.jpg",
    "category_id": 7
  }'
```

**Response:**

```json
{
  "success": true,
  "pipeline_steps": {
    "1_original_image": "https://example.com/original.jpg",
    "2_segmented_image": "https://s3.amazonaws.com/segmented.jpg",
    "3_measurements_image": "https://s3.amazonaws.com/measured.jpg"
  },
  "measurements": {
    "length": 467.31,
    "width": 900.0,
    "l1": [566, 1483],
    "l2": [583, 1016],
    "w1": [166, 366],
    "w2": [1066, 366]
  },
  "category_id": 7,
  "processing_timestamp": "2025-06-27T14:38:18.756815"
}
```

### 4. Full Analysis (Complete Pipeline)

Complete garment analysis including category prediction, measurements, and condition assessment.

**Endpoint:** `POST /full-analysis`

**Payload:**

```json
{
  "image_url": "https://example.com/garment.jpg",
  "additional_image_urls": [  // Optional
    "https://example.com/garment_back.jpg",
    "https://example.com/garment_detail.jpg"
  ]
}
```

**Example:**

```bash
curl -X POST http://localhost:5000/full-analysis \
  -H "Content-Type: application/json" \
  -d '{
    "image_url": "https://media.remix.eu/files/20-2025/Majki-kas-pantalon-Samsoe---Samsoe-132036343b.jpg",
    "additional_image_urls": [
      "https://example.com/back_view.jpg"
    ]
  }'
```

**Response:**

```json
{
  "success": true,
  "original_image": "https://example.com/original.jpg",
  "segmented_image": "https://s3.amazonaws.com/segmented.jpg",
  "processing_timestamp": "2025-06-27T14:38:18.756815",
  "category_prediction": {
    "success": true,
    "topx": [
      ["Shorts", 0.8333],
      ["Skirts", 0.0798],
      ["Sportswear", 0.0562]
    ]
  },
  "measurements": {
    "success": true,
    "measurements": {
      "length": 467.31,
      "width": 900.0,
      "l1": [566, 1483],
      "w1": [166, 366]
    },
    "url": "https://s3.amazonaws.com/measured.jpg"
  },
  "condition_prediction": {
    "condition_rating": "This product has no signs of use.",
    "condition_description": ""
  }
}
```


### 5. Category Prediction Only

Predict garment category without other processing.

**Endpoint:** `POST /predict-category`

**Payload:**

```json
{
  "image_url": "https://example.com/garment.jpg"
}
```

**Example:**

```bash
curl -X POST http://localhost:5000/predict-category \
  -H "Content-Type: application/json" \
  -d '{
    "image_url": "https://example.com/dress.jpg"
  }'
```

**Response:**

```json
{
  "success": true,
  "topx": [
    ["Dresses", 0.9234],
    ["Skirts", 0.0456],
    ["Tops", 0.0234]
  ]
}
```

### 6. Condition Assessment Only

Assess garment condition from multiple images.

**Endpoint:** `POST /predict-condition`

**Payload:**

```json
{
  "image_urls": [
    "https://example.com/front.jpg",
    "https://example.com/back.jpg",
    "https://example.com/detail.jpg"
  ]
}
```

**Example:**

```bash
curl -X POST http://localhost:5000/predict-condition \
  -H "Content-Type: application/json" \
  -d '{
    "image_urls": [
      "https://example.com/shirt_front.jpg",
      "https://example.com/shirt_back.jpg"
    ]
  }'
```

**Response:**

```json
{
  "condition_rating": "This product shows minimal signs of wear.",
  "condition_description": "Slight pilling on sleeves, otherwise excellent condition."
}
```

### 7. Landmarks Only

Extract garment landmarks without measurements.

**Endpoint:** `POST /get-landmarks`

**Payload:**

```json
{
  "image_url": "https://example.com/garment.jpg"
  // OR
  // "image_path": "/path/to/local/image.jpg"
}
```

**Example:**

```bash
curl -X POST http://localhost:5000/get-landmarks \
  -H "Content-Type: application/json" \
  -d '{
    "image_url": "https://example.com/jacket.jpg"
  }'
```

**Response:**

```json
{
  "success": true,
  "landmarks": [
    [100, 200], [150, 200], [200, 250],
    // ... array of [x, y] coordinate pairs
  ]
}
```

## Category IDs

The system supports 13 garment categories:


**Automatic Category Mapping:** The system automatically maps category names (like "Shorts", "Dresses") to the appropriate category IDs using the built-in `CategoryMapper`.

## Error Handling

All endpoints return appropriate HTTP status codes:

- `200` - Success
- `400` - Bad Request (missing required parameters)
- `500` - Internal Server Error (service failure)

**Error Response Format:**

```json
{
  "error": "Descriptive error message"
}
```

## Advanced Usage

### Batch Processing Multiple Garments

Process multiple garments and get a comprehensive PDF report:

```bash
curl -X POST http://localhost:5000/batch-analysis \
  -H "Content-Type: application/json" \
  -d '{
    "garment_groups": [
      ["https://example.com/dress1.jpg"],
      ["https://example.com/shirt1_front.jpg", "https://example.com/shirt1_back.jpg"],
      ["https://example.com/pants1.jpg"]
    ]
  }'
```

### Python Batch Processing

```python
import requests
import json

def process_garment_batch(garment_groups, output_filename=None):
    payload = {
        'garment_groups': garment_groups
    }
    if output_filename:
        payload['output_filename'] = output_filename
  
    response = requests.post(
        'http://localhost:5000/batch-analysis',
        json=payload,
        headers={'Content-Type': 'application/json'},
        timeout=1800  # 30 minutes for batch processing
    )
  
    if response.status_code == 200:
        return response.json()
    else:
        print(f"Error: {response.status_code} - {response.text}")
        return None

# Usage
garment_groups = [
    ["https://example.com/dress.jpg"],
    ["https://example.com/shirt_front.jpg", "https://example.com/shirt_back.jpg"],
    ["https://example.com/pants.jpg"]
]

result = process_garment_batch(garment_groups, "my_analysis_report.pdf")

if result and result.get('success'):
    print(f"Batch analysis completed!")
    print(f"PDF Report: {result['pdf_path']}")
    print(f"Processed {result['processed_garments']} garments")
```

### Processing Individual Garments

```python
def analyze_garment(image_url, additional_images=None):
    payload = {
        'image_url': image_url,
        'additional_image_urls': additional_images or []
    }
  
    response = requests.post(
        'http://localhost:5000/full-analysis',
        json=payload,
        headers={'Content-Type': 'application/json'},
        timeout=300
    )
  
    if response.status_code == 200:
        return response.json()
    else:
        print(f"Error: {response.status_code} - {response.text}")
        return None

# Usage
result = analyze_garment(
    "https://example.com/dress.jpg",
    ["https://example.com/dress_back.jpg"]
)

if result and result.get('success'):
    print(f"Category: {result['category_prediction']['topx'][0][0]}")
    print(f"Measurements: {result['measurements']['measurements']}")
```

## Service URLs

The main orchestrator coordinates these microservices:

- **Main Orchestrator**: `http://localhost:5000`
- **Mannequin Segmenter**: `http://localhost:5001`
- **Category Predictor**: `http://localhost:5002`
- **Measuring HPE**: `http://localhost:5003`
- **Attribute Predictor**: `http://localhost:5004`

## Troubleshooting

### Check Service Health

```bash
curl http://localhost:5000/health
```

### View Service Logs

```bash
# View all services
sudo docker compose logs

# View specific service
sudo docker compose logs main-orchestrator
sudo docker compose logs mannequin-segmenter
```

### Restart Services

```bash
# Restart all services
sudo docker compose restart

# Restart specific service
sudo docker compose restart main-orchestrator
```

## PDF Reports

The batch analysis generates comprehensive PDF reports with:

- **Title page** - Overview and processing summary
- **Summary page** - List of all processed garments with top predictions
- **Individual garment pages** - Detailed analysis for each garment including:
  - Original, segmented, and measured images
  - Category predictions with confidence scores
  - Condition assessment
  - Detailed measurements with landmark coordinates
  - Processing metadata
- **Error pages** - For any failed analyses with error details

Reports are saved in the `reports/` directory and can be downloaded or processed further as needed.
