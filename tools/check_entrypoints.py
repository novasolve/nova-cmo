#!/usr/bin/env python
"""
Check that critical entrypoints exist to prevent regression.
"""
import sys
import pathlib
from typing import List

def check_entrypoints() -> int:
    """Check that all required entrypoints exist."""
    
    # Critical entrypoints that must exist
    required_paths = [
        "cmo_agent/scripts/run_web.py",
        "cmo_agent/scripts/run_agent.py", 
        "dev.sh",
        "cmo_agent/obs/beautiful_logging.py",
        "cmo_agent/core/state.py"
    ]
    
    missing = []
    for path_str in required_paths:
        path = pathlib.Path(path_str)
        if not path.exists():
            missing.append(path_str)
    
    if missing:
        print("❌ Missing critical entrypoints:")
        for path in missing:
            print(f"  - {path}")
        print("\nThese files are required for the system to function.")
        print("Restore them from git history or regenerate.")
        return 1
    
    print("✅ All critical entrypoints present:")
    for path in required_paths:
        print(f"  ✓ {path}")
    
    return 0

if __name__ == "__main__":
    sys.exit(check_entrypoints())
