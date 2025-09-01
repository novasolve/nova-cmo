#!/usr/bin/env python3
"""
Script to save campaign outputs to logs directory
"""
import json
import csv
from pathlib import Path
from datetime import datetime

def save_campaign_outputs_to_logs(checkpoint_file: str):
    """Extract campaign data and save outputs to logs directory"""

    checkpoint_path = Path(checkpoint_file)
    if not checkpoint_path.exists():
        print(f"❌ Checkpoint file not found: {checkpoint_file}")
        return

    # Load checkpoint data
    with open(checkpoint_path, 'r') as f:
        data = json.load(f)

    # Handle nested state structure
    if 'state' in data:
        state_data = data['state']
        job_id = state_data.get('job_id', data.get('job_id', 'unknown'))
        leads = state_data.get('leads', [])
    else:
        job_id = data.get('job_id', 'unknown')
        leads = data.get('leads', [])

    # Filter leads with valid emails (exclude noreply but include others)
    leads_with_emails = []
    for lead in leads:
        email = lead.get('email')
        if email and '@' in str(email):
            email_str = str(email).lower()
            # Exclude only GitHub noreply addresses
            if not email_str.endswith('@users.noreply.github.com') and email_str != 'noreply@github.com':
                leads_with_emails.append(lead)

    print(f"📊 Processing campaign: {job_id}")
    print(f"📧 Found {len(leads_with_emails)} leads with valid emails")

    # Create logs directory
    logs_dir = Path('./logs')
    logs_dir.mkdir(exist_ok=True)

    if leads_with_emails:
        # Save CSV file
        csv_filename = f"{job_id}_leads_with_emails.csv"
        csv_path = logs_dir / csv_filename

        with open(csv_path, 'w', newline='', encoding='utf-8') as csvfile:
            fieldnames = ['login', 'name', 'email', 'company', 'location', 'bio', 'public_repos', 'followers', 'html_url', 'blog', 'twitter_username']
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()

            for lead in leads_with_emails:
                writer.writerow({
                    'login': lead.get('login', ''),
                    'name': lead.get('name', ''),
                    'email': lead.get('email', ''),
                    'company': lead.get('company', ''),
                    'location': lead.get('location', ''),
                    'bio': lead.get('bio', ''),
                    'public_repos': lead.get('public_repos', ''),
                    'followers': lead.get('followers', ''),
                    'html_url': lead.get('html_url', ''),
                    'blog': lead.get('blog', ''),
                    'twitter_username': lead.get('twitter_username', '')
                })

        # Save summary report
        report_filename = f"{job_id}_campaign_summary.md"
        report_path = logs_dir / report_filename

        repos_count = len(data.get("repos", []))
        candidates_count = len(data.get("candidates", []))
        leads_count = len(leads_with_emails)

        report_content = f"""# Campaign Summary - {job_id}

## 📊 Results Overview
- **Repositories Found:** {repos_count}
- **Contributors Extracted:** {candidates_count}
- **Qualified Leads with Emails:** {leads_count}
- **Email Discovery Rate:** {(leads_count/candidates_count*100) if candidates_count > 0 else 0:.1f}%

## 📁 Output Files
- **Lead List:** {csv_filename}
- **Full Checkpoint:** {checkpoint_path.name}
- **Campaign Log:** {job_id}.log

## 🎯 Top Leads Found
"""

        # Add top leads to summary
        for i, lead in enumerate(leads_with_emails[:5], 1):
            name = lead.get('name') or lead.get('login', 'Unknown')
            email = lead.get('email', '')
            company = lead.get('company', 'Independent')
            followers = lead.get('followers', 0)

            report_content += f"{i}. **{name}** - {email}\n"
            report_content += f"   - Company: {company}\n"
            report_content += f"   - GitHub: {followers} followers\n\n"

        report_content += f"\n_Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}_"

        with open(report_path, 'w', encoding='utf-8') as f:
            f.write(report_content)

        print(f"✅ Saved CSV: {csv_path}")
        print(f"✅ Saved Report: {report_path}")

        # Create a log entry about the files
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "event": "output_files_saved",
            "job_id": job_id,
            "csv_file": str(csv_path),
            "report_file": str(report_path),
            "leads_count": leads_count,
            "message": f"Campaign output files saved to logs directory"
        }

        # Save log entry
        log_file = logs_dir / f"{job_id}_output_log.json"
        with open(log_file, 'w', encoding='utf-8') as f:
            json.dump(log_entry, f, indent=2)

        print(f"✅ Saved Log Entry: {log_file}")
        print(f"\n🎉 All output files saved to logs directory!")

    else:
        print("⚠️ No leads with valid emails found")

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        save_campaign_outputs_to_logs(sys.argv[1])
    else:
        # Use the latest checkpoint
        latest_checkpoint = "cmo_agent/checkpoints/cmo-20250831-181335-112231-ecd7f0_completed_20250831_181442.json"
        save_campaign_outputs_to_logs(latest_checkpoint)
