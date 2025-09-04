#!/usr/bin/env python3
"""
Sequential Single Instance Test Script for Mannequin Segmenter API
Sends 50 random pulover images sequentially (one after another) to a single VM instance
to analyze response time variations without any concurrency
"""

import asyncio
import aiohttp
import time
import statistics
from datetime import datetime
import json
import random
import os

# ========== KONFIGURÁCIÓS PARAMÉTEREK ==========
TARGET_INSTANCE = "http://35.233.66.133:5001"  # Tesztelendő VM instance
TOTAL_REQUESTS = 50                             # Összes kérések száma
REQUEST_TIMEOUT = 120                           # Timeout másodpercben (hosszabb a stabilitásért)
URL_LIST_FILE = "pulover_urls.txt"              # Pulover URL-ek fájlja
DELAY_BETWEEN_REQUESTS = 0.5                    # Kis szünet kérések között (másodperc)

# API endpoint
API_ENDPOINT = "/infer"

# ===============================================

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

class SequentialTester:
    def __init__(self, image_urls, target_instance):
        self.image_urls = image_urls
        self.target_instance = target_instance
        self.results = []
        self.errors = []
        
        # Random kiválasztás és keverés
        if len(image_urls) >= TOTAL_REQUESTS:
            self.test_urls = random.sample(image_urls, TOTAL_REQUESTS)
        else:
            self.test_urls = image_urls
            print(f"⚠️  Csak {len(image_urls)} URL elérhető, az összeset használjuk")
        
        # Keverés a random sorrendért
        random.shuffle(self.test_urls)
        
        print(f"🎯 {len(self.test_urls)} random pulover kép kiválasztva szekvenciális teszthez")
    
    async def make_single_request(self, session, request_id, image_url):
        """Egyetlen API kérés végrehajtása"""
        full_url = f"{self.target_instance}{API_ENDPOINT}"
        request_start = time.time()
        
        # URL rövid megjelenítése
        short_url = image_url.split('/')[-1][:50] + "..." if len(image_url.split('/')[-1]) > 50 else image_url.split('/')[-1]
        
        print(f"🔄 Request {request_id:2d}/50: {short_url}", end="", flush=True)
        
        try:
            payload = {
                "image_url": image_url,
                "prompt_mode": "both"
            }
            
            async with session.post(
                full_url,
                json=payload,
                timeout=aiohttp.ClientTimeout(total=REQUEST_TIMEOUT)
            ) as response:
                response_text = await response.text()
                request_end = time.time()
                response_time = request_end - request_start
                
                result = {
                    "request_id": request_id,
                    "image_url": image_url,
                    "status_code": response.status,
                    "response_time": response_time,
                    "timestamp": datetime.fromtimestamp(request_start),
                    "success": response.status == 200,
                    "response_size": len(response_text)
                }
                
                if response.status == 200:
                    try:
                        json_response = json.loads(response_text)
                        result["has_visualization_url"] = "visualization_url" in json_response
                        if "timing" in json_response:
                            result["server_timing"] = json_response["timing"]
                            # Server-side timing részletezése
                            timing = json_response["timing"]
                            if "model_inference" in timing and "gcs_total" in timing:
                                result["server_model_inference"] = timing["model_inference"]
                                result["server_gcs_total"] = timing["gcs_total"]
                                result["server_total_request"] = timing.get("total_request", 0)
                    except json.JSONDecodeError:
                        result["has_visualization_url"] = False
                
                self.results.append(result)
                
                # Részletes kimenet
                status_icon = "✅" if response.status == 200 else "❌"
                server_info = ""
                if "server_timing" in result:
                    model_time = result.get("server_model_inference", 0)
                    gcs_time = result.get("server_gcs_total", 0)
                    server_info = f" (model: {model_time:.2f}s, gcs: {gcs_time:.2f}s)"
                
                print(f" {status_icon} {response.status} ({response_time:.3f}s{server_info})")
                
        except asyncio.TimeoutError:
            request_end = time.time()
            response_time = request_end - request_start
            error = {
                "request_id": request_id,
                "image_url": image_url,
                "error": "Timeout",
                "response_time": response_time,
                "timestamp": datetime.fromtimestamp(request_start)
            }
            self.errors.append(error)
            print(f" ⏰ TIMEOUT ({response_time:.3f}s)")
            
        except Exception as e:
            request_end = time.time()
            response_time = request_end - request_start
            error = {
                "request_id": request_id,
                "image_url": image_url,
                "error": str(e),
                "response_time": response_time,
                "timestamp": datetime.fromtimestamp(request_start)
            }
            self.errors.append(error)
            print(f" ❌ ERROR: {e}")
    
    async def run_sequential_test(self):
        """Szekvenciális teszt futtatása"""
        print(f"🚀 Sequential Single Instance Test")
        print(f"📊 Konfiguráció:")
        print(f"   - Target instance: {self.target_instance}")
        print(f"   - Kérések száma: {len(self.test_urls)}")
        print(f"   - Request timeout: {REQUEST_TIMEOUT}s")
        print(f"   - Kérések közötti szünet: {DELAY_BETWEEN_REQUESTS}s")
        print(f"   - Mód: SZEKVENCIÁLIS (egy kérés egyszerre)")
        print()
        
        start_time = time.time()
        
        async with aiohttp.ClientSession() as session:
            for i, url in enumerate(self.test_urls, 1):
                await self.make_single_request(session, i, url)
                
                # Kis szünet a következő kérés előtt (kivéve az utolsó után)
                if i < len(self.test_urls):
                    await asyncio.sleep(DELAY_BETWEEN_REQUESTS)
                
                # Progress minden 10. kérésnél
                if i % 10 == 0 or i == len(self.test_urls):
                    elapsed = time.time() - start_time
                    successful = len([r for r in self.results if r["success"]])
                    print(f"📊 Progress: {i}/{len(self.test_urls)} kérés, {successful} sikeres ({elapsed:.1f}s)")
        
        end_time = time.time()
        total_time = end_time - start_time
        
        print(f"\n⏱️  Teszt befejezve! (összes idő: {total_time:.2f}s)")
        self.print_detailed_statistics()
    
    def print_detailed_statistics(self):
        """Részletes statisztikák kiírása"""
        successful_requests = [r for r in self.results if r["success"]]
        failed_requests = len(self.results) - len(successful_requests)
        total_requests = len(self.results) + len(self.errors)
        
        print(f"\n📈 RÉSZLETES TESZT EREDMÉNYEK - SZEKVENCIÁLIS")
        print(f"=" * 70)
        print(f"🎯 Target Instance: {self.target_instance}")
        print(f"📊 Összes kérés: {total_requests}")
        print(f"✅ Sikeres kérések: {len(successful_requests)}")
        print(f"❌ Sikertelen kérések: {failed_requests + len(self.errors)}")
        if total_requests > 0:
            print(f"📈 Sikeresség arány: {len(successful_requests)/total_requests*100:.1f}%")
        
        if successful_requests:
            response_times = [r["response_time"] for r in successful_requests]
            
            print(f"\n⏰ VÁLASZIDŐ STATISZTIKÁK")
            print(f"   🔹 Minimum: {min(response_times):.3f} másodperc")
            print(f"   🔹 Maximum: {max(response_times):.3f} másodperc")
            print(f"   🔹 Átlag: {statistics.mean(response_times):.3f} másodperc")
            print(f"   🔹 Medián: {statistics.median(response_times):.3f} másodperc")
            if len(response_times) > 1:
                print(f"   🔹 Szórás: {statistics.stdev(response_times):.3f} másodperc")
            
            # Server-side timing statisztikák ha elérhetők
            model_times = [r.get("server_model_inference", 0) for r in successful_requests if "server_model_inference" in r]
            gcs_times = [r.get("server_gcs_total", 0) for r in successful_requests if "server_gcs_total" in r]
            
            if model_times:
                print(f"\n🤖 SERVER-SIDE MODEL INFERENCE STATISZTIKÁK")
                print(f"   🔹 Minimum: {min(model_times):.3f} másodperc")
                print(f"   🔹 Maximum: {max(model_times):.3f} másodperc")
                print(f"   🔹 Átlag: {statistics.mean(model_times):.3f} másodperc")
                print(f"   🔹 Medián: {statistics.median(model_times):.3f} másodperc")
            
            if gcs_times:
                print(f"\n☁️  SERVER-SIDE GCS STATISZTIKÁK")
                print(f"   🔹 Minimum: {min(gcs_times):.3f} másodperc")
                print(f"   🔹 Maximum: {max(gcs_times):.3f} másodperc")
                print(f"   🔹 Átlag: {statistics.mean(gcs_times):.3f} másodperc")
                print(f"   🔹 Medián: {statistics.median(gcs_times):.3f} másodperc")
            
            # Teljesítmény trend elemzés
            if len(response_times) >= 10:
                print(f"\n📊 TELJESÍTMÉNY TREND ELEMZÉS")
                first_10 = response_times[:10]
                last_10 = response_times[-10:]
                middle_section = response_times[10:-10] if len(response_times) > 20 else []
                
                print(f"   🔹 Első 10 kérés átlag: {statistics.mean(first_10):.3f}s")
                if middle_section:
                    print(f"   🔹 Középső rész átlag: {statistics.mean(middle_section):.3f}s")
                print(f"   🔹 Utolsó 10 kérés átlag: {statistics.mean(last_10):.3f}s")
                
                # Trend kiértékelés
                first_avg = statistics.mean(first_10)
                last_avg = statistics.mean(last_10)
                
                if last_avg > first_avg * 1.1:
                    print(f"   ⚠️  Teljesítmény romlás észlelve (+{((last_avg/first_avg-1)*100):.1f}%)")
                elif last_avg < first_avg * 0.9:
                    print(f"   ✅ Teljesítmény javulás észlelve (-{((1-last_avg/first_avg)*100):.1f}%)")
                else:
                    print(f"   📊 Stabil teljesítmény (változás: {((last_avg/first_avg-1)*100):+.1f}%)")
            
            # Outlier elemzés
            print(f"\n🔍 OUTLIER ELEMZÉS")
            avg_time = statistics.mean(response_times)
            std_time = statistics.stdev(response_times) if len(response_times) > 1 else 0
            threshold = avg_time + 2 * std_time
            
            outliers = [(i+1, r) for i, r in enumerate(successful_requests) if r["response_time"] > threshold]
            
            if outliers:
                print(f"   ⚠️  {len(outliers)} outlier találva (>{threshold:.3f}s):")
                for req_num, outlier in outliers[:5]:  # Első 5 outlier
                    short_url = outlier["image_url"].split('/')[-1][:40]
                    print(f"      {req_num:2d}. {outlier['response_time']:6.3f}s - {short_url}")
                if len(outliers) > 5:
                    print(f"      ... és még {len(outliers) - 5} darab")
            else:
                print(f"   ✅ Nincs jelentős outlier (küszöb: {threshold:.3f}s)")
        
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
        
        # Összes kérés listája
        print(f"\n📋 ÖSSZES KÉRÉS RÉSZLETESEN")
        print(f"{'#':<3} {'Időbélyeg':<12} {'Válaszidő':<10} {'Model':<8} {'GCS':<6} {'Státusz':<7} {'Kép':<40}")
        print(f"{'-'*3} {'-'*12} {'-'*10} {'-'*8} {'-'*6} {'-'*7} {'-'*40}")
        
        for i, result in enumerate(self.results, 1):
            timestamp_str = result["timestamp"].strftime("%H:%M:%S")
            model_time = result.get("server_model_inference", 0)
            gcs_time = result.get("server_gcs_total", 0)
            status = "✅ 200" if result["success"] else f"❌ {result['status_code']}"
            short_url = result["image_url"].split('/')[-1][:35]
            
            print(f"{i:<3} {timestamp_str:<12} {result['response_time']:8.3f}s {model_time:6.3f}s {gcs_time:4.3f}s {status:<7} {short_url:<40}")
        
        # Hibás kérések
        for i, error in enumerate(self.errors, len(self.results) + 1):
            timestamp_str = error["timestamp"].strftime("%H:%M:%S")
            short_url = error["image_url"].split('/')[-1][:35]
            print(f"{i:<3} {timestamp_str:<12} {error['response_time']:8.3f}s {'N/A':>6} {'N/A':>4} ❌ ERR {short_url:<40}")

async def main():
    """Fő program belépési pont"""
    print("🔧 Sequential Single Instance Performance Test")
    print("=" * 60)
    
    # URL-ek betöltése
    if not os.path.exists(URL_LIST_FILE):
        print(f"❌ URL fájl nem található: {URL_LIST_FILE}")
        print("💡 Futtasd előbb az improved_dynamic_load_balancer.py-t hogy generálja a URL-eket")
        return
    
    image_urls = load_urls_from_file(URL_LIST_FILE)
    if not image_urls:
        print("❌ Nem sikerült URL-eket betölteni")
        return
    
    print(f"🎯 {len(image_urls)} pulover kép elérhető")
    
    # Teszter létrehozása és futtatása
    tester = SequentialTester(image_urls, TARGET_INSTANCE)
    await tester.run_sequential_test()

if __name__ == "__main__":
    asyncio.run(main())
