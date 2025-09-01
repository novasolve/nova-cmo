#!/usr/bin/env python
"""
Clean API keys from existing checkpoint files.
"""
import json
import os
import sys
from pathlib import Path
from typing import Dict, Any


def clean_checkpoint_file(file_path: Path) -> bool:
    """Clean API keys from a single checkpoint file."""
    try:
        # Read the checkpoint
        with open(file_path, 'r') as f:
            data = json.load(f)
        
        # Track if we made changes
        changed = False
        
        # Clean sensitive data from state.config
        if "state" in data and isinstance(data["state"], dict):
            state = data["state"]
            
            sensitive_keys = [
                "GITHUB_TOKEN", "OPENAI_API_KEY", "INSTANTLY_API_KEY", 
                "ATTIO_API_KEY", "ATTIO_ACCESS_TOKEN", "LINEAR_API_KEY",
                "LANGFUSE_SECRET_KEY", "SMTP_PASSWORD", "DATABASE_URL"
            ]
            
            if "config" in state and isinstance(state["config"], dict):
                config = state["config"]
                
                for key in sensitive_keys:
                    if key in config and config[key] != "***REDACTED***":
                        config[key] = "***REDACTED***"
                        changed = True
            
            # Also check nested agent state if present
            if "agent" in state and isinstance(state["agent"], dict):
                agent_state = state["agent"]
                if "config" in agent_state and isinstance(agent_state["config"], dict):
                    config = agent_state["config"]
                    
                    for key in sensitive_keys:
                        if key in config and config[key] != "***REDACTED***":
                            config[key] = "***REDACTED***"
                            changed = True
        
        # Write back if changed
        if changed:
            with open(file_path, 'w') as f:
                json.dump(data, f, indent=2, default=str)
            return True
        
        return False
        
    except Exception as e:
        print(f"Error cleaning {file_path}: {e}")
        return False


def main():
    """Clean all checkpoint files."""
    checkpoints_dir = Path("cmo_agent/checkpoints")
    
    if not checkpoints_dir.exists():
        print("No checkpoints directory found.")
        return 0
    
    checkpoint_files = list(checkpoints_dir.glob("*.json"))
    
    if not checkpoint_files:
        print("No checkpoint files found.")
        return 0
    
    print(f"🔍 Scanning {len(checkpoint_files)} checkpoint files...")
    
    cleaned_count = 0
    for file_path in checkpoint_files:
        if clean_checkpoint_file(file_path):
            cleaned_count += 1
            if cleaned_count <= 5:  # Show first few for progress
                print(f"✅ Cleaned: {file_path.name}")
            elif cleaned_count == 6:
                print("   ... (continuing silently)")
    
    if cleaned_count > 0:
        print(f"\n🔐 Cleaned {cleaned_count}/{len(checkpoint_files)} checkpoint files")
        print("✅ API keys replaced with ***REDACTED***")
    else:
        print("✅ No API keys found in checkpoint files")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
