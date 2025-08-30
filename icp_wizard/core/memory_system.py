#!/usr/bin/env python3
"""
Advanced Conversation Memory System for ICP Wizard
Provides persistent user profiles, conversation history, and learning capabilities
"""

import os
import json
import hashlib
from pathlib import Path
from typing import Dict, List, Optional, Any, TypedDict, Set
from datetime import datetime, timedelta
from collections import defaultdict
import pickle

from ..utils.logging_utils import get_logger

logger = get_logger(__name__)


class UserProfile(TypedDict):
    """User profile structure for memory system"""
    user_id: str
    created_at: str
    last_conversation: Optional[str]
    conversation_count: int
    successful_icps: List[Dict[str, Any]]
    preferred_icp_types: List[str]
    common_industries: List[str]
    technical_preferences: List[str]
    conversation_patterns: List[Dict[str, Any]]
    learning_data: Dict[str, Any]
    preferences: Dict[str, Any]


class ConversationMemory:
    """Advanced conversation memory system with learning capabilities"""

    def __init__(self, memory_dir: Optional[Path] = None):
        """Initialize memory system with configurable storage directory"""
        self.memory_dir = memory_dir or Path("lead_intelligence/data/conversation_memory")
        self.memory_dir.mkdir(parents=True, exist_ok=True)
        self.user_memories: Dict[str, UserProfile] = {}
        self.session_cache: Dict[str, Any] = {}

        # Learning patterns across all users
        self.global_patterns = defaultdict(lambda: defaultdict(int))

        logger.info(f"Initialized conversation memory system at {self.memory_dir}")

    def _get_user_hash(self, user_identifier: str) -> str:
        """Generate consistent hash for user identification"""
        return hashlib.md5(user_identifier.encode()).hexdigest()[:12]

    def _get_memory_file(self, user_hash: str) -> Path:
        """Get memory file path for user"""
        return self.memory_dir / f"{user_hash}_memory.json"

    def load_user_memory(self, user_identifier: str) -> UserProfile:
        """Load user's conversation memory and preferences"""
        user_hash = self._get_user_hash(user_identifier)
        memory_file = self._get_memory_file(user_hash)

        if memory_file.exists():
            try:
                with open(memory_file, 'r', encoding='utf-8') as f:
                    memory_data = json.load(f)
                    # Validate and upgrade memory structure if needed
                    return self._validate_and_upgrade_memory(memory_data)
            except Exception as e:
                logger.warning(f"Could not load user memory for {user_identifier}: {e}")
                return self._create_default_memory(user_identifier)

        return self._create_default_memory(user_identifier)

    def save_user_memory(self, user_identifier: str, memory: UserProfile) -> None:
        """Save user's conversation memory and preferences"""
        user_hash = self._get_user_hash(user_identifier)
        memory_file = self._get_memory_file(user_hash)

        try:
            with open(memory_file, 'w', encoding='utf-8') as f:
                json.dump(memory, f, indent=2, ensure_ascii=False)
            logger.debug(f"Saved memory for user {user_identifier}")
        except Exception as e:
            logger.error(f"Could not save user memory for {user_identifier}: {e}")

    def _create_default_memory(self, user_identifier: str) -> UserProfile:
        """Create default memory structure for new users"""
        return {
            "user_id": user_identifier,
            "created_at": datetime.now().isoformat(),
            "last_conversation": None,
            "conversation_count": 0,
            "successful_icps": [],
            "preferred_icp_types": [],
            "common_industries": [],
            "technical_preferences": [],
            "conversation_patterns": [],
            "learning_data": {
                "stage_transitions": {},
                "successful_refinements": [],
                "rejected_suggestions": [],
                "preferred_stages": {},
                "conversation_durations": [],
                "success_patterns": []
            },
            "preferences": {
                "communication_style": "conversational",
                "detail_level": "balanced",
                "pace_preference": "guided",
                "feedback_style": "encouraging"
            }
        }

    def _validate_and_upgrade_memory(self, memory_data: Dict[str, Any]) -> UserProfile:
        """Validate and upgrade memory structure to latest version"""
        # Ensure all required fields exist with defaults
        defaults = self._create_default_memory(memory_data.get("user_id", "unknown"))

        # Merge with defaults, preserving existing data
        for key, default_value in defaults.items():
            if key not in memory_data:
                memory_data[key] = default_value
            elif isinstance(default_value, dict) and isinstance(memory_data[key], dict):
                # Deep merge for nested dictionaries
                memory_data[key] = {**default_value, **memory_data[key]}

        return memory_data

    def update_memory_from_conversation(self, user_identifier: str, conversation_data: Dict[str, Any]) -> UserProfile:
        """Update user's memory with new conversation insights"""
        memory = self.load_user_memory(user_identifier)

        # Update basic conversation metadata
        memory["conversation_count"] += 1
        memory["last_conversation"] = datetime.now().isoformat()

        # Update successful ICPs if any
        if conversation_data.get("final_icp_config"):
            icp_config = conversation_data["final_icp_config"]
            successful_icp = {
                "icp_id": icp_config.get("icp_id"),
                "icp_name": icp_config.get("icp_name"),
                "timestamp": datetime.now().isoformat(),
                "success_score": conversation_data.get("success_score", 1.0),
                "conversation_duration": conversation_data.get("duration_seconds", 0)
            }
            memory["successful_icps"].append(successful_icp)

            # Keep only last 20 successful ICPs
            memory["successful_icps"] = memory["successful_icps"][-20:]

        # Learn from conversation patterns
        self._learn_from_conversation(memory, conversation_data)

        # Update global learning patterns
        self._update_global_patterns(conversation_data)

        # Save updated memory
        self.save_user_memory(user_identifier, memory)

        return memory

    def _learn_from_conversation(self, memory: UserProfile, conversation_data: Dict[str, Any]) -> None:
        """Learn patterns from successful conversations"""
        messages = conversation_data.get("messages", [])

        # Extract ICP preferences
        if conversation_data.get("final_icp_config"):
            icp_config = conversation_data["final_icp_config"]
            icp_id = icp_config.get("icp_id", "")

            # Add to preferred ICP types
            if icp_id and icp_id not in memory["preferred_icp_types"]:
                memory["preferred_icp_types"].append(icp_id)
                # Keep only top 10 preferred ICPs
                memory["preferred_icp_types"] = memory["preferred_icp_types"][-10:]

        # Extract industry preferences from conversation
        conversation_text = " ".join([
            msg.get("content", "") for msg in messages
            if msg.get("role") == "user"
        ]).lower()

        industries = self._extract_industries(conversation_text)
        for industry in industries:
            if industry not in memory["common_industries"]:
                memory["common_industries"].append(industry)

        # Extract technical preferences
        tech_stack = self._extract_technical_preferences(conversation_text)
        for tech in tech_stack:
            if tech not in memory["technical_preferences"]:
                memory["technical_preferences"].append(tech)

        # Keep lists manageable
        memory["common_industries"] = memory["common_industries"][-10:]
        memory["technical_preferences"] = memory["technical_preferences"][-10:]

        # Track conversation patterns
        pattern = {
            "timestamp": datetime.now().isoformat(),
            "duration": conversation_data.get("duration_seconds", 0),
            "stage_count": len(conversation_data.get("stage_transitions", [])),
            "success": bool(conversation_data.get("final_icp_config")),
            "message_count": len(messages)
        }
        memory["conversation_patterns"].append(pattern)
        memory["conversation_patterns"] = memory["conversation_patterns"][-50:]

    def _extract_industries(self, text: str) -> List[str]:
        """Extract industry mentions from conversation text"""
        industries = []
        industry_keywords = {
            "saas": ["saas", "software as a service", "cloud service", "web app"],
            "fintech": ["fintech", "financial", "banking", "payment", "crypto"],
            "healthtech": ["healthtech", "healthcare", "medical", "health", "biotech"],
            "ecommerce": ["ecommerce", "e-commerce", "retail", "shopping", "marketplace"],
            "ai": ["artificial intelligence", "ai", "machine learning", "ml", "deep learning"],
            "blockchain": ["blockchain", "crypto", "cryptocurrency", "web3", "defi"],
            "gaming": ["gaming", "game", "entertainment", "esports"],
            "education": ["education", "learning", "edtech", "course", "training"],
            "enterprise": ["enterprise", "b2b", "business software", "corporate"],
            "mobile": ["mobile", "ios", "android", "app development"],
            "devtools": ["devtools", "developer tools", "api", "sdk", "platform"],
            "data": ["data", "analytics", "business intelligence", "bi"],
            "security": ["security", "cybersecurity", "infosec"]
        }

        text_lower = text.lower()
        for industry, keywords in industry_keywords.items():
            if any(keyword in text_lower for keyword in keywords):
                industries.append(industry)

        return list(set(industries))  # Remove duplicates

    def _extract_technical_preferences(self, text: str) -> List[str]:
        """Extract technical preferences from conversation text"""
        tech_stack = []
        tech_keywords = {
            "python": ["python", "django", "flask", "fastapi", "pandas", "numpy"],
            "javascript": ["javascript", "node", "react", "vue", "angular", "typescript"],
            "java": ["java", "spring", "kotlin", "scala"],
            "golang": ["golang", "go", "gin", "echo"],
            "rust": ["rust", "cargo", "tokio"],
            "cpp": ["c++", "cpp", "qt", "boost"],
            "csharp": ["c#", "csharp", ".net", "dotnet"],
            "php": ["php", "laravel", "symfony"],
            "ruby": ["ruby", "rails", "sinatra"],
            "swift": ["swift", "ios development"],
            "kotlin": ["kotlin", "android development"],
            "scala": ["scala", "akka", "play framework"],
            "clojure": ["clojure", "clojurescript"],
            "elixir": ["elixir", "phoenix"],
            "erlang": ["erlang", "otp"],
            "haskell": ["haskell", "cabal"],
            "r": ["r", "rstudio", "tidyverse"],
            "matlab": ["matlab", "simulink"],
            "julia": ["julia"],
            "lua": ["lua", "luajit"],
            "perl": ["perl", "mojo"],
            "shell": ["bash", "zsh", "shell", "scripting"],
            "docker": ["docker", "container", "kubernetes", "k8s"],
            "aws": ["aws", "amazon web services", "ec2", "s3", "lambda"],
            "azure": ["azure", "microsoft azure"],
            "gcp": ["gcp", "google cloud", "firebase"],
            "react": ["react", "jsx", "nextjs"],
            "vue": ["vue", "nuxt"],
            "angular": ["angular", "ng"],
            "svelte": ["svelte"],
            "django": ["django", "drf"],
            "flask": ["flask", "sqlalchemy"],
            "express": ["express", "nodejs"],
            "spring": ["spring", "spring boot"],
            "dotnet": [".net", "asp.net", "entity framework"],
            "laravel": ["laravel", "php"],
            "rails": ["rails", "ruby on rails"],
            "graphql": ["graphql", "apollo"],
            "rest": ["rest", "api", "restful"],
            "grpc": ["grpc", "protobuf"],
            "websocket": ["websocket", "socket.io"],
            "redis": ["redis", "cache"],
            "mongodb": ["mongodb", "nosql"],
            "postgresql": ["postgresql", "postgres"],
            "mysql": ["mysql", "mariadb"],
            "sqlite": ["sqlite"],
            "elasticsearch": ["elasticsearch", "elastic"],
            "kafka": ["kafka", "message queue"],
            "rabbitmq": ["rabbitmq", "amqp"],
            "nginx": ["nginx", "reverse proxy"],
            "apache": ["apache", "httpd"],
            "jenkins": ["jenkins", "ci/cd"],
            "github_actions": ["github actions", "gha"],
            "gitlab_ci": ["gitlab ci", "gitlab-ci"],
            "circleci": ["circleci"],
            "travis": ["travis ci"],
            "pytest": ["pytest", "unittest"],
            "jest": ["jest", "testing"],
            "mocha": ["mocha"],
            "cypress": ["cypress", "e2e"],
            "selenium": ["selenium"],
            "tensorflow": ["tensorflow", "tf"],
            "pytorch": ["pytorch", "torch"],
            "keras": ["keras"],
            "scikit": ["scikit-learn", "sklearn"],
            "pandas": ["pandas", "dataframe"],
            "numpy": ["numpy", "array"],
            "matplotlib": ["matplotlib", "plot"],
            "seaborn": ["seaborn", "visualization"],
            "jupyter": ["jupyter", "notebook"],
            "streamlit": ["streamlit", "dashboard"],
            "fastapi": ["fastapi", "asyncapi"],
            "sqlalchemy": ["sqlalchemy", "orm"],
            "alembic": ["alembic", "migration"],
            "celery": ["celery", "task queue"],
            "dramatiq": ["dramatiq"],
            "flower": ["flower", "monitoring"]
        }

        text_lower = text.lower()
        for tech, keywords in tech_keywords.items():
            if any(keyword in text_lower for keyword in keywords):
                tech_stack.append(tech)

        return list(set(tech_stack))  # Remove duplicates

    def _update_global_patterns(self, conversation_data: Dict[str, Any]) -> None:
        """Update global learning patterns across all users"""
        # Track successful ICP patterns
        if conversation_data.get("final_icp_config"):
            icp_id = conversation_data["final_icp_config"].get("icp_id")
            if icp_id:
                self.global_patterns["successful_icps"][icp_id] += 1

        # Track conversation patterns
        duration = conversation_data.get("duration_seconds", 0)
        if duration > 0:
            if duration < 300:  # < 5 minutes
                self.global_patterns["conversation_duration"]["quick"] += 1
            elif duration < 900:  # < 15 minutes
                self.global_patterns["conversation_duration"]["medium"] += 1
            else:  # > 15 minutes
                self.global_patterns["conversation_duration"]["long"] += 1

    def get_personalized_suggestions(self, user_identifier: str) -> Dict[str, Any]:
        """Get personalized suggestions based on user's history"""
        memory = self.load_user_memory(user_identifier)

        suggestions = {
            "conversation_count": memory.get("conversation_count", 0),
            "success_rate": self._calculate_success_rate(memory),
            "preferred_icps": memory.get("preferred_icp_types", [])[:5],
            "common_industries": memory.get("common_industries", [])[:5],
            "technical_preferences": memory.get("technical_preferences", [])[:5],
            "avg_conversation_duration": self._calculate_avg_duration(memory),
            "last_conversation": memory.get("last_conversation"),
            "is_returning_user": memory.get("conversation_count", 0) > 1,
            "learning_insights": self._generate_learning_insights(memory)
        }

        return suggestions

    def _calculate_success_rate(self, memory: UserProfile) -> float:
        """Calculate user's success rate"""
        conversation_count = memory.get("conversation_count", 0)
        successful_icps = len(memory.get("successful_icps", []))

        if conversation_count == 0:
            return 0.0

        return successful_icps / conversation_count

    def _calculate_avg_duration(self, memory: UserProfile) -> Optional[float]:
        """Calculate average conversation duration"""
        patterns = memory.get("conversation_patterns", [])
        if not patterns:
            return None

        durations = [p.get("duration", 0) for p in patterns if p.get("duration", 0) > 0]
        if not durations:
            return None

        return sum(durations) / len(durations)

    def _generate_learning_insights(self, memory: UserProfile) -> Dict[str, Any]:
        """Generate learning insights from user's history"""
        insights = {
            "most_successful_time": None,
            "preferred_day_of_week": None,
            "avg_stages_per_conversation": 0,
            "learning_progress": "beginner"
        }

        patterns = memory.get("conversation_patterns", [])
        if not patterns:
            return insights

        # Calculate average stages
        stages = [p.get("stage_count", 0) for p in patterns]
        if stages:
            insights["avg_stages_per_conversation"] = sum(stages) / len(stages)

        # Determine learning progress
        conversation_count = memory.get("conversation_count", 0)
        success_rate = self._calculate_success_rate(memory)

        if conversation_count >= 10 and success_rate >= 0.8:
            insights["learning_progress"] = "expert"
        elif conversation_count >= 5 and success_rate >= 0.6:
            insights["learning_progress"] = "intermediate"
        elif conversation_count >= 2:
            insights["learning_progress"] = "beginner"
        else:
            insights["learning_progress"] = "new"

        return insights

    def get_memory_stats(self) -> Dict[str, Any]:
        """Get overall memory system statistics"""
        # Count total users
        user_count = len(list(self.memory_dir.glob("*_memory.json")))

        # Aggregate global patterns
        total_conversations = sum(self.global_patterns["successful_icps"].values())

        return {
            "total_users": user_count,
            "total_conversations": total_conversations,
            "popular_icps": dict(self.global_patterns["successful_icps"]),
            "conversation_duration_distribution": dict(self.global_patterns["conversation_duration"]),
            "memory_dir": str(self.memory_dir),
            "last_updated": datetime.now().isoformat()
        }

    def cleanup_old_memories(self, days_to_keep: int = 365) -> int:
        """Clean up old memory files beyond retention period"""
        cutoff_date = datetime.now() - timedelta(days=days_to_keep)
        deleted_count = 0

        for memory_file in self.memory_dir.glob("*_memory.json"):
            try:
                # Check file modification time
                if memory_file.stat().st_mtime < cutoff_date.timestamp():
                    memory_file.unlink()
                    deleted_count += 1
                    logger.info(f"Cleaned up old memory file: {memory_file}")
            except Exception as e:
                logger.warning(f"Could not cleanup memory file {memory_file}: {e}")

        return deleted_count

    def export_memory_data(self, export_path: Path) -> bool:
        """Export all memory data for analysis"""
        try:
            export_data = {
                "export_timestamp": datetime.now().isoformat(),
                "global_patterns": dict(self.global_patterns),
                "users": {}
            }

            # Export individual user memories
            for memory_file in self.memory_dir.glob("*_memory.json"):
                try:
                    with open(memory_file, 'r', encoding='utf-8') as f:
                        user_data = json.load(f)
                        user_id = user_data.get("user_id", "unknown")
                        export_data["users"][user_id] = user_data
                except Exception as e:
                    logger.warning(f"Could not export user memory {memory_file}: {e}")

            with open(export_path, 'w', encoding='utf-8') as f:
                json.dump(export_data, f, indent=2, ensure_ascii=False)

            logger.info(f"Exported memory data to {export_path}")
            return True

        except Exception as e:
            logger.error(f"Could not export memory data: {e}")
            return False
