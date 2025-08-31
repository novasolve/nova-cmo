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

        # Record API call attempt
        try:
            from ..core.monitoring import record_api_call
            record_api_call_attempted = True
        except ImportError:
            try:
                from core.monitoring import record_api_call
                record_api_call_attempted = True
            except ImportError:
                record_api_call_attempted = False

        url = f"{self.base_url}{endpoint}"
        headers = {
            "Authorization": f"Bearer {self.github_token}",
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "CMO-Agent/1.0"
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.request(method, url, headers=headers, **kwargs) as response:
                    if response.status == 403:
                        # Respect rate-limit reset header when present
                        reset_time = int(response.headers.get("X-RateLimit-Reset", 0))
                        reset_datetime = datetime.fromtimestamp(reset_time) if reset_time else None
                        if record_api_call_attempted:
                            record_api_call(False)
                        # Sleep until reset (bounded) before raising to allow retry wrappers to proceed
                        try:
                            if reset_time:
                                now = time.time()
                                wait_seconds = max(0.0, reset_time - now)
                                # Bound the wait to a reasonable maximum per config patterns (5 minutes)
                                bounded_wait = min(wait_seconds, 300.0)
                                if bounded_wait > 0:
                                    logger.warning(f"GitHub rate limited. Waiting {bounded_wait:.1f}s until reset at {reset_datetime}")
                                    await asyncio.sleep(bounded_wait)
                        except Exception:
                            pass
                        raise Exception(f"Rate limited until {reset_datetime or 'later'}")

                    response.raise_for_status()
                    
                    # Handle 204 No Content responses (empty body)
                    if response.status == 204:
                        result = {}
                    else:
                        # Only try to decode JSON if there's content
                        content_type = response.headers.get('content-type', '')
                        if 'application/json' in content_type:
                            result = await response.json()
                        else:
                            # Handle non-JSON responses
                            text = await response.text()
                            result = {"text": text} if text else {}

                    # Record successful API call
                    if record_api_call_attempted:
                        record_api_call(True)

                    return result
        except Exception as e:
            # Record failed API call
            if record_api_call_attempted:
                record_api_call(False)
            raise


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
