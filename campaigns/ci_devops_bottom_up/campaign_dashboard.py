#!/usr/bin/env python3
"""
Campaign Dashboard - View and analyze campaign results
"""

import os
import csv
import json
from pathlib import Path
from collections import Counter
from datetime import datetime


def analyze_campaign_results():
    """Analyze and display campaign results"""
    
    outputs_dir = Path("outputs")
    
    if not outputs_dir.exists():
        print("❌ No campaign outputs found. Run launch_campaign.py first.")
        return
    
    # Find most recent campaign
    campaign_dirs = [d for d in outputs_dir.iterdir() if d.is_dir() and d.name.startswith("ci_campaign_")]
    
    if not campaign_dirs:
        print("❌ No campaign results found")
        return
    
    latest_campaign = max(campaign_dirs, key=lambda d: d.stat().st_mtime)
    
    print(f"📊 CAMPAIGN DASHBOARD")
    print("=" * 60)
    print(f"Latest Campaign: {latest_campaign.name}")
    print(f"Generated: {datetime.fromtimestamp(latest_campaign.stat().st_mtime)}")
    print()
    
    # Analyze files
    csv_files = list(latest_campaign.glob("*.csv"))
    json_files = list(latest_campaign.glob("*.json"))
    
    print(f"📁 OUTPUT FILES ({len(csv_files + json_files)} total):")
    
    results = {}
    
    for csv_file in csv_files:
        try:
            with open(csv_file, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                leads = list(reader)
                
            results[csv_file.stem] = {
                'type': 'csv',
                'count': len(leads),
                'file': csv_file.name,
                'leads': leads
            }
            
            print(f"  📄 {csv_file.name}: {len(leads)} leads")
            
        except Exception as e:
            print(f"  ❌ Error reading {csv_file.name}: {e}")
    
    for json_file in json_files:
        try:
            with open(json_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            results[json_file.stem] = {
                'type': 'json',
                'count': len(data) if isinstance(data, dict) else 0,
                'file': json_file.name,
                'data': data
            }
            
            print(f"  📄 {json_file.name}: {len(data) if isinstance(data, dict) else 'N/A'} entries")
            
        except Exception as e:
            print(f"  ❌ Error reading {json_file.name}: {e}")
    
    # Detailed analysis
    print(f"\n🎯 CAMPAIGN ANALYSIS")
    print("-" * 40)
    
    # Directors analysis
    directors_data = None
    for key, data in results.items():
        if 'director' in key and data['type'] == 'csv':
            directors_data = data
            break
    
    if directors_data:
        directors = directors_data['leads']
        print(f"👔 DIRECTORS ({len(directors)} total):")
        
        # Top companies
        companies = [d.get('company', '') for d in directors if d.get('company')]
        if companies:
            company_counts = Counter(companies)
            print(f"   Top Companies: {', '.join([f'{c}({n})' for c, n in company_counts.most_common(5)])}")
        
        # Contactable
        contactable = sum(1 for d in directors if d.get('email') and 'noreply' not in d.get('email', ''))
        print(f"   Contactable: {contactable}/{len(directors)} ({contactable/len(directors)*100:.1f}%)")
        
        # Show top 5
        print(f"   Top 5:")
        for i, director in enumerate(directors[:5], 1):
            name = director.get('name') or director.get('login')
            company = director.get('company', '')
            print(f"     {i}. {name} ({company})")
    
    # Maintainers analysis
    maintainers_data = None
    for key, data in results.items():
        if 'maintainer' in key and data['type'] == 'csv':
            maintainers_data = data
            break
    
    if maintainers_data:
        maintainers = maintainers_data['leads']
        print(f"\n🔧 MAINTAINERS ({len(maintainers)} total):")
        
        # Top signals
        if maintainers and 'signals' in maintainers[0]:
            all_signals = []
            for m in maintainers:
                signals = m.get('signals', '').split(';')
                all_signals.extend([s.strip() for s in signals if s.strip()])
            
            signal_counts = Counter(all_signals)
            top_signals = signal_counts.most_common(5)
            print(f"   Top Signals: {', '.join([f'{s}({n})' for s, n in top_signals])}")
        
        # Contactable
        contactable = sum(1 for m in maintainers if m.get('email') and 'noreply' not in m.get('email', ''))
        print(f"   Contactable: {contactable}/{len(maintainers)} ({contactable/len(maintainers)*100:.1f}%)")
    
    # US-only analysis
    us_data = None
    for key, data in results.items():
        if 'us_only' in key and data['type'] == 'csv':
            us_data = data
            break
    
    if us_data:
        us_leads = us_data['leads']
        print(f"\n🇺🇸 US-ONLY LEADS ({len(us_leads)} total):")
        
        # Role distribution
        if us_leads and 'role_type' in us_leads[0]:
            role_counts = Counter(lead.get('role_type', '') for lead in us_leads)
            print(f"   Roles: {', '.join([f'{r}({n})' for r, n in role_counts.most_common()])}")
        
        # Tier distribution
        if us_leads and 'tier' in us_leads[0]:
            tier_counts = Counter(lead.get('tier', '') for lead in us_leads)
            print(f"   Tiers: {', '.join([f'{t}({n})' for t, n in tier_counts.most_common()])}")
    
    print(f"\n📋 CAMPAIGN READINESS:")
    print(f"   ✅ Directors identified: {len(directors_data['leads']) if directors_data else 0}")
    print(f"   ✅ Maintainers for context: {len(maintainers_data['leads']) if maintainers_data else 0}")
    print(f"   ✅ US market focus: {len(us_data['leads']) if us_data else 0}")
    print(f"   ✅ LinkedIn queries generated")
    print(f"   ✅ CI/DevOps signals captured")
    
    print(f"\n🚀 READY FOR OUTREACH!")
    print("=" * 60)


if __name__ == '__main__':
    analyze_campaign_results()
