#!/usr/bin/env python3
"""
MTN API Inspector - Debug tool to understand API requirements
"""

import requests
import json

def test_api_call(url, method='GET', data=None, headers=None):
    """Test an API call and show detailed response"""
    print(f"\n{'='*60}")
    print(f"Testing: {method} {url}")
    print(f"Data: {data}")
    print(f"{'='*60}\n")
    
    session = requests.Session()
    
    # Default headers
    default_headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Accept': 'application/json, text/javascript, */*; q=0.01',
        'Accept-Language': 'en-US,en;q=0.9',
        'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
        'X-Requested-With': 'XMLHttpRequest',  # Important for AJAX requests
        'Origin': 'https://apps.mtn.ng',
        'Referer': 'https://apps.mtn.ng/fibre/'
    }
    
    if headers:
        default_headers.update(headers)
    
    try:
        if method.upper() == 'POST':
            response = session.post(url, data=data, headers=default_headers, timeout=10)
        else:
            response = session.get(url, params=data, headers=default_headers, timeout=10)
        
        print(f"Status Code: {response.status_code}")
        print(f"Headers: {dict(response.headers)}\n")
        print(f"Response Text (first 500 chars):")
        print(response.text[:500])
        print("\n")
        
        # Try to parse as JSON
        try:
            json_data = response.json()
            print("JSON Response:")
            print(json.dumps(json_data, indent=2))
            return json_data
        except:
            print("Response is not valid JSON")
            return None
            
    except Exception as e:
        print(f"Error: {e}")
        return None


def main():
    print("MTN API INSPECTOR")
    print("="*60)
    
    base_url = "https://apps.mtn.ng/fibre/home"
    
    # Test 1: Get state areas with known state_id from your example
    print("\n\n### TEST 1: Get areas for State ID 25 (Kwara from your example)")
    test_api_call(
        f"{base_url}/getstateareas",
        method='POST',
        data={'state_id': '25'}
    )
    
    # Test 2: Get streets for known area_id from your example
    print("\n\n### TEST 2: Get streets for Area ID 57 (G.R.A Ilorin from your example)")
    test_api_call(
        f"{base_url}/getareastreet",
        method='POST',
        data={'area_id': '57'}
    )
    
    # Test 3: Try different state IDs
    print("\n\n### TEST 3: Try state_id = 1 (likely Lagos)")
    test_api_call(
        f"{base_url}/getstateareas",
        method='POST',
        data={'state_id': '1'}
    )
    
    # Test 4: Try with GET instead of POST
    print("\n\n### TEST 4: Try GET request instead of POST")
    test_api_call(
        f"{base_url}/getstateareas",
        method='GET',
        data={'state_id': '25'}
    )
    
    # Test 5: Check if there's a states endpoint
    print("\n\n### TEST 5: Check for states list endpoint")
    test_api_call(
        f"{base_url}/getstates",
        method='POST'
    )
    
    print("\n\n" + "="*60)
    print("INSPECTION COMPLETE")
    print("="*60)


if __name__ == "__main__":
    main()