"""
CRM and ticketing tools
"""
import logging
import json
from typing import Dict, Any, List
try:
    from .base import AttioTool, LinearTool, ToolResult
except ImportError:
    from base import AttioTool, LinearTool, ToolResult

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
        """Sync people to Attio CRM"""
        try:
            synced_people = []
            errors = []

            for person in people:
                try:
                    # Create or update person in Attio
                    attio_person = await self._upsert_person(person)

                    # Add to campaign list
                    await self._add_to_list(attio_person["id"], list_id)

                    # Create signal note
                    await self._create_signal_note(attio_person["id"], person)

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
        """Create or update person in Attio"""
        try:
            # Prepare person data for Attio
            attio_person = {
                "data": {
                    "email_addresses": [{"email_address": person_data.get("email")}],
                    "first_name": person_data.get("first_name", ""),
                    "last_name": person_data.get("last_name", ""),
                }
            }

            # Add optional fields
            if person_data.get("company"):
                attio_person["data"]["company"] = person_data["company"]

            if person_data.get("location"):
                attio_person["data"]["location"] = person_data["location"]

            # This would make actual Attio API call
            # For now, return mock response
            return {
                "id": f"person_{hash(person_data.get('email', '')) % 10000}",
                "created": True,
            }

        except Exception as e:
            logger.error(f"Person upsert failed: {e}")
            raise

    async def _add_to_list(self, person_id: str, list_id: str):
        """Add person to Attio list"""
        try:
            # This would make actual Attio API call to add person to list
            # For now, just log the action
            logger.info(f"Added person {person_id} to list {list_id}")
        except Exception as e:
            logger.error(f"List addition failed: {e}")
            raise

    async def _create_signal_note(self, person_id: str, person_data: Dict[str, Any]):
        """Create signal note for the person"""
        try:
            note_content = f"""Cold email scheduled for campaign outreach.

Profile: {person_data.get('name', 'Unknown')} ({person_data.get('login', 'Unknown')})
Company: {person_data.get('company', 'Unknown')}
Primary Repo: {person_data.get('primary_repo', 'Unknown')}
Activity: {person_data.get('activity_90d', 0)} commits in last 90 days
"""

            # This would make actual Attio API call to create note
            # For now, just log the action
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
        """Create Linear issues for campaign events"""
        try:
            # Create parent campaign issue
            parent_issue = await self._create_parent_issue(parent_title)

            # Create child issues for events
            child_issues = []
            for event in events:
                try:
                    child_issue = await self._create_child_issue(parent_issue["id"], event)
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

    async def _create_parent_issue(self, title: str) -> Dict[str, Any]:
        """Create parent campaign issue"""
        try:
            # This would make actual Linear GraphQL mutation
            # For now, return mock response
            return {
                "id": f"issue_{hash(title) % 10000}",
                "identifier": f"CMO-{hash(title) % 1000}",
                "url": f"https://linear.app/issue/CMO-{hash(title) % 1000}",
                "title": title,
            }
        except Exception as e:
            logger.error(f"Parent issue creation failed: {e}")
            raise

    async def _create_child_issue(self, parent_id: str, event: Dict[str, Any]) -> Dict[str, Any]:
        """Create child issue for specific event"""
        try:
            event_type = event.get("type", "error")
            if event_type == "error":
                title = f"Error: {event.get('error_type', 'Unknown error')}"
                description = f"""Campaign error occurred.

Error: {event.get('error_message', 'Unknown error')}
Context: {event.get('context', 'No additional context')}
Timestamp: {event.get('timestamp', 'Unknown time')}

Please investigate and resolve.
"""
            else:
                title = f"Event: {event.get('event_type', 'Unknown event')}"
                description = f"""Campaign event logged.

Details: {event.get('details', 'No details provided')}
Timestamp: {event.get('timestamp', 'Unknown time')}
"""

            # This would make actual Linear GraphQL mutation
            # For now, return mock response
            return {
                "id": f"child_{hash(title + parent_id) % 10000}",
                "identifier": f"CMO-{hash(title + parent_id) % 1000}",
                "url": f"https://linear.app/issue/CMO-{hash(title + parent_id) % 1000}",
                "title": title,
                "parent_id": parent_id,
            }
        except Exception as e:
            logger.error(f"Child issue creation failed: {e}")
            raise
