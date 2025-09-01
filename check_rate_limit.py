#!/usr/bin/env python3
"""Quick script to check GitHub API rate limit status"""

import os
import sys
import requests
from datetime import datetime

def check_token_rate_limit(token):
    """Check rate limit for a specific token"""
    headers = {'Authorization': f'token {token}'}
    response = requests.get('https://api.github.com/rate_limit', headers=headers)

    if response.status_code != 200:
        print(f"❌ Failed to check rate limit: {response.status_code}")
        return

    data = response.json()
    core = data['resources']['core']
    search = data['resources']['search']

    print(f"\n🔑 Token: {token[:20]}...")
    print(f"┌─────────────────────────────────────────────┐")
    print(f"│ Core API:   {core['remaining']:4d} / {core['limit']:4d} calls remaining │")
    print(f"│ Search API: {search['remaining']:4d} / {search['limit']:4d} calls remaining │")

    if core['remaining'] == 0:
        reset_time = datetime.fromtimestamp(core['reset'])
        minutes_until_reset = (core['reset'] - datetime.now().timestamp()) / 60
        print(f"│ ⚠️  Core API exhausted!                      │")
        print(f"│ Resets at: {reset_time.strftime('%H:%M:%S')} ({minutes_until_reset:.0f} min)     │")

    print(f"└─────────────────────────────────────────────┘")

def main():
    # Check primary token
    token = os.getenv('GITHUB_TOKEN')
    if not token:
        print("❌ No GITHUB_TOKEN environment variable set!")
        sys.exit(1)

    check_token_rate_limit(token)

    # Check for additional tokens
    for i in range(2, 10):
        token = os.getenv(f'GITHUB_TOKEN_{i}')
        if token:
            check_token_rate_limit(token)

if __name__ == '__main__':
    main()
