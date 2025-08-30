"""
CRM and ticketing tools
"""
import logging
import sys
import os
import json
from typing import Dict, Any, List

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

        class AttioTool:
            def __init__(self, name: str, description: str, api_key: str, workspace_id: str):
                self.name = name
                self.description = description
                self.api_key = api_key
                self.workspace_id = workspace_id

        class LinearTool:
            def __init__(self, name: str, description: str, api_key: str):
                self.name = name
                self.description = description
                self.api_key = api_key

logger = logging.getLogger(__name__)


class SyncAttio(AttioTool):
    """Attio CRM synchronization tool"""

    def __init__(self, api_key: str, workspace_id: str):
        super().__init__(
            name="sync_attio",
            description="Sync people and campaign data to Attio CRM",
            api_key=api_key,
            workspace_id=workspace_id
        )

    async def execute(self, people: List[Dict[str, Any]], list_id: str, **kwargs) -> ToolResult:
        """Sync people to Attio CRM (real API).

        Steps per person:
        - Upsert People record via Attio REST API
        - Best-effort add to list (if provided)
        - Create a simple note describing the action
        """
        try:
            synced_people = []
            errors = []

            for person in people:
                try:
                    # Create or update person in Attio
                    attio_person = await self._upsert_person(person)

                    # Add to campaign list (best-effort; ignore if list API not configured)
                    try:
                        if list_id:
                            await self._add_to_list(attio_person["id"], list_id)
                    except Exception as list_err:
                        logger.warning(f"Attio list add failed for {person.get('email')}: {list_err}")

                    # Create signal note (best-effort)
                    try:
                        await self._create_signal_note(attio_person["id"], person)
                    except Exception as note_err:
                        logger.warning(f"Attio note create failed for {person.get('email')}: {note_err}")

                    synced_people.append({
                        "original_email": person.get("email"),
                        "attio_id": attio_person["id"],
                        "status": "synced",
                    })

                except Exception as e:
                    logger.error(f"Failed to sync person {person.get('email')}: {e}")
                    errors.append({
                        "email": person.get("email"),
                        "error": str(e),
                    })
                    continue

            result_data = {
                "synced_count": len(synced_people),
                "error_count": len(errors),
                "total_attempted": len(people),
                "synced_people": synced_people,
                "errors": errors,
                "list_id": list_id,
            }

            return ToolResult(success=True, data=result_data)

        except Exception as e:
            logger.error(f"Attio sync failed: {e}")
            return ToolResult(success=False, error=str(e))

    async def _upsert_person(self, person_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a People record in Attio.

        Note: We use a create-first approach; Attio will prevent exact duplicates
        depending on your schema. If needed, extend with a lookup using the
        records query endpoint.
        """
        import aiohttp

        try:
            full_name = person_data.get("name") or " ".join(
                [
                    str(person_data.get("first_name", "")).strip(),
                    str(person_data.get("last_name", "")).strip(),
                ]
            ).strip()
            payload = {
                "data": {
                    "values": {
                        # Use Attio value wrapper schema aligned with setup_attio_objects.py
                        "email_addresses": (
                            [{"email_address": person_data.get("email")}] if person_data.get("email") else []
                        ),
                        # Attio "name" typed attribute expects the structured object
                        "name": {
                            "first_name": person_data.get("first_name", "").strip() or None,
                            "last_name": person_data.get("last_name", "").strip() or None,
                            "full_name": (full_name or person_data.get("login", "")).strip() or None,
                        },
                    }
                }
            }

            # Optional safe text fields (commented out due to workspace schema variance)
            # Only include simple attributes known to exist to avoid validation errors.
            # If your People object includes these with text types, you can uncomment.
            # if person_data.get("company"):
            #     payload["data"]["values"]["company"] = {"value": person_data["company"]}
            # if person_data.get("location"):
            #     payload["data"]["values"]["location"] = {"value": person_data["location"]}

            url = f"{self.base_url}/objects/people/records"
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            }

            async with aiohttp.ClientSession() as session:
                async with session.post(url, headers=headers, json=payload) as resp:
                    # If exists, Attio may return 409 or 400; try a tolerant parse
                    if resp.status >= 400:
                        text = await resp.text()
                        raise Exception(f"Attio create failed: {resp.status} {text}")
                    data = await resp.json()

            attio_id = (
                data.get("data", {}).get("id", {}).get("value")
                if isinstance(data, dict)
                else None
            )
            return {"id": attio_id or "unknown", "created": True}

        except Exception as e:
            logger.error(f"Person upsert failed: {e}")
            raise

    async def _add_to_list(self, person_id: str, list_id: str):
        """Add person to Attio list (best-effort).

        API shape can vary by workspace configuration. We attempt the common
        v2 pattern: POST /lists/{list_id}/entries with the People record.
        """
        import aiohttp

        try:
            url = f"{self.base_url}/lists/{list_id}/entries"
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            }
            payload = {
                "data": {
                    "object": "people",
                    "record_id": person_id,
                }
            }
            async with aiohttp.ClientSession() as session:
                async with session.post(url, headers=headers, json=payload) as resp:
                    if resp.status >= 400:
                        text = await resp.text()
                        raise Exception(f"{resp.status} {text}")
            logger.info(f"Added person {person_id} to list {list_id}")
        except Exception as e:
            logger.error(f"List addition failed: {e}")
            raise

    async def _create_signal_note(self, person_id: str, person_data: Dict[str, Any]):
        """Create note for the person via Attio Notes API."""
        import aiohttp

        try:
            note_content = (
                "Cold email scheduled for campaign outreach.\n\n"
                f"Profile: {person_data.get('name', 'Unknown')} ({person_data.get('login', 'Unknown')})\n"
                f"Company: {person_data.get('company', 'Unknown')}\n"
                f"Primary Repo: {person_data.get('primary_repo', 'Unknown')}\n"
                f"Activity: {person_data.get('activity_90d', 0)} commits in last 90 days\n"
            )

            url = f"{self.base_url}/notes"
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            }
            payload = {
                "data": {
                    "parent_object": "people",
                    "parent_record_id": person_id,
                    "title": "Outreach scheduled",
                    "content": note_content,
                }
            }
            async with aiohttp.ClientSession() as session:
                async with session.post(url, headers=headers, json=payload) as resp:
                    if resp.status >= 400:
                        text = await resp.text()
                        raise Exception(f"{resp.status} {text}")
            logger.info(f"Created signal note for person {person_id}")
        except Exception as e:
            logger.error(f"Signal note creation failed: {e}")
            raise


class SyncLinear(LinearTool):
    """Linear ticketing tool"""

    def __init__(self, api_key: str):
        super().__init__(
            name="sync_linear",
            description="Create Linear issues for campaign tracking and error handling",
            api_key=api_key
        )

    async def execute(self, parent_title: str, events: List[Dict[str, Any]], **kwargs) -> ToolResult:
        """Create Linear issues for campaign events (real API)."""
        try:
            team_key = kwargs.get("team_key") or os.getenv("LINEAR_TEAM_KEY")
            team_id = kwargs.get("team_id") or os.getenv("LINEAR_TEAM_ID")
            if not team_id:
                team_id = await self._resolve_team_id_by_key(team_key) if team_key else None

            # Create parent campaign issue
            parent_issue = await self._create_parent_issue(parent_title, team_id)

            # Create child issues for events
            child_issues = []
            for event in events:
                try:
                    child_issue = await self._create_child_issue(parent_issue["id"], team_id, event)
                    child_issues.append(child_issue)
                except Exception as e:
                    logger.error(f"Failed to create child issue for event: {e}")
                    continue

            result_data = {
                "parent_issue": parent_issue,
                "child_issues": child_issues,
                "child_count": len(child_issues),
                "events_attempted": len(events),
            }

            return ToolResult(success=True, data=result_data)

        except Exception as e:
            logger.error(f"Linear sync failed: {e}")
            return ToolResult(success=False, error=str(e))

    async def _create_parent_issue(self, title: str, team_id: str | None) -> Dict[str, Any]:
        """Create parent campaign issue via Linear GraphQL."""
        import aiohttp
        try:
            if not team_id:
                raise Exception("Missing Linear team_id; set LINEAR_TEAM_KEY or LINEAR_TEAM_ID")

            query = {
                "query": """
                mutation IssueCreate($input: IssueCreateInput!) {
                  issueCreate(input: $input) {
                    success
                    issue { id identifier url title }
                  }
                }
                """,
                "variables": {
                    "input": {"teamId": team_id, "title": title}
                },
            }
            headers = {
                "Authorization": self.api_key,
                "Content-Type": "application/json",
            }
            async with aiohttp.ClientSession() as session:
                async with session.post(self.base_url, headers=headers, json=query) as resp:
                    data = await resp.json()
                    if resp.status >= 400 or not data.get("data", {}).get("issueCreate", {}).get("success"):
                        raise Exception(f"Linear issueCreate failed: {data}")
                    issue = data["data"]["issueCreate"]["issue"]
                    return issue
        except Exception as e:
            logger.error(f"Parent issue creation failed: {e}")
            raise

    async def _create_child_issue(self, parent_id: str, team_id: str, event: Dict[str, Any]) -> Dict[str, Any]:
        """Create child issue for specific event via Linear GraphQL."""
        import aiohttp
        try:
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
                "query": """
                mutation IssueCreate($input: IssueCreateInput!) {
                  issueCreate(input: $input) {
                    success
                    issue { id identifier url title }
                  }
                }
                """,
                "variables": {
                    "input": {
                        "teamId": team_id,
                        "title": title,
                        "description": description,
                        "parentId": parent_id,
                    }
                },
            }
            headers = {
                "Authorization": self.api_key,
                "Content-Type": "application/json",
            }
            async with aiohttp.ClientSession() as session:
                async with session.post(self.base_url, headers=headers, json=query) as resp:
                    data = await resp.json()
                    if resp.status >= 400 or not data.get("data", {}).get("issueCreate", {}).get("success"):
                        raise Exception(f"Linear child issueCreate failed: {data}")
                    issue = data["data"]["issueCreate"]["issue"]
                    issue["parent_id"] = parent_id
                    return issue
        except Exception as e:
            logger.error(f"Child issue creation failed: {e}")
            raise

    async def _resolve_team_id_by_key(self, team_key: str) -> str:
        """Resolve Linear team ID by short key (e.g., OS)."""
        import aiohttp
        try:
            if not team_key:
                raise Exception("team_key required to resolve team id")
            query = {
                "query": """
                query TeamByKey($key: String!) {
                  teams(filter: { key: { eq: $key } }, first: 1) {
                    nodes { id key name }
                  }
                }
                """,
                "variables": {"key": team_key},
            }
            headers = {
                "Authorization": self.api_key,
                "Content-Type": "application/json",
            }
            async with aiohttp.ClientSession() as session:
                async with session.post(self.base_url, headers=headers, json=query) as resp:
                    data = await resp.json()
                    nodes = data.get("data", {}).get("teams", {}).get("nodes", [])
                    if not nodes:
                        raise Exception(f"Linear team with key {team_key} not found")
                    return nodes[0]["id"]
        except Exception as e:
            logger.error(f"Resolve team id failed: {e}")
            raise
