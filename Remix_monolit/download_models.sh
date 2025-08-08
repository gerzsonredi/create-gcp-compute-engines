#!/bin/bash

# Download Garment Measuring HPE Models from GCP Cloud Storage
# This script downloads:
# 1. pose_hrnet-w48_384x288-deepfashion2_mAP_0.7017.pth
# 2. bbox_result_val.pkl
#
# Required environment variables:
# - GCP_PROJECT_ID
# - GCP_SA_KEY 
# - BUCKET_NAME_ARTIFACTS (optional, defaults to 'artifactsredi')

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}=== Garment Measuring HPE Model Downloader ===${NC}"

# Check if required environment variables are set
if [ -z "$GCP_PROJECT_ID" ]; then
    echo -e "${RED}Error: GCP_PROJECT_ID environment variable is not set${NC}"
    echo "Please set it with: export GCP_PROJECT_ID=your-project-id"
    exit 1
fi

if [ -z "$GCP_SA_KEY" ]; then
    echo -e "${RED}Error: GCP_SA_KEY environment variable is not set${NC}"
    echo "Please set it with: export GCP_SA_KEY='your-service-account-key-json'"
    exit 1
fi

echo -e "${YELLOW}Project ID: $GCP_PROJECT_ID${NC}"
echo -e "${YELLOW}Bucket: ${BUCKET_NAME_ARTIFACTS:-artifactsredi}${NC}"

# Check if Python script exists
if [ ! -f "download_models.py" ]; then
    echo -e "${RED}Error: download_models.py not found in current directory${NC}"
    echo "Please run this script from the garment-measuring-hpe directory"
    exit 1
fi

# Install required packages if not already installed
echo -e "${YELLOW}Installing required Python packages...${NC}"
pip install google-cloud-storage google-auth > /dev/null 2>&1 || {
    echo -e "${RED}Error: Failed to install required packages${NC}"
    echo "Please install manually: pip install google-cloud-storage google-auth"
    exit 1
}

# Run the Python download script
echo -e "${YELLOW}Starting download of HPE models...${NC}"
echo -e "${YELLOW}Files to download:${NC}"
echo -e "  1. pose_hrnet-w48_384x288-deepfashion2_mAP_0.7017.pth"
echo -e "  2. bbox_result_val.pkl"

python download_models.py

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✅ HPE models download completed successfully!${NC}"
    echo -e "${YELLOW}Downloaded files:${NC}"
    ls -lh artifacts/pose_hrnet-w48_384x288-deepfashion2_mAP_0.7017.pth 2>/dev/null && echo -e "${GREEN}✅ pose_hrnet model${NC}"
    ls -lh artifacts/bbox_result_val.pkl 2>/dev/null && echo -e "${GREEN}✅ bbox_result file${NC}"
else
    echo -e "${RED}❌ HPE models download failed${NC}"
    exit 1
fi 