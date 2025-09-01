"""
CRM and ticketing tools (real API implementations)
"""
import logging
import sys
import os
from typing import Dict, Any, List, Optional

# Add current directory to path for imports
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

try:
    from .base import AttioTool, LinearTool, ToolResult
except ImportError:
    try:
        from base import AttioTool, LinearTool, ToolResult
    except ImportError:
        # Minimal fallbacks
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

        class AttioTool:
            def __init__(self, name: str, description: str, api_key: str, workspace_id: str):
                self.name = name
                self.description = description
                self.api_key = api_key
                self.workspace_id = workspace_id
                self.base_url = "https://api.attio.com/v2"

        class LinearTool:
            def __init__(self, name: str, description: str, api_key: str):
                self.name = name
                self.description = description
                self.api_key = api_key
                self.base_url = "https://api.linear.app/graphql"

logger = logging.getLogger(__name__)


class SyncAttio(AttioTool):
    """Attio CRM synchronization tool (real API)"""

    def __init__(self, api_key: str, workspace_id: str):
        super().__init__(
            name="sync_attio",
            description="Sync people and campaign data to Attio CRM",
            api_key=api_key,
            workspace_id=workspace_id,
        )

    async def execute(self, people: List[Dict[str, Any]], list_id: str, **kwargs) -> ToolResult:
        """Sync people to Attio:
        - Create (or find existing by email) People records
        - Best-effort add to a list and create a note
        """
        try:
            dry_run: bool = bool(kwargs.get("dry_run", False))
            job_id: str = (kwargs.get("job_id") or os.getenv("JOB_ID") or "job")
            synced_people: List[Dict[str, Any]] = []
            errors: List[Dict[str, str]] = []

            for person in people:
                try:
                    # Idempotency key for CRM upsert
                    email = person.get("email") or ""
                    idem_key = f"{job_id}:{email}" if email else f"{job_id}:noemail:{person.get('login','') }"

                    if dry_run:
                        record = {"id": f"dryrun-{email or 'unknown'}", "created": False}
                    else:
                        record = await self._upsert_person(person)

                    # Best-effort list add and note
                    if record["id"] and record["id"] != "unknown":
                        if list_id:
                            try:
                                if not dry_run:
                                    await self._add_to_list(record["id"], list_id)
                            except Exception as e:
                                logger.warning(f"Attio list add failed: {e}")
                        try:
                            if not dry_run:
                                await self._create_signal_note(record["id"], person)
                        except Exception as e:
                            logger.warning(f"Attio note create failed: {e}")

                    synced_people.append({
                        "original_email": person.get("email"),
                        "attio_id": record["id"],
                        "status": "synced",
                        "idempotency_key": idem_key,
                    })
                except Exception as e:
                    logger.error(f"Failed to sync person {person.get('email')}: {e}")
                    errors.append({"email": person.get("email", ""), "error": str(e)})

            return ToolResult(
                success=True,
                data={
                    "synced_count": len(synced_people),
                    "error_count": len(errors),
                    "total_attempted": len(people),
                    "synced_people": synced_people,
                    "errors": errors,
                    "list_id": list_id,
                },
            )
        except Exception as e:
            logger.error(f"Attio sync failed: {e}")
            return ToolResult(success=False, error=str(e))

    async def _upsert_person(self, person: Dict[str, Any]) -> Dict[str, Any]:
        """Create a People record, or find existing by email on uniqueness conflict."""
        import aiohttp

        email: Optional[str] = person.get("email")
        full_name: str = (person.get("name") or person.get("login") or "").strip()
        payload = {
            "data": {
                "values": {
                    # Attio email field shape
                    "email_addresses": ([{"email_address": email}] if email else []),
                    # Name structured input; include all keys as empty strings if absent
                    "name": {
                        "first_name": (person.get("first_name") or ""),
                        "last_name": (person.get("last_name") or ""),
                        "full_name": full_name,
                    },
                }
            }
        }

        url = f"{self.base_url}/objects/people/records"
        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}

        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=headers, json=payload) as resp:
                text = await resp.text()
                if resp.status >= 400:
                    # Uniqueness conflict (email exists) → lookup and reuse existing
                    if "uniqueness" in text or "conflict" in text:
                        existing_id = await self._find_person_by_email(session, headers, email)
                        if existing_id:
                            return {"id": existing_id, "created": False}
                        # Treat as success with unknown id to proceed
                        return {"id": "unknown", "created": False}
                    raise Exception(f"Attio create failed: {resp.status} {text}")
                data = await resp.json()

        attio_id = (
            data.get("data", {}).get("id", {}).get("value") if isinstance(data, dict) else None
        )
        return {"id": attio_id or "unknown", "created": True}

    async def _find_person_by_email(self, session, headers: Dict[str, Any], email: Optional[str]) -> Optional[str]:
        if not email:
            return None
        url = f"{self.base_url}/objects/people/records"
        params = {"filter[email_addresses.email_address][eq]": email, "limit": 1}
        async with session.get(url, headers=headers, params=params) as resp:
            if resp.status >= 400:
                return None
            data = await resp.json()
            records = data.get("data", [])
            if records:
                return records[0].get("id", {}).get("value")
            return None

    async def _add_to_list(self, person_id: str, list_id: str):
        """Add People record to an Attio list (best-effort)."""
        import aiohttp

        url = f"{self.base_url}/lists/{list_id}/entries"
        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
        payload = {"data": {"object": "people", "record_id": person_id}}
        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=headers, json=payload) as resp:
                if resp.status >= 400:
                    text = await resp.text()
                    raise Exception(f"{resp.status} {text}")
        logger.info(f"Added person {person_id} to list {list_id}")

    async def _create_signal_note(self, person_id: str, person: Dict[str, Any]):
        """Create a note on the People record (best-effort)."""
        import aiohttp

        note_content = (
            "Cold email scheduled for campaign outreach.\n\n"
            f"Profile: {person.get('name', 'Unknown')} ({person.get('login', 'Unknown')})\n"
            f"Primary Repo: {person.get('primary_repo', 'Unknown')}\n"
            f"Activity: {person.get('activity_90d', 0)} commits in last 90 days\n"
        )
        url = f"{self.base_url}/notes"
        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
        payload = {
            "data": {
                "parent_object": "people",
                "parent_record_id": person_id,
                "title": "Outreach scheduled",
                "content": note_content,
                "format": "plaintext",
            }
        }
        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=headers, json=payload) as resp:
                if resp.status >= 400:
                    text = await resp.text()
                    raise Exception(f"{resp.status} {text}")
        logger.info(f"Created note for person {person_id}")


class SyncLinear(LinearTool):
    """Linear ticketing tool (real GraphQL)"""

    def __init__(self, api_key: str):
        super().__init__(
            name="sync_linear",
            description="Create Linear issues for campaign tracking and error handling",
            api_key=api_key,
        )

    async def execute(self, parent_title: str, events: List[Dict[str, Any]], **kwargs) -> ToolResult:
        try:
            dry_run: bool = bool(kwargs.get("dry_run", False))
            job_id: str = (kwargs.get("job_id") or os.getenv("JOB_ID") or "job")
            team_key = kwargs.get("team_key") or os.getenv("LINEAR_TEAM_KEY")
            team_id = kwargs.get("team_id") or os.getenv("LINEAR_TEAM_ID")
            if not team_id and team_key:
                team_id = await self._resolve_team_id_by_key(team_key)
            if not team_id:
                raise Exception("Missing LINEAR_TEAM_ID/LINEAR_TEAM_KEY")

            if dry_run:
                parent_issue = {"id": f"dryrun-parent-{job_id}", "title": parent_title, "url": ""}
            else:
                # Try to find existing open parent issue with same title to avoid duplicates
                parent_issue = await self._find_existing_parent_issue(parent_title, team_id) or await self._create_parent_issue(parent_title, team_id)

            child_issues = []
            seen_child_keys = set()
            for event in events:
                try:
                    if dry_run:
                        # Stable idempotency key per event
                        key = f"{job_id}:{event.get('type','event')}:{event.get('error_type') or event.get('event_type') or ''}"
                        if key in seen_child_keys:
                            continue
                        seen_child_keys.add(key)
                        child = {"id": f"dryrun-{key}", "parent_id": parent_issue["id"], "title": parent_title}
                    else:
                        # Avoid creating duplicate child issues with same signature under the parent
                        key = f"{event.get('type','event')}:{event.get('error_type') or event.get('event_type') or ''}"
                        if key in seen_child_keys:
                            continue
                        existing = await self._find_existing_child_issue(parent_issue["id"], team_id, event)
                        if existing:
                            child = existing
                        else:
                            child = await self._create_child_issue(parent_issue["id"], team_id, event)
                        seen_child_keys.add(key)
                    child_issues.append(child)
                except Exception as e:
                    logger.error(f"Failed to create child issue: {e}")

            return ToolResult(success=True, data={
                "parent_issue": parent_issue,
                "child_issues": child_issues,
                "child_count": len(child_issues),
                "events_attempted": len(events),
            })
        except Exception as e:
            logger.error(f"Linear sync failed: {e}")
            return ToolResult(success=False, error=str(e))

    async def _find_existing_parent_issue(self, title: str, team_id: str) -> Optional[Dict[str, Any]]:
        """Search for an existing open parent issue with the given title."""
        import aiohttp
        headers = {"Authorization": self.api_key, "Content-Type": "application/json"}
        query = {
            "query": (
                "query Issues($query: String!, $first: Int!) {"
                "  issues(filter: { title: { eq: $query } }, first: $first) { nodes { id identifier url title state { type } team { id } } }"
                "}"
            ),
            "variables": {"query": title, "first": 10},
        }
        async with aiohttp.ClientSession() as session:
            async with session.post(self.base_url, headers=headers, json=query) as resp:
                data = await resp.json()
                nodes = data.get("data", {}).get("issues", {}).get("nodes", [])
                for node in nodes:
                    if node.get("team", {}).get("id") == team_id and node.get("state", {}).get("type") in ("started", "triage", "backlog"):
                        return {"id": node.get("id"), "identifier": node.get("identifier"), "url": node.get("url"), "title": node.get("title")}
        return None

    async def _find_existing_child_issue(self, parent_id: str, team_id: str, event: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Best-effort search for an existing child under parent with similar title."""
        import aiohttp
        headers = {"Authorization": self.api_key, "Content-Type": "application/json"}
        event_type = event.get("type", "error")
        title = (f"Error: {event.get('error_type', 'Unknown error')}" if event_type == "error" else f"Event: {event.get('event_type', 'Unknown event')}")
        query = {
            "query": (
                "query Issues($first: Int!, $title: String!) {"
                "  issues(filter: { title: { eq: $title } }, first: $first) { nodes { id identifier url title parent { id } team { id } } }"
                "}"
            ),
            "variables": {"title": title, "first": 20},
        }
        async with aiohttp.ClientSession() as session:
            async with session.post(self.base_url, headers=headers, json=query) as resp:
                data = await resp.json()
                nodes = data.get("data", {}).get("issues", {}).get("nodes", [])
                for node in nodes:
                    if node.get("team", {}).get("id") == team_id and node.get("parent", {}).get("id") == parent_id:
                        issue = {"id": node.get("id"), "identifier": node.get("identifier"), "url": node.get("url"), "title": node.get("title"), "parent_id": parent_id}
                        return issue
        return None

    async def _create_parent_issue(self, title: str, team_id: str) -> Dict[str, Any]:
        import aiohttp

        query = {
            "query": (
                "mutation IssueCreate($input: IssueCreateInput!) {"
                "  issueCreate(input: $input) { success issue { id identifier url title } }"
                "}"
            ),
            "variables": {"input": {"teamId": team_id, "title": title}},
        }
        headers = {"Authorization": self.api_key, "Content-Type": "application/json"}
        async with aiohttp.ClientSession() as session:
            async with session.post(self.base_url, headers=headers, json=query) as resp:
                data = await resp.json()
                node = data.get("data", {}).get("issueCreate", {})
                if resp.status >= 400 or not node.get("success"):
                    raise Exception(f"Linear issueCreate failed: {data}")
                return node["issue"]

    async def _create_child_issue(self, parent_id: str, team_id: str, event: Dict[str, Any]) -> Dict[str, Any]:
        import aiohttp

        event_type = event.get("type", "error")
        if event_type == "error":
            title = f"Error: {event.get('error_type', 'Unknown error')}"
            description = (
                "Campaign error occurred.\n\n"
                f"Error: {event.get('error_message', 'Unknown error')}\n"
                f"Context: {event.get('context', 'No additional context')}\n"
                f"Timestamp: {event.get('timestamp', 'Unknown time')}\n\n"
                "Please investigate and resolve.\n"
            )
        else:
            title = f"Event: {event.get('event_type', 'Unknown event')}"
            description = (
                "Campaign event logged.\n\n"
                f"Details: {event.get('details', 'No details provided')}\n"
                f"Timestamp: {event.get('timestamp', 'Unknown time')}\n"
            )

        query = {
            "query": (
                "mutation IssueCreate($input: IssueCreateInput!) {"
                "  issueCreate(input: $input) { success issue { id identifier url title } }"
                "}"
            ),
            "variables": {
                "input": {
                    "teamId": team_id,
                    "title": title,
                    "description": description,
                    "parentId": parent_id,
                }
            },
        }
        headers = {"Authorization": self.api_key, "Content-Type": "application/json"}
        async with aiohttp.ClientSession() as session:
            async with session.post(self.base_url, headers=headers, json=query) as resp:
                data = await resp.json()
                node = data.get("data", {}).get("issueCreate", {})
                if resp.status >= 400 or not node.get("success"):
                    raise Exception(f"Linear child issueCreate failed: {data}")
                issue = node["issue"]
                issue["parent_id"] = parent_id
                return issue

    async def _resolve_team_id_by_key(self, team_key: str) -> str:
        import aiohttp

        headers = {"Authorization": self.api_key, "Content-Type": "application/json"}
        query = {
            "query": "query TeamByKey($key: String!) { teams(filter: { key: { eq: $key } }, first: 1) { nodes { id key name } } }",
            "variables": {"key": team_key},
        }
        async with aiohttp.ClientSession() as session:
            async with session.post(self.base_url, headers=headers, json=query) as resp:
                data = await resp.json()
                nodes = data.get("data", {}).get("teams", {}).get("nodes", [])
                if nodes:
                    return nodes[0]["id"]
            # Fallback list
            list_query = {"query": "query { teams(first: 50) { nodes { id key name } } }"}
            async with session.post(self.base_url, headers=headers, json=list_query) as resp2:
                data2 = await resp2.json()
                nodes2 = data2.get("data", {}).get("teams", {}).get("nodes", [])
                for t in nodes2:
                    if t.get("key") == team_key:
                        return t.get("id")
        raise Exception(f"Linear team with key {team_key} not found")
