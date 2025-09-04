#!/usr/bin/env python3
"""
Parallel Dynamic URL Test Script for Mannequin Segmenter API
Mint az improved_dynamic_load_balancer: a kérésekhez a CSV-ből választunk
random pulóver képeket, amelyek 'b.jpg'-re végződnek.
"""

import asyncio
import aiohttp
import time
import statistics
from datetime import datetime
import json
import random
import csv
import os

# ========== KONFIGURÁCIÓS PARAMÉTEREK ==========
TOTAL_REQUESTS_PER_INSTANCE = 500               # Összes kérések száma instance-onként
REQUEST_TIMEOUT = 10                           # Timeout másodpercben (same as single test)
DELAY_BETWEEN_REQUESTS = 20                # Szünet kérések között instance-onként (same as single test)
CSV_FILE = "data_for_categorisation.csv"     # Forrás CSV a képekhez
STAGGER_BETWEEN_WORKERS_MS = 500           # Kezdési eltérés a workerek között (ms)

# VM Instance IP címek
VM_INSTANCES = [
    "http://35.233.66.133:5001",
    "http://35.187.98.56:5001", 
    "http://34.34.136.96:5001",
    "http://34.22.166.98:5001",
    "http://34.14.83.46:5001",
    "http://35.205.73.127:5001",
    "http://34.22.130.174:5001",
    "http://34.79.218.203:5001",
    "http://34.140.252.94:5001",
    "http://104.155.15.184:5001",
    "http://35.195.4.217:5001",
    "http://34.77.34.87:5001",
    "http://34.52.210.152:5001",
    "http://34.77.40.49:5001",
    "http://104.199.74.153:5001",
    "http://35.205.176.188:5001",
    "http://35.195.189.152:5001",
    "http://35.187.44.31:5001",
    "http://23.251.142.224:5001",
    "http://34.14.34.215:5001",
]

# URL kiválasztás CSV-ből (pulóver + 'b.jpg')
def extract_pulover_urls_from_csv(csv_file):
    urls = []
    try:
        with open(csv_file, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            for line in lines[1:]:  # skip header
                line = line.strip()
                if not line:
                    continue
                parts = line.split(',')
                if len(parts) >= 3:
                    full_name = parts[1].lower()
                    image_url = parts[2]
                    if ("pulover" in full_name or "пуловери" in full_name) and image_url.endswith('b.jpg'):
                        urls.append(image_url)
    except Exception as e:
        print(f"❌ CSV olvasási hiba: {e}")
    return urls
# API endpoint
API_ENDPOINT = "/infer"

# ===============================================

class InstanceWorker:
    def __init__(self, instance_url, instance_id, image_urls):
        self.instance_url = instance_url
        self.instance_id = instance_id
        self.instance_name = instance_url.split('/')[-1].split(':')[0]  # IP only
        self.results = []
        self.errors = []
        self.completed_requests = 0
        self.image_urls = image_urls
    
    async def make_request(self, session, request_id):
        """Egyetlen kérés végrehajtása ezen az instance-on"""
        full_url = f"{self.instance_url}{API_ENDPOINT}"
        request_start = time.time()
        
        try:
            # Random pulóver kép kiválasztása a CSV-ből betöltött listából
            image_url = random.choice(self.image_urls)
            payload = {
                "image_url": image_url,
                "prompt_mode": "both"
            }
            
            connect_start = time.time()
            async with session.post(
                full_url,
                json=payload
            ) as response:
                first_byte_time = time.time()
                response_text = await response.text()
                request_end = time.time()
                response_time = request_end - request_start
                ttfb = first_byte_time - request_start
                
                result = {
                    "instance_id": self.instance_id,
                    "instance_url": self.instance_url,
                    "instance_name": self.instance_name,
                    "request_id": request_id,
                    "global_request_id": f"VM{self.instance_id}-{request_id}",
                    "status_code": response.status,
                    "response_time": response_time,
                    "timestamp": datetime.fromtimestamp(request_start),
                    "success": response.status == 200,
                    "response_size": len(response_text),
                    "client_ttfb": ttfb
                }
                
                if response.status == 200:
                    try:
                        json_response = json.loads(response_text)
                        result["has_visualization_url"] = "visualization_url" in json_response
                        if "timing" in json_response:
                            result["server_timing"] = json_response["timing"]
                            timing = json_response["timing"]
                            result["server_model_inference"] = timing.get("model_inference", 0)
                            result["server_gcs_total"] = timing.get("gcs_total", 0)
                            result["server_total_request"] = timing.get("total_request", 0)
                    except json.JSONDecodeError:
                        result["has_visualization_url"] = False
                
                self.results.append(result)
                self.completed_requests += 1
                
                # Azonnali kimenet minden kéréshez
                status_icon = "✅" if response.status == 200 else "❌"
                server_info = ""
                if "server_timing" in result:
                    model_time = result.get("server_model_inference", 0)
                    gcs_time = result.get("server_gcs_total", 0)
                    server_info = f" (model: {model_time:.2f}s, gcs: {gcs_time:.2f}s)"
                client_info = f" | ttfb: {ttfb:.2f}s"
                print(f"{status_icon} VM{self.instance_id} Req {request_id:2d}: {self.instance_name:13s} -> {response_time:.3f}s{server_info}{client_info}")
                
        except asyncio.TimeoutError:
            request_end = time.time()
            response_time = request_end - request_start
            error = {
                "instance_id": self.instance_id,
                "instance_url": self.instance_url,
                "instance_name": self.instance_name,
                "request_id": request_id,
                "global_request_id": f"VM{self.instance_id}-{request_id}",
                "error": "Timeout",
                "response_time": response_time,
                "timestamp": datetime.fromtimestamp(request_start)
            }
            self.errors.append(error)
            print(f"⏰ VM{self.instance_id} Req {request_id:2d}: {self.instance_name:13s} -> TIMEOUT ({response_time:.3f}s)")
            
        except Exception as e:
            request_end = time.time()
            response_time = request_end - request_start
            error = {
                "instance_id": self.instance_id,
                "instance_url": self.instance_url,
                "instance_name": self.instance_name,
                "request_id": request_id,
                "global_request_id": f"VM{self.instance_id}-{request_id}",
                "error": str(e),
                "response_time": response_time,
                "timestamp": datetime.fromtimestamp(request_start)
            }
            self.errors.append(error)
            print(f"❌ VM{self.instance_id} Req {request_id:2d}: {self.instance_name:13s} -> ERROR: {e}")
    
    async def run_worker(self):
        """Worker egy adott instance-hoz - saját ClientSession-nel, szekvenciálisan küldi a kéréseket"""
        print(f"🚀 VM{self.instance_id} worker started: {self.instance_url} | dynamic CSV pulover képek")
        
        # Staggered start to avoid bursty contention across instances (200ms lépés)
        initial_delay = (self.instance_id - 1) * (STAGGER_BETWEEN_WORKERS_MS / 1000.0)
        if initial_delay > 0:
            await asyncio.sleep(initial_delay)
        
        # Minden worker-nek saját ClientSession
        connector = aiohttp.TCPConnector(
            limit=10,              # Kisebb pool per worker
            limit_per_host=5,      # Max connections per host per worker
            keepalive_timeout=30,   
            enable_cleanup_closed=True
        )
        
        timeout = aiohttp.ClientTimeout(total=REQUEST_TIMEOUT)
        
        async with aiohttp.ClientSession(
            connector=connector, 
            timeout=timeout
        ) as session:
            for request_id in range(1, TOTAL_REQUESTS_PER_INSTANCE + 1):
                await self.make_request(session, request_id)
                
                # Kis szünet a következő kérés előtt (kivéve az utolsó után)
                if request_id < TOTAL_REQUESTS_PER_INSTANCE:
                    await asyncio.sleep(DELAY_BETWEEN_REQUESTS)
        
        print(f"✅ VM{self.instance_id} worker finished: {self.completed_requests}/{TOTAL_REQUESTS_PER_INSTANCE} completed")

class ParallelFixedUrlTester:
    def __init__(self):
        # Betöltjük a pulóver 'b.jpg' képeket a CSV-ből
        image_urls = extract_pulover_urls_from_csv(CSV_FILE)
        if not image_urls:
            raise RuntimeError("Nem találtunk megfelelő pulóver képeket a CSV-ben ('b.jpg').")

        self.workers = []
        for i, instance_url in enumerate(VM_INSTANCES, 1):
            worker = InstanceWorker(instance_url, i, image_urls)
            self.workers.append(worker)

        print(f"🎯 Parallel Dynamic URL Teszt: {len(VM_INSTANCES)} VM, {TOTAL_REQUESTS_PER_INSTANCE} kérés/VM")
        print(f"🖼️  Elérhető pulóver képek száma (CSV): {len(image_urls)}")
    
    async def run_parallel_test(self):
        """Párhuzamos teszt futtatása"""
        print(f"\n🚀 Parallel Dynamic URL Test (CSV pulóver képek)")
        print(f"📊 Konfiguráció:")
        print(f"   - VM instance-ok: {len(VM_INSTANCES)}")
        print(f"   - Kérések/instance: {TOTAL_REQUESTS_PER_INSTANCE}")
        print(f"   - Összes kérések: {len(VM_INSTANCES) * TOTAL_REQUESTS_PER_INSTANCE}")
        print(f"   - Request timeout: {REQUEST_TIMEOUT}s")
        print(f"   - Kérések közötti szünet: {DELAY_BETWEEN_REQUESTS}s")
        print(f"   - Mód: PÁRHUZAMOS (minden VM egyszerre dolgozik)")
        print(f"   - Kép: Random pulóver képek a CSV-ből ('b.jpg')")
        print()
        
        for i, worker in enumerate(self.workers):
            print(f"   VM{worker.instance_id}: {worker.instance_url}")
        print()
        
        start_time = time.time()
        
        # Minden worker saját ClientSession-t kap - nincs közös session
        tasks = []
        for worker in self.workers:
            task = asyncio.create_task(worker.run_worker())  # No shared session!
            tasks.append(task)
        
        # Progress monitoring
        monitor_task = asyncio.create_task(self.progress_monitor(start_time))
        tasks.append(monitor_task)
        
        # Várjuk meg az összes worker befejezését
        await asyncio.gather(*tasks, return_exceptions=True)
        
        end_time = time.time()
        total_time = end_time - start_time
        
        print(f"\n⏱️  Teszt befejezve! (összes idő: {total_time:.2f}s)")
        self.print_comprehensive_statistics()
    
    async def progress_monitor(self, start_time):
        """Folyamatos progress monitoring"""
        while True:
            await asyncio.sleep(5)  # 5 másodpercenként
            
            current_time = time.time()
            elapsed = current_time - start_time
            
            total_completed = sum(worker.completed_requests for worker in self.workers)
            total_expected = len(self.workers) * TOTAL_REQUESTS_PER_INSTANCE
            
            if total_completed >= total_expected:
                break
            
            # Per-instance progress
            progress_info = []
            for worker in self.workers:
                progress_info.append(f"VM{worker.instance_id}:{worker.completed_requests}/{TOTAL_REQUESTS_PER_INSTANCE}")
            
            print(f"📊 Progress ({elapsed:.0f}s): {total_completed}/{total_expected} total, {' | '.join(progress_info)}")
    
    def print_comprehensive_statistics(self):
        """Átfogó statisztikák kiírása"""
        # Összesített adatok
        all_successful = []
        all_failed = []
        
        for worker in self.workers:
            all_successful.extend([r for r in worker.results if r["success"]])
            all_failed.extend([r for r in worker.results if not r["success"]])
            all_failed.extend(worker.errors)
        
        total_requests = len(all_successful) + len(all_failed)
        
        print(f"\n📈 PÁRHUZAMOS DINAMIKUS URL TESZT EREDMÉNYEK (CSV)")
        print(f"=" * 80)
        print(f"🖼️  Forrás: {CSV_FILE} (pulóver + 'b.jpg')")
        print(f"📊 Összes kérés: {total_requests}")
        print(f"✅ Sikeres kérések: {len(all_successful)}")
        print(f"❌ Sikertelen kérések: {len(all_failed)}")
        if total_requests > 0:
            print(f"📈 Sikeresség arány: {len(all_successful)/total_requests*100:.1f}%")
        
        if all_successful:
            response_times = [r["response_time"] for r in all_successful]
            
            print(f"\n⏰ ÖSSZESÍTETT VÁLASZIDŐ STATISZTIKÁK")
            print(f"   🔹 Minimum: {min(response_times):.3f} másodperc")
            print(f"   🔹 Maximum: {max(response_times):.3f} másodperc")
            print(f"   🔹 Átlag: {statistics.mean(response_times):.3f} másodperc")
            print(f"   🔹 Medián: {statistics.median(response_times):.3f} másodperc")
            if len(response_times) > 1:
                print(f"   🔹 Szórás: {statistics.stdev(response_times):.3f} másodperc")
            
            # Instance-onkénti részletes statisztikák
            print(f"\n🖥️  INSTANCE-ONKÉNTI TELJESÍTMÉNY")
            for worker in self.workers:
                successful_results = [r for r in worker.results if r["success"]]
                failed_count = len(worker.results) - len(successful_results) + len(worker.errors)
                
                print(f"\n   VM{worker.instance_id} ({worker.instance_name}):")
                print(f"      - Befejezett kérések: {len(worker.results) + len(worker.errors)}/{TOTAL_REQUESTS_PER_INSTANCE}")
                print(f"      - Sikeres: {len(successful_results)}")
                print(f"      - Sikertelen: {failed_count}")
                
                if successful_results:
                    times = [r["response_time"] for r in successful_results]
                    model_times = [r.get("server_model_inference", 0) for r in successful_results if "server_model_inference" in r]
                    
                    print(f"      - Válaszidő átlag: {statistics.mean(times):.3f}s")
                    print(f"      - Válaszidő min/max: {min(times):.3f}s / {max(times):.3f}s")
                    if len(times) > 1:
                        print(f"      - Válaszidő szórás: {statistics.stdev(times):.3f}s")
                    
                    if model_times:
                        print(f"      - Server model átlag: {statistics.mean(model_times):.3f}s")
            
            # Konkurens teljesítmény elemzés
            print(f"\n🔄 KONKURENS TELJESÍTMÉNY ELEMZÉS")
            
            # Időbélyeg alapú throughput számítás
            if len(all_successful) > 1:
                start_timestamp = min(r["timestamp"] for r in all_successful)
                end_timestamp = max(r["timestamp"] for r in all_successful)
                duration = (end_timestamp - start_timestamp).total_seconds()
                
                if duration > 0:
                    throughput = len(all_successful) / duration
                    print(f"   🔹 Átlagos throughput: {throughput:.2f} kérés/másodperc")
                    print(f"   🔹 Instance átlag: {throughput/len(self.workers):.2f} kérés/sec/instance")
            
            # Outlier elemzés párhuzamos környezetben
            avg_time = statistics.mean(response_times)
            std_time = statistics.stdev(response_times) if len(response_times) > 1 else 0
            threshold = avg_time + 2 * std_time
            
            outliers = [r for r in all_successful if r["response_time"] > threshold]
            
            print(f"\n🔍 OUTLIER ELEMZÉS (párhuzamos terhelés)")
            if outliers:
                print(f"   ⚠️  {len(outliers)} outlier találva (>{threshold:.3f}s):")
                for outlier in outliers[:5]:
                    vm_id = outlier["instance_id"]
                    req_id = outlier["request_id"]
                    response_time = outlier["response_time"]
                    print(f"      VM{vm_id} Req {req_id:2d}: {response_time:.3f}s")
                if len(outliers) > 5:
                    print(f"      ... és még {len(outliers) - 5} darab")
                print(f"   💡 Párhuzamos terhelés miatt a lassulás VÁRHATÓ")
            else:
                print(f"   ✅ Nincs jelentős outlier - stabil párhuzamos teljesítmény")
        
        # Hibák részletezése
        if all_failed:
            print(f"\n❌ HIBÁK RÉSZLETEZÉSE")
            error_by_instance = {}
            for error in all_failed:
                instance_id = error.get("instance_id", "Unknown")
                if instance_id not in error_by_instance:
                    error_by_instance[instance_id] = []
                error_by_instance[instance_id].append(error)
            
            for instance_id, errors in error_by_instance.items():
                print(f"   VM{instance_id}: {len(errors)} hiba")
                error_types = {}
                for error in errors:
                    error_type = error.get("error", f"HTTP {error.get('status_code', 'Unknown')}")
                    error_types[error_type] = error_types.get(error_type, 0) + 1
                
                for error_type, count in error_types.items():
                    print(f"      - {error_type}: {count} alkalom")

async def main():
    """Fő program belépési pont"""
    print("🔧 Parallel Fixed URL Performance Test")
    print("=" * 60)
    print("🎯 Ez a teszt ugyanazt a képet küldi el párhuzamosan 4 VM-re")
    print("💡 Célja: párhuzamos terhelés hatásának mérése")
    print("📊 Minden kérés eredménye valós időben megjelenik")
    print()
    
    # Teszter létrehozása és futtatása
    tester = ParallelFixedUrlTester()
    await tester.run_parallel_test()

if __name__ == "__main__":
    asyncio.run(main())
