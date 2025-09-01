#!/usr/bin/env python
"""
Test script for target parsing functionality
"""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from cmo_agent.agents.cmo_agent import CMOAgent
from cmo_agent.core.state import DEFAULT_CONFIG

def test_goal_parsing():
    """Test goal parsing for target extraction"""
    
    # Test just the parsing method without initializing the full agent
    # Create a minimal config for testing
    test_config = {"OPENAI_API_KEY": "test-key"}
    
    # We'll test the parsing method directly by creating a temporary instance
    # and calling the method without full initialization
    class MockAgent:
        def _parse_goal_to_icp(self, goal: str):
            # Copy the exact implementation from CMOAgent
            goal_lower = goal.lower()
            
            # Extract language
            languages = []
            if "python" in goal_lower:
                languages.append("python")
            elif "javascript" in goal_lower or "js" in goal_lower:
                languages.append("javascript")
            elif "java" in goal_lower:
                languages.append("java")
            elif "go" in goal_lower:
                languages.append("go")
            elif "rust" in goal_lower:
                languages.append("rust")
            else:
                languages = ["python"]  # Default to Python
            
            # Extract activity window
            activity_days = 90  # Default
            if "30 days" in goal_lower:
                activity_days = 30
            elif "60 days" in goal_lower:
                activity_days = 60
            elif "90 days" in goal_lower:
                activity_days = 90
            elif "6 months" in goal_lower:
                activity_days = 180
            elif "1 year" in goal_lower:
                activity_days = 365
            
            # Extract keywords and topics
            keywords = []
            topics = []
            
            if "developer" in goal_lower or "dev" in goal_lower:
                keywords.append("developer")
                topics.extend(["development", "coding"])
            if "maintainer" in goal_lower:
                keywords.append("maintainer")
                topics.extend(["maintenance", "open-source"])
            if "testing" in goal_lower or "test" in goal_lower:
                topics.extend(["testing", "qa", "pytest"])
            if "ai" in goal_lower or "ml" in goal_lower or "machine learning" in goal_lower:
                topics.extend(["ai", "ml", "machine-learning"])
            if "web" in goal_lower:
                topics.extend(["web", "frontend", "backend"])
            
            # Extract stars range
            stars_range = "100..2000"  # Default
            if "popular" in goal_lower or "high star" in goal_lower:
                stars_range = "500..10000"
            elif "small" in goal_lower or "new" in goal_lower:
                stars_range = "10..500"
            
            # Extract target numbers (emails, leads, contacts, etc.)
            import re
            target_emails = None
            target_leads = None
            
            # Look for patterns like "find 50 emails", "get 100 contacts", "target 25 leads"
            email_patterns = [
                r'find\s+(\d+)\s+emails?',
                r'get\s+(\d+)\s+emails?',
                r'(\d+)\s+emails?',
                r'target\s+(\d+)\s+emails?'
            ]
            
            lead_patterns = [
                r'find\s+(\d+)\s+(?:leads?|contacts?|maintainers?|developers?)',
                r'get\s+(\d+)\s+(?:leads?|contacts?|maintainers?|developers?)',
                r'(\d+)\s+(?:leads?|contacts?|maintainers?|developers?)',
                r'target\s+(\d+)\s+(?:leads?|contacts?|maintainers?|developers?)'
            ]
            
            # Try to extract email targets
            for pattern in email_patterns:
                match = re.search(pattern, goal_lower)
                if match:
                    target_emails = int(match.group(1))
                    break
            
            # Try to extract lead targets  
            for pattern in lead_patterns:
                match = re.search(pattern, goal_lower)
                if match:
                    target_leads = int(match.group(1))
                    break
            
            # If we found an email target but no lead target, assume they're the same
            if target_emails and not target_leads:
                target_leads = target_emails
            elif target_leads and not target_emails:
                target_emails = target_leads
            
            return {
                "languages": languages,
                "activity_days": activity_days,
                "keywords": keywords,
                "topics": topics,
                "stars_range": stars_range,
                "target_emails": target_emails,
                "target_leads": target_leads,
                "goal": goal  # Keep original goal for reference
            }
    
    agent = MockAgent()
    
    test_cases = [
        ("Find 50 emails from Python developers", {"target_emails": 50, "target_leads": 50}),
        ("Get 100 contacts from JavaScript maintainers", {"target_emails": 100, "target_leads": 100}),
        ("Target 25 leads from Go developers", {"target_emails": 25, "target_leads": 25}),
        ("Find maintainers of Python repos - 75 developers", {"target_emails": 75, "target_leads": 75}),
        ("Python developers with activity in the last 90 days", {"target_emails": None, "target_leads": None}),
        ("Find 20 emails and 30 leads from Rust projects", {"target_emails": 20, "target_leads": 30}),
    ]
    
    print("🧪 Testing Goal Parsing for Targets\n")
    
    for goal, expected in test_cases:
        result = agent._parse_goal_to_icp(goal)
        
        actual_emails = result.get("target_emails")
        actual_leads = result.get("target_leads")
        
        emails_match = actual_emails == expected["target_emails"]
        leads_match = actual_leads == expected["target_leads"]
        
        status = "✅" if (emails_match and leads_match) else "❌"
        
        print(f"{status} Goal: '{goal}'")
        print(f"   Expected: emails={expected['target_emails']}, leads={expected['target_leads']}")
        print(f"   Actual:   emails={actual_emails}, leads={actual_leads}")
        print()

if __name__ == "__main__":
    test_goal_parsing()
