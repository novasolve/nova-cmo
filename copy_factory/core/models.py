#!/usr/bin/env python3
"""
Core data models for Copy Factory
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Set
from datetime import datetime
from pathlib import Path
import json


@dataclass
class ICPProfile:
    """Ideal Customer Profile data model"""
    id: str
    name: str
    description: Optional[str] = None
    personas: List[Dict[str, Any]] = field(default_factory=list)
    firmographics: Dict[str, Any] = field(default_factory=dict)
    technographics: Dict[str, Any] = field(default_factory=dict)
    triggers: List[str] = field(default_factory=list)
    disqualifiers: List[str] = field(default_factory=list)
    github_queries: List[str] = field(default_factory=list)
    outreach_sequence_tag: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        data = {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'personas': self.personas,
            'firmographics': self.firmographics,
            'technographics': self.technographics,
            'triggers': self.triggers,
            'disqualifiers': self.disqualifiers,
            'github_queries': self.github_queries,
            'outreach_sequence_tag': self.outreach_sequence_tag,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat()
        }
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ICPProfile':
        """Create from dictionary"""
        # Handle datetime parsing
        created_at = datetime.fromisoformat(data.get('created_at', datetime.now().isoformat()))
        updated_at = datetime.fromisoformat(data.get('updated_at', datetime.now().isoformat()))

        return cls(
            id=data['id'],
            name=data['name'],
            description=data.get('description'),
            personas=data.get('personas', []),
            firmographics=data.get('firmographics', {}),
            technographics=data.get('technographics', {}),
            triggers=data.get('triggers', []),
            disqualifiers=data.get('disqualifiers', []),
            github_queries=data.get('github_queries', []),
            outreach_sequence_tag=data.get('outreach_sequence_tag'),
            created_at=created_at,
            updated_at=updated_at
        )


@dataclass
class ProspectData:
    """Prospect data model with email information"""
    lead_id: str
    login: str
    name: Optional[str] = None
    company: Optional[str] = None
    email_public_commit: Optional[str] = None
    email_profile: Optional[str] = None
    location: Optional[str] = None
    bio: Optional[str] = None
    pronouns: Optional[str] = None
    repo_full_name: Optional[str] = None
    repo_description: Optional[str] = None
    signal: Optional[str] = None
    signal_type: Optional[str] = None
    topics: List[str] = field(default_factory=list)
    language: Optional[str] = None
    stars: Optional[int] = None
    forks: Optional[int] = None
    watchers: Optional[int] = None
    followers: Optional[int] = None
    public_repos: Optional[int] = None
    contributions_last_year: Optional[int] = None
    linkedin_username: Optional[str] = None
    blog: Optional[str] = None
    hireable: bool = False
    icp_matches: List[str] = field(default_factory=list)  # ICP IDs that match this prospect
    intelligence_score: float = 0.0
    engagement_potential: str = "low"
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)

    def get_best_email(self) -> Optional[str]:
        """Get the best available email (profile email preferred)"""
        return self.email_profile or self.email_public_commit

    def has_email(self) -> bool:
        """Check if prospect has any email"""
        return bool(self.get_best_email())

    def get_email_domain(self) -> Optional[str]:
        """Extract email domain"""
        email = self.get_best_email()
        if email and '@' in email:
            return email.split('@')[1].lower()
        return None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        data = {
            'lead_id': self.lead_id,
            'login': self.login,
            'name': self.name,
            'company': self.company,
            'email_public_commit': self.email_public_commit,
            'email_profile': self.email_profile,
            'location': self.location,
            'bio': self.bio,
            'pronouns': self.pronouns,
            'repo_full_name': self.repo_full_name,
            'repo_description': self.repo_description,
            'signal': self.signal,
            'signal_type': self.signal_type,
            'topics': ','.join(self.topics) if self.topics else '',
            'language': self.language,
            'stars': self.stars,
            'forks': self.forks,
            'watchers': self.watchers,
            'followers': self.followers,
            'public_repos': self.public_repos,
            'contributions_last_year': self.contributions_last_year,
            'linkedin_username': self.linkedin_username,
            'blog': self.blog,
            'hireable': self.hireable,
            'icp_matches': ','.join(self.icp_matches) if self.icp_matches else '',
            'intelligence_score': self.intelligence_score,
            'engagement_potential': self.engagement_potential,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat()
        }
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ProspectData':
        """Create from dictionary"""
        # Handle datetime parsing
        created_at = datetime.fromisoformat(data.get('created_at', datetime.now().isoformat()))
        updated_at = datetime.fromisoformat(data.get('updated_at', datetime.now().isoformat()))

        # Handle topics
        topics = []
        if data.get('topics'):
            if isinstance(data['topics'], str):
                topics = [t.strip() for t in data['topics'].split(',') if t.strip()]
            elif isinstance(data['topics'], list):
                topics = data['topics']

        # Handle ICP matches
        icp_matches = []
        if data.get('icp_matches'):
            if isinstance(data['icp_matches'], str):
                icp_matches = [i.strip() for i in data['icp_matches'].split(',') if i.strip()]
            elif isinstance(data['icp_matches'], list):
                icp_matches = data['icp_matches']

        return cls(
            lead_id=data['lead_id'],
            login=data['login'],
            name=data.get('name'),
            company=data.get('company'),
            email_public_commit=data.get('email_public_commit'),
            email_profile=data.get('email_profile'),
            location=data.get('location'),
            bio=data.get('bio'),
            pronouns=data.get('pronouns'),
            repo_full_name=data.get('repo_full_name'),
            repo_description=data.get('repo_description'),
            signal=data.get('signal'),
            signal_type=data.get('signal_type'),
            topics=topics,
            language=data.get('language'),
            stars=data.get('stars'),
            forks=data.get('forks'),
            watchers=data.get('watchers'),
            followers=data.get('followers'),
            public_repos=data.get('public_repos'),
            contributions_last_year=data.get('contributions_last_year'),
            linkedin_username=data.get('linkedin_username'),
            blog=data.get('blog'),
            hireable=data.get('hireable', False),
            icp_matches=icp_matches,
            intelligence_score=data.get('intelligence_score', 0.0),
            engagement_potential=data.get('engagement_potential', 'low'),
            created_at=created_at,
            updated_at=updated_at
        )


@dataclass
class CopyTemplate:
    """Copy template for outreach campaigns"""
    id: str
    name: str
    icp_id: str
    template_type: str  # 'email', 'linkedin', 'twitter', etc.
    subject_template: Optional[str] = None
    body_template: str = ""
    variables: List[str] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        return {
            'id': self.id,
            'name': self.name,
            'icp_id': self.icp_id,
            'template_type': self.template_type,
            'subject_template': self.subject_template,
            'body_template': self.body_template,
            'variables': list(self.variables) if self.variables else [],
            'tags': ','.join(self.tags) if self.tags else '',
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat()
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'CopyTemplate':
        """Create from dictionary"""
        created_at = datetime.fromisoformat(data.get('created_at', datetime.now().isoformat()))
        updated_at = datetime.fromisoformat(data.get('updated_at', datetime.now().isoformat()))

        # Handle tags
        tags = []
        if data.get('tags'):
            if isinstance(data['tags'], str):
                tags = [t.strip() for t in data['tags'].split(',') if t.strip()]
            elif isinstance(data['tags'], list):
                tags = data['tags']

        return cls(
            id=data['id'],
            name=data['name'],
            icp_id=data['icp_id'],
            template_type=data['template_type'],
            subject_template=data.get('subject_template'),
            body_template=data['body_template'],
            variables=data.get('variables', []),
            tags=tags,
            created_at=created_at,
            updated_at=updated_at
        )


@dataclass
class OutreachCampaign:
    """Outreach campaign data model"""
    id: str
    name: str
    icp_id: str
    template_id: str
    prospect_ids: List[str] = field(default_factory=list)
    status: str = "draft"  # 'draft', 'active', 'paused', 'completed'
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        return {
            'id': self.id,
            'name': self.name,
            'icp_id': self.icp_id,
            'template_id': self.template_id,
            'prospect_ids': ','.join(self.prospect_ids) if self.prospect_ids else '',
            'status': self.status,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat()
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'OutreachCampaign':
        """Create from dictionary"""
        created_at = datetime.fromisoformat(data.get('created_at', datetime.now().isoformat()))
        updated_at = datetime.fromisoformat(data.get('updated_at', datetime.now().isoformat()))

        # Handle prospect_ids
        prospect_ids = []
        if data.get('prospect_ids'):
            if isinstance(data['prospect_ids'], str):
                prospect_ids = [p.strip() for p in data['prospect_ids'].split(',') if p.strip()]
            elif isinstance(data['prospect_ids'], list):
                prospect_ids = data['prospect_ids']

        return cls(
            id=data['id'],
            name=data['name'],
            icp_id=data['icp_id'],
            template_id=data['template_id'],
            prospect_ids=prospect_ids,
            status=data.get('status', 'draft'),
            created_at=created_at,
            updated_at=updated_at
        )
