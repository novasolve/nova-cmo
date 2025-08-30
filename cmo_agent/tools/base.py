"""
Base tool classes and contracts for CMO Agent toolbelt
"""
import asyncio
import time
import logging
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional, Union
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class ToolResult:
    """Standardized tool result format"""

    def __init__(self, success: bool, data: Any = None, error: str = None, metadata: Dict = None):
        self.success = success
        self.data = data or {}
        self.error = error
        self.metadata = metadata or {}
        self.timestamp = datetime.now().isoformat()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "data": self.data,
            "error": self.error,
            "metadata": self.metadata,
            "timestamp": self.timestamp,
        }


class RateLimiter:
    """Simple rate limiter for API calls"""

    def __init__(self, calls_per_second: float):
        self.calls_per_second = calls_per_second
        self.last_call_time = 0.0
        self.min_interval = 1.0 / calls_per_second

    async def wait_if_needed(self):
        """Wait if necessary to respect rate limit"""
        current_time = time.time()
        time_since_last = current_time - self.last_call_time

        if time_since_last < self.min_interval:
            wait_time = self.min_interval - time_since_last
            await asyncio.sleep(wait_time)

        self.last_call_time = time.time()


class BaseTool(ABC):
    """Base class for all CMO Agent tools"""

    def __init__(self, name: str, description: str, rate_limit: float = 1.0):
        self.name = name
        self.description = description
        self.rate_limiter = RateLimiter(rate_limit)
        self.call_count = 0
        self.error_count = 0

    @abstractmethod
    async def execute(self, **kwargs) -> ToolResult:
        """Execute the tool with given parameters"""
        pass

    async def _execute_with_retry(self, max_attempts: int = 3, **kwargs) -> ToolResult:
        """Execute with automatic retry logic"""
        for attempt in range(max_attempts):
            try:
                await self.rate_limiter.wait_if_needed()
                result = await self.execute(**kwargs)
                self.call_count += 1

                if result.success:
                    return result
                else:
                    self.error_count += 1
                    if attempt == max_attempts - 1:
                        return result

            except Exception as e:
                self.error_count += 1
                logger.error(f"Tool {self.name} failed on attempt {attempt + 1}: {e}")

                if attempt == max_attempts - 1:
                    return ToolResult(
                        success=False,
                        error=f"Tool failed after {max_attempts} attempts: {str(e)}",
                        metadata={"attempts": attempt + 1, "error_type": type(e).__name__}
                    )

            # Exponential backoff
            wait_time = (2 ** attempt) * 1.0
            await asyncio.sleep(wait_time)

        return ToolResult(success=False, error="Max retries exceeded")

    def get_stats(self) -> Dict[str, Any]:
        """Get tool usage statistics"""
        return {
            "name": self.name,
            "calls": self.call_count,
            "errors": self.error_count,
            "success_rate": (self.call_count - self.error_count) / max(self.call_count, 1),
        }


class GitHubTool(BaseTool):
    """Base class for GitHub-related tools"""

    def __init__(self, name: str, description: str, github_token: str):
        super().__init__(name, description, rate_limit=5000/3600)  # 5000 calls/hour
        self.github_token = github_token
        self.base_url = "https://api.github.com"

    async def _github_request(self, endpoint: str, method: str = "GET", **kwargs) -> Dict:
        """Make authenticated GitHub API request"""
        import aiohttp

        url = f"{self.base_url}{endpoint}"
        headers = {
            "Authorization": f"Bearer {self.github_token}",
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "CMO-Agent/1.0"
        }

        async with aiohttp.ClientSession() as session:
            async with session.request(method, url, headers=headers, **kwargs) as response:
                if response.status == 403:
                    reset_time = int(response.headers.get("X-RateLimit-Reset", 0))
                    reset_datetime = datetime.fromtimestamp(reset_time)
                    logger.warning(f"GitHub rate limited. Reset at: {reset_datetime}")
                    raise Exception(f"Rate limited until {reset_datetime}")

                response.raise_for_status()
                return await response.json()


class InstantlyTool(BaseTool):
    """Base class for Instantly-related tools"""

    def __init__(self, name: str, description: str, api_key: str):
        super().__init__(name, description, rate_limit=10)  # Conservative rate limit
        self.api_key = api_key
        self.base_url = "https://api.instantly.ai/api/v2"


class AttioTool(BaseTool):
    """Base class for Attio CRM tools"""

    def __init__(self, name: str, description: str, api_key: str, workspace_id: str):
        super().__init__(name, description, rate_limit=60/60)  # 60 calls/minute
        self.api_key = api_key
        self.workspace_id = workspace_id
        self.base_url = "https://api.attio.com/v2"


class LinearTool(BaseTool):
    """Base class for Linear ticketing tools"""

    def __init__(self, name: str, description: str, api_key: str):
        super().__init__(name, description, rate_limit=30/60)  # 30 calls/minute
        self.api_key = api_key
        self.base_url = "https://api.linear.app/graphql"
