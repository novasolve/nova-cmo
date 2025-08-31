# GitHub Prospect Scraper - Quick Start

## 📍 New Location: `/Users/seb/leads`

All lead generation tools are now in this directory.

## 🚀 Quick Setup

1. **Set up GitHub Token** (Classic token required):

   ```bash
   export GITHUB_TOKEN='ghp_your_token_here'
   ```

2. **Test your token**:

   ```bash
   python test_token.py
   ```

3. **Run scraper** (test with 2 repos):
   ```bash
   ./run_scraper.sh -n 2
   ```

## 📊 Features

- **Email-only filtering**: Only returns prospects with public emails
- **65+ data fields**: Everything from GitHub profiles
- **Social extraction**: Auto-extracts LinkedIn from blog URLs
- **Incremental writing**: CSV updates as prospects are found
- **Attio-ready**: All fields needed for CRM import

## 📁 Directory Structure

```
/Users/seb/leads/
├── github_prospect_scraper.py  # Main scraper (65+ fields)
├── run_scraper.sh             # Easy runner script
├── config.yaml                # Search configuration
├── test_token.py              # Token tester
├── setup_token.sh             # Token setup helper
├── data/                      # CSV outputs
│   └── prospects_latest.csv   # Symlink to latest run
├── configs/                   # Preset configurations
│   ├── ai-startups.yaml
│   ├── devtools.yaml
│   └── web3.yaml
└── docs/
    ├── COMPLETE_GITHUB_DATA.md
    └── ENHANCED_FIELDS.md
```

## 🔧 Common Commands

```bash
# Quick test (2 repos)
./run_scraper.sh -n 2

# Full run (50 repos from config)
./run_scraper.sh

# Use different config
./run_scraper.sh -c configs/ai-startups.yaml

# Check results
head -5 data/prospects_latest.csv | cut -d',' -f1-10
```

## 🔑 Need a Token?

Run `./setup_token.sh` for step-by-step instructions.


