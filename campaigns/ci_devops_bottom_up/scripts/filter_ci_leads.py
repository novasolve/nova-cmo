#!/usr/bin/env python3
"""
CI/DevOps Lead Filter & Refinement
Clean the lead list to focus on contactable humans with strong CI/dev-infra signals
"""

import csv
import re
from datetime import datetime
from typing import Dict, List, Tuple
from collections import Counter
import pandas as pd


class CILeadFilter:
    """Filter and refine CI/DevOps leads for outreach readiness"""
    
    def __init__(self, csv_file: str):
        self.csv_file = csv_file
        self.leads = []
        self.filtered_leads = []
        self.removed_leads = []
        
        # Bot/automation patterns
        self.bot_patterns = [
            'bot', 'automation', '[bot]', 'dependabot', 'renovate', 'weblate',
            'actions-user', 'smokedetector', 'tensorflower', 'github-actions',
            'codecov', 'coveralls', 'greenkeeper', 'snyk-bot', 'deepsource',
            'stale[bot]', 'allcontributors', 'semantic-release-bot'
        ]
        
        # Strong CI/DevOps signals
        self.ci_signals = [
            'bio:ci', 'bio:build', 'bio:ansible', 'bio:docker', 'bio:kubernetes',
            'bio:terraform', 'bio:jenkins', 'bio:github actions', 'bio:aws',
            'bio:azure', 'bio:gcp', 'bio:devops', 'bio:sre', 'bio:monitoring',
            'bio:observability', 'bio:infrastructure', 'bio:platform', 'bio:cloud'
        ]
        
        # Leadership titles
        self.leadership_signals = [
            'title:cto', 'title:director', 'title:vp', 'title:principal',
            'title:lead', 'title:architect', 'title:founder', 'title:head of',
            'title:senior', 'title:manager'
        ]
    
    def load_leads(self):
        """Load leads from CSV file"""
        with open(self.csv_file, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            self.leads = list(reader)
        print(f"📊 Loaded {len(self.leads)} leads from {self.csv_file}")
    
    def is_bot_or_automation(self, lead: Dict) -> Tuple[bool, str]:
        """Check if lead is a bot or automation account"""
        login = (lead.get('login', '') or '').lower()
        name = (lead.get('name', '') or '').lower()
        bio = (lead.get('bio', '') or '').lower()
        
        for pattern in self.bot_patterns:
            if pattern in login or pattern in name or pattern in bio:
                return True, f"bot_pattern:{pattern}"
        
        # Check for automation indicators
        if any(indicator in bio for indicator in ['i\'m a bot', 'beep boop', 'automated']):
            return True, "automation_bio"
        
        return False, ""
    
    def is_contactable_human(self, lead: Dict) -> Tuple[bool, str]:
        """Check if lead is a contactable human"""
        email = lead.get('email', '') or ''
        login = lead.get('login', '') or ''
        
        # Check for bot first
        is_bot, bot_reason = self.is_bot_or_automation(lead)
        if is_bot:
            return False, f"bot:{bot_reason}"
        
        # Check email quality
        if not email or email.strip() == '':
            return False, "no_email"
        
        if 'noreply@' in email.lower():
            return False, "noreply_email"
        
        if not '@' in email:
            return False, "invalid_email"
        
        # Check for valid email domains (basic validation)
        email_domain = email.split('@')[-1].lower()
        if email_domain in ['example.com', 'test.com', 'localhost']:
            return False, "test_email"
        
        return True, "contactable"
    
    def has_ci_signals(self, lead: Dict) -> Tuple[bool, List[str]]:
        """Check for CI/DevOps signals"""
        signals = (lead.get('signals', '') or '').lower()
        found_signals = []
        
        # Check for explicit CI signals
        for signal in self.ci_signals:
            if signal in signals:
                found_signals.append(signal)
        
        # Check for leadership signals
        for signal in self.leadership_signals:
            if signal in signals:
                found_signals.append(signal)
        
        return len(found_signals) > 0, found_signals
    
    def calculate_quality_score(self, lead: Dict) -> int:
        """Calculate overall quality score for lead"""
        score = 0
        
        # Base CI relevance score
        try:
            base_score = int(lead.get('ci_relevance_score', 0))
            score += base_score
        except (ValueError, TypeError):
            pass
        
        # Tier bonus
        tier = lead.get('tier', 'C')
        if tier == 'A':
            score += 20
        elif tier == 'B':
            score += 10
        
        # Role bonus
        role = lead.get('role_type', '')
        if role == 'director':
            score += 15
        elif role == 'maintainer':
            score += 10
        
        # Contactability bonus
        is_contactable, _ = self.is_contactable_human(lead)
        if is_contactable:
            score += 15
        
        # CI signals bonus
        has_ci, ci_signals = self.has_ci_signals(lead)
        if has_ci:
            score += len(ci_signals) * 3
        
        # Followers influence
        try:
            followers = int(lead.get('followers', 0) or 0)
            if followers > 1000:
                score += 10
            elif followers > 500:
                score += 5
            elif followers > 100:
                score += 3
        except (ValueError, TypeError):
            pass
        
        return score
    
    def filter_leads(self):
        """Filter leads into good and removed categories"""
        print("\n🔍 Filtering leads...")
        
        for lead in self.leads:
            is_contactable, contact_reason = self.is_contactable_human(lead)
            has_ci, ci_signals = self.has_ci_signals(lead)
            quality_score = self.calculate_quality_score(lead)
            
            # Add computed fields
            lead['is_contactable'] = is_contactable
            lead['contact_reason'] = contact_reason
            lead['has_ci_signals'] = has_ci
            lead['ci_signals_found'] = '; '.join(ci_signals)
            lead['quality_score'] = quality_score
            
            # Filtering logic
            tier = lead.get('tier', 'C')
            role = lead.get('role_type', '')
            
            # Keep if: contactable human + (Tier A/B OR director/maintainer) + some CI signals
            if (is_contactable and 
                (tier in ['A', 'B'] or role in ['director', 'maintainer']) and
                (has_ci or quality_score > 30)):
                self.filtered_leads.append(lead)
            else:
                self.removed_leads.append(lead)
        
        # Sort filtered leads by quality score
        self.filtered_leads.sort(key=lambda x: x['quality_score'], reverse=True)
        
        print(f"✅ Filtered to {len(self.filtered_leads)} high-quality leads")
        print(f"🗑️  Removed {len(self.removed_leads)} leads")
    
    def print_analysis(self):
        """Print comprehensive analysis"""
        total = len(self.leads)
        filtered = len(self.filtered_leads)
        removed = len(self.removed_leads)
        
        print(f"\n📊 LEAD LIST — QUICK METRICS")
        print("=" * 50)
        print(f"Total leads processed: {total}")
        print(f"High-quality targets: {filtered} ({filtered/total*100:.1f}%)")
        print(f"Removed/deprioritized: {removed} ({removed/total*100:.1f}%)")
        
        # Contactable humans analysis
        contactable = sum(1 for lead in self.leads if lead.get('is_contactable'))
        bots = sum(1 for lead in self.leads if 'bot:' in lead.get('contact_reason', ''))
        noreply = sum(1 for lead in self.leads if 'noreply' in lead.get('contact_reason', ''))
        
        print(f"\nContactable humans: {contactable}")
        print(f"Bots/automation: {bots}")
        print(f"Noreply/blank emails: {noreply}")
        
        # CI signals analysis
        explicit_ci = sum(1 for lead in self.leads if 'bio:ci' in lead.get('signals', ''))
        ci_aligned = sum(1 for lead in self.leads if lead.get('has_ci_signals'))
        
        print(f"\nExplicit CI bio signals: {explicit_ci}")
        print(f"Broader CI-aligned: {ci_aligned}")
        
        # Role/tier breakdown
        print(f"\n🎯 TIER/ROLE BREAKDOWN (Filtered Leads)")
        print("-" * 40)
        
        role_counts = Counter(lead['role_type'] for lead in self.filtered_leads)
        tier_counts = Counter(lead['tier'] for lead in self.filtered_leads)
        
        for role, count in role_counts.most_common():
            print(f"{role.title()}: {count}")
        
        print()
        for tier in ['A', 'B', 'C']:
            count = tier_counts.get(tier, 0)
            print(f"Tier {tier}: {count}")
        
        # Top 25 recommendations
        print(f"\n🏆 RECOMMENDED TARGETS (Top 25)")
        print("-" * 60)
        
        top_25 = self.filtered_leads[:25]
        for i, lead in enumerate(top_25, 1):
            name = lead.get('name') or lead.get('login')
            company = lead.get('company', '')
            email = lead.get('email', '')
            role = lead.get('role_type', '')
            tier = lead.get('tier', '')
            score = lead.get('quality_score', 0)
            
            print(f"{i:2d}. {name} ({role}, Tier {tier}) - Score: {score}")
            if company:
                print(f"    Company: {company}")
            print(f"    Email: {email}")
            if i <= 5:  # Show signals for top 5
                signals = lead.get('ci_signals_found', '')
                if signals:
                    print(f"    CI Signals: {signals}")
            print()
        
        # Removal reasons
        print(f"\n🗑️  LIKELY REMOVE - Top Reasons")
        print("-" * 40)
        
        removal_reasons = Counter(lead['contact_reason'] for lead in self.removed_leads)
        for reason, count in removal_reasons.most_common(5):
            print(f"{reason}: {count} leads")
    
    def save_results(self):
        """Save filtered and removed leads to separate files"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Save filtered leads
        filtered_file = f"filtered_ci_leads_{timestamp}.csv"
        if self.filtered_leads:
            fieldnames = list(self.filtered_leads[0].keys())
            with open(filtered_file, 'w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(self.filtered_leads)
        
        # Save removed leads
        removed_file = f"removed_leads_{timestamp}.csv"
        if self.removed_leads:
            fieldnames = list(self.removed_leads[0].keys())
            with open(removed_file, 'w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(self.removed_leads)
        
        print(f"\n💾 FILES SAVED:")
        print(f"✅ Filtered leads: {filtered_file}")
        print(f"🗑️  Removed leads: {removed_file}")
        
        return filtered_file, removed_file


def main():
    """Run the CI lead filtering analysis"""
    csv_file = "FINAL_1000_LEADS_MAXIMUM_FROM_DATA.csv"
    
    print("🎯 CI/DevOps Lead Filter & Refinement")
    print("=" * 50)
    print("Cleaning lead list for contactable humans with strong CI/dev-infra signals")
    
    filter_system = CILeadFilter(csv_file)
    filter_system.load_leads()
    filter_system.filter_leads()
    filter_system.print_analysis()
    filtered_file, removed_file = filter_system.save_results()
    
    print(f"\n💡 NEXT STEPS:")
    print(f"1. Review top 25 recommended targets")
    print(f"2. Start with Tier A directors for decision maker outreach")
    print(f"3. Use maintainer context to personalize director emails")
    print(f"4. Consider PostHog/Astronomer/Red Hat micro-sequences")
    
    return filtered_file, removed_file


if __name__ == '__main__':
    main()
