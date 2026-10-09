#!/usr/bin/env python3
"""
Test backend endpoints functionality
"""

import requests
import json

BASE_URL = "http://localhost:8000"

def test_health():
    """Test /health endpoint"""
    print("=== Testing /health endpoint ===")
    try:
        resp = requests.get(f"{BASE_URL}/health", timeout=10)
        resp.raise_for_status()
        data = resp.json()
        
        print("✅ Health endpoint responding")
        print(f"  Demo mode: {data.get('demo_mode', 'unknown')}")
        print(f"  Planner provider: {data.get('planner', {}).get('provider', 'unknown')}")
        print(f"  API key configured: {data.get('planner', {}).get('api_key_configured', False)}")
        print(f"  Model: {data.get('planner', {}).get('model', 'unknown')}")
        
        return True
    except Exception as e:
        print(f"❌ Health endpoint failed: {e}")
        return False

def test_chat():
    """Test /chat endpoint"""
    print("\n=== Testing /chat endpoint ===")
    try:
        payload = {
            "query": "airports near water",
            "lang": "en"
        }
        
        resp = requests.post(f"{BASE_URL}/chat", json=payload, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        
        print("✅ Chat endpoint responding")
        print(f"  Session ID: {data.get('session_id', 'missing')[:8]}...")
        print(f"  Results: {len(data.get('results', []))}")
        print(f"  Target concept: {data.get('plan', {}).get('target', {}).get('concept', 'unknown')}")
        print(f"  Sample data: {data.get('_sample_data', False)}")
        
        # Validate schema
        required_fields = ['session_id', 'plan', 'results', 'candidates', 'session_history']
        missing = [f for f in required_fields if f not in data]
        if missing:
            print(f"⚠️  Missing fields: {missing}")
        else:
            print("✅ Response schema valid")
        
        return True
    except Exception as e:
        print(f"❌ Chat endpoint failed: {e}")
        return False

def test_attribution():
    """Test /attribution endpoint"""
    print("\n=== Testing /attribution endpoint ===")
    try:
        resp = requests.get(f"{BASE_URL}/attribution", timeout=10)
        resp.raise_for_status()
        data = resp.json()
        
        print("✅ Attribution endpoint responding")
        if isinstance(data, dict) and 'datasets' in data:
            datasets = data['datasets']
            print(f"  Dataset count: {len(datasets)}")
            if datasets:
                first = datasets[0]
                print(f"  First dataset: {first.get('name', 'unnamed')}")
        else:
            print(f"  Unexpected response format: {type(data)}")
        
        return True
    except Exception as e:
        print(f"❌ Attribution endpoint failed: {e}")
        return False

def test_export():
    """Test /export endpoint"""
    print("\n=== Testing /export endpoint ===") 
    try:
        # First get a session with results
        chat_payload = {"query": "swimming pools near roads"}
        chat_resp = requests.post(f"{BASE_URL}/chat", json=chat_payload, timeout=30)
        chat_resp.raise_for_status()
        chat_data = chat_resp.json()
        results = chat_data.get('results', [])
        
        if not results:
            print("❌ No results from chat to export")
            return False
        
        # Test export with POST method
        export_payload = {"results": results}
        resp = requests.post(f"{BASE_URL}/export", json=export_payload, timeout=10)
        resp.raise_for_status()
        
        print("✅ Export endpoint responding")
        print(f"  Content-Type: {resp.headers.get('content-type', 'unknown')}")
        print(f"  Content length: {len(resp.content)} bytes")
        
        # Try to parse as GeoJSON
        try:
            geojson = resp.json()
            if geojson.get('type') == 'FeatureCollection':
                features = geojson.get('features', [])
                print(f"✅ Valid GeoJSON with {len(features)} features")
                return True
            else:
                print("⚠️  Not a GeoJSON FeatureCollection")
                return False
        except json.JSONDecodeError:
            print("❌ Response not valid JSON")
            return False
            
    except Exception as e:
        print(f"❌ Export endpoint failed: {e}")
        return False

if __name__ == "__main__":
    results = {
        'health': test_health(),
        'chat': test_chat(), 
        'attribution': test_attribution(),
        'export': test_export()
    }
    
    print(f"\n=== Backend Endpoint Summary ===")
    for endpoint, status in results.items():
        status_icon = "✅" if status else "❌"
        print(f"{status_icon} /{endpoint}")
    
    all_working = all(results.values())
    print(f"\nBackend status: {'✅ OPERATIONAL' if all_working else '❌ ISSUES FOUND'}")