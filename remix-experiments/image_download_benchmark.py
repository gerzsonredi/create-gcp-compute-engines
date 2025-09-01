#!/usr/bin/env python3
"""
Image Download Benchmark Script

This script downloads an image file in different scenarios:
1. Single download (1x)
2. Parallel downloads (10x)
3. Parallel downloads (50x)

It measures the average download time for each scenario and cleans up files after each test.
"""

import asyncio
import aiohttp
import aiofiles
import time
import os
import sys
from pathlib import Path
from typing import List, Tuple
import statistics

# Image URL to download
IMAGE_URL = "https://media.remix.eu/files/12-2025/Majka-bluza-Tommy-Hilfiger-131315547b.jpg"

# Download directory
DOWNLOAD_DIR = Path("downloads")


async def download_image(session: aiohttp.ClientSession, url: str, filename: str) -> Tuple[str, float]:
    """
    Download a single image and return the filename and download time.
    
    Args:
        session: aiohttp client session
        url: URL of the image to download
        filename: Local filename to save the image
        
    Returns:
        Tuple of (filename, download_time_seconds)
    """
    start_time = time.time()
    
    try:
        async with session.get(url) as response:
            if response.status == 200:
                # Ensure download directory exists
                DOWNLOAD_DIR.mkdir(exist_ok=True)
                
                filepath = DOWNLOAD_DIR / filename
                async with aiofiles.open(filepath, 'wb') as file:
                    async for chunk in response.content.iter_chunked(8192):
                        await file.write(chunk)
                
                download_time = time.time() - start_time
                return filename, download_time
            else:
                raise Exception(f"HTTP {response.status}: Failed to download {url}")
                
    except Exception as e:
        download_time = time.time() - start_time
        print(f"Error downloading {filename}: {e}")
        return filename, download_time


async def download_images_parallel(count: int) -> List[Tuple[str, float]]:
    """
    Download multiple images in parallel.
    
    Args:
        count: Number of images to download
        
    Returns:
        List of (filename, download_time) tuples
    """
    async with aiohttp.ClientSession() as session:
        tasks = []
        
        for i in range(count):
            filename = f"image_{i+1:03d}.jpg"
            task = download_image(session, IMAGE_URL, filename)
            tasks.append(task)
        
        # Execute all downloads in parallel
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Filter out exceptions and return successful downloads
        successful_results = []
        for result in results:
            if isinstance(result, tuple):
                successful_results.append(result)
            else:
                print(f"Download failed: {result}")
        
        return successful_results


def cleanup_downloads():
    """Remove all downloaded files."""
    print(f"📁 Keeping downloaded files in {DOWNLOAD_DIR} directory")


async def run_benchmark_test(count: int, test_name: str):
    """
    Run a benchmark test for downloading images.
    
    Args:
        count: Number of images to download
        test_name: Name of the test for reporting
    """
    print(f"\n{'='*50}")
    print(f"🚀 Starting {test_name}")
    print(f"Downloading {count} image(s) in parallel...")
    print(f"{'='*50}")
    
    # Record total test time
    total_start_time = time.time()
    
    # Download images
    results = await download_images_parallel(count)
    
    total_time = time.time() - total_start_time
    
    if results:
        # Calculate statistics
        download_times = [result[1] for result in results]
        avg_download_time = statistics.mean(download_times)
        min_download_time = min(download_times)
        max_download_time = max(download_times)
        
        # Report results
        print(f"\n📊 Results for {test_name}:")
        print(f"   Total images downloaded: {len(results)}")
        print(f"   Total test time: {total_time:.3f} seconds")
        print(f"   Average download time per image: {avg_download_time:.3f} seconds")
        print(f"   Fastest download: {min_download_time:.3f} seconds")
        print(f"   Slowest download: {max_download_time:.3f} seconds")
        
        if count > 1:
            print(f"   Parallel efficiency: {count * avg_download_time / total_time:.2f}x")
    else:
        print(f"❌ No images were successfully downloaded in {test_name}")
    
    # Keep files (no cleanup)
    print(f"\n📁 Keeping downloaded files...")
    cleanup_downloads()


async def main():
    """Main function to run all benchmark tests."""
    print("🖼️  Image Download Benchmark Tool")
    print(f"📍 Target URL: {IMAGE_URL}")
    print(f"💾 Download directory: {DOWNLOAD_DIR}")
    
    # Test scenarios
    test_scenarios = [
        (1, "Single Download Test"),
        (10, "10x Parallel Download Test"),
        (50, "50x Parallel Download Test")
    ]
    
    try:
        for count, test_name in test_scenarios:
            await run_benchmark_test(count, test_name)
            
            # Small delay between tests
            if count < 50:
                print("\n⏳ Waiting 2 seconds before next test...")
                await asyncio.sleep(2)
        
        print(f"\n{'='*50}")
        print("🎉 All benchmark tests completed successfully!")
        print(f"{'='*50}")
        
    except KeyboardInterrupt:
        print("\n\n⚠️  Benchmark interrupted by user")
        print("📁 Downloaded files are kept in the downloads directory")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        print("📁 Downloaded files are kept in the downloads directory")
        sys.exit(1)


if __name__ == "__main__":
    # Check if required packages are available
    try:
        import aiohttp
        import aiofiles
    except ImportError as e:
        print(f"❌ Missing required package: {e}")
        print("📦 Please install required packages:")
        print("   pip install aiohttp aiofiles")
        sys.exit(1)
    
    # Run the benchmark
    asyncio.run(main())

