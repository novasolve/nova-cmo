from dataclasses import dataclass, asdict
from typing import Dict, Any

@dataclass
class RunStats:
    """Shared stats object for accurate progress/summary"""
    repos: int = 0
    candidates: int = 0
    leads: int = 0
    emails: int = 0
    llm_calls: int = 0
    api_calls: int = 0
    steps: int = 0
    errors: int = 0
    
    def as_dict(self) -> Dict[str, Any]:
        return asdict(self)
    
    def reset(self):
        """Reset all counters"""
        self.repos = 0
        self.candidates = 0
        self.leads = 0
        self.emails = 0
        self.llm_calls = 0
        self.api_calls = 0
        self.steps = 0
        self.errors = 0

# Global stats instance
stats = RunStats()

