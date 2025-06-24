# garment-measuring-hpe

# Docker 🐋

**Build the image**
```bash
docker build -t clothing-api .
```

**Run the container**
```bash
docker run -it -p 5000:5000 -e PYTHONUNBUFFERED=1 clothing-api
```

# API Endpoints

## Health Check ❤️

Test if the API is running:

```bash
curl http://127.0.0.1:5000/health
```

**Expected Response:**
```json
{
  "message": "API is running",
  "status": "healthy"
}
```

## Landmarks Endpoint 🗺️

Get clothing landmarks from an image.

### With image_path:
```bash
curl -X POST http://127.0.0.1:5000/landmarks \
  -H "Content-Type: application/json" \
  -d '{"image_path": "/path/to/your/image.jpg"}'
```

### With image_url:
```bash
curl -X POST http://127.0.0.1:5000/landmarks \
  -H "Content-Type: application/json" \
  -d '{"image_url": "https://example.com/image.jpg"}'
```

**Expected Response:**
```json
{
  "success": true,
  "landmarks": [[x1, y1], [x2, y2], ...]
}
```

## Measurements Endpoint 📏

Calculate clothing measurements from an image.

### With image_path and default category (category_id=1):
```bash
curl -X POST http://127.0.0.1:5000/measurements \
  -H "Content-Type: application/json" \
  -d '{"image_path": "/path/to/your/image.jpg"}'
```

### With image_path and specific category:
```bash
curl -X POST http://127.0.0.1:5000/measurements \
  -H "Content-Type: application/json" \
  -d '{"image_path": "/path/to/your/image.jpg", "category_id": 7}'
```

### With image_url:
```bash
curl -X POST http://127.0.0.1:5000/measurements \
  -H "Content-Type: application/json" \
  -d '{"image_url": "https://example.com/image.jpg", "category_id": 8}'
```

**Expected Response:**
```json
{
  "success": true,
  "measurements": {
    "width": 150.5,
    "length": 200.3,
    "w1": [x1, y1],
    "w2": [x2, y2],
    "l1": [x3, y3],
    "l2": [x4, y4]
  },
  "url": "https://public-images-redivivum.s3.eu-central-1.amazonaws.com/Remix_data/predictions/image_1750776340.jpg"
}
```

## Category IDs

- `1`: Short-sleeved tops
- `7`: Shorts  
- `8`: Trousers

## Error Testing

Test missing image parameter (should return 400 error):
```bash
curl -X POST http://127.0.0.1:5000/landmarks \
  -H "Content-Type: application/json" \
  -d '{}'
```

## Pretty JSON Output

For formatted JSON responses, pipe the output through `jq`:
```bash
curl -X POST http://127.0.0.1:5000/landmarks \
  -H "Content-Type: application/json" \
  -d '{"image_path": "/path/to/your/image.jpg"}' | jq
```

## Notes

- Provide either `image_path` OR `image_url`, not both
- Image files must be accessible from within the Docker container when using `image_path`
- Default `category_id` is 1 if not specified

