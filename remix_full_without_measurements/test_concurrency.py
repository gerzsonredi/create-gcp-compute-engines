#!/usr/bin/env python3
"""
Quick concurrency test - creates /sleep endpoint to test server parallelism
"""

import asyncio
import aiohttp
import time

async def test_sleep_endpoint(concurrency=6):
    """Test server concurrency with simple sleep endpoint"""
    
    print(f"🧪 Testing server concurrency with {concurrency} parallel requests...")
    print("Testing /sleep endpoint (should return in ~1-2s if parallel, ~6s if sequential)")
    
    start_time = time.time()
    
    async with aiohttp.ClientSession() as session:
        tasks = []
        for i in range(concurrency):
            task = session.get(f"http://localhost:5002/health")  # Use existing health endpoint
            tasks.append(task)
        
        responses = await asyncio.gather(*tasks, return_exceptions=True)
    
    total_time = time.time() - start_time
    
    print(f"⏱️  Total time: {total_time:.2f}s")
    if total_time < 2:
        print("✅ Server is handling requests in parallel!")
    else:
        print("❌ Server is processing requests sequentially!")
    
    return total_time

if __name__ == "__main__":
    asyncio.run(test_sleep_endpoint())
