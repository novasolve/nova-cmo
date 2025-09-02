#!/usr/bin/env python3
"""
Apollo API Integration for Lead Enrichment
Enrich CI/DevOps leads with Apollo's contact and company data
"""

import os
import csv
import json
import time
import requests
from datetime import datetime
from typing import Dict, List, Optional
from tqdm import tqdm


class ApolloEnricher:
    """Apollo API integration for lead enrichment"""
    
    def __init__(self, api_key: str = None):
        self.api_key = api_key or os.environ.get('APOLLO_API_KEY')
        if not self.api_key:
            raise ValueError("Apollo API key required. Set APOLLO_API_KEY environment variable.")
        
        self.base_url = "https://api.apollo.io/v1"
        self.headers = {
            'Cache-Control': 'no-cache',
            'Content-Type': 'application/json',
            'X-Api-Key': self.api_key
        }
        
        self.session = requests.Session()
        self.session.headers.update(self.headers)
        
    def search_person(self, name: str = None, email: str = None, company: str = None, 
                     title: str = None) -> Optional[Dict]:
        """Search for a person using Apollo's person search API"""
        
        url = f"{self.base_url}/mixed_people/search"
        
        # Build search criteria
        person_titles = []
        if title:
            person_titles = [title]
        elif any(role in (name or '').lower() for role in ['cto', 'director', 'vp']):
            person_titles = ['CTO', 'Director', 'VP Engineering', 'Head of Engineering']
        
        # Build request payload
        payload = {
            "page": 1,
            "per_page": 10,
            "person_titles": person_titles,
            "q_keywords": name if name else None,
        }
        
        # Add email if available
        if email and '@' in email and 'noreply' not in email.lower():
            payload["emails"] = [email]
        
        # Add company if available
        if company:
            # Clean company name
            company_clean = company.replace('@', '').strip()
            payload["organization_names"] = [company_clean]
        
        try:
            response = self.session.post(url, json=payload, timeout=30)
            
            if response.status_code == 200:
                data = response.json()
                people = data.get('people', [])
                return people[0] if people else None
            elif response.status_code == 429:
                print("⏳ Apollo rate limit hit, waiting...")
                time.sleep(60)  # Wait 1 minute
                return None
            else:
                print(f"❌ Apollo API error: {response.status_code}")
                return None
                
        except Exception as e:
            print(f"❌ Apollo request error: {e}")
            return None
    
    def get_person_details(self, person_id: str) -> Optional[Dict]:
        """Get detailed person information"""
        
        url = f"{self.base_url}/people/{person_id}"
        
        try:
            response = self.session.get(url, timeout=30)
            
            if response.status_code == 200:
                return response.json()
            else:
                return None
                
        except Exception as e:
            print(f"❌ Error getting person details: {e}")
            return None
    
    def enrich_lead(self, lead: Dict) -> Dict:
        """Enrich a single lead with Apollo data"""
        
        name = lead.get('name', '') or lead.get('login', '')
        email = lead.get('email', '')
        company = lead.get('company', '')
        
        # Search Apollo
        apollo_person = self.search_person(name=name, email=email, company=company)
        
        if apollo_person:
            # Extract enriched data
            enriched = {
                'apollo_id': apollo_person.get('id'),
                'apollo_first_name': apollo_person.get('first_name'),
                'apollo_last_name': apollo_person.get('last_name'),
                'apollo_title': apollo_person.get('title'),
                'apollo_email': apollo_person.get('email'),
                'apollo_phone': apollo_person.get('phone_numbers', [{}])[0].get('raw_number') if apollo_person.get('phone_numbers') else None,
                'apollo_linkedin': apollo_person.get('linkedin_url'),
                'apollo_company_name': apollo_person.get('organization', {}).get('name'),
                'apollo_company_domain': apollo_person.get('organization', {}).get('primary_domain'),
                'apollo_company_industry': apollo_person.get('organization', {}).get('industry'),
                'apollo_company_size': apollo_person.get('organization', {}).get('estimated_num_employees'),
                'apollo_company_location': apollo_person.get('organization', {}).get('primary_phone', {}).get('sanitized_number') if apollo_person.get('organization', {}).get('primary_phone') else None,
                'apollo_seniority': apollo_person.get('seniority'),
                'apollo_departments': ', '.join(apollo_person.get('departments', [])),
                'apollo_confidence': apollo_person.get('email_status'),
                'apollo_last_activity': apollo_person.get('last_activity_date'),
                'apollo_enriched': True
            }
            
            # Merge with original lead data
            enriched_lead = {**lead, **enriched}
            
            return enriched_lead
        else:
            # No Apollo match found
            lead['apollo_enriched'] = False
            return lead
    
    def enrich_leads_batch(self, leads: List[Dict], output_file: str = None) -> List[Dict]:
        """Enrich multiple leads with Apollo data"""
        
        enriched_leads = []
        
        print(f"🔍 Enriching {len(leads)} leads with Apollo...")
        
        # Process with progress bar
        for lead in tqdm(leads, desc="Apollo enrichment"):
            try:
                enriched_lead = self.enrich_lead(lead)
                enriched_leads.append(enriched_lead)
                
                # Rate limiting - Apollo has limits
                time.sleep(0.5)  # 2 requests per second
                
            except Exception as e:
                print(f"❌ Error enriching {lead.get('login', 'unknown')}: {e}")
                # Add original lead without enrichment
                lead['apollo_enriched'] = False
                enriched_leads.append(lead)
        
        # Save results if output file specified
        if output_file and enriched_leads:
            fieldnames = list(enriched_leads[0].keys())
            with open(output_file, 'w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(enriched_leads)
        
        return enriched_leads
    
    def print_enrichment_stats(self, leads: List[Dict]):
        """Print enrichment statistics"""
        
        total = len(leads)
        enriched = sum(1 for lead in leads if lead.get('apollo_enriched'))
        
        print(f"\n📊 APOLLO ENRICHMENT STATS")
        print("=" * 40)
        print(f"Total leads: {total}")
        print(f"Successfully enriched: {enriched} ({enriched/total*100:.1f}%)")
        print(f"Not found in Apollo: {total - enriched}")
        
        # Show enriched examples
        enriched_leads = [lead for lead in leads if lead.get('apollo_enriched')]
        if enriched_leads:
            print(f"\n🏆 TOP 5 ENRICHED LEADS:")
            for i, lead in enumerate(enriched_leads[:5], 1):
                name = lead.get('apollo_first_name', '') + ' ' + lead.get('apollo_last_name', '')
                title = lead.get('apollo_title', '')
                company = lead.get('apollo_company_name', '')
                email = lead.get('apollo_email', '')
                phone = lead.get('apollo_phone', '')
                
                print(f"{i}. {name.strip()} - {title}")
                if company:
                    print(f"   Company: {company}")
                if email:
                    print(f"   Email: {email}")
                if phone:
                    print(f"   Phone: {phone}")
                print()


def enrich_us_leads_with_apollo():
    """Main function to enrich US CI leads with Apollo"""
    
    print("🚀 Apollo API Lead Enrichment")
    print("=" * 40)
    
    # Check for API key
    api_key = os.environ.get('APOLLO_API_KEY')
    if not api_key:
        print("❌ Apollo API key required!")
        print("Set environment variable: export APOLLO_API_KEY=your_api_key")
        print("Get your API key from: https://app.apollo.io/settings/integrations/api")
        return
    
    # Load US leads
    input_file = "US_ONLY_100_LEADS_FINAL.csv"
    
    try:
        with open(input_file, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            leads = list(reader)
    except FileNotFoundError:
        print(f"❌ Input file not found: {input_file}")
        return
    
    print(f"📊 Loaded {len(leads)} US CI/DevOps leads")
    
    # Initialize Apollo enricher
    try:
        enricher = ApolloEnricher(api_key)
    except ValueError as e:
        print(f"❌ {e}")
        return
    
    # Enrich leads
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = f"us_leads_apollo_enriched_{timestamp}.csv"
    
    enriched_leads = enricher.enrich_leads_batch(leads, output_file)
    
    # Print stats
    enricher.print_enrichment_stats(enriched_leads)
    
    print(f"\n💾 Enriched leads saved to: {output_file}")
    print(f"\n💡 Next steps:")
    print(f"   1. Review Apollo-enriched data for phone numbers and verified emails")
    print(f"   2. Use Apollo company data for account-based marketing")
    print(f"   3. Leverage Apollo titles for personalized outreach")
    print(f"   4. Cross-reference Apollo confidence scores with your CI relevance scores")


if __name__ == '__main__':
    enrich_us_leads_with_apollo()
