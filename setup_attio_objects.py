#!/usr/bin/env python3
"""
Setup Attio objects for Lead Intelligence integration
Creates required objects (People, Repos, Signals) if they don't exist
"""

import os
import json
import requests
from typing import Dict, List, Any, Optional

class AttioObjectManager:
    """Manages Attio object creation and validation"""

    def __init__(self, api_token: str, workspace_id: str):
        self.api_token = api_token
        self.workspace_id = workspace_id
        self.base_url = 'https://api.attio.com/v2'
        self.session = requests.Session()
        self.session.headers.update({
            'Authorization': f'Bearer {api_token}',
            'Content-Type': 'application/json'
        })

    def _make_request(self, method: str, endpoint: str, data: Optional[Dict] = None) -> Dict[str, Any]:
        """Make authenticated request to Attio API"""
        url = f"{self.base_url}{endpoint}"
        response = self.session.request(method, url, json=data)
        response.raise_for_status()
        return response.json()

    def get_objects(self) -> List[Dict[str, Any]]:
        """Get all objects in the workspace"""
        try:
            response = self._make_request('GET', '/objects')
            return response.get('data', [])
        except Exception as e:
            print(f"Error getting objects: {e}")
            return []

    def get_object(self, object_id: str) -> Optional[Dict[str, Any]]:
        """Get specific object details"""
        try:
            response = self._make_request('GET', f'/objects/{object_id}')
            return response.get('data')
        except Exception as e:
            print(f"Error getting object {object_id}: {e}")
            return None

    def create_object(self, name: str, description: str, attributes: List[Dict[str, Any]]) -> Optional[str]:
        """Create a new object"""
        try:
            data = {
                "api_slug": name.lower().replace(' ', '_'),
                "name": name,
                "description": description,
                "singular_name": name.rstrip('s'),
                "attributes": attributes
            }
            response = self._make_request('POST', '/objects', data)
            object_id = response.get('data', {}).get('id', {}).get('value')
            print(f"✅ Created object: {name} (ID: {object_id})")
            return object_id
        except Exception as e:
            print(f"❌ Error creating object {name}: {e}")
            return None

    def create_attribute(self, object_id: str, name: str, type_name: str, config: Dict[str, Any]) -> Optional[str]:
        """Create an attribute for an object"""
        try:
            data = {
                "api_slug": name.lower().replace(' ', '_'),
                "name": name,
                "type": type_name,
                "is_required": False,
                "config": config
            }
            response = self._make_request('POST', f'/objects/{object_id}/attributes', data)
            attr_id = response.get('data', {}).get('id', {}).get('value')
            print(f"  ✅ Created attribute: {name}")
            return attr_id
        except Exception as e:
            print(f"  ❌ Error creating attribute {name}: {e}")
            return None

def setup_people_object(manager: AttioObjectManager) -> bool:
    """Setup People object with required attributes"""
    print("🔍 Checking People object...")

    objects = manager.get_objects()
    people_object = next((obj for obj in objects if obj.get('api_slug') == 'people'), None)

    if people_object:
        print("✅ People object already exists")
        return True

    # Create People object
    people_attributes = [
        {"api_slug": "login", "name": "Login", "type": "text", "is_required": False, "config": {}},
        {"api_slug": "name", "name": "Name", "type": "text", "is_required": False, "config": {}},
        {"api_slug": "company", "name": "Company", "type": "text", "is_required": False, "config": {}},
        {"api_slug": "location", "name": "Location", "type": "text", "is_required": False, "config": {}},
        {"api_slug": "bio", "name": "Bio", "type": "text", "is_required": False, "config": {}},
        {"api_slug": "email_addresses", "name": "Email Addresses", "type": "email", "is_required": False, "config": {}},
        {"api_slug": "html_url", "name": "GitHub URL", "type": "url", "is_required": False, "config": {}},
        {"api_slug": "public_repos", "name": "Public Repos", "type": "number", "is_required": False, "config": {}},
        {"api_slug": "followers", "name": "Followers", "type": "number", "is_required": False, "config": {}},
        {"api_slug": "created_at", "name": "Created At", "type": "date-time", "is_required": False, "config": {}},
        {"api_slug": "updated_at", "name": "Updated At", "type": "date-time", "is_required": False, "config": {}}
    ]

    object_id = manager.create_object("People", "GitHub users and maintainers", people_attributes)
    return object_id is not None

def setup_repos_object(manager: AttioObjectManager) -> bool:
    """Setup Repos object with required attributes"""
    print("🔍 Checking Repos object...")

    objects = manager.get_objects()
    repos_object = next((obj for obj in objects if obj.get('api_slug') == 'repos'), None)

    if repos_object:
        print("✅ Repos object already exists")
        return True

    # Create Repos object
    repos_attributes = [
        {"api_slug": "repo_full_name", "name": "Full Name", "type": "text", "is_required": True, "config": {}},
        {"api_slug": "repo_name", "name": "Name", "type": "text", "is_required": False, "config": {}},
        {"api_slug": "owner_login", "name": "Owner", "type": "text", "is_required": False, "config": {}},
        {"api_slug": "description", "name": "Description", "type": "text", "is_required": False, "config": {}},
        {"api_slug": "primary_language", "name": "Language", "type": "text", "is_required": False, "config": {}},
        {"api_slug": "stars", "name": "Stars", "type": "number", "is_required": False, "config": {}},
        {"api_slug": "forks", "name": "Forks", "type": "number", "is_required": False, "config": {}},
        {"api_slug": "watchers", "name": "Watchers", "type": "number", "is_required": False, "config": {}},
        {"api_slug": "html_url", "name": "GitHub URL", "type": "url", "is_required": False, "config": {}},
        {"api_slug": "topics", "name": "Topics", "type": "text", "is_required": False, "config": {}},
        {"api_slug": "has_ci", "name": "Has CI", "type": "checkbox", "is_required": False, "config": {}},
        {"api_slug": "created_at", "name": "Created At", "type": "date-time", "is_required": False, "config": {}},
        {"api_slug": "updated_at", "name": "Updated At", "type": "date-time", "is_required": False, "config": {}}
    ]

    object_id = manager.create_object("Repos", "GitHub repositories", repos_attributes)
    return object_id is not None

def setup_signals_object(manager: AttioObjectManager) -> bool:
    """Setup Signals object with required attributes"""
    print("🔍 Checking Signals object...")

    objects = manager.get_objects()
    signals_object = next((obj for obj in objects if obj.get('api_slug') == 'signals'), None)

    if signals_object:
        print("✅ Signals object already exists")
        return True

    # Create Signals object
    signals_attributes = [
        {"api_slug": "signal_id", "name": "Signal ID", "type": "text", "is_required": True, "config": {}},
        {"api_slug": "signal_type", "name": "Signal Type", "type": "text", "is_required": False, "config": {}},
        {"api_slug": "signal", "name": "Signal", "type": "text", "is_required": False, "config": {}},
        {"api_slug": "signal_at", "name": "Signal At", "type": "date-time", "is_required": False, "config": {}},
        {"api_slug": "url", "name": "URL", "type": "url", "is_required": False, "config": {}},
        {"api_slug": "source", "name": "Source", "type": "text", "is_required": False, "config": {}},
        {"api_slug": "repo_full_name", "name": "Repository", "type": "text", "is_required": False, "config": {}},
        {"api_slug": "login", "name": "User", "type": "text", "is_required": False, "config": {}},
        {"api_slug": "priority_score", "name": "Priority Score", "type": "number", "is_required": False, "config": {}},
        {"api_slug": "cohort", "name": "Cohort", "type": "text", "is_required": False, "config": {}}
    ]

    object_id = manager.create_object("Signals", "GitHub activity signals", signals_attributes)
    return object_id is not None

def setup_repo_membership_object(manager: AttioObjectManager) -> bool:
    """Setup Repo Membership object with required attributes"""
    print("🔍 Checking Repo Membership object...")

    objects = manager.get_objects()
    membership_object = next((obj for obj in objects if obj.get('api_slug') == 'repo_membership'), None)

    if membership_object:
        print("✅ Repo Membership object already exists")
        return True

    # Create Repo Membership object
    membership_attributes = [
        {"api_slug": "membership_id", "name": "Membership ID", "type": "text", "is_required": True, "config": {}},
        {"api_slug": "login", "name": "User", "type": "text", "is_required": False, "config": {}},
        {"api_slug": "repo_full_name", "name": "Repository", "type": "text", "is_required": False, "config": {}},
        {"api_slug": "role", "name": "Role", "type": "text", "is_required": False, "config": {}},
        {"api_slug": "permission", "name": "Permission", "type": "text", "is_required": False, "config": {}},
        {"api_slug": "contributions_past_year", "name": "Contributions Past Year", "type": "number", "is_required": False, "config": {}},
        {"api_slug": "last_activity_at", "name": "Last Activity At", "type": "date-time", "is_required": False, "config": {}}
    ]

    object_id = manager.create_object("Repo Membership", "User-repository relationships", membership_attributes)
    return object_id is not None

def main():
    """Main setup function"""
    print("🔗 Attio Objects Setup for Lead Intelligence")
    print("=" * 50)

    # Check environment variables
    api_token = os.environ.get('ATTIO_API_TOKEN')
    workspace_id = os.environ.get('ATTIO_WORKSPACE_ID')

    if not api_token:
        print("❌ ATTIO_API_TOKEN environment variable not set")
        print("💡 Run './setup_attio.sh' first to configure your credentials")
        return False

    if not workspace_id:
        print("⚠️  ATTIO_WORKSPACE_ID not set (optional but recommended)")

    try:
        # Initialize manager
        manager = AttioObjectManager(api_token, workspace_id or "")

        # Setup objects
        success = True
        success &= setup_people_object(manager)
        success &= setup_repos_object(manager)
        success &= setup_signals_object(manager)
        success &= setup_repo_membership_object(manager)

        if success:
            print("\n🎉 All Attio objects are ready!")
            print("✅ Your Attio workspace is configured for Lead Intelligence integration")
            return True
        else:
            print("\n❌ Some objects failed to create. Check your permissions.")
            return False

    except Exception as e:
        print(f"❌ Error setting up Attio objects: {e}")
        return False

if __name__ == '__main__':
    success = main()
    exit(0 if success else 1)
