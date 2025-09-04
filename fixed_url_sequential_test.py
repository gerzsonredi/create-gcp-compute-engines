#!/usr/bin/env python3
"""
Fixed URL Sequential Test Script for Mannequin Segmenter API
Sends the same image URL repeatedly to test consistency and eliminate image-specific variance
"""

import asyncio
import aiohttp
import time
import statistics
from datetime import datetime
import json

# ========== KONFIGURÁCIÓS PARAMÉTEREK ==========
TARGET_INSTANCE = "http://34.140.252.94:5001"  # Tesztelendő VM instance
TOTAL_REQUESTS = 50                             # Összes kérések száma
REQUEST_TIMEOUT = 120                           # Timeout másodpercben
DELAY_BETWEEN_REQUESTS = 0.5                    # Kis szünet kérések között (másodperc)

# FIXED URL - mindig ugyanaz a kép
FIXED_IMAGE_URL = "https://storage.googleapis.com/public-images-redi/131727003.jpg"

# API endpoint
API_ENDPOINT = "/infer"

# ===============================================

class FixedUrlTester:
    def __init__(self, target_instance, image_url):
        self.target_instance = target_instance
        self.image_url = image_url
        self.results = []
        self.errors = []
        
        print(f"🎯 Fixed URL teszt: {TOTAL_REQUESTS} kérés ugyanazzal a képpel")
        print(f"🖼️  Teszt kép: {image_url}")
    
    async def make_single_request(self, session, request_id):
        """Egyetlen API kérés végrehajtása"""
        full_url = f"{self.target_instance}{API_ENDPOINT}"
        request_start = time.time()
        
        print(f"🔄 Request {request_id:2d}/50: Fixed URL teszt", end="", flush=True)
        
        try:
            payload = {
                "image_url": self.image_url,
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
                    "image_url": self.image_url,
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
                                result["server_image_conversion"] = timing.get("image_conversion", 0)
                                result["server_gcs_upload"] = timing.get("gcs_upload", 0)
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
                "image_url": self.image_url,
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
                "image_url": self.image_url,
                "error": str(e),
                "response_time": response_time,
                "timestamp": datetime.fromtimestamp(request_start)
            }
            self.errors.append(error)
            print(f" ❌ ERROR: {e}")
    
    async def run_sequential_test(self):
        """Szekvenciális teszt futtatása"""
        print(f"\n🚀 Fixed URL Sequential Test")
        print(f"📊 Konfiguráció:")
        print(f"   - Target instance: {self.target_instance}")
        print(f"   - Kérések száma: {TOTAL_REQUESTS}")
        print(f"   - Request timeout: {REQUEST_TIMEOUT}s")
        print(f"   - Kérések közötti szünet: {DELAY_BETWEEN_REQUESTS}s")
        print(f"   - Mód: SZEKVENCIÁLIS (egy kérés egyszerre)")
        print(f"   - Kép: MINDIG UGYANAZ (consistency teszt)")
        print()
        
        start_time = time.time()
        
        async with aiohttp.ClientSession() as session:
            for i in range(1, TOTAL_REQUESTS + 1):
                await self.make_single_request(session, i)
                
                # Kis szünet a következő kérés előtt (kivéve az utolsó után)
                if i < TOTAL_REQUESTS:
                    await asyncio.sleep(DELAY_BETWEEN_REQUESTS)
                
                # Progress minden 10. kérésnél
                if i % 10 == 0 or i == TOTAL_REQUESTS:
                    elapsed = time.time() - start_time
                    successful = len([r for r in self.results if r["success"]])
                    print(f"📊 Progress: {i}/{TOTAL_REQUESTS} kérés, {successful} sikeres ({elapsed:.1f}s)")
        
        end_time = time.time()
        total_time = end_time - start_time
        
        print(f"\n⏱️  Teszt befejezve! (összes idő: {total_time:.2f}s)")
        self.print_detailed_statistics()
    
    def print_detailed_statistics(self):
        """Részletes statisztikák kiírása"""
        successful_requests = [r for r in self.results if r["success"]]
        failed_requests = len(self.results) - len(successful_requests)
        total_requests = len(self.results) + len(self.errors)
        
        print(f"\n📈 FIXED URL TESZT EREDMÉNYEK - CONSISTENCY ELEMZÉS")
        print(f"=" * 80)
        print(f"🎯 Target Instance: {self.target_instance}")
        print(f"🖼️  Fixed Image URL: {self.image_url}")
        print(f"📊 Összes kérés: {total_requests}")
        print(f"✅ Sikeres kérések: {len(successful_requests)}")
        print(f"❌ Sikertelen kérések: {failed_requests + len(self.errors)}")
        if total_requests > 0:
            print(f"📈 Sikeresség arány: {len(successful_requests)/total_requests*100:.1f}%")
        
        if successful_requests:
            response_times = [r["response_time"] for r in successful_requests]
            
            print(f"\n⏰ VÁLASZIDŐ STATISZTIKÁK (ugyanaz a kép {len(successful_requests)}x)")
            print(f"   🔹 Minimum: {min(response_times):.3f} másodperc")
            print(f"   🔹 Maximum: {max(response_times):.3f} másodperc")
            print(f"   🔹 Átlag: {statistics.mean(response_times):.3f} másodperc")
            print(f"   🔹 Medián: {statistics.median(response_times):.3f} másodperc")
            if len(response_times) > 1:
                print(f"   🔹 Szórás: {statistics.stdev(response_times):.3f} másodperc")
                variability = (statistics.stdev(response_times) / statistics.mean(response_times)) * 100
                print(f"   🔹 Variabilitás: {variability:.1f}% (CV)")
            
            # Server-side timing statisztikák ha elérhetők
            model_times = [r.get("server_model_inference", 0) for r in successful_requests if "server_model_inference" in r]
            gcs_times = [r.get("server_gcs_total", 0) for r in successful_requests if "server_gcs_total" in r]
            image_conv_times = [r.get("server_image_conversion", 0) for r in successful_requests if "server_image_conversion" in r]
            gcs_upload_times = [r.get("server_gcs_upload", 0) for r in successful_requests if "server_gcs_upload" in r]
            
            if model_times:
                print(f"\n🤖 SERVER-SIDE MODEL INFERENCE STATISZTIKÁK")
                print(f"   🔹 Minimum: {min(model_times):.3f} másodperc")
                print(f"   🔹 Maximum: {max(model_times):.3f} másodperc")
                print(f"   🔹 Átlag: {statistics.mean(model_times):.3f} másodperc")
                print(f"   🔹 Medián: {statistics.median(model_times):.3f} másodperc")
                if len(model_times) > 1:
                    model_var = (statistics.stdev(model_times) / statistics.mean(model_times)) * 100
                    print(f"   🔹 Variabilitás: {model_var:.1f}% (CV)")
            
            if gcs_times:
                print(f"\n☁️  SERVER-SIDE GCS STATISZTIKÁK")
                print(f"   🔹 Minimum: {min(gcs_times):.3f} másodperc")
                print(f"   🔹 Maximum: {max(gcs_times):.3f} másodperc")
                print(f"   🔹 Átlag: {statistics.mean(gcs_times):.3f} másodperc")
                print(f"   🔹 Medián: {statistics.median(gcs_times):.3f} másodperc")
            
            if image_conv_times:
                print(f"\n🖼️  IMAGE CONVERSION STATISZTIKÁK")
                print(f"   🔹 Minimum: {min(image_conv_times):.3f} másodperc")
                print(f"   🔹 Maximum: {max(image_conv_times):.3f} másodperc")
                print(f"   🔹 Átlag: {statistics.mean(image_conv_times):.3f} másodperc")
                
            if gcs_upload_times:
                print(f"\n📤 GCS UPLOAD STATISZTIKÁK")
                print(f"   🔹 Minimum: {min(gcs_upload_times):.3f} másodperc")
                print(f"   🔹 Maximum: {max(gcs_upload_times):.3f} másodperc")
                print(f"   🔹 Átlag: {statistics.mean(gcs_upload_times):.3f} másodperc")
            
            # Consistency elemzés - bemelegedési hatás
            if len(response_times) >= 10:
                print(f"\n🔥 BEMELEGEDÉSI HATÁS ELEMZÉS")
                first_5 = response_times[:5]
                first_10 = response_times[:10]
                last_10 = response_times[-10:]
                middle_section = response_times[10:-10] if len(response_times) > 20 else response_times[5:-5]
                
                print(f"   🔹 Első 5 kérés átlag: {statistics.mean(first_5):.3f}s")
                print(f"   🔹 Első 10 kérés átlag: {statistics.mean(first_10):.3f}s")
                if middle_section:
                    print(f"   🔹 Középső rész átlag: {statistics.mean(middle_section):.3f}s")
                print(f"   🔹 Utolsó 10 kérés átlag: {statistics.mean(last_10):.3f}s")
                
                # Trend kiértékelés
                first_avg = statistics.mean(first_5)
                stable_avg = statistics.mean(last_10)
                
                if stable_avg < first_avg * 0.8:
                    improvement = ((first_avg - stable_avg) / first_avg) * 100
                    print(f"   ✅ Jelentős bemelegedési hatás: -{improvement:.1f}% javulás")
                elif abs(stable_avg - first_avg) / first_avg < 0.1:
                    print(f"   📊 Stabil teljesítmény kezdettől")
                else:
                    print(f"   ⚠️  Változó teljesítmény")
            
            # Outlier elemzés
            print(f"\n🔍 OUTLIER ELEMZÉS (ugyanaz a kép!)")
            avg_time = statistics.mean(response_times)
            std_time = statistics.stdev(response_times) if len(response_times) > 1 else 0
            threshold = avg_time + 2 * std_time
            
            outliers = [(i+1, r) for i, r in enumerate(successful_requests) if r["response_time"] > threshold]
            
            if outliers:
                print(f"   ⚠️  {len(outliers)} outlier találva (>{threshold:.3f}s) UGYANAZZAL a képpel:")
                for req_num, outlier in outliers:
                    model_time = outlier.get("server_model_inference", 0)
                    print(f"      Request {req_num:2d}: {outlier['response_time']:6.3f}s (model: {model_time:.3f}s)")
                print(f"   💡 Ez azt jelenti, hogy NEM a kép komplexitása okozza a lassulást!")
            else:
                print(f"   ✅ Nincs outlier - konzisztens teljesítmény")
                print(f"   💡 A fixed URL teszt bizonyítja, hogy a service stabil")
        
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
        
        # Minden kérés részletesen (kompakt formátum)
        print(f"\n📋 ÖSSZES KÉRÉS IDŐZÍTÉSE (Fixed URL)")
        print(f"{'#':<3} {'Időbélyeg':<12} {'Válaszidő':<10} {'Model':<8} {'GCS':<6} {'Státusz'}")
        print(f"{'-'*3} {'-'*12} {'-'*10} {'-'*8} {'-'*6} {'-'*7}")
        
        for i, result in enumerate(self.results, 1):
            timestamp_str = result["timestamp"].strftime("%H:%M:%S")
            model_time = result.get("server_model_inference", 0)
            gcs_time = result.get("server_gcs_total", 0)
            status = "✅ 200" if result["success"] else f"❌ {result['status_code']}"
            
            print(f"{i:<3} {timestamp_str:<12} {result['response_time']:8.3f}s {model_time:6.3f}s {gcs_time:4.3f}s {status}")
        
        # Hibás kérések
        for i, error in enumerate(self.errors, len(self.results) + 1):
            timestamp_str = error["timestamp"].strftime("%H:%M:%S")
            print(f"{i:<3} {timestamp_str:<12} {error['response_time']:8.3f}s {'N/A':>6} {'N/A':>4} ❌ ERR")

async def main():
    """Fő program belépési pont"""
    print("🔧 Fixed URL Sequential Performance Test")
    print("=" * 60)
    print("🎯 Ez a teszt ugyanazt a képet küldi el többször")
    print("💡 Célja: kép-specifikus variabilitás kizárása")
    print()
    
    # Teszter létrehozása és futtatása
    tester = FixedUrlTester(TARGET_INSTANCE, FIXED_IMAGE_URL)
    await tester.run_sequential_test()

if __name__ == "__main__":
    asyncio.run(main())
