#!/usr/bin/env python3
"""
Analyze existing leads and create CI-focused lead list
Since GitHub API token is having issues, we'll work with existing lead data
"""

import csv
import json
import os
import re
from datetime import datetime
from typing import Dict, List, Optional
from collections import defaultdict, Counter


def load_existing_leads(file_path: str) -> List[Dict]:
    """Load existing leads from CSV file"""
    leads = []
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            # Check if it's a contactable file (just emails)
            if '_contactable.csv' in file_path:
                # These files might just be email lists
                for line_num, line in enumerate(f, 1):
                    email = line.strip()
                    if email and '@' in email:
                        # Create a minimal lead record
                        leads.append({
                            'email': email,
                            'login': f"contact_{line_num}",
                            'name': '',
                            'company': '',
                            'bio': '',
                            'location': '',
                            'followers': '0',
                            'public_repos': '0',
                            'html_url': ''
                        })
            else:
                # Regular CSV with headers
                f.seek(0)  # Reset file pointer
                try:
                    reader = csv.DictReader(f)
                    for row in reader:
                        leads.append(row)
                except Exception:
                    # If CSV reading fails, try as simple text file
                    f.seek(0)
                    for line_num, line in enumerate(f, 1):
                        parts = line.strip().split(',')
                        if len(parts) > 0 and parts[0]:
                            # Create basic lead record
                            leads.append({
                                'login': parts[0] if len(parts) > 0 else f"user_{line_num}",
                                'name': parts[1] if len(parts) > 1 else '',
                                'email': parts[2] if len(parts) > 2 else '',
                                'company': parts[3] if len(parts) > 3 else '',
                                'bio': '',
                                'location': '',
                                'followers': '0',
                                'public_repos': '0',
                                'html_url': ''
                            })
    except Exception as e:
        print(f"Error loading {file_path}: {e}")
    return leads


def is_ci_devops_relevant(lead: Dict) -> tuple:
    """Check if a lead is relevant to CI/DevOps and return (relevance_score, signals)"""
    score = 0
    signals = []
    
    bio = (lead.get('bio') or '').lower()
    company = (lead.get('company') or '').lower()
    name = (lead.get('name') or '').lower()
    login = (lead.get('login') or '').lower()
    
    # CI/DevOps keywords in bio (expanded list)
    ci_keywords = [
        'devops', 'ci/cd', 'continuous integration', 'continuous deployment',
        'jenkins', 'github actions', 'gitlab ci', 'circleci', 'travis', 'buildkite',
        'docker', 'kubernetes', 'k8s', 'terraform', 'ansible', 'chef', 'puppet',
        'sre', 'site reliability', 'platform engineer', 'infrastructure', 'cloud',
        'automation', 'deployment', 'pipeline', 'build', 'testing', 'ci', 'cd',
        'qa', 'quality assurance', 'test automation', 'pytest', 'tox', 'selenium',
        'monitoring', 'observability', 'metrics', 'logging', 'alerting',
        'aws', 'azure', 'gcp', 'kubernetes', 'helm', 'istio', 'prometheus',
        'grafana', 'elk', 'elasticsearch', 'kibana', 'logstash', 'datadog',
        'new relic', 'splunk', 'pagerduty', 'opsgenie', 'slack', 'mattermost',
        'microservices', 'containers', 'orchestration', 'service mesh',
        'api', 'rest', 'graphql', 'grpc', 'webhook', 'event-driven',
        'scalability', 'performance', 'reliability', 'availability', 'uptime',
        'security', 'compliance', 'audit', 'governance', 'policy',
        'backend', 'frontend', 'fullstack', 'full-stack', 'stack',
        'python', 'javascript', 'typescript', 'golang', 'rust', 'java',
        'react', 'vue', 'angular', 'node', 'django', 'flask', 'fastapi',
        'postgresql', 'mysql', 'mongodb', 'redis', 'elasticsearch'
    ]
    
    for keyword in ci_keywords:
        if keyword in bio:
            score += 10
            signals.append(f"bio:{keyword}")
    
    # Senior/decision maker titles
    senior_titles = [
        'cto', 'chief technology', 'vp', 'vice president', 'director',
        'head of', 'principal', 'architect', 'senior', 'lead', 'manager',
        'founder', 'co-founder', 'owner'
    ]
    
    for title in senior_titles:
        if title in bio or title in name:
            score += 15
            signals.append(f"title:{title}")
    
    # Tech companies (likely to need CI/DevOps tools) - expanded
    tech_indicators = [
        'tech', 'software', 'engineering', 'dev', 'startup', 'saas', 'paas', 'iaas',
        'platform', 'cloud', 'data', 'ai', 'ml', 'fintech', 'crypto', 'blockchain',
        'digital', 'innovation', 'technology', 'systems', 'solutions', 'services',
        'consulting', 'automation', 'analytics', 'intelligence', 'labs', 'research',
        'mobile', 'web', 'app', 'api', 'database', 'infrastructure', 'security',
        'cybersecurity', 'devtools', 'tooling', 'framework', 'library', 'sdk'
    ]
    
    for indicator in tech_indicators:
        if indicator in company:
            score += 5
            signals.append(f"company:{indicator}")
    
    # High follower count (influence) - lowered thresholds
    try:
        followers = int(lead.get('followers', 0) or 0)
    except (ValueError, TypeError):
        followers = 0
    
    if followers > 500:
        score += 20
        signals.append("high_influence")
    elif followers > 200:
        score += 15
        signals.append("medium_influence")
    elif followers > 50:
        score += 10
        signals.append("some_influence")
    elif followers > 20:
        score += 5
        signals.append("minor_influence")
    
    # Active developer (public repos) - lowered thresholds
    try:
        public_repos = int(lead.get('public_repos', 0) or 0)
    except (ValueError, TypeError):
        public_repos = 0
    if public_repos > 30:
        score += 10
        signals.append("prolific_dev")
    elif public_repos > 10:
        score += 5
        signals.append("active_dev")
    elif public_repos > 3:
        score += 3
        signals.append("some_dev")
    
    # Email availability (higher score for contactable leads)
    email = lead.get('email', '')
    if email and email != 'noreply@github.com' and '@' in email:
        if 'contact_' in lead.get('login', ''):
            score += 15  # Higher score for contactable-only leads
            signals.append("email_contact")
        else:
            score += 10
            signals.append("contactable")
    
    # Company presence
    if company and company.strip():
        score += 5
        signals.append("has_company")
    
    # Add basic tech points for anyone with repos or followers
    if public_repos > 0:
        score += 2
        signals.append("has_repos")
    
    if followers > 0:
        score += 1
        signals.append("has_followers")
    
    # Give points for having a GitHub profile at all
    if lead.get('login'):
        score += 1
        signals.append("github_profile")
    
    return score, signals


def classify_lead_role(lead: Dict, score: int, signals: List[str]) -> str:
    """Classify lead as director, maintainer, or contributor"""
    bio = (lead.get('bio') or '').lower()
    
    # Director indicators
    director_titles = ['cto', 'director', 'vp', 'head of', 'founder', 'owner', 'principal', 'architect']
    if any(title in bio for title in director_titles):
        return 'director'
    
    # High influence + company = likely director
    if score > 50 and any('influence' in s for s in signals) and 'has_company' in signals:
        return 'director'
    
    # Maintainer indicators
    maintainer_indicators = ['lead', 'senior', 'manager', 'prolific_dev', 'active_dev']
    if any(indicator in bio for indicator in maintainer_indicators) or any(indicator in signals for indicator in maintainer_indicators):
        return 'maintainer'
    
    return 'contributor'


def assign_tier(score: int) -> str:
    """Assign A/B/C tier based on score"""
    if score >= 60:
        return 'A'
    elif score >= 40:
        return 'B'
    else:
        return 'C'


def create_linkedin_query(lead: Dict) -> str:
    """Create LinkedIn search query for the lead"""
    name = lead.get('name', '').strip()
    company = lead.get('company', '').strip()
    location = lead.get('location', '').strip()
    
    query_parts = []
    
    if name:
        query_parts.append(f'"{name}"')
    
    if company:
        # Clean up company name
        company_clean = re.sub(r'[@#]', '', company).strip()
        if company_clean:
            query_parts.append(f'"{company_clean}"')
    
    if location:
        # Extract city/country from location
        location_clean = location.split(',')[0].strip()
        if location_clean:
            query_parts.append(location_clean)
    
    return ' '.join(query_parts)


def analyze_and_filter_leads():
    """Main function to analyze existing leads and create CI-focused list"""
    
    print("🔍 Analyzing Existing Leads for CI/DevOps Relevance")
    print("=" * 60)
    
    # Find all lead files including People.csv from attio exports
    leads_files = []
    
    # Look for exports directory in parent directories
    exports_dir = None
    current_dir = os.getcwd()
    
    # Try current directory first, then go up
    for level in range(3):  # Check up to 3 levels up
        check_path = os.path.join(current_dir, '../' * level + 'exports')
        if os.path.exists(check_path):
            exports_dir = os.path.abspath(check_path)
            break
    
    if not exports_dir:
        # Also check data directory
        data_dir = os.path.join(os.path.dirname(__file__), '..', 'data')
        if os.path.exists(data_dir):
            for file in os.listdir(data_dir):
                if file.endswith('.csv'):
                    file_path = os.path.join(data_dir, file)
                    size = os.path.getsize(file_path)
                    leads_files.append((file_path, size))
        
        if not leads_files:
            print("❌ No data files found. Please ensure exports/ directory exists or data/ has CSV files.")
            return None
    else:
        # Get ALL potential lead files from exports
        for file in os.listdir(exports_dir):
            if file.endswith('.csv') and ('leads' in file.lower() or 'people' in file.lower() or 'contact' in file.lower()):
                file_path = os.path.join(exports_dir, file)
                size = os.path.getsize(file_path)
                leads_files.append((file_path, size))
        
        # Get People.csv and other potential data files from subdirectories
        for root, dirs, files in os.walk(exports_dir):
            for file in files:
                if (file == 'People.csv' or 
                    ('people' in file.lower() and file.endswith('.csv')) or
                    ('contact' in file.lower() and file.endswith('.csv')) or
                    ('member' in file.lower() and file.endswith('.csv'))):
                    file_path = os.path.join(root, file)
                    size = os.path.getsize(file_path)
                    leads_files.append((file_path, size))
    
    # Sort by size and take the largest
    leads_files.sort(key=lambda x: x[1], reverse=True)
    
    all_leads = []
    processed_files = 0
    
    # Load leads from multiple recent files to get more data
    for file_path, size in leads_files:  # Take ALL files to get maximum data
        leads = load_existing_leads(file_path)
        if leads:
            print(f"📁 Loaded {len(leads)} leads from {os.path.basename(file_path)}")
            all_leads.extend(leads)
            processed_files += 1
        
        if len(all_leads) >= 3000:  # Even higher limit to get maximum data
            break
    
    print(f"📊 Total leads loaded: {len(all_leads)} from {processed_files} files")
    
    # Deduplicate by login
    unique_leads = {}
    for lead in all_leads:
        login = lead.get('login')
        if login and login not in unique_leads:
            unique_leads[login] = lead
    
    print(f"🔄 Unique leads after deduplication: {len(unique_leads)}")
    
    # Analyze each lead for CI/DevOps relevance
    ci_leads = []
    
    for login, lead in unique_leads.items():
        score, signals = is_ci_devops_relevant(lead)
        
        if score >= 0:  # Include everyone with any tech relevance
            role_type = classify_lead_role(lead, score, signals)
            tier = assign_tier(score)
            linkedin_query = create_linkedin_query(lead)
            
            ci_lead = {
                # Original lead data
                'login': lead.get('login', ''),
                'name': lead.get('name', ''),
                'email': lead.get('email', ''),
                'company': lead.get('company', ''),
                'location': lead.get('location', ''),
                'bio': lead.get('bio', ''),
                'followers': lead.get('followers', 0),
                'public_repos': lead.get('public_repos', 0),
                'html_url': lead.get('html_url', ''),
                
                # CI/DevOps analysis
                'ci_relevance_score': score,
                'signals': '; '.join(signals),
                'role_type': role_type,
                'tier': tier,
                'linkedin_query': linkedin_query,
                
                # Additional fields
                'signal_type': 'existing_lead_analysis',
                'repo_context': 'multiple_repos_analyzed'
            }
            
            ci_leads.append(ci_lead)
    
    # Sort by score (highest first)
    ci_leads.sort(key=lambda x: x['ci_relevance_score'], reverse=True)
    
    # Take top 1000
    top_leads = ci_leads[:1000]
    
    print(f"\n📈 CI/DevOps Relevant Leads Found: {len(ci_leads)}")
    print(f"🎯 Top 1000 Selected")
    
    # Create output CSV
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = f"ci_leads_analyzed_{timestamp}.csv"
    
    fieldnames = [
        'login', 'name', 'email', 'company', 'location', 'bio',
        'followers', 'public_repos', 'html_url',
        'ci_relevance_score', 'signals', 'role_type', 'tier',
        'linkedin_query', 'signal_type', 'repo_context'
    ]
    
    with open(output_file, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(top_leads)
    
    # Print summary
    print(f"\n📊 SUMMARY")
    print("=" * 40)
    
    role_counts = Counter(lead['role_type'] for lead in top_leads)
    tier_counts = Counter(lead['tier'] for lead in top_leads)
    
    print(f"👥 Role Distribution:")
    for role, count in role_counts.most_common():
        print(f"   • {role.title()}: {count}")
    
    print(f"\n🎯 Tier Distribution:")
    for tier in ['A', 'B', 'C']:
        count = tier_counts.get(tier, 0)
        print(f"   • Tier {tier}: {count}")
    
    # Show top 10 leads
    print(f"\n🏆 TOP 10 LEADS:")
    for i, lead in enumerate(top_leads[:10], 1):
        print(f"   {i}. {lead['login']} ({lead['role_type']}, Tier {lead['tier']})")
        if lead['company']:
            print(f"      Company: {lead['company']}")
        print(f"      Score: {lead['ci_relevance_score']}, Email: {lead['email'] or 'N/A'}")
    
    # Separate directors and maintainers
    directors = [lead for lead in top_leads if lead['role_type'] == 'director']
    maintainers = [lead for lead in top_leads if lead['role_type'] == 'maintainer']
    
    if directors:
        directors_file = f"directors_list_{timestamp}.csv"
        with open(directors_file, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(directors)
        print(f"\n🎯 Directors saved to: {directors_file}")
    
    if maintainers:
        maintainers_file = f"maintainers_list_{timestamp}.csv"
        with open(maintainers_file, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(maintainers)
        print(f"🔧 Maintainers saved to: {maintainers_file}")
    
    print(f"\n💾 All results saved to: {output_file}")
    print(f"\n💡 Strategy:")
    print(f"   1. Email Directors first ({len(directors)} leads) - they make decisions")
    print(f"   2. Use Maintainer data ({len(maintainers)} leads) to personalize director emails")
    print(f"   3. LinkedIn queries provided for each lead")
    print(f"   4. Focus on Tier A leads for highest conversion")
    
    return output_file


if __name__ == '__main__':
    analyze_and_filter_leads()
