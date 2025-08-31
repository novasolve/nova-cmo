"""
Hygiene and validation tools
"""
import asyncio
import logging
import sys
import os
import dns.resolver
import dns.exception
from typing import List, Dict, Any

# Add current directory to path for imports
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

try:
    from .base import BaseTool, ToolResult
except ImportError:
    try:
        from base import BaseTool, ToolResult
    except ImportError:
        # Create minimal fallback classes
        class ToolResult:
            def __init__(self, success: bool, data: Any = None, error: str = None, metadata: Dict = None):
                self.success = success
                self.data = data or {}
                self.error = error
                self.metadata = metadata or {}

            def to_dict(self) -> Dict[str, Any]:
                return {
                    "success": self.success,
                    "data": self.data,
                    "error": self.error,
                    "metadata": self.metadata,
                }

        class BaseTool:
            def __init__(self, name: str, description: str, rate_limit: float = 1000):
                self.name = name
                self.description = description
                self.rate_limit = rate_limit

logger = logging.getLogger(__name__)


class MXCheck(BaseTool):
    """MX record validation tool"""

    def __init__(self):
        super().__init__(
            name="mx_check",
            description="Validate email domains by checking MX records",
            rate_limit=100  # 100 checks per second
        )

    async def execute(self, emails: List[str], **kwargs) -> ToolResult:
        """Execute MX validation"""
        try:
            valid_emails = []
            invalid_emails = []

            # Process emails in batches to avoid overwhelming DNS
            batch_size = 10
            for i in range(0, len(emails), batch_size):
                batch = emails[i:i + batch_size]

                # Check MX records for this batch
                tasks = [self._check_mx_record(email) for email in batch]
                results = await asyncio.gather(*tasks, return_exceptions=True)

                for email, result in zip(batch, results):
                    if isinstance(result, Exception):
                        logger.warning(f"MX check failed for {email}: {result}")
                        invalid_emails.append(email)
                    elif result:
                        valid_emails.append(email)
                    else:
                        invalid_emails.append(email)

                # Small delay between batches
                if i + batch_size < len(emails):
                    await asyncio.sleep(0.1)

            return ToolResult(
                success=True,
                data={
                    "valid_emails": valid_emails,
                    "invalid_emails": invalid_emails,
                    "valid_count": len(valid_emails),
                    "invalid_count": len(invalid_emails)
                },
                metadata={"total_checked": len(emails)}
            )

        except Exception as e:
            logger.error(f"MX check failed: {e}")
            return ToolResult(success=False, error=str(e))

    async def _check_mx_record(self, email: str) -> bool:
        """Check if email domain has valid MX records"""
        try:
            # Extract domain from email
            if "@" not in email:
                return False

            domain = email.split("@")[1].lower()

            # Check MX records
            answers = dns.resolver.resolve(domain, "MX")
            return len(answers) > 0

        except (dns.resolver.NXDOMAIN, dns.resolver.NoAnswer, dns.exception.DNSException):
            return False
        except Exception as e:
            logger.error(f"DNS lookup failed for {domain}: {e}")
            return False


class ICPScores(BaseTool):
    """ICP scoring tool for lead qualification"""

    def __init__(self):
        super().__init__(
            name="score_icp",
            description="Score prospects against ICP criteria with deterministic weights",
            rate_limit=1000  # Very fast, pure computation
        )

    async def execute(self, profile: Dict[str, Any], weights: Dict[str, float] = None, **kwargs) -> ToolResult:
        """Score a prospect against ICP criteria"""
        try:
            if weights is None:
                # Default ICP weights
                weights = {
                    "stars_contributed": 0.3,
                    "activity_recency": 0.25,
                    "language_match": 0.2,
                    "topic_relevance": 0.15,
                    "follower_count": 0.1,
                }

            scores = {}
            explanations = {}

            # Score based on repository contributions
            repo_stars = sum(c.get("repo_stars", 0) for c in profile.get("contributions", []))
            stars_score = min(repo_stars / 1000, 1.0)  # Normalize to 1000 stars
            scores["stars_contributed"] = stars_score
            explanations["stars_contributed"] = f"Contributed to repos with {repo_stars} total stars"

            # Score based on activity recency (last 90 days)
            recent_activity = self._calculate_recent_activity(profile)
            recency_score = min(recent_activity / 90, 1.0)  # Normalize to 90 days
            scores["activity_recency"] = recency_score
            explanations["activity_recency"] = f"Active in last {recent_activity} days"

            # Score based on language match
            language_match = self._calculate_language_match(profile)
            scores["language_match"] = language_match
            explanations["language_match"] = f"Language alignment: {language_match:.2f}"

            # Score based on topic relevance
            topic_relevance = self._calculate_topic_relevance(profile)
            scores["topic_relevance"] = topic_relevance
            explanations["topic_relevance"] = f"Topic relevance: {topic_relevance:.2f}"

            # Score based on follower count
            followers = profile.get("followers", 0)
            follower_score = min(followers / 1000, 1.0)  # Normalize to 1000 followers
            scores["follower_count"] = follower_score
            explanations["follower_count"] = f"Has {followers} followers"

            # Calculate final score
            final_score = sum(scores[key] * weights.get(key, 0) for key in scores)

            # Determine qualification
            is_qualified = final_score >= 0.6  # 60% threshold

            result_data = {
                "final_score": final_score,
                "is_qualified": is_qualified,
                "component_scores": scores,
                "explanations": explanations,
                "profile_summary": self._create_profile_summary(profile),
            }

            return ToolResult(success=True, data=result_data)

        except Exception as e:
            logger.error(f"ICP scoring failed: {e}")
            return ToolResult(success=False, error=str(e))

    def _calculate_recent_activity(self, profile: Dict[str, Any]) -> int:
        """Calculate days since last activity"""
        # This would use actual contribution dates
        # For now, return a mock value
        return 45  # Assume 45 days of activity

    def _calculate_language_match(self, profile: Dict[str, Any]) -> float:
        """Calculate language alignment with ICP"""
        # Check if profile has Python contributions
        contributions = profile.get("contributions", [])
        python_contribs = sum(1 for c in contributions if c.get("repo_language") == "Python")
        return min(python_contribs / max(len(contributions), 1), 1.0)

    def _calculate_topic_relevance(self, profile: Dict[str, Any]) -> float:
        """Calculate topic relevance to ICP"""
        icp_topics = {"ci", "testing", "pytest", "devtools", "llm"}
        profile_topics = set()

        for contrib in profile.get("contributions", []):
            profile_topics.update(contrib.get("repo_topics", []))

        if not profile_topics:
            return 0.0

        matching_topics = icp_topics.intersection(profile_topics)
        return len(matching_topics) / len(icp_topics)

    def _create_profile_summary(self, profile: Dict[str, Any]) -> str:
        """Create human-readable profile summary"""
        login = profile.get("login", "unknown")
        name = profile.get("name", login)
        company = profile.get("company", "Unknown")
        followers = profile.get("followers", 0)

        contributions = profile.get("contributions", [])
        total_stars = sum(c.get("repo_stars", 0) for c in contributions)

        return f"{name} ({login}) from {company}, {followers} followers, contributed to {len(contributions)} repos with {total_stars} total stars"
