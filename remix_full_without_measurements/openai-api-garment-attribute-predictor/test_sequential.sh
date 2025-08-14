#!/bin/bash

echo "=== SEQUENTIAL MICRO-PROMPT PERFORMANCE TEST ==="
echo "Testing each micro-prompt individually with optimized image selection"
echo "Images: b.jpg, c.jpg, d.jpg, a.jpg"
echo ""

IMAGES='["https://media.remix.eu/files/32-2025/Damsko-sportno-gornishte-Crane-133086502b.jpg","https://media.remix.eu/files/32-2025/Damsko-sportno-gornishte-Crane-133086502c.jpg","https://media.remix.eu/files/32-2025/Damsko-sportno-gornishte-Crane-133086502d.jpg","https://media.remix.eu/files/32-2025/Damsko-sportno-gornishte-Crane-133086502a.jpg"]'

# Category - only first image
echo "1. CATEGORY (first image only):"
time curl -s -X POST http://localhost:5002/category \
  -H "Content-Type: application/json" \
  -d '{"image_url": "https://media.remix.eu/files/32-2025/Damsko-sportno-gornishte-Crane-133086502b.jpg"}' \
  | jq -r '.topx[0][0] // "Error"'
echo ""

# Brand - images 1, 3, 4
echo "2. BRAND (images 1, 3, 4):"
time curl -s -X POST http://localhost:5004/micro_prompt \
  -H "Content-Type: application/json" \
  -d '{"prompt_type": "brand", "image_urls": ["https://media.remix.eu/files/32-2025/Damsko-sportno-gornishte-Crane-133086502b.jpg","https://media.remix.eu/files/32-2025/Damsko-sportno-gornishte-Crane-133086502d.jpg","https://media.remix.eu/files/32-2025/Damsko-sportno-gornishte-Crane-133086502a.jpg"]}' \
  | jq -r '.brand // "Error"'
echo ""

# Color - first image only
echo "3. COLOR (first image only):"
time curl -s -X POST http://localhost:5004/micro_prompt \
  -H "Content-Type: application/json" \
  -d '{"prompt_type": "color", "image_urls": ["https://media.remix.eu/files/32-2025/Damsko-sportno-gornishte-Crane-133086502b.jpg"]}' \
  | jq -r '.primary_color // "Error"'
echo ""

# Material - images 3, 4
echo "4. MATERIAL (images 3, 4):"
time curl -s -X POST http://localhost:5004/micro_prompt \
  -H "Content-Type: application/json" \
  -d '{"prompt_type": "material", "image_urls": ["https://media.remix.eu/files/32-2025/Damsko-sportno-gornishte-Crane-133086502d.jpg","https://media.remix.eu/files/32-2025/Damsko-sportno-gornishte-Crane-133086502a.jpg"]}' \
  | jq -r '.fabric_composition // "Error"'
echo ""

# Size - images 3, 4
echo "5. SIZE (images 3, 4):"
time curl -s -X POST http://localhost:5004/micro_prompt \
  -H "Content-Type: application/json" \
  -d '{"prompt_type": "size", "image_urls": ["https://media.remix.eu/files/32-2025/Damsko-sportno-gornishte-Crane-133086502d.jpg","https://media.remix.eu/files/32-2025/Damsko-sportno-gornishte-Crane-133086502a.jpg"]}' \
  | jq -r '.size_tag // "Error"'
echo ""

# Condition - images 1, 2
echo "6. CONDITION (images 1, 2):"
time curl -s -X POST http://localhost:5004/micro_prompt \
  -H "Content-Type: application/json" \
  -d '{"prompt_type": "condition", "image_urls": ["https://media.remix.eu/files/32-2025/Damsko-sportno-gornishte-Crane-133086502b.jpg","https://media.remix.eu/files/32-2025/Damsko-sportno-gornishte-Crane-133086502c.jpg"]}' \
  | jq -r '.condition_grade // "Error"'
echo ""

echo "=== TEST COMPLETED ==="
