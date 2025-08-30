#!/usr/bin/env python3
"""
Quick test to verify your hardcoded GitHub token works
"""

import requests

# ⚠️ REPLACE THIS WITH YOUR ACTUAL GITHUB TOKEN ⚠️
GITHUB_TOKEN = "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"

def test_token():
    """Test if the GitHub token is valid"""
    
    print("🔑 Testing GitHub token...")
    
    if GITHUB_TOKEN == "YOUR_ACTUAL_TOKEN_HERE":
        print("❌ Error: You need to replace 'YOUR_ACTUAL_TOKEN_HERE' with your actual GitHub token!")
        print("\nTo get a token:")
        print("1. Go to https://github.com/settings/tokens")
        print("2. Click 'Generate new token' → 'Generate new token (classic)'")
        print("3. Give it a name (e.g., 'Lead Intelligence')")
        print("4. Select scopes: 'repo' and 'user:email'")
        print("5. Generate the token and copy it")
        print("6. Replace 'YOUR_ACTUAL_TOKEN_HERE' in this file with your token")
        return False
    
    # Test the token
    headers = {
        'Authorization': f'token {GITHUB_TOKEN}',
        'Accept': 'application/vnd.github.v3+json'
    }
    
    try:
        response = requests.get('https://api.github.com/user', headers=headers)
        
        if response.status_code == 200:
            user_data = response.json()
            print(f"✅ Token is valid! Authenticated as: {user_data.get('login', 'unknown')}")
            print(f"📧 Email: {user_data.get('email', 'not set')}")
            print(f"👤 Name: {user_data.get('name', 'not set')}")
            
            # Check rate limits
            rate_limit = requests.get('https://api.github.com/rate_limit', headers=headers).json()
            core_limit = rate_limit.get('rate', {})
            print(f"\n📊 API Rate Limits:")
            print(f"   Limit: {core_limit.get('limit', 0)}/hour")
            print(f"   Remaining: {core_limit.get('remaining', 0)}")
            
            return True
        elif response.status_code == 401:
            print(f"❌ Token is invalid! Status: {response.status_code}")
            print(f"Response: {response.text}")
            return False
        else:
            print(f"⚠️ Unexpected response: {response.status_code}")
            print(f"Response: {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ Error testing token: {e}")
        return False

if __name__ == "__main__":
    import sys
    success = test_token()
    sys.exit(0 if success else 1)
