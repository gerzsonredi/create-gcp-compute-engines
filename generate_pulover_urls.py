#!/usr/bin/env python3
"""
Pulover URL generator script
Kiválaszt random pulover képeket a CSV-ből amelyek 'b.jpg'-re végződnek
"""

import csv
import random
import sys

def extract_pulover_urls(csv_file, count=50):
    """Kiválaszt random pulover URL-eket a CSV-ből"""
    pulover_urls = []
    
    try:
        with open(csv_file, 'r', encoding='utf-8') as file:
            lines = file.readlines()
            
            for line_num, line in enumerate(lines[1:], 2):  # Skip header
                line = line.strip()
                if not line:
                    continue
                    
                # Split by comma and clean up
                parts = line.split(',')
                if len(parts) >= 3:
                    full_name = parts[1].lower()
                    image_url = parts[2]
                    
                    # Ellenőrizzük hogy pulover van a nevében vagy a kategóriában és b.jpg végződésű
                    if ('pulover' in full_name or 'пуловери' in full_name) and image_url.endswith('b.jpg'):
                        pulover_urls.append(image_url)
        
        print(f"🔍 Összesen talált pulover képek (b.jpg): {len(pulover_urls)}")
        
        # Random kiválasztás
        if len(pulover_urls) < count:
            print(f"⚠️  Csak {len(pulover_urls)} kép elérhető, az összeset használjuk")
            selected_urls = pulover_urls
        else:
            selected_urls = random.sample(pulover_urls, count)
        
        print(f"✅ Kiválasztott képek száma: {len(selected_urls)}")
        return selected_urls
        
    except Exception as e:
        print(f"❌ Hiba a CSV olvasásakor: {e}")
        return []

def update_dynamic_load_balancer(urls):
    """Frissíti a dynamic_load_balancer_test.py fájlt az új URL-ekkel"""
    
    # Generáljuk a Python lista string-et
    url_list_str = '[\n    "' + '",\n    "'.join(urls) + '"\n]'
    
    script_content = f'''#!/usr/bin/env python3
"""
Dynamic Load Balancer Test Script for Mannequin Segmenter API
Each instance gets exactly one task at a time. When an instance finishes, 
it immediately gets assigned the next pending task from the queue.
Updated with random pulover URLs from CSV data.
"""

import asyncio
import aiohttp
import time
import statistics
from datetime import datetime
import json
from collections import deque
import random

# ========== KONFIGURÁCIÓS PARAMÉTEREK ==========
TEST_DURATION_SECONDS = 30  # Teszt futási ideje másodpercben
TOTAL_REQUESTS = {len(urls)}         # Összes kérések száma amit fel akarunk dolgozni
REQUEST_TIMEOUT = 60        # Timeout másodpercben

# VM Instance IP címek
VM_INSTANCES = [
    "http://35.233.66.133:5001",
    "http://34.34.136.96:5001", 
    "http://192.158.29.6:5001",
    "http://35.187.98.56:5001"
]

# Pulover képek URL listája (random kiválasztva CSV-ből)
PULOVER_URLS = {url_list_str}

# API endpoint
API_ENDPOINT = "/infer"

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
        
        # Feltöltjük a task queue-t random pulover képekkel
        for i in range(TOTAL_REQUESTS):
            random_url = random.choice(PULOVER_URLS)
            self.task_queue.append({{
                "task_id": i + 1,
                "payload": {{
                    "image_url": random_url,
                    "prompt_mode": "both"
                }}
            }})
    
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
        
        full_url = f"{{instance.url}}{{API_ENDPOINT}}"
        request_start = time.time()
        
        print(f"🔄 Task {{task['task_id']}}: {{instance.url}} -> Küldés...", end="", flush=True)
        
        try:
            async with session.post(
                full_url,
                json=task["payload"],
                timeout=aiohttp.ClientTimeout(total=REQUEST_TIMEOUT)
            ) as response:
                response_text = await response.text()
                request_end = time.time()
                response_time = request_end - request_start
                
                result = {{
                    "task_id": task["task_id"],
                    "instance_url": instance.url,
                    "status_code": response.status,
                    "response_time": response_time,
                    "timestamp": request_start,
                    "success": response.status == 200,
                    "response_size": len(response_text),
                    "image_url": task["payload"]["image_url"]
                }}
                
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
                
                print(f" ✅ {{response.status}} ({{response_time:.2f}}s)")
                
        except asyncio.TimeoutError:
            request_end = time.time()
            response_time = request_end - request_start
            error = {{
                "task_id": task["task_id"],
                "instance_url": instance.url,
                "error": "Timeout",
                "response_time": response_time,
                "timestamp": request_start,
                "image_url": task["payload"]["image_url"]
            }}
            self.errors.append(error)
            instance.errors += 1
            print(f" ⏰ TIMEOUT ({{response_time:.2f}}s)")
            
        except Exception as e:
            request_end = time.time()
            response_time = request_end - request_start
            error = {{
                "task_id": task["task_id"],
                "instance_url": instance.url,
                "error": str(e),
                "response_time": response_time,
                "timestamp": request_start,
                "image_url": task["payload"]["image_url"]
            }}
            self.errors.append(error)
            instance.errors += 1
            print(f" ❌ ERROR: {{e}}")
        
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
                print(f"⏰ {{instance.url}}: Időtúllépés, leállítás")
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
        print(f"🚀 Dynamic Load Balancer Teszt - Pulover Képekkel")
        print(f"📊 Konfiguráció:")
        print(f"   - Teszt időtartam: {{TEST_DURATION_SECONDS}} másodperc")
        print(f"   - Összes task: {{TOTAL_REQUESTS}}")
        print(f"   - VM instance-ok: {{len(VM_INSTANCES)}}")
        print(f"   - Request timeout: {{REQUEST_TIMEOUT}}s")
        print(f"   - Stratégia: Minden instance max 1 task egyszerre")
        print(f"   - Képek: Random pulover képek a CSV-ből")
        print()
        
        for i, instance in enumerate(self.instances):
            print(f"   VM {{i+1}}: {{instance.url}}")
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
        
        print(f"\\n⏱️  Teszt befejezve!")
        self.print_statistics()
    
    async def progress_monitor(self):
        """Folyamatosan monitorozza a progresst"""
        while True:
            await asyncio.sleep(3)  # 3 másodpercenként
            
            current_time = time.time()
            elapsed = current_time - self.start_time
            
            if elapsed >= TEST_DURATION_SECONDS:
                break
            
            completed = len(self.completed_results)
            remaining = len(self.task_queue)
            busy_instances = sum(1 for inst in self.instances if inst.is_busy)
            successful = len([r for r in self.completed_results if r["success"]])
            
            print(f"📊 Progress: {{completed}} kész ({{successful}} sikeres), {{remaining}} várakozik, {{busy_instances}}/{{len(self.instances)}} instance dolgozik ({{elapsed:.0f}}s)")
    
    def print_statistics(self):
        """Statisztikák kiírása"""
        successful_requests = [r for r in self.completed_results if r["success"]]
        failed_requests = len(self.completed_results) - len(successful_requests)
        total_requests = len(self.completed_results) + len(self.errors)
        
        print(f"\\n📈 TESZT EREDMÉNYEK - PULOVER KÉPEK")
        print(f"=" * 60)
        print(f"⏱️  Teszt időtartam: {{TEST_DURATION_SECONDS}} másodperc")
        print(f"📊 Összes task: {{TOTAL_REQUESTS}}")
        print(f"✅ Befejezett task-ok: {{total_requests}}")
        print(f"🔄 Feldolgozatlan task-ok: {{len(self.task_queue)}}")
        print(f"✅ Sikeres kérések: {{len(successful_requests)}}")
        print(f"❌ Sikertelen kérések: {{failed_requests + len(self.errors)}}")
        if total_requests > 0:
            print(f"📈 Sikeresség arány: {{len(successful_requests)/total_requests*100:.1f}}%")
        
        if successful_requests:
            response_times = [r["response_time"] for r in successful_requests]
            
            print(f"\\n⏰ VÁLASZIDŐ STATISZTIKÁK (sikeres kérések)")
            print(f"   🔹 Minimum: {{min(response_times):.3f}} másodperc")
            print(f"   🔹 Maximum: {{max(response_times):.3f}} másodperc")
            print(f"   🔹 Átlag: {{statistics.mean(response_times):.3f}} másodperc")
            print(f"   🔹 Medián: {{statistics.median(response_times):.3f}} másodperc")
            
            # Instance-onkénti teljesítmény
            print(f"\\n🖥️  INSTANCE-ONKÉNTI TELJESÍTMÉNY")
            for i, instance in enumerate(self.instances):
                print(f"   VM {{i+1}} ({{instance.url}}):")
                print(f"      - Befejezett task-ok: {{instance.completed_tasks}}")
                print(f"      - Hibák: {{instance.errors}}")
                if instance.completed_tasks > 0:
                    avg_time = instance.total_response_time / instance.completed_tasks
                    print(f"      - Átlag válaszidő: {{avg_time:.3f}}s")
                    
                    # Instance-specifikus task-ok
                    instance_results = [r for r in successful_requests if r["instance_url"] == instance.url]
                    if instance_results:
                        instance_times = [r["response_time"] for r in instance_results]
                        print(f"      - Min/Max: {{min(instance_times):.3f}}s / {{max(instance_times):.3f}}s")
                else:
                    print(f"      - Átlag válaszidő: N/A")
            
            # Throughput számítás
            if successful_requests:
                actual_test_duration = max([r["timestamp"] for r in successful_requests]) - min([r["timestamp"] for r in successful_requests])
                if actual_test_duration > 0:
                    throughput = len(successful_requests) / actual_test_duration
                    print(f"\\n🚀 THROUGHPUT")
                    print(f"   🔹 Sikeres kérések/másodperc: {{throughput:.2f}}")
                    print(f"   🔹 Átlagos instance terhelés: {{throughput/len(self.instances):.2f}} kérés/sec/instance")
        
        # Queue és task-ok státusza
        print(f"\\n📋 TASK QUEUE STATISZTIKÁK")
        print(f"   🔹 Eredeti task-ok: {{TOTAL_REQUESTS}}")
        print(f"   🔹 Befejezett: {{len(self.completed_results) + len(self.errors)}}")
        print(f"   🔹 Feldolgozatlan: {{len(self.task_queue)}}")
        
        # Sikeres képek mintái
        if successful_requests:
            print(f"\\n🖼️  SIKERES KÉPEK MINTÁI")
            sample_size = min(5, len(successful_requests))
            for i, result in enumerate(successful_requests[:sample_size]):
                print(f"   {{i+1}}. {{result['image_url']}} ({{result['response_time']:.2f}}s)")
        
        # Hibák részletezése
        if self.errors:
            print(f"\\n❌ HIBÁK RÉSZLETEZÉSE")
            error_types = {{}}
            for error in self.errors:
                error_type = error["error"]
                if error_type not in error_types:
                    error_types[error_type] = 0
                error_types[error_type] += 1
            
            for error_type, count in error_types.items():
                print(f"   🔹 {{error_type}}: {{count}} alkalom")

async def main():
    """Fő program belépési pont"""
    balancer = DynamicLoadBalancer()
    await balancer.run_test()

if __name__ == "__main__":
    print("🔧 Mannequin Segmenter Dynamic Load Balancer Test - Pulover Edition")
    print("=" * 70)
    asyncio.run(main())'''
    
    try:
        with open('dynamic_load_balancer_pulover.py', 'w', encoding='utf-8') as f:
            f.write(script_content)
        print(f"✅ Létrehozva: dynamic_load_balancer_pulover.py")
        print(f"📊 {len(urls)} random pulover URL beépítve")
        return True
    except Exception as e:
        print(f"❌ Hiba a fájl írásakor: {e}")
        return False

def main():
    if len(sys.argv) > 1:
        try:
            count = int(sys.argv[1])
        except ValueError:
            print("❌ Hibás szám formátum")
            return
    else:
        count = 50  # Default
    
    print(f"🎯 {count} random pulover URL kiválasztása...")
    
    urls = extract_pulover_urls('data_for_categorisation.csv', count)
    
    if urls:
        print("\\n📋 Kiválasztott URL-ek:")
        for i, url in enumerate(urls[:10], 1):  # Első 10 megjelenítése
            print(f"   {i}. {url}")
        if len(urls) > 10:
            print(f"   ... és még {len(urls) - 10} darab")
        
        print("\\n🔄 Load balancer script generálása...")
        if update_dynamic_load_balancer(urls):
            print("\\n🚀 Futtatáshoz használd: python3 dynamic_load_balancer_pulover.py")
    else:
        print("❌ Nem sikerült URL-eket találni")

if __name__ == "__main__":
    main()
