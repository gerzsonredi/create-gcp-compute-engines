#!/usr/bin/env python3
"""
Load Balancer Test Script for Mannequin Segmenter API
Tests multiple VM instances with round-robin load balancing and collects performance metrics
"""

import asyncio
import aiohttp
import time
import statistics
from datetime import datetime
import json

# ========== KONFIGURÁCIÓS PARAMÉTEREK ==========
TEST_DURATION_SECONDS = 10  # Teszt futási ideje másodpercben
CONCURRENT_REQUESTS = 5     # Egyidejű kérések száma
REQUEST_TIMEOUT = 30        # Timeout másodpercben
DELAY_BETWEEN_REQUESTS = 0.1 # Késleltetés kérések között másodpercben

# VM Instance IP címek
VM_INSTANCES = [
    "http://35.233.66.133:5001",
    "http://34.34.136.96:5001", 
    "http://192.158.29.6:5001",
    "http://35.187.98.56:5001"
]

# API endpoint és payload
API_ENDPOINT = "/infer"
TEST_PAYLOAD = {
    "image_url": "https://media.remix.eu/files/12-2025/Majka-bluza-Tommy-Hilfiger-131315547b.jpg",
    "prompt_mode": "both"
}

# ===============================================

class LoadBalancerTest:
    def __init__(self):
        self.results = []
        self.errors = []
        self.start_time = None
        self.current_instance_index = 0
        
    def get_next_instance(self):
        """Round-robin load balancing"""
        instance = VM_INSTANCES[self.current_instance_index]
        self.current_instance_index = (self.current_instance_index + 1) % len(VM_INSTANCES)
        return instance
    
    async def make_request(self, session, instance_url, request_id):
        """Egyetlen API kérés végrehajtása"""
        full_url = f"{instance_url}{API_ENDPOINT}"
        request_start = time.time()
        
        try:
            async with session.post(
                full_url,
                json=TEST_PAYLOAD,
                timeout=aiohttp.ClientTimeout(total=REQUEST_TIMEOUT)
            ) as response:
                response_text = await response.text()
                request_end = time.time()
                response_time = request_end - request_start
                
                result = {
                    "request_id": request_id,
                    "instance_url": instance_url,
                    "status_code": response.status,
                    "response_time": response_time,
                    "timestamp": request_start,
                    "success": response.status == 200,
                    "response_size": len(response_text)
                }
                
                if response.status == 200:
                    try:
                        json_response = json.loads(response_text)
                        result["has_visualization_url"] = "visualization_url" in json_response
                    except json.JSONDecodeError:
                        result["has_visualization_url"] = False
                
                self.results.append(result)
                print(f"✅ Request {request_id}: {instance_url} -> {response.status} ({response_time:.2f}s)")
                
        except asyncio.TimeoutError:
            request_end = time.time()
            response_time = request_end - request_start
            error = {
                "request_id": request_id,
                "instance_url": instance_url,
                "error": "Timeout",
                "response_time": response_time,
                "timestamp": request_start
            }
            self.errors.append(error)
            print(f"⏰ Request {request_id}: {instance_url} -> TIMEOUT ({response_time:.2f}s)")
            
        except Exception as e:
            request_end = time.time()
            response_time = request_end - request_start
            error = {
                "request_id": request_id,
                "instance_url": instance_url,
                "error": str(e),
                "response_time": response_time,
                "timestamp": request_start
            }
            self.errors.append(error)
            print(f"❌ Request {request_id}: {instance_url} -> ERROR: {e}")
    
    async def worker(self, session, worker_id):
        """Worker coroutine, amely folyamatosan küld kéréseket"""
        request_counter = 0
        
        while time.time() - self.start_time < TEST_DURATION_SECONDS:
            instance_url = self.get_next_instance()
            request_id = f"worker-{worker_id}-req-{request_counter}"
            
            await self.make_request(session, instance_url, request_id)
            request_counter += 1
            
            # Kis szünet a következő kérés előtt
            await asyncio.sleep(DELAY_BETWEEN_REQUESTS)
    
    async def run_test(self):
        """Fő teszt futtatás"""
        print(f"🚀 Load Balancer Teszt Indítás")
        print(f"📊 Konfiguráció:")
        print(f"   - Teszt időtartam: {TEST_DURATION_SECONDS} másodperc")
        print(f"   - Egyidejű worker-ek: {CONCURRENT_REQUESTS}")
        print(f"   - VM instance-ok: {len(VM_INSTANCES)}")
        print(f"   - Kérések közötti késleltetés: {DELAY_BETWEEN_REQUESTS}s")
        print(f"   - Request timeout: {REQUEST_TIMEOUT}s")
        print()
        
        for i, vm in enumerate(VM_INSTANCES):
            print(f"   VM {i+1}: {vm}")
        print()
        
        self.start_time = time.time()
        
        async with aiohttp.ClientSession() as session:
            # Worker task-ok létrehozása
            tasks = []
            for worker_id in range(CONCURRENT_REQUESTS):
                task = asyncio.create_task(self.worker(session, worker_id))
                tasks.append(task)
            
            # Várjuk meg az összes worker befejezését
            await asyncio.gather(*tasks)
        
        print(f"\n⏱️  Teszt befejezve!")
        self.print_statistics()
    
    def print_statistics(self):
        """Statisztikák kiírása"""
        successful_requests = [r for r in self.results if r["success"]]
        failed_requests = len(self.results) - len(successful_requests)
        total_requests = len(self.results) + len(self.errors)
        
        print(f"\n📈 TESZT EREDMÉNYEK")
        print(f"=" * 50)
        print(f"⏱️  Teszt időtartam: {TEST_DURATION_SECONDS} másodperc")
        print(f"📊 Összes kérés: {total_requests}")
        print(f"✅ Sikeres kérések: {len(successful_requests)}")
        print(f"❌ Sikertelen kérések: {failed_requests + len(self.errors)}")
        print(f"📈 Sikeresség arány: {len(successful_requests)/total_requests*100:.1f}%")
        
        if successful_requests:
            response_times = [r["response_time"] for r in successful_requests]
            
            print(f"\n⏰ VÁLASZIDŐ STATISZTIKÁK (sikeres kérések)")
            print(f"   🔹 Minimum: {min(response_times):.3f} másodperc")
            print(f"   🔹 Maximum: {max(response_times):.3f} másodperc")
            print(f"   🔹 Átlag: {statistics.mean(response_times):.3f} másodperc")
            print(f"   🔹 Medián: {statistics.median(response_times):.3f} másodperc")
            
            # Instance-onkénti bontás
            print(f"\n🖥️  INSTANCE-ONKÉNTI TELJESÍTMÉNY")
            instance_stats = {}
            for result in successful_requests:
                url = result["instance_url"]
                if url not in instance_stats:
                    instance_stats[url] = []
                instance_stats[url].append(result["response_time"])
            
            for i, vm_url in enumerate(VM_INSTANCES):
                if vm_url in instance_stats:
                    times = instance_stats[vm_url]
                    print(f"   VM {i+1} ({vm_url}):")
                    print(f"      - Kérések száma: {len(times)}")
                    print(f"      - Átlag válaszidő: {statistics.mean(times):.3f}s")
                    print(f"      - Min/Max: {min(times):.3f}s / {max(times):.3f}s")
                else:
                    print(f"   VM {i+1} ({vm_url}): Nincs sikeres kérés")
            
            # Throughput számítás
            actual_test_duration = max([r["timestamp"] for r in successful_requests]) - min([r["timestamp"] for r in successful_requests])
            if actual_test_duration > 0:
                throughput = len(successful_requests) / actual_test_duration
                print(f"\n🚀 THROUGHPUT")
                print(f"   🔹 Sikeres kérések/másodperc: {throughput:.2f}")
                print(f"   🔹 Átlagos instance terhelés: {throughput/len(VM_INSTANCES):.2f} kérés/sec/instance")
        
        # Hibák részletezése
        if self.errors:
            print(f"\n❌ HIBÁK RÉSZLETEZÉSE")
            error_types = {}
            for error in self.errors:
                error_type = error["error"]
                if error_type not in error_types:
                    error_types[error_type] = 0
                error_types[error_type] += 1
            
            for error_type, count in error_types.items():
                print(f"   🔹 {error_type}: {count} alkalom")

async def main():
    """Fő program belépési pont"""
    tester = LoadBalancerTest()
    await tester.run_test()

if __name__ == "__main__":
    print("🔧 Mannequin Segmenter Load Balancer Test")
    print("=" * 50)
    asyncio.run(main())
