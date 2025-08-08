#!/bin/bash

# Smart entrypoint script for garment-measuring-hpe Docker container
# Handles different environments: local development vs GCP deployment

set -e

echo "🐳 Starting garment-measuring-hpe container..."

# Run smart initialization script
echo "🔍 Running smart model initialization..."
python /app/docker_init.py

# Check if initialization was successful (but don't fail if not)
if [ $? -eq 0 ]; then
    echo "✅ Smart initialization completed successfully"
else
    echo "⚠️  Smart initialization completed with warnings"
fi

# Start the main application
echo "🚀 Starting main application..."
exec "$@" 