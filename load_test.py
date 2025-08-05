#!/usr/bin/env python3
"""
🚀 High-Performance API Load Testing Script
Tests staggered request performance to simulate real traffic patterns
"""

import asyncio
import aiohttp
import time
import json
import statistics
from datetime import datetime
from typing import List, Dict, Tuple

# 🔧 CONFIGURATION
API_URL = "https://garment-measuring-api-o4c5wdhnoa-ez.a.run.app/measurements"
TEST_IMAGE_URL = "https://media.remix.eu/files/11-2025/Roklya-Loft-131183184b.jpg"
TEST_DATA = {"image_url": TEST_IMAGE_URL}

# Test levels: number of staggered requests
TEST_LEVELS = [1, 5, 10, 20, 30, 50]

class PerformanceTest:
    def __init__(self):
        self.results = {}
        self.session = None
    
    async def single_request(self, session: aiohttp.ClientSession, request_id: int) -> Dict:
        """Send a single API request and measure performance"""
        start_time = time.time()
        
        try:
            async with session.post(
                API_URL,
                json=TEST_DATA,
                headers={
                    "Content-Type": "application/json",
                    "Connection": "close"  # Force new connection for each request (better load balancing)
                },
                timeout=aiohttp.ClientTimeout(total=120)  # 2 minute timeout
            ) as response:
                end_time = time.time()
                response_time = end_time - start_time
                
                if response.status == 200:
                    response_data = await response.json()
                    success = response_data.get('success', False)
                    api_total_time = response_data.get('performance_timing', {}).get('total_time_seconds', 0)
                else:
                    success = False
                    api_total_time = 0
                    response_data = {"error": f"HTTP {response.status}"}
                
                return {
                    "request_id": request_id,
                    "success": success,
                    "response_time": response_time,
                    "api_total_time": api_total_time,
                    "status_code": response.status,
                    "timestamp": datetime.now().isoformat()
                }
                
        except Exception as e:
            end_time = time.time()
            response_time = end_time - start_time
            return {
                "request_id": request_id,
                "success": False,
                "response_time": response_time,
                "api_total_time": 0,
                "status_code": 0,
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }
    
    async def run_concurrent_test(self, num_requests: int) -> Dict:
        """Run requests with staggered timing instead of all at once"""
        print(f"\n🚀 Testing {num_requests} requests with staggered timing...")
        
        connector = aiohttp.TCPConnector(limit=100, limit_per_host=50)
        timeout = aiohttp.ClientTimeout(total=180)  # 3 minute timeout
        
        async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
            # Record test start time
            test_start = time.time()
            
            # Send requests with small delays between them (50ms)
            tasks = []
            for i in range(num_requests):
                if i > 0:
                    await asyncio.sleep(0.05)  # 50ms delay between requests
                
                task = asyncio.create_task(self.single_request(session, i+1))
                tasks.append(task)
            
            # Wait for all requests to complete
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            test_end = time.time()
            total_test_time = test_end - test_start
            
            # Process results
            successful_results = []
            failed_results = []
            
            for result in results:
                if isinstance(result, Exception):
                    failed_results.append({"error": str(result)})
                elif result.get("success", False):
                    successful_results.append(result)
                else:
                    failed_results.append(result)
            
            # Calculate statistics
            if successful_results:
                response_times = [r["response_time"] for r in successful_results]
                api_times = [r["api_total_time"] for r in successful_results if r["api_total_time"] > 0]
                
                stats = {
                    "num_requests": num_requests,
                    "successful_requests": len(successful_results),
                    "failed_requests": len(failed_results),
                    "success_rate": len(successful_results) / num_requests * 100,
                    "total_test_time": total_test_time,
                    "response_times": {
                        "min": min(response_times),
                        "max": max(response_times),
                        "mean": statistics.mean(response_times),
                        "median": statistics.median(response_times),
                        "std_dev": statistics.stdev(response_times) if len(response_times) > 1 else 0
                    },
                    "api_times": {
                        "min": min(api_times) if api_times else 0,
                        "max": max(api_times) if api_times else 0,
                        "mean": statistics.mean(api_times) if api_times else 0,
                        "median": statistics.median(api_times) if api_times else 0
                    },
                    "requests_per_second": num_requests / total_test_time,
                    "raw_results": successful_results + failed_results
                }
            else:
                stats = {
                    "num_requests": num_requests,
                    "successful_requests": 0,
                    "failed_requests": len(failed_results),
                    "success_rate": 0,
                    "total_test_time": total_test_time,
                    "error": "All requests failed",
                    "raw_results": failed_results
                }
            
            return stats
    
    async def run_full_test_suite(self):
        """Run the complete test suite across all levels"""
        print("🧪 GARMENT MEASURING API PERFORMANCE TEST")
        print("=" * 50)
        print(f"🎯 Target API: {API_URL}")
        print(f"🖼️ Test Image: {TEST_IMAGE_URL}")
        print(f"📊 Test Levels: {TEST_LEVELS} staggered requests (50ms delays)")
        print(f"⏰ Start Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        all_results = {}
        
        for level in TEST_LEVELS:
            try:
                result = await self.run_concurrent_test(level)
                all_results[level] = result
                
                # Print immediate results
                if result.get("successful_requests", 0) > 0:
                    print(f"✅ {level} staggered: Max response time = {result['response_times']['max']:.2f}s")
                    print(f"   Success rate: {result['success_rate']:.1f}% | "
                          f"Avg: {result['response_times']['mean']:.2f}s | "
                          f"RPS: {result['requests_per_second']:.1f}")
                else:
                    print(f"❌ {level} staggered: All failed")
                
                # Brief pause between test levels
                if level < max(TEST_LEVELS):
                    print("   Waiting 10 seconds before next test level...")
                    await asyncio.sleep(10)
                    
            except Exception as e:
                print(f"❌ {level} staggered: Test failed with error: {e}")
                all_results[level] = {"error": str(e)}
        
        return all_results
    
    def print_summary(self, results: Dict):
        """Print comprehensive test summary"""
        print("\n" + "="*60)
        print("📊 COMPREHENSIVE PERFORMANCE SUMMARY")
        print("="*60)
        
        print(f"\n🎯 MAXIMUM RESPONSE TIMES BY STAGGERED LEVEL:")
        print("-" * 50)
        
        max_times = []
        for level in TEST_LEVELS:
            if level in results and "response_times" in results[level]:
                max_time = results[level]["response_times"]["max"]
                success_rate = results[level]["success_rate"]
                print(f"  {level:2d} staggered: {max_time:6.2f}s (Success: {success_rate:5.1f}%)")
                max_times.append(max_time)
            else:
                print(f"  {level:2d} staggered: FAILED")
        
        if max_times:
            print(f"\n🏆 OVERALL PERFORMANCE:")
            print(f"  Best max time:    {min(max_times):.2f}s")
            print(f"  Worst max time:   {max(max_times):.2f}s")
            print(f"  Average max time: {statistics.mean(max_times):.2f}s")
        
        print(f"\n📈 DETAILED STATISTICS:")
        print("-" * 50)
        for level in TEST_LEVELS:
            if level in results and "response_times" in results[level]:
                stats = results[level]
                print(f"\n  {level} staggered requests:")
                print(f"    Total test time:   {stats['total_test_time']:.2f}s")
                print(f"    Success rate:      {stats['success_rate']:.1f}%")
                print(f"    Requests/second:   {stats['requests_per_second']:.1f}")
                print(f"    Response times:")
                print(f"      Min:  {stats['response_times']['min']:.2f}s")
                print(f"      Max:  {stats['response_times']['max']:.2f}s")
                print(f"      Avg:  {stats['response_times']['mean']:.2f}s")
                print(f"      Med:  {stats['response_times']['median']:.2f}s")
        
        print(f"\n⏰ Test completed: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

async def main():
    """Main execution function"""
    tester = PerformanceTest()
    
    try:
        results = await tester.run_full_test_suite()
        tester.print_summary(results)
        
        # Save detailed results to JSON file
        output_file = f"load_test_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(output_file, 'w') as f:
            json.dump(results, f, indent=2, default=str)
        print(f"\n💾 Detailed results saved to: {output_file}")
        
    except KeyboardInterrupt:
        print("\n⚠️ Test interrupted by user")
    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")

if __name__ == "__main__":
    # Install required packages hint
    print("📦 Required packages: pip install aiohttp")
    print("🚀 Starting performance test...\n")
    
    asyncio.run(main()) 