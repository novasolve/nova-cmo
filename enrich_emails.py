#!/usr/bin/env python3
"""
Email Enrichment Helper
Adds email addresses to prospects using various strategies
"""

import csv
import re
import time
from typing import Dict, Optional
import requests


class EmailEnricher:
    """Email enrichment strategies"""

    def __init__(self):
        self.email_patterns = [
            "{first}.{last}@{domain}",
            "{first}{last}@{domain}",
            "{first}_{last}@{domain}",
            "{first}-{last}@{domain}",
            "{first}@{domain}",
            "{f}{last}@{domain}",
            "{first}{l}@{domain}",
            "{f}.{last}@{domain}",
        ]

    def guess_email_patterns(self, name: str, company: str) -> list:
        """Generate possible email patterns"""
        if not name or not company:
            return []

        # Clean and split name
        name_parts = name.lower().strip().split()
        if len(name_parts) < 2:
            return []

        first = name_parts[0]
        last = name_parts[-1]
        f = first[0]
        l = last[0]

        # Clean company name to domain
        domain = self._company_to_domain(company)
        if not domain:
            return []

        # Generate email variations
        emails = []
        for pattern in self.email_patterns:
            email = pattern.format(
                first=first,
                last=last,
                f=f,
                l=l,
                domain=domain
            )
            emails.append(email)

        return emails

    def _company_to_domain(self, company: str) -> Optional[str]:
        """Convert company name to likely domain"""
        if not company:
            return None

        # Clean company name
        company = company.lower().strip()

        # Remove common suffixes
        suffixes = [
            ', inc.', ', inc', ' inc.', ' inc',
            ', llc', ' llc',
            ', ltd', ' ltd',
            ' corporation', ' corp',
            ' limited', ' ltd',
            ' labs', ' lab',
            ' technologies', ' technology', ' tech',
            ' software', ' systems',
            ' solutions', ' services',
            ' company', ' co',
        ]

        for suffix in suffixes:
            if company.endswith(suffix):
                company = company[:-len(suffix)]

        # Convert to domain format
        domain = re.sub(r'[^a-z0-9]', '', company)

        # Try common TLDs
        return f"{domain}.com"

    def verify_email(self, email: str) -> bool:
        """
        Basic email verification (implement your preferred method)
        Options:
        - Email validation service API
        - SMTP check
        - DNS MX record check
        """
        # For now, just check format
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return bool(re.match(pattern, email))

    def enrich_csv(self, input_file: str, output_file: str):
        """Add email guesses to prospect CSV"""
        enriched_count = 0

        with open(input_file, 'r', encoding='utf-8') as infile:
            reader = csv.DictReader(infile)
            prospects = list(reader)

        # Add email columns
        for prospect in prospects:
            # Skip if already has email
            if prospect.get('email_public_commit'):
                prospect['email_enriched'] = prospect['email_public_commit']
                prospect['email_source'] = 'github'
                continue

            # Try to guess email
            name = prospect.get('name', '')
            company = prospect.get('company', '')

            if name and company:
                possible_emails = self.guess_email_patterns(name, company)
                if possible_emails:
                    # Take the first pattern as most likely
                    prospect['email_enriched'] = possible_emails[0]
                    prospect['email_source'] = 'pattern_guess'
                    prospect['email_alternatives'] = '|'.join(possible_emails[1:4])
                    enriched_count += 1
                else:
                    prospect['email_enriched'] = ''
                    prospect['email_source'] = ''
                    prospect['email_alternatives'] = ''
            else:
                prospect['email_enriched'] = ''
                prospect['email_source'] = ''
                prospect['email_alternatives'] = ''

        # Write enriched data
        if prospects:
            fieldnames = list(prospects[0].keys())
            with open(output_file, 'w', newline='', encoding='utf-8') as outfile:
                writer = csv.DictWriter(outfile, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(prospects)

        print(f"✅ Enriched {enriched_count} prospects with email patterns")
        print(f"📧 Output saved to: {output_file}")

        # Show sample patterns
        print("\n📋 Sample email patterns generated:")
        sample_count = 0
        for p in prospects[:10]:
            if p.get('email_enriched') and p.get('email_source') == 'pattern_guess':
                print(f"  - {p['name']} @ {p['company']} → {p['email_enriched']}")
                sample_count += 1
                if sample_count >= 5:
                    break


def main():
    import argparse

    parser = argparse.ArgumentParser(description='Email Enrichment Helper')
    parser.add_argument('input', help='Input CSV file from scraper')
    parser.add_argument('-o', '--output', help='Output CSV file (default: input_enriched.csv)')
    args = parser.parse_args()

    # Set output filename
    if not args.output:
        base = args.input.rsplit('.csv', 1)[0]
        args.output = f"{base}_enriched.csv"

    enricher = EmailEnricher()
    enricher.enrich_csv(args.input, args.output)

    print("\n💡 Next steps:")
    print("1. Verify emails with a validation service")
    print("2. Use Hunter.io, Apollo, or Clearbit for professional enrichment")
    print("3. Cross-reference with LinkedIn Sales Navigator")
    print("4. Start with pattern guesses for companies you recognize")


if __name__ == '__main__':
    main()
