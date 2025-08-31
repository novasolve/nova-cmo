"""
Personalization and sending tools
"""
import logging
import sys
import os
import jinja2
from typing import Dict, Any, List

# Add current directory to path for imports
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

try:
    from .base import BaseTool, InstantlyTool, ToolResult
except ImportError:
    try:
        from base import BaseTool, InstantlyTool, ToolResult
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

        class InstantlyTool(BaseTool):
            def __init__(self, name: str, description: str, api_key: str):
                super().__init__(name, description)
                self.api_key = api_key

logger = logging.getLogger(__name__)


class RenderCopy(BaseTool):
    """Copy rendering and personalization tool"""

    def __init__(self):
        super().__init__(
            name="render_copy",
            description="Render personalized email copy using templates and lead data",
            rate_limit=1000  # Pure computation
        )

        # Jinja2 environment for template rendering
        self.env = jinja2.Environment(
            loader=jinja2.DictLoader({}),
            autoescape=True,
            trim_blocks=True,
            lstrip_blocks=True
        )

    async def execute(self, lead: Dict[str, Any], campaign: Dict[str, Any] = None, **kwargs) -> ToolResult:
        """Render personalized copy"""
        try:
            if campaign is None:
                campaign = self._get_default_campaign()

            # Prepare template variables
            template_vars = self._prepare_template_vars(lead)

            # Render subject line
            subject_template = self.env.from_string(campaign.get("subject_template", ""))
            subject = subject_template.render(**template_vars)

            # Render email body
            body_template = self.env.from_string(campaign.get("body_template", ""))
            body = body_template.render(**template_vars)

            # Generate personalization payload (from spec)
            personalization = self._create_personalization_payload(lead)

            result_data = {
                "email": lead.get("best_email", lead.get("email")),
                "subject": subject,
                "body": body,
                "personalization": personalization,
                "campaign_id": campaign.get("id", "default"),
                "template_vars": template_vars,
            }

            return ToolResult(success=True, data=result_data)

        except Exception as e:
            logger.error(f"Copy rendering failed: {e}")
            return ToolResult(success=False, error=str(e))

    def _prepare_template_vars(self, lead: Dict[str, Any]) -> Dict[str, Any]:
        """Prepare template variables from lead data"""
        return {
            "first_name": self._extract_first_name(lead),
            "full_name": lead.get("name", lead.get("login", "there")),
            "company": lead.get("company", "your company"),
            "repo": lead.get("primary_repo", "your project"),
            "language": lead.get("primary_language", "Python"),
            "activity_days": lead.get("activity_90d", 30),
            "stars": lead.get("total_stars", 100),
            "followers": lead.get("followers", 0),
            "recent_pr": lead.get("recent_pr_title", "performance improvements"),
            "why_now": lead.get("why_now", "recent activity in your project"),
            "hook": lead.get("hook", "Nova can help with your development workflow"),
        }

    def _extract_first_name(self, lead: Dict[str, Any]) -> str:
        """Extract first name from lead data"""
        name = lead.get("name", lead.get("login", ""))
        if not name:
            return "there"

        # Split on spaces and take first part
        first_name = name.split()[0]
        return first_name if first_name else "there"

    def _get_default_campaign(self) -> Dict[str, str]:
        """Get default campaign templates"""
        return {
            "id": "default",
            "subject_template": "Quick fix for {{repo}} CI flakes",
            "body_template": """Hi {{first_name}},

I noticed {{repo}} has shown recent activity with {{language}} development. Nova is a small GitHub App that only wakes up when CI fails on a PR, pinpoints the cause, and pushes a minimal patch as a PR.

{{why_now}}

Zero lock-in, BYO API key, OSS license. Want a one-off trial on a test PR?

— Sebastian
{{unsub_link}}
""",
        }

    def _create_personalization_payload(self, lead: Dict[str, Any]) -> Dict[str, Any]:
        """Create personalization payload as specified in the CMO Agent spec"""
        return {
            "login": lead.get("login", ""),
            "name": lead.get("name", ""),
            "best_email": lead.get("best_email", lead.get("email", "")),
            "signals": {
                "maintainer_of": lead.get("maintainer_repos", []),
                "recent_pr_titles": lead.get("recent_pr_titles", []),
                "topics": lead.get("topics", []),
                "primary_language": lead.get("primary_language", "Python"),
                "activity_90d_commits": lead.get("activity_90d", 0),
                "followers": lead.get("followers", 0),
            },
            "snippets": {
                "why_now": lead.get("why_now", "Recent activity shows active development"),
                "hook": lead.get("hook", "Nova can help optimize your development workflow"),
            },
        }


class SendInstantly(InstantlyTool):
    """Instantly email sending tool"""

    def __init__(self, api_key: str):
        super().__init__(
            name="send_instantly",
            description="Send personalized emails via Instantly API",
            api_key=api_key
        )

    async def execute(self, contacts: List[Dict[str, Any]], seq_id: str, per_inbox_cap: int = 50, **kwargs) -> ToolResult:
        """Send emails via Instantly"""
        try:
            dry_run: bool = bool(kwargs.get("dry_run", False))
            job_id: str = (kwargs.get("job_id") or os.getenv("JOB_ID") or "job")
            # Validate inputs
            if not contacts:
                return ToolResult(success=False, error="No contacts provided")

            if not seq_id:
                return ToolResult(success=False, error="Sequence ID required")

            # Prepare contacts for Instantly API
            instantly_contacts = []
            for contact in contacts[:per_inbox_cap]:  # Respect per-inbox cap
                instantly_contact = {
                    "email": contact.get("email"),
                    "first_name": contact.get("first_name", ""),
                    "last_name": contact.get("last_name", ""),
                    "custom_subject": contact.get("subject", ""),
                    "custom_body": contact.get("body", ""),
                }

                # Add optional fields if available
                if contact.get("company"):
                    instantly_contact["company"] = contact["company"]
                if contact.get("linkedin"):
                    instantly_contact["linkedin"] = contact["linkedin"]

                instantly_contacts.append(instantly_contact)

            # Idempotency key per contact: job_id + email + seq_id
            for c in instantly_contacts:
                email = c.get("email") or ""
                c["idempotency_key"] = f"{job_id}:{seq_id}:{email}"

            # Dry-run: do not call Instantly; simulate a response
            if dry_run:
                campaign_id = f"dryrun-{seq_id}"
                send_result = {"status": "dry_run", "accepted": len(instantly_contacts)}
            else:
                # Check if we have a campaign, if not create one
                campaign_id = await self._get_or_create_campaign(seq_id)
                # Send contacts to Instantly
                send_result = await self._send_contacts(campaign_id, instantly_contacts)

            result_data = {
                "campaign_id": campaign_id,
                "contacts_sent": len(instantly_contacts),
                "contacts_attempted": len(contacts),
                "send_result": send_result,
                "seq_id": seq_id,
            }

            return ToolResult(success=True, data=result_data)

        except Exception as e:
            logger.error(f"Instantly send failed: {e}")
            return ToolResult(success=False, error=str(e))

    async def _get_or_create_campaign(self, seq_id: str) -> str:
        """Get existing campaign or create new one via Instantly API v2.

        Notes:
        - This uses common Instantly patterns: list campaigns and match by name,
          otherwise create. If your account uses different endpoints, you'll get
          a clear error message.
        """
        import aiohttp
        try:
            base = self.base_url
            headers = {
                "X-API-KEY": self.api_key,
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
                "Accept": "application/json",
            }

            # If INSTANTLY_CAMPAIGN_ID is set, prefer it directly
            forced_id = os.getenv("INSTANTLY_CAMPAIGN_ID")
            if forced_id:
                return forced_id

            # Try to find by name
            list_url = f"{base}/campaigns"
            async with aiohttp.ClientSession() as session:
                async with session.get(list_url, headers=headers) as resp:
                    data = await resp.json()
                    if resp.status == 200 and isinstance(data, dict):
                        for c in data.get("campaigns", []):
                            if c.get("name") == seq_id:
                                return c.get("id")

            # Create campaign
            create_url = f"{base}/campaigns"
            # Minimal required fields – some accounts require schedule; default to draft
            payload = {"name": seq_id, "campaign_schedule": {"status": "paused"}}
            async with aiohttp.ClientSession() as session:
                async with session.post(create_url, headers=headers, json=payload) as resp:
                    data = await resp.json()
                    if resp.status >= 400:
                        raise Exception(f"Instantly create campaign failed: {data}")
                    return data.get("id") or data.get("campaign", {}).get("id")
        except Exception as e:
            logger.error(f"Campaign creation/lookup failed: {e}")
            raise

    async def _send_contacts(self, campaign_id: str, contacts: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Send contacts to Instantly campaign via API v2."""
        import aiohttp
        try:
            base = self.base_url
            headers = {"X-API-KEY": self.api_key, "Content-Type": "application/json"}

            url = f"{base}/campaigns/{campaign_id}/leads/bulk"
            payload = {"leads": contacts}
            async with aiohttp.ClientSession() as session:
                async with session.post(url, headers=headers, json=payload) as resp:
                    data = await resp.json()
                    if resp.status >= 400:
                        raise Exception(f"Instantly add leads failed: {data}")
                    return data
        except Exception as e:
            logger.error(f"Contact sending failed: {e}")
            raise
