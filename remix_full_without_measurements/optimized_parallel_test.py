#!/usr/bin/env python3
"""
Optimized parallel micro-prompt testing with OpenAI rate limiting and smart image distribution
"""

import asyncio
import aiohttp
import json
import time
import random
from typing import List, Dict, Any
from urllib.parse import urlparse, quote

# Configuration
CONCURRENCY = 6          # egyszerre ennyi aktív kérés (6 micro-prompt)
TARGET_RPM = 120         # szervezeted limitje alapján
TARGET_TPM = 200_000     # becsült/limit alapján
SAFETY_FACTOR = 0.9      # hagyj fejteret

# Image URLs
IMAGES = [
    "https://media.remix.eu/files/32-2025/Damsko-sportno-gornishte-Crane-133086502b.jpg",
    "https://media.remix.eu/files/32-2025/Damsko-sportno-gornishte-Crane-133086502c.jpg", 
    "https://media.remix.eu/files/32-2025/Damsko-sportno-gornishte-Crane-133086502d.jpg",
    "https://media.remix.eu/files/32-2025/Damsko-sportno-gornishte-Crane-133086502a.jpg"
]

# Service endpoints
CATEGORY_URL = "http://localhost:5002/category"
MICRO_PROMPT_URL = "http://localhost:5004/micro_prompt"

# Rate limiting
sem = asyncio.Semaphore(CONCURRENCY)
rpm_delay = 60.0 / (TARGET_RPM * SAFETY_FACTOR)

def resize_via_proxy(original_url: str, width: int = 1000, height: int = 1000) -> str:
    """Return a proxy URL that serves a resized version of the image.
    Uses images.weserv.nl as a public resizing proxy so the server downloads the 500x500 image directly.
    """
    parsed = urlparse(original_url)
    # weserv expects the URL without the scheme; include netloc + path, URL-encoded
    target = f"{parsed.netloc}{parsed.path}"
    encoded = quote(target, safe="")
    return f"https://images.weserv.nl/?url={encoded}&w={width}&h={height}&fit=cover"

async def call_service_with_retry(session: aiohttp.ClientSession, url: str, data: Dict[str, Any], task_name: str) -> Dict[str, Any]:
    """Call service with exponential backoff retry logic"""
    # await asyncio.sleep(rpm_delay * (0.5 + random.random()))  # commented out for local testing
    tries, backoff = 0, 1.0
    
    while True:
        try:
            async with sem:
                print(f"🚀 Starting {task_name}...")
                start_time = time.time()
                
                async with session.post(url, json=data, timeout=aiohttp.ClientTimeout(total=60)) as response:
                    response.raise_for_status()
                    result = await response.json()
                    
                    duration = time.time() - start_time
                    print(f"✅ {task_name} completed in {duration:.2f}s")
                    return {"task": task_name, "result": result, "duration": duration, "error": None}
                    
        except (aiohttp.ClientError, asyncio.TimeoutError) as e:
            # 429/5xx -> exponenciális backoff + jitter
            if tries < 6:
                wait_time = backoff + random.random()
                print(f"⚠️  {task_name} failed (attempt {tries + 1}), retrying in {wait_time:.1f}s...")
                await asyncio.sleep(wait_time)
                tries += 1
                backoff = min(backoff * 2, 30)
                continue
            
            duration = time.time() - start_time if 'start_time' in locals() else 0
            print(f"❌ {task_name} failed after {tries} attempts: {str(e)}")
            return {"task": task_name, "result": None, "duration": duration, "error": str(e)}

async def run_optimized_parallel_test():
    """Run optimized parallel micro-prompt test with smart image distribution"""
    
    print("🎯 OPTIMIZED PARALLEL MICRO-PROMPT TEST")
    print("=" * 50)
    print(f"Concurrency: {CONCURRENCY}")
    print(f"Target RPM: {TARGET_RPM}")
    print(f"Images: {len(IMAGES)} (Category uses original; OpenAI: img1-2=500x500, img3-4=1000x1000)")
    print()
    
    # Define tasks with optimized image selection
    # Prepare resized URLs per index
    img0 = resize_via_proxy(IMAGES[0], 500, 500)
    img1 = resize_via_proxy(IMAGES[1], 500, 500)
    img2 = resize_via_proxy(IMAGES[2], 1000, 1000)
    img3 = resize_via_proxy(IMAGES[3], 1000, 1000)

    tasks = [
        {
            "url": CATEGORY_URL,
            "data": {"image_url": IMAGES[0]},  # Category: first image only (original)
            "name": "CATEGORY"
        },
        {
            "url": MICRO_PROMPT_URL, 
            "data": {"prompt_type": "brand", "image_urls": [img0, img2, img3]},  # Brand: images 1,3,4 (resized)
            "name": "BRAND"
        },
        {
            "url": MICRO_PROMPT_URL,
            "data": {"prompt_type": "color", "image_urls": [img0]},  # Color: first image only (resized)
            "name": "COLOR"
        },
        {
            "url": MICRO_PROMPT_URL,
            "data": {"prompt_type": "material", "image_urls": [img2, img3]},  # Material: images 3,4 (resized)
            "name": "MATERIAL" 
        },
        {
            "url": MICRO_PROMPT_URL,
            "data": {"prompt_type": "size", "image_urls": [img2, img3]},  # Size: images 3,4 (resized)
            "name": "SIZE"
        },
        {
            "url": MICRO_PROMPT_URL,
            "data": {"prompt_type": "condition", "image_urls": [img0, img1]},  # Condition: images 1,2 (resized)
            "name": "CONDITION"
        }
    ]
    
    # Execute all tasks in parallel
    start_time = time.time()
    
    async with aiohttp.ClientSession() as session:
        print("🔥 Starting parallel execution...")
        print()
        
        # Create coroutines for all tasks
        coroutines = [
            call_service_with_retry(session, task["url"], task["data"], task["name"])
            for task in tasks
        ]
        
        # Run all tasks in parallel
        results = await asyncio.gather(*coroutines, return_exceptions=True)
    
    total_duration = time.time() - start_time
    
    # Process and display results
    print()
    print("📊 RESULTS SUMMARY")
    print("=" * 50)
    
    successful_results = {}
    failed_tasks = []
    
    for result in results:
        if isinstance(result, Exception):
            failed_tasks.append(f"Exception: {result}")
            continue
            
        task_name = result["task"]
        duration = result["duration"]
        error = result["error"]
        
        if error:
            failed_tasks.append(f"{task_name}: {error}")
            print(f"❌ {task_name:<12} FAILED ({duration:.2f}s): {error}")
        else:
            successful_results[task_name] = result["result"]
            print(f"✅ {task_name:<12} SUCCESS ({duration:.2f}s)")
    
    print()
    print(f"⚡ Total parallel execution time: {total_duration:.2f}s")
    print(f"🎯 Success rate: {len(successful_results)}/{len(tasks)} ({len(successful_results)/len(tasks)*100:.1f}%)")
    
    if failed_tasks:
        print(f"❌ Failed tasks: {len(failed_tasks)}")
        for fail in failed_tasks:
            print(f"   - {fail}")
    
    # Extract and display attribute results
    if successful_results:
        print()
        print("🔍 EXTRACTED ATTRIBUTES")
        print("=" * 50)
        
        # Category
        if "CATEGORY" in successful_results:
            category_data = successful_results["CATEGORY"]
            if category_data.get("success") and category_data.get("topx"):
                category = category_data["topx"][0][0]
                print(f"Category: {category}")
        
        # Brand
        if "BRAND" in successful_results:
            brand = successful_results["BRAND"].get("brand", "Unknown")
            print(f"Brand: {brand}")
        
        # Color
        if "COLOR" in successful_results:
            color = successful_results["COLOR"].get("primary_color", "Unknown")
            print(f"Color: {color}")
        
        # Material
        if "MATERIAL" in successful_results:
            material = successful_results["MATERIAL"].get("fabric_composition", "Unknown")
            if len(material) > 80:
                material = material[:80] + "..."
            print(f"Material: {material}")
        
        # Size
        if "SIZE" in successful_results:
            size = successful_results["SIZE"].get("size_tag", "Unknown")
            print(f"Size: {size}")
        
        # Condition
        if "CONDITION" in successful_results:
            condition_grade = successful_results["CONDITION"].get("condition_grade", "Unknown")
            condition_note = successful_results["CONDITION"].get("condition_note", "")
            print(f"Condition: Grade {condition_grade}")
            if condition_note and len(condition_note) < 100:
                print(f"  Note: {condition_note}")
    
    print()
    print("🚀 Test completed!")
    return successful_results, total_duration

if __name__ == "__main__":
    asyncio.run(run_optimized_parallel_test())
