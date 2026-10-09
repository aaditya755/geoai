#!/usr/bin/env python3
"""
Test actual service functionality - no secrets exposed
"""

import os
from dotenv import load_dotenv
load_dotenv()

def test_openrouter():
    """Test OpenRouter API with real request"""
    print("=== OpenRouter API Test ===")
    
    api_key = os.environ.get('OPENROUTER_API_KEY')
    if not api_key:
        print("❌ No API key configured")
        return False
        
    print("✅ API key present")
    
    try:
        # Use the planner agent interface
        from planner_agent import plan as planner_plan
        
        # Test with simple query
        test_query = "buildings within 100 meters of roads"
        print(f"🔄 Testing query: {test_query}")
        
        result_plan, session_id = planner_plan(test_query)
        print("✅ API request succeeded")
        print(f"  Target concept: {result_plan.target.concept}")
        print(f"  Relations: {len(result_plan.relations)}")
        print(f"  Session ID: {session_id}")
        
        return True
        
    except Exception as e:
        print(f"❌ API test failed: {e}")
        return False

def test_sarvam_ai():
    """Test Sarvam AI translation"""
    print("\n=== Sarvam AI Translation Test ===")
    
    api_key = os.environ.get('SARVAM_API_KEY')
    if not api_key:
        print("❌ No API key configured")
        return False
        
    print("✅ API key present")
    
    try:
        from translate import translate
        
        # Test Hindi to English
        test_text = "नमस्ते"
        result = translate(test_text, from_lang="hi", to_lang="en")
        
        if result == test_text:
            print("⚠️  Passthrough fallback active (endpoint not verified)")
            return False
        else:
            print(f"✅ Translation succeeded: {test_text} -> {result}")
            return True
            
    except Exception as e:
        print(f"❌ Translation test failed: {e}")
        return False

def test_jev_ai():
    """Check Jev AI configuration (disabled by design)"""
    print("\n=== Jev AI Status ===")
    
    api_key = os.environ.get('JEV_API_KEY')
    enabled = os.environ.get('JEV_ENABLED', 'false').lower() == 'true'
    
    if not api_key:
        print("❌ No API key configured")
        return False
        
    print("✅ API key present")
    
    if not enabled:
        print("⚠️  Deliberately disabled (JEV_ENABLED=false)")
        print("   This is correct until endpoint verification")
        return True
    else:
        print("❌ Enabled but endpoint not verified - should be disabled")
        return False

def test_skyclip():
    """Test SkyCLIP model loading and basic inference"""
    print("\n=== SkyCLIP Model Test ===")
    
    weights_path = os.environ.get('SKYCLIP_WEIGHTS')
    if weights_path:
        print(f"✅ Weights path configured: {weights_path}")
    else:
        print("⚠️  No weights path - will try auto-download")
    
    try:
        from skyclip_loader import load_skyclip, get_device, embed_text
        
        print("🔄 Loading SkyCLIP model...")
        model, preprocess, tokenizer = load_skyclip()
        device = get_device()
        
        print(f"✅ Model loaded on {device}")
        
        # Test text embedding with correct signature
        test_embedding = embed_text(model, tokenizer, "swimming pool", device)
        
        if test_embedding is not None and len(test_embedding) > 0:
            print(f"✅ Text embedding generated (dim: {len(test_embedding)})")
            return True
        else:
            print("❌ Text embedding failed")
            return False
            
    except Exception as e:
        print(f"❌ SkyCLIP test failed: {e}")
        return False

if __name__ == "__main__":
    results = {}
    results['openrouter'] = test_openrouter()
    results['sarvam'] = test_sarvam_ai()
    results['jev'] = test_jev_ai()
    results['skyclip'] = test_skyclip()
    
    print(f"\n=== Service Test Summary ===")
    for service, status in results.items():
        status_icon = "✅" if status else "❌"
        print(f"{status_icon} {service.upper()}")
    
    all_critical_working = results['openrouter'] and results['skyclip']
    print(f"\nCritical services: {'✅ OPERATIONAL' if all_critical_working else '❌ ISSUES FOUND'}")