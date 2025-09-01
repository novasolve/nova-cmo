#!/usr/bin/env python
"""
Environment validation to catch missing critical environment variables early.
"""
import os
import sys
from typing import List, Dict, Optional
from pathlib import Path


class EnvChecker:
    """Environment validation with clear error messages."""
    
    def __init__(self):
        self.errors: List[str] = []
        self.warnings: List[str] = []
        
    def check_required(self, var_name: str, description: str) -> Optional[str]:
        """Check if a required environment variable is set."""
        value = os.getenv(var_name, "").strip()
        if not value:
            self.errors.append(f"❌ {var_name}: {description}")
            return None
        return value
    
    def check_optional(self, var_name: str, description: str, default: str = None) -> str:
        """Check an optional environment variable and warn if missing."""
        value = os.getenv(var_name, "").strip()
        if not value:
            if default:
                self.warnings.append(f"⚠️  {var_name}: {description} (using default: {default})")
                return default
            else:
                self.warnings.append(f"⚠️  {var_name}: {description} (optional)")
                return ""
        return value
    
    def validate_token_format(self, token: str, var_name: str, expected_prefixes: List[str]) -> bool:
        """Validate token format and warn if suspicious."""
        if not token:
            return False
            
        if not any(token.startswith(prefix) for prefix in expected_prefixes):
            self.warnings.append(
                f"⚠️  {var_name}: Format doesn't match expected patterns {expected_prefixes}. "
                "This may cause API failures."
            )
        
        return True


def check_environment(dry_run: bool = False) -> int:
    """
    Check critical environment variables for CMO Agent.
    
    Args:
        dry_run: If True, only check variables needed for dry runs
        
    Returns:
        0 if all required variables are present, 1 otherwise
    """
    checker = EnvChecker()
    
    print("🔍 Checking environment configuration...")
    
    # Always required for any operation
    github_token = checker.check_required(
        "GITHUB_TOKEN", 
        "Required for GitHub API access. Get one at https://github.com/settings/tokens"
    )
    
    if github_token and not dry_run:
        checker.validate_token_format(
            github_token, 
            "GITHUB_TOKEN", 
            ["ghp_", "github_pat_", "gho_", "ghu_", "ghs_"]
        )
    
    # Required for AI operations (unless dry run)
    if not dry_run:
        openai_key = checker.check_required(
            "OPENAI_API_KEY",
            "Required for AI agent operations. Get one at https://platform.openai.com/api-keys"
        )
        
        if openai_key:
            checker.validate_token_format(
                openai_key,
                "OPENAI_API_KEY", 
                ["sk-"]
            )
    
    # Optional but recommended
    checker.check_optional(
        "ATTIO_API_KEY",
        "CRM integration for lead management",
        "disabled"
    )
    
    checker.check_optional(
        "LOG_LEVEL", 
        "Logging verbosity (DEBUG, INFO, WARNING, ERROR)",
        "INFO"
    )
    
    checker.check_optional(
        "FORCE_TQDM",
        "Force progress bars in non-TTY environments", 
        "1"
    )
    
    # Check for .env files in multiple locations
    env_locations = [
        Path(".env"),
        Path("cmo_agent/.env"),
        Path.home() / ".cmo_agent.env"
    ]
    
    env_found = any(env_file.exists() for env_file in env_locations)
    env_example = Path(".env.example")
    
    if not env_found:
        if env_example.exists():
            checker.warnings.append(
                "⚠️  No .env file found. Copy .env.example to .env and fill in your credentials."
            )
        else:
            checker.warnings.append(
                "⚠️  No .env file found. Create one with your API credentials."
            )
        checker.warnings.append(
            f"⚠️  Checked locations: {', '.join(str(p) for p in env_locations)}"
        )
    else:
        # Find which env file exists and mention it
        existing_env = next((str(p) for p in env_locations if p.exists()), None)
        if existing_env:
            print(f"📄 Found environment file: {existing_env}")
            
        # Security reminder for cmo_agent/.env
        cmo_env = Path("cmo_agent/.env")
        if cmo_env.exists():
            print("🔐 Security reminder: cmo_agent/.env contains real API keys - ensure it's in .gitignore")
    
    # Print results
    if checker.warnings:
        print("\n📋 Warnings:")
        for warning in checker.warnings:
            print(f"  {warning}")
    
    if checker.errors:
        print("\n💥 Critical Issues:")
        for error in checker.errors:
            print(f"  {error}")
        
        print(f"\n🔧 Quick Fix:")
        if not env_file.exists() and env_example.exists():
            print(f"  cp .env.example .env")
            print(f"  # Then edit .env with your actual credentials")
        else:
            print(f"  export GITHUB_TOKEN='your_token_here'")
            if not dry_run:
                print(f"  export OPENAI_API_KEY='your_key_here'")
        
        print(f"\n📖 See .env.example for all available options")
        return 1
    
    print("✅ Environment validation passed!")
    if checker.warnings:
        print(f"   ({len(checker.warnings)} warnings - see above)")
    
    return 0


def main():
    """CLI entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Validate CMO Agent environment")
    parser.add_argument(
        "--dry-run", 
        action="store_true", 
        help="Only check variables needed for dry runs"
    )
    
    args = parser.parse_args()
    return check_environment(dry_run=args.dry_run)


if __name__ == "__main__":
    sys.exit(main())
