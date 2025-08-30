#!/usr/bin/env python3
"""
GitHub Token Manager
Manages multiple GitHub tokens to avoid rate limiting
"""

import os
import json
import time
import requests
from typing import List, Dict, Optional

class TokenManager:
    def __init__(self, tokens: List[str]):
        self.tokens = tokens
        self.current_index = 0
        self.token_stats = {}
        
    def get_current_token(self) -> str:
        """Get the current active token"""
        return self.tokens[self.current_index]
    
    def check_rate_limit(self, token: str) -> Dict:
        """Check rate limit for a specific token"""
        headers = {'Authorization': f'token {token}'}
        response = requests.get('https://api.github.com/rate_limit', headers=headers)
        if response.status_code == 200:
            return response.json()
        return {}
    
    def get_best_token(self) -> Optional[str]:
        """Get the token with the most remaining API calls"""
        best_token = None
        max_remaining = -1
        
        for token in self.tokens:
            rate_info = self.check_rate_limit(token)
            if rate_info:
                core_remaining = rate_info.get('resources', {}).get('core', {}).get('remaining', 0)
                search_remaining = rate_info.get('resources', {}).get('search', {}).get('remaining', 0)
                total_remaining = core_remaining + (search_remaining * 100)  # Weight search more
                
                print(f"Token {token[:10]}...: Core: {core_remaining}, Search: {search_remaining}")
                
                if total_remaining > max_remaining:
                    max_remaining = total_remaining
                    best_token = token
        
        return best_token
    
    def rotate_token(self):
        """Rotate to the next token"""
        self.current_index = (self.current_index + 1) % len(self.tokens)
        print(f"Rotated to token index {self.current_index}")
        
    def save_token_config(self, filepath: str = '.token_config.json'):
        """Save token configuration"""
        config = {
            'tokens': self.tokens,
            'current_index': self.current_index
        }
        with open(filepath, 'w') as f:
            json.dump(config, f, indent=2)
            
    @classmethod
    def load_from_config(cls, filepath: str = '.token_config.json') -> 'TokenManager':
        """Load token configuration from file"""
        if os.path.exists(filepath):
            with open(filepath, 'r') as f:
                config = json.load(f)
                manager = cls(config['tokens'])
                manager.current_index = config.get('current_index', 0)
                return manager
        return cls([])

def main():
    """Setup and test tokens"""
    tokens = []
    
    # Check environment variables
    primary_token = os.getenv('GITHUB_TOKEN')
    if primary_token:
        tokens.append(primary_token)
    
    # Check for additional tokens
    for i in range(2, 10):
        token = os.getenv(f'GITHUB_TOKEN_{i}')
        if token:
            tokens.append(token)
    
    if not tokens:
        print("❌ No GitHub tokens found in environment variables!")
        print("Please set GITHUB_TOKEN or GITHUB_TOKEN_2, GITHUB_TOKEN_3, etc.")
        return
    
    print(f"✅ Found {len(tokens)} GitHub token(s)")
    
    # Create token manager
    manager = TokenManager(tokens)
    
    # Check all tokens
    print("\n📊 Checking token rate limits...")
    best_token = manager.get_best_token()
    
    if best_token:
        print(f"\n✅ Best token to use: {best_token[:10]}...")
        print(f"\nExport this token:")
        print(f"export GITHUB_TOKEN={best_token}")
    else:
        print("\n❌ No valid tokens found!")

if __name__ == '__main__':
    main()
