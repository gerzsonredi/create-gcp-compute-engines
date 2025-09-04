#!/usr/bin/env python3
"""
Dynamic Load Balancer Test Script for Mannequin Segmenter API
Each instance gets exactly one task at a time. When an instance finishes, 
it immediately gets assigned the next pending task from the queue.
"""

import asyncio
import aiohttp
import time
import statistics
from datetime import datetime
import json
from collections import deque

# ========== KONFIGURÁCIÓS PARAMÉTEREK ==========
TEST_DURATION_SECONDS = 20  # Teszt futási ideje másodpercben
TOTAL_REQUESTS = 50         # Összes kérések száma amit fel akarunk dolgozni
REQUEST_TIMEOUT = 60        # Timeout másodpercben

# VM Instance IP címek
VM_INSTANCES = [
    "http://34.22.130.174:5001",
    "http://34.79.218.203:5001", 
    "http://104.155.15.184:5001",
    "http://35.195.4.217:5001",
    "http://34.140.252.94:5001"
]

# API endpoint és payload
API_ENDPOINT = "/infer"
TEST_PAYLOAD = {
    "image_url": "https://storage.googleapis.com/public-images-redi/131727003.jpg",
    "prompt_mode": "both"
}

# ===============================================

class InstanceState:
    def __init__(self, url):
        self.url = url
        self.is_busy = False
        self.current_task_id = None
        self.completed_tasks = 0
        self.total_response_time = 0.0
        self.errors = 0
        self.last_completed = None

class DynamicLoadBalancer:
    def __init__(self):
        self.instances = [InstanceState(url) for url in VM_INSTANCES]
        self.task_queue = deque()
        self.completed_results = []
        self.errors = []
        self.start_time = None
        self.next_task_id = 1
        
        # Feltöltjük a task queue-t
        for i in range(TOTAL_REQUESTS):
            self.task_queue.append({
                "task_id": i + 1,
                "payload": TEST_PAYLOAD.copy()
            })
    
    def get_available_instance(self):
        """Visszaad egy szabad instance-t, ha van"""
        for instance in self.instances:
            if not instance.is_busy:
                return instance
        return None
    
    def get_next_task(self):
        """Kivesz egy task-ot a queue-ból"""
        if self.task_queue:
            return self.task_queue.popleft()
        return None
    
    async def execute_task(self, session, instance, task):
        """Végrehajtja a task-ot egy adott instance-on"""
        instance.is_busy = True
        instance.current_task_id = task["task_id"]
        
        full_url = f"{instance.url}{API_ENDPOINT}"
        request_start = time.time()
        
        print(f"🔄 Task {task['task_id']}: {instance.url} -> Küldés...", end="", flush=True)
        
        try:
            async with session.post(
                full_url,
                json=task["payload"],
                timeout=aiohttp.ClientTimeout(total=REQUEST_TIMEOUT)
            ) as response:
                response_text = await response.text()
                request_end = time.time()
                response_time = request_end - request_start
                
                result = {
                    "task_id": task["task_id"],
                    "instance_url": instance.url,
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
                        if "timing" in json_response:
                            result["server_timing"] = json_response["timing"]
                    except json.JSONDecodeError:
                        result["has_visualization_url"] = False
                
                self.completed_results.append(result)
                
                # Instance statisztikák frissítése
                instance.completed_tasks += 1
                instance.total_response_time += response_time
                instance.last_completed = time.time()
                
                print(f" ✅ {response.status} ({response_time:.2f}s)")
                
        except asyncio.TimeoutError:
            request_end = time.time()
            response_time = request_end - request_start
            error = {
                "task_id": task["task_id"],
                "instance_url": instance.url,
                "error": "Timeout",
                "response_time": response_time,
                "timestamp": request_start
            }
            self.errors.append(error)
            instance.errors += 1
            print(f" ⏰ TIMEOUT ({response_time:.2f}s)")
            
        except Exception as e:
            request_end = time.time()
            response_time = request_end - request_start
            error = {
                "task_id": task["task_id"],
                "instance_url": instance.url,
                "error": str(e),
                "response_time": response_time,
                "timestamp": request_start
            }
            self.errors.append(error)
            instance.errors += 1
            print(f" ❌ ERROR: {e}")
        
        # Instance felszabadítása
        instance.is_busy = False
        instance.current_task_id = None
    
    async def instance_worker(self, session, instance):
        """Worker egy adott instance-hoz - folyamatosan dolgozik"""
        while True:
            # Ellenőrizzük hogy van-e még munka és nincs-e időtúllépés
            current_time = time.time()
            if (current_time - self.start_time >= TEST_DURATION_SECONDS and 
                len(self.task_queue) == 0):
                break
                
            if current_time - self.start_time >= TEST_DURATION_SECONDS:
                print(f"⏰ {instance.url}: Időtúllépés, leállítás")
                break
            
            # Próbálunk task-ot szerezni
            task = self.get_next_task()
            if task is None:
                # Nincs több task, várunk egy kicsit
                await asyncio.sleep(0.1)
                continue
            
            # Végrehajtjuk a task-ot
            await self.execute_task(session, instance, task)
    
    async def run_test(self):
        """Fő teszt futtatás"""
        print(f"🚀 Dynamic Load Balancer Teszt")
        print(f"📊 Konfiguráció:")
        print(f"   - Teszt időtartam: {TEST_DURATION_SECONDS} másodperc")
        print(f"   - Összes task: {TOTAL_REQUESTS}")
        print(f"   - VM instance-ok: {len(VM_INSTANCES)}")
        print(f"   - Request timeout: {REQUEST_TIMEOUT}s")
        print(f"   - Stratégia: Minden instance max 1 task egyszerre")
        print()
        
        for i, instance in enumerate(self.instances):
            print(f"   VM {i+1}: {instance.url}")
        print()
        
        self.start_time = time.time()
        
        async with aiohttp.ClientSession() as session:
            # Minden instance-hoz egy worker task
            tasks = []
            for instance in self.instances:
                task = asyncio.create_task(self.instance_worker(session, instance))
                tasks.append(task)
            
            # Progress monitoring task
            monitor_task = asyncio.create_task(self.progress_monitor())
            tasks.append(monitor_task)
            
            # Várjuk meg az összes worker befejezését
            await asyncio.gather(*tasks, return_exceptions=True)
        
        print(f"\n⏱️  Teszt befejezve!")
        self.print_statistics()
    
    async def progress_monitor(self):
        """Folyamatosan monitorozza a progresst"""
        while True:
            await asyncio.sleep(2)  # 2 másodpercenként
            
            current_time = time.time()
            elapsed = current_time - self.start_time
            
            if elapsed >= TEST_DURATION_SECONDS:
                break
            
            completed = len(self.completed_results)
            remaining = len(self.task_queue)
            busy_instances = sum(1 for inst in self.instances if inst.is_busy)
            
            print(f"📊 Progress: {completed} kész, {remaining} várakozik, {busy_instances}/{len(self.instances)} instance dolgozik ({elapsed:.0f}s)")
    
    def print_statistics(self):
        """Statisztikák kiírása"""
        successful_requests = [r for r in self.completed_results if r["success"]]
        failed_requests = len(self.completed_results) - len(successful_requests)
        total_requests = len(self.completed_results) + len(self.errors)
        
        print(f"\n📈 TESZT EREDMÉNYEK")
        print(f"=" * 60)
        print(f"⏱️  Teszt időtartam: {TEST_DURATION_SECONDS} másodperc")
        print(f"📊 Összes task: {TOTAL_REQUESTS}")
        print(f"✅ Befejezett task-ok: {total_requests}")
        print(f"🔄 Feldolgozatlan task-ok: {len(self.task_queue)}")
        print(f"✅ Sikeres kérések: {len(successful_requests)}")
        print(f"❌ Sikertelen kérések: {failed_requests + len(self.errors)}")
        if total_requests > 0:
            print(f"📈 Sikeresség arány: {len(successful_requests)/total_requests*100:.1f}%")
        
        if successful_requests:
            response_times = [r["response_time"] for r in successful_requests]
            
            print(f"\n⏰ VÁLASZIDŐ STATISZTIKÁK (sikeres kérések)")
            print(f"   🔹 Minimum: {min(response_times):.3f} másodperc")
            print(f"   🔹 Maximum: {max(response_times):.3f} másodperc")
            print(f"   🔹 Átlag: {statistics.mean(response_times):.3f} másodperc")
            print(f"   🔹 Medián: {statistics.median(response_times):.3f} másodperc")
            
            # Instance-onkénti teljesítmény
            print(f"\n🖥️  INSTANCE-ONKÉNTI TELJESÍTMÉNY")
            for i, instance in enumerate(self.instances):
                print(f"   VM {i+1} ({instance.url}):")
                print(f"      - Befejezett task-ok: {instance.completed_tasks}")
                print(f"      - Hibák: {instance.errors}")
                if instance.completed_tasks > 0:
                    avg_time = instance.total_response_time / instance.completed_tasks
                    print(f"      - Átlag válaszidő: {avg_time:.3f}s")
                    
                    # Instance-specifikus task-ok
                    instance_results = [r for r in successful_requests if r["instance_url"] == instance.url]
                    if instance_results:
                        instance_times = [r["response_time"] for r in instance_results]
                        print(f"      - Min/Max: {min(instance_times):.3f}s / {max(instance_times):.3f}s")
                else:
                    print(f"      - Átlag válaszidő: N/A")
            
            # Throughput számítás
            if successful_requests:
                actual_test_duration = max([r["timestamp"] for r in successful_requests]) - min([r["timestamp"] for r in successful_requests])
                if actual_test_duration > 0:
                    throughput = len(successful_requests) / actual_test_duration
                    print(f"\n🚀 THROUGHPUT")
                    print(f"   🔹 Sikeres kérések/másodperc: {throughput:.2f}")
                    print(f"   🔹 Átlagos instance terhelés: {throughput/len(self.instances):.2f} kérés/sec/instance")
        
        # Queue és task-ok státusza
        print(f"\n📋 TASK QUEUE STATISZTIKÁK")
        print(f"   🔹 Eredeti task-ok: {TOTAL_REQUESTS}")
        print(f"   🔹 Befejezett: {len(self.completed_results) + len(self.errors)}")
        print(f"   🔹 Feldolgozatlan: {len(self.task_queue)}")
        
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
    balancer = DynamicLoadBalancer()
    await balancer.run_test()

if __name__ == "__main__":
    print("🔧 Mannequin Segmenter Dynamic Load Balancer Test")
    print("=" * 60)
    asyncio.run(main())
