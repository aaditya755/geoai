#!/usr/bin/env python3
"""
Check status of all API services and their configuration
"""

import os
from dotenv import load_dotenv
load_dotenv()

def check_service_status():
    services = {
        'OpenRouter (LLM Planning)': {
            'api_key': os.environ.get('OPENROUTER_API_KEY'),
            'model': os.environ.get('OPENROUTER_MODEL'),
            'purpose': 'Natural language to spatial query planning',
            'docs': 'https://openrouter.ai/settings/keys'
        },
        'Sarvam AI (Translation)': {
            'api_key': os.environ.get('SARVAM_API_KEY'),
            'purpose': 'Multi-language support',
            'docs': 'https://dashboard.sarvam.ai/'
        },
        'Jev AI (Ranking)': {
            'api_key': os.environ.get('JEV_API_KEY'),
            'enabled_flag': os.environ.get('JEV_ENABLED', 'false').lower() == 'true',
            'endpoint': os.environ.get('JEV_API_ENDPOINT'),
            'purpose': 'Advanced result ranking',
            'docs': 'https://jev-ai.org/docs/'
        }
    }

    print("=== GeoLens AI Service Configuration Status ===\n")
    
    for name, info in services.items():
        has_key = bool(info['api_key'])
        is_enabled = info.get('enabled_flag', has_key)
        
        if has_key and is_enabled:
            status = "✅ CONFIGURED & ENABLED"
        elif has_key and not is_enabled:
            status = "⚠️  CONFIGURED BUT DISABLED"
        else:
            status = "❌ NOT CONFIGURED"
            
        print(f"{status} - {name}")
        print(f"   Purpose: {info['purpose']}")
        
        if has_key:
            key_preview = info['api_key'][:15] + "..." if len(info['api_key']) > 15 else info['api_key']
            print(f"   API Key: {key_preview}")
        else:
            print(f"   API Key: None")
            print(f"   Get API Key: {info['docs']}")
            
        if 'model' in info and info['model']:
            print(f"   Model: {info['model']}")
            
        if 'endpoint' in info and info['endpoint']:
            print(f"   Endpoint: {info['endpoint']}")
            
        if 'enabled_flag' in info:
            print(f"   Enabled Flag: {info['enabled_flag']}")
            
        print()

    # Check additional components
    print("=== Additional Components ===\n")
    
    demo_mode = os.environ.get('DEMO_MODE', 'false').lower() == 'true'
    print(f"{'✅' if demo_mode else '❌'} Demo Mode: {demo_mode}")
    
    skyclip_weights = os.environ.get('SKYCLIP_WEIGHTS')
    print(f"{'✅' if skyclip_weights else '❌'} SkyCLIP Weights: {skyclip_weights or 'Not set'}")
    
    feature_negate = os.environ.get('FEATURE_NEGATE', 'false').lower() == 'true'
    print(f"{'⚠️' if feature_negate else '❌'} Feature Negate: {feature_negate} (Proposed)")
    
    feature_min_area = os.environ.get('FEATURE_MIN_AREA', 'false').lower() == 'true'
    print(f"{'⚠️' if feature_min_area else '❌'} Feature Min Area: {feature_min_area} (Proposed)")
    
    print()
    print("=== Summary ===")
    print("To enable missing services, add API keys to the .env file:")
    print("1. OpenRouter: For real LLM query processing (currently working)")
    print("2. Sarvam AI: For multi-language support (optional)")  
    print("3. Jev AI: For advanced ranking (optional, disabled by default)")

if __name__ == "__main__":
    check_service_status()