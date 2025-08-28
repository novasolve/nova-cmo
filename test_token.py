#!/usr/bin/env python3
"""Test GitHub token and show what data we can access"""

import os
import requests
import json

def test_github_token():
    token = os.environ.get('GITHUB_TOKEN')
    if not token:
        print("❌ GITHUB_TOKEN not set")
        return
    
    print(f"🔑 Token: {token[:10]}...{token[-4:]}")
    print(f"📏 Token length: {len(token)}")
    
    headers = {
        'Authorization': f'token {token}',
        'Accept': 'application/vnd.github.v3+json'
    }
    
    # Test 1: Basic auth check
    print("\n1️⃣ Testing basic authentication...")
    response = requests.get('https://api.github.com/user', headers=headers)
    print(f"   Status: {response.status_code}")
    if response.status_code == 200:
        user = response.json()
        print(f"   ✅ Authenticated as: {user.get('login')}")
        print(f"   Name: {user.get('name')}")
        print(f"   Email: {user.get('email')}")
    else:
        print(f"   ❌ Error: {response.json().get('message', 'Unknown error')}")
        return
    
    # Test 2: Search repositories
    print("\n2️⃣ Testing repository search...")
    search_query = "language:python stars:>1000 topic:ai"
    response = requests.get(
        'https://api.github.com/search/repositories',
        params={'q': search_query, 'per_page': 1},
        headers=headers
    )
    print(f"   Status: {response.status_code}")
    if response.status_code == 200:
        data = response.json()
        print(f"   ✅ Found {data['total_count']} repositories")
        if data['items']:
            repo = data['items'][0]
            print(f"   Example: {repo['full_name']} ({repo['stargazers_count']} stars)")
    else:
        print(f"   ❌ Error: {response.json().get('message', 'Unknown error')}")
    
    # Test 3: Rate limit check
    print("\n3️⃣ Checking rate limits...")
    response = requests.get('https://api.github.com/rate_limit', headers=headers)
    if response.status_code == 200:
        limits = response.json()
        core = limits['rate']['limit']
        remaining = limits['rate']['remaining']
        search = limits['resources']['search']['remaining']
        print(f"   ✅ Core API: {remaining}/{core} requests remaining")
        print(f"   ✅ Search API: {search}/30 requests remaining")
    
    # Test 4: Sample user with all fields
    print("\n4️⃣ Testing user data retrieval (torvalds)...")
    response = requests.get('https://api.github.com/users/torvalds', headers=headers)
    if response.status_code == 200:
        user = response.json()
        print("   ✅ Available fields:")
        print(f"   - Email: {user.get('email', 'Not public')}")
        print(f"   - Company: {user.get('company', 'None')}")
        print(f"   - Location: {user.get('location', 'None')}")
        print(f"   - Bio: {user.get('bio', 'None')[:50]}...")
        print(f"   - Blog: {user.get('blog', 'None')}")
        print(f"   - Twitter: {user.get('twitter_username', 'None')}")
        print(f"   - Followers: {user.get('followers', 0)}")
        print(f"   - Public repos: {user.get('public_repos', 0)}")
        print(f"   - Created: {user.get('created_at', 'Unknown')}")
        print(f"   - GitHub URL: https://github.com/{user.get('login')}")

if __name__ == '__main__':
    test_github_token()
