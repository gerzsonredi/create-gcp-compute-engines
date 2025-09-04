#!/usr/bin/env python3
"""
Improved Dynamic Load Balancer Test Script for Mannequin Segmenter API
Generates random pulover URLs to a file, then uses each URL individually for requests
"""

import asyncio
import aiohttp
import time
import statistics
from datetime import datetime
import json
from collections import deque
import random
import csv
import os

# ========== KONFIGURÁCIÓS PARAMÉTEREK ==========
TEST_DURATION_SECONDS = 30  # Teszt futási ideje másodpercben
TOTAL_REQUESTS = 50         # Összes kérések száma amit fel akarunk dolgozni
REQUEST_TIMEOUT = 60        # Timeout másodpercben
CSV_FILE = "data_for_categorisation.csv"
URL_LIST_FILE = "pulover_urls.txt"

# VM Instance IP címek
VM_INSTANCES = [
    "http://34.22.130.174:5001",
    "http://34.79.218.203:5001", 
    "http://104.155.15.184:5001",
    "http://35.195.4.217:5001",
    "http://34.140.252.94:5001"
]

# API endpoint
API_ENDPOINT = "/infer"

# ===============================================

def extract_pulover_urls_from_csv(csv_file, count):
    """Kiválaszt random pulover URL-eket a CSV-ből"""
    pulover_urls = []
    
    print(f"📖 CSV fájl olvasása: {csv_file}")
    
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

def save_urls_to_file(urls, filename):
    """URL-ek mentése fájlba"""
    try:
        with open(filename, 'w', encoding='utf-8') as f:
            for url in urls:
                f.write(url + '\n')
        print(f"💾 URL-ek elmentve: {filename} ({len(urls)} darab)")
        return True
    except Exception as e:
        print(f"❌ Hiba a fájl mentésekor: {e}")
        return False

def load_urls_from_file(filename):
    """URL-ek betöltése fájlból"""
    try:
        with open(filename, 'r', encoding='utf-8') as f:
            urls = [line.strip() for line in f if line.strip()]
        print(f"📂 URL-ek betöltve: {filename} ({len(urls)} darab)")
        return urls
    except Exception as e:
        print(f"❌ Hiba a fájl olvasásakor: {e}")
        return []

class InstanceState:
    def __init__(self, url):
        self.url = url
        self.is_busy = False
        self.current_task_id = None
        self.completed_tasks = 0
        self.total_response_time = 0.0
        self.errors = 0
        self.last_completed = None
        # Concurrency guard
        self.in_flight = 0
        self.violations = 0

class ImprovedDynamicLoadBalancer:
    def __init__(self, image_urls):
        self.instances = [InstanceState(url) for url in VM_INSTANCES]
        self.image_urls = image_urls
        self.task_queue = deque()
        self.completed_results = []
        self.errors = []
        self.start_time = None
        self.next_task_id = 1
        
        # Feltöltjük a task queue-t - minden kérés KÜLÖN URL-t kap
        for i in range(min(TOTAL_REQUESTS, len(image_urls))):
            self.task_queue.append({
                "task_id": i + 1,
                "payload": {
                    "image_url": image_urls[i],  # Minden task külön URL-t kap
                    "prompt_mode": "both"
                }
            })
        
        print(f"📋 Task queue feltöltve {len(self.task_queue)} egyedi URL-lel")
    
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
        # Concurrency guard start
        instance.in_flight += 1
        if instance.in_flight > 1:
            instance.violations += 1
            print(f"⚠️  CONCURRENCY VIOLATION on {instance.url} (in_flight={instance.in_flight})")
        instance.is_busy = True
        instance.current_task_id = task["task_id"]
        
        full_url = f"{instance.url}{API_ENDPOINT}"
        request_start = time.time()
        
        # URL rövid megjelenítése
        image_url = task["payload"]["image_url"]
        short_url = image_url.split('/')[-1][:30] + "..." if len(image_url.split('/')[-1]) > 30 else image_url.split('/')[-1]
        
        print(f"🔄 Task {task['task_id']}: {instance.url} -> {short_url}", end="", flush=True)
        
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
                    "response_size": len(response_text),
                    "image_url": task["payload"]["image_url"]
                }
                
                if response.status == 200:
                    try:
                        json_response = json.loads(response_text)
                        result["has_visualization_url"] = "visualization_url" in json_response
                        if "timing" in json_response:
                            result["server_timing"] = json_response["timing"]
                            # Server timing részletek kinyerése
                            if "model_inference_time" in json_response["timing"]:
                                result["model_time"] = json_response["timing"]["model_inference_time"]
                            if "gcs_upload_time" in json_response["timing"]:
                                result["gcs_time"] = json_response["timing"]["gcs_upload_time"]
                    except json.JSONDecodeError:
                        result["has_visualization_url"] = False
                
                self.completed_results.append(result)
                
                # Instance statisztikák frissítése
                instance.completed_tasks += 1
                instance.total_response_time += response_time
                instance.last_completed = time.time()
                
                # Server timing megjelenítése ha van
                timing_str = ""
                if response.status == 200 and "model_time" in result and "gcs_time" in result:
                    timing_str = f" (model: {result['model_time']:.2f}s, gcs: {result['gcs_time']:.2f}s)"
                print(f" ✅ {response.status} ({response_time:.2f}s){timing_str}")
                
        except asyncio.TimeoutError:
            request_end = time.time()
            response_time = request_end - request_start
            error = {
                "task_id": task["task_id"],
                "instance_url": instance.url,
                "error": "Timeout",
                "response_time": response_time,
                "timestamp": request_start,
                "image_url": task["payload"]["image_url"]
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
                "timestamp": request_start,
                "image_url": task["payload"]["image_url"]
            }
            self.errors.append(error)
            instance.errors += 1
            print(f" ❌ ERROR: {e}")
        
        # Instance felszabadítása + concurrency guard end
        instance.is_busy = False
        instance.current_task_id = None
        instance.in_flight = max(0, instance.in_flight - 1)
    
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
        print(f"🚀 Improved Dynamic Load Balancer Teszt - Egyedi Pulover Képekkel")
        print(f"📊 Konfiguráció:")
        print(f"   - Teszt időtartam: {TEST_DURATION_SECONDS} másodperc")
        print(f"   - Összes task: {len(self.task_queue)}")
        print(f"   - VM instance-ok: {len(VM_INSTANCES)}")
        print(f"   - Request timeout: {REQUEST_TIMEOUT}s")
        print(f"   - Stratégia: Minden instance max 1 task egyszerre")
        print(f"   - Képek: Minden task EGYEDI pulover képet használ")
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
            await asyncio.sleep(3)  # 3 másodpercenként
            
            current_time = time.time()
            elapsed = current_time - self.start_time
            
            if elapsed >= TEST_DURATION_SECONDS:
                break
            
            completed = len(self.completed_results)
            remaining = len(self.task_queue)
            busy_instances = sum(1 for inst in self.instances if inst.is_busy)
            successful = len([r for r in self.completed_results if r["success"]])
            
            print(f"📊 Progress: {completed} kész ({successful} sikeres), {remaining} várakozik, {busy_instances}/{len(self.instances)} instance dolgozik ({elapsed:.0f}s)")
    
    def print_statistics(self):
        """Statisztikák kiírása"""
        successful_requests = [r for r in self.completed_results if r["success"]]
        failed_requests = len(self.completed_results) - len(successful_requests)
        total_requests = len(self.completed_results) + len(self.errors)
        
        print(f"\n📈 TESZT EREDMÉNYEK - EGYEDI PULOVER KÉPEK")
        print(f"=" * 70)
        print(f"⏱️  Teszt időtartam: {TEST_DURATION_SECONDS} másodperc")
        print(f"📊 Összes task: {len(self.task_queue) + total_requests}")
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
                print(f"      - Concurrency violations: {instance.violations}")
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
        print(f"   🔹 Eredeti task-ok: {len(self.task_queue) + total_requests}")
        print(f"   🔹 Befejezett: {len(self.completed_results) + len(self.errors)}")
        print(f"   🔹 Feldolgozatlan: {len(self.task_queue)}")
        
        # Összes futás eredménye
        if successful_requests:
            print(f"\n🖼️  ÖSSZES SIKERES FUTÁS EREDMÉNYE")
            for i, result in enumerate(successful_requests, 1):
                short_url = result['image_url'].split('/')[-1]
                instance_name = result['instance_url'].split('/')[-1].split(':')[0]
                timing_details = ""
                if "model_time" in result and "gcs_time" in result:
                    timing_details = f" (model: {result['model_time']:.2f}s, gcs: {result['gcs_time']:.2f}s)"
                print(f"   {i:2d}. Task {result['task_id']:2d} | {instance_name:13s} | {short_url:50s} | {result['response_time']:6.2f}s{timing_details}")
        
        # Sikertelen futások
        failed_all = [r for r in self.completed_results if not r["success"]] + self.errors
        if failed_all:
            print(f"\n❌ ÖSSZES SIKERTELEN FUTÁS")
            for i, result in enumerate(failed_all, 1):
                if 'image_url' in result:
                    short_url = result['image_url'].split('/')[-1]
                    instance_name = result['instance_url'].split('/')[-1].split(':')[0]
                    error_msg = result.get('error', f'HTTP {result.get("status_code", "Unknown")}')
                    print(f"   {i:2d}. Task {result['task_id']:2d} | {instance_name:13s} | {short_url:50s} | {error_msg}")
                else:
                    print(f"   {i:2d}. {result}")
        
        # Mintákat is megtartjuk
        if successful_requests:
            print(f"\n🖼️  SIKERES KÉPEK MINTÁI (első 5)")
            sample_size = min(5, len(successful_requests))
            for i, result in enumerate(successful_requests[:sample_size]):
                short_url = result['image_url'].split('/')[-1]
                print(f"   {i+1}. {short_url} ({result['response_time']:.2f}s)")
        
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

def main():
    """Fő program belépési pont"""
    print("🔧 Improved Mannequin Segmenter Dynamic Load Balancer Test")
    print("=" * 70)
    
    # Ellenőrizzük hogy van-e már URL fájl
    if os.path.exists(URL_LIST_FILE):
        print(f"📂 URL fájl már létezik: {URL_LIST_FILE}")
        recreate = input("🔄 Új URL-eket generáljunk? (y/n): ").lower().strip()
        
        if recreate == 'y' or recreate == 'yes':
            print("🔄 Új URL-ek generálása...")
            urls = extract_pulover_urls_from_csv(CSV_FILE, TOTAL_REQUESTS)
            if urls:
                save_urls_to_file(urls, URL_LIST_FILE)
            else:
                print("❌ Nem sikerült URL-eket generálni")
                return
        else:
            print("📂 Meglévő URL fájl használata...")
    else:
        print(f"🆕 URL fájl nem létezik, új generálás: {URL_LIST_FILE}")
        urls = extract_pulover_urls_from_csv(CSV_FILE, TOTAL_REQUESTS)
        if urls:
            save_urls_to_file(urls, URL_LIST_FILE)
        else:
            print("❌ Nem sikerült URL-eket generálni")
            return
    
    # URL-ek betöltése
    image_urls = load_urls_from_file(URL_LIST_FILE)
    if not image_urls:
        print("❌ Nem sikerült URL-eket betölteni")
        return
    
    print(f"🎯 {len(image_urls)} egyedi pulover kép betöltve a teszthez")
    
    # Load balancer teszt futtatása
    balancer = ImprovedDynamicLoadBalancer(image_urls)
    asyncio.run(balancer.run_test())

if __name__ == "__main__":
    main()
