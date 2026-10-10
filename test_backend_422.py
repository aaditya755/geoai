#!/usr/bin/env python3
"""
Test backend to identify 422 error cause
"""

import requests
import json

def test_chat_endpoint():
    """Test various chat requests to identify 422 error"""
    
    base_url = "http://localhost:8000"
    
    test_cases = [
        {
            "name": "Simple query",
            "payload": {"query": "buildings within 200m of parks"}
        },
        {
            "name": "With language",
            "payload": {"query": "buildings within 200m of parks", "lang": "en"}
        },
        {
            "name": "Empty query",
            "payload": {"query": ""}
        },
        {
            "name": "Complex query",
            "payload": {"query": "find all swimming pools within 100 meters of main roads"}
        },
        {
            "name": "Session ID",
            "payload": {"query": "roads near buildings", "session_id": "test-session"}
        }
    ]
    
    print("=== Testing Chat Endpoint ===\n")
    
    for test_case in test_cases:
        print(f"🔄 Testing: {test_case['name']}")
        
        try:
            resp = requests.post(
                f"{base_url}/chat",
                json=test_case["payload"],
                timeout=30
            )
            
            print(f"  Status: {resp.status_code}")
            
            if resp.status_code == 200:
                data = resp.json()
                print(f"  ✅ Success")
                print(f"    Results: {len(data.get('results', []))}")
                print(f"    Target: {data.get('plan', {}).get('target', {}).get('concept', 'unknown')}")
                
            elif resp.status_code == 422:
                print(f"  ❌ 422 Unprocessable Content")
                try:
                    error_data = resp.json()
                    print(f"    Error: {error_data}")
                except:
                    print(f"    Raw response: {resp.text[:200]}")
                    
            else:
                print(f"  ⚠️  Status {resp.status_code}")
                print(f"    Response: {resp.text[:200]}")
                
        except Exception as e:
            print(f"  ❌ Request failed: {e}")
            
        print()

def test_health():
    """Test health endpoint"""
    print("=== Testing Health Endpoint ===")
    
    try:
        resp = requests.get("http://localhost:8000/health", timeout=10)
        resp.raise_for_status()
        data = resp.json()
        
        print("✅ Health endpoint OK")
        print(f"  Demo mode: {data.get('demo_mode', 'unknown')}")
        print(f"  OSM layers: {len(data.get('osm_layers_loaded', []))}")
        print(f"  Planner: {data.get('planner', {}).get('provider', 'unknown')}")
        print(f"  Model: {data.get('planner', {}).get('model', 'unknown')}")
        
        return True
        
    except Exception as e:
        print(f"❌ Health endpoint failed: {e}")
        return False

if __name__ == "__main__":
    health_ok = test_health()
    if health_ok:
        test_chat_endpoint()
    else:
        print("Backend not responding - check if server is running")