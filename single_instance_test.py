#!/usr/bin/env python3
"""
Single Instance Performance Test for Mannequin Segmenter API
Tests one specific VM instance with sequential requests to analyze performance consistency
"""

import asyncio
import aiohttp
import time
import statistics
from datetime import datetime
import json

# ========== KONFIGURÁCIÓS PARAMÉTEREK ==========
TARGET_INSTANCE = "http://35.233.66.133:5001"  # Tesztelendő VM instance
NUMBER_OF_REQUESTS = 1000                        # Kérések száma
REQUEST_TIMEOUT = 60                           # Timeout másodpercben
DELAY_BETWEEN_REQUESTS = 0.5                   # Késleltetés kérések között másodpercben

# API endpoint és payload
API_ENDPOINT = "/infer"
TEST_PAYLOAD = {
    "image_url": "https://media.remix.eu/files/16-2025/Roklya-C-A-131676053b.jpg",
    "prompt_mode": "both"
}

# ===============================================

class SingleInstanceTest:
    def __init__(self):
        self.results = []
        self.errors = []
        
    async def make_request(self, session, request_id):
        """Egyetlen API kérés végrehajtása"""
        full_url = f"{TARGET_INSTANCE}{API_ENDPOINT}"
        request_start = time.time()
        
        print(f"🔄 Request {request_id}: Küldés... ", end="", flush=True)
        
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
                    except json.JSONDecodeError:
                        result["has_visualization_url"] = False
                
                self.results.append(result)
                print(f"✅ {response.status} ({response_time:.3f}s)")
                
        except asyncio.TimeoutError:
            request_end = time.time()
            response_time = request_end - request_start
            error = {
                "request_id": request_id,
                "error": "Timeout",
                "response_time": response_time,
                "timestamp": datetime.fromtimestamp(request_start)
            }
            self.errors.append(error)
            print(f"⏰ TIMEOUT ({response_time:.3f}s)")
            
        except Exception as e:
            request_end = time.time()
            response_time = request_end - request_start
            error = {
                "request_id": request_id,
                "error": str(e),
                "response_time": response_time,
                "timestamp": datetime.fromtimestamp(request_start)
            }
            self.errors.append(error)
            print(f"❌ ERROR: {e}")
    
    async def run_test(self):
        """Fő teszt futtatás"""
        print(f"🎯 Single Instance Teljesítmény Teszt")
        print(f"📊 Konfiguráció:")
        print(f"   - Target instance: {TARGET_INSTANCE}")
        print(f"   - Kérések száma: {NUMBER_OF_REQUESTS}")
        print(f"   - Kérések közötti késleltetés: {DELAY_BETWEEN_REQUESTS}s")
        print(f"   - Request timeout: {REQUEST_TIMEOUT}s")
        print(f"   - Teszt kép: {TEST_PAYLOAD['image_url']}")
        print()
        
        start_time = time.time()
        
        async with aiohttp.ClientSession() as session:
            for i in range(NUMBER_OF_REQUESTS):
                await self.make_request(session, i + 1)
                
                # Várunk a következő kérés előtt (kivéve az utolsó után)
                if i < NUMBER_OF_REQUESTS - 1:
                    await asyncio.sleep(DELAY_BETWEEN_REQUESTS)
        
        end_time = time.time()
        total_test_time = end_time - start_time
        
        print(f"\n⏱️  Teszt befejezve! (összes idő: {total_test_time:.2f}s)")
        self.print_statistics()
    
    def print_statistics(self):
        """Statisztikák kiírása"""
        successful_requests = [r for r in self.results if r["success"]]
        failed_requests = len(self.results) - len(successful_requests)
        total_requests = len(self.results) + len(self.errors)
        
        print(f"\n📈 TESZT EREDMÉNYEK")
        print(f"=" * 60)
        print(f"🎯 Target Instance: {TARGET_INSTANCE}")
        print(f"📊 Összes kérés: {total_requests}")
        print(f"✅ Sikeres kérések: {len(successful_requests)}")
        print(f"❌ Sikertelen kérések: {failed_requests + len(self.errors)}")
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
            
            # Részletes kérés lista
            print(f"\n📋 RÉSZLETES KÉRÉS LISTA")
            print(f"{'ID':<4} {'Időbélyeg':<20} {'Válaszidő':<12} {'Státusz':<8} {'Méret':<8}")
            print(f"{'-'*4} {'-'*20} {'-'*12} {'-'*8} {'-'*8}")
            
            for result in successful_requests:
                timestamp_str = result["timestamp"].strftime("%H:%M:%S.%f")[:-3]
                print(f"{result['request_id']:<4} {timestamp_str:<20} {result['response_time']:.3f}s{'':<5} {result['status_code']:<8} {result['response_size']:<8}")
            
            # Teljesítmény trend elemzés
            if len(response_times) >= 3:
                print(f"\n📊 TELJESÍTMÉNY TREND ELEMZÉS")
                first_third = response_times[:len(response_times)//3]
                last_third = response_times[-len(response_times)//3:]
                
                if first_third and last_third:
                    first_avg = statistics.mean(first_third)
                    last_avg = statistics.mean(last_third)
                    
                    print(f"   🔹 Első harmad átlag: {first_avg:.3f}s")
                    print(f"   🔹 Utolsó harmad átlag: {last_avg:.3f}s")
                    
                    if last_avg > first_avg * 1.1:
                        print(f"   ⚠️  Teljesítmény romlás észlelve (+{((last_avg/first_avg-1)*100):.1f}%)")
                    elif last_avg < first_avg * 0.9:
                        print(f"   ✅ Teljesítmény javulás észlelve (-{((1-last_avg/first_avg)*100):.1f}%)")
                    else:
                        print(f"   📊 Stabil teljesítmény")
            
            # Server-side timing információ ha elérhető
            server_timings = [r.get("server_timing") for r in successful_requests if r.get("server_timing")]
            if server_timings:
                print(f"\n🖥️  SERVER-SIDE TIMING STATISZTIKÁK")
                
                timing_keys = set()
                for timing in server_timings:
                    timing_keys.update(timing.keys())
                
                for key in sorted(timing_keys):
                    values = [t[key] for t in server_timings if key in t]
                    if values:
                        print(f"   🔹 {key}: min={min(values):.3f}s, max={max(values):.3f}s, avg={statistics.mean(values):.3f}s")
        
        # Hibák részletezése
        if self.errors:
            print(f"\n❌ HIBÁK RÉSZLETEZÉSE")
            for i, error in enumerate(self.errors, 1):
                print(f"   {i}. {error['timestamp'].strftime('%H:%M:%S')} - {error['error']}")

async def main():
    """Fő program belépési pont"""
    tester = SingleInstanceTest()
    await tester.run_test()

if __name__ == "__main__":
    print("🔧 Mannequin Segmenter Single Instance Performance Test")
    print("=" * 60)
    asyncio.run(main())
