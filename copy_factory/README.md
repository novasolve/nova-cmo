# Copy Factory

Copy Factory is a comprehensive system for managing Ideal Customer Profiles (ICPs), prospect data, and generating personalized outreach copy for sales and marketing campaigns.

## Features

- **ICP Management**: Store and manage detailed customer profiles with technographics, firmographics, and behavioral triggers
- **Prospect Storage**: Import and organize prospect data from CSV files with email enrichment
- **Copy Generation**: Create personalized email, LinkedIn, and social media copy using templates
- **Campaign Management**: Organize outreach campaigns with automated copy generation
- **Data Integration**: Seamless integration with existing lead intelligence systems

## Quick Start

### 1. Setup

```bash
# Initialize Copy Factory with your existing data
python copy_factory/setup.py \
  --icp-yaml configs/icp/options.yaml \
  --prospects-csv data/prospects_latest.csv \
  --match-prospects \
  --create-templates
```

### 2. Basic Usage

```bash
# List available ICPs
python -m copy_factory.cli list-icps

# List prospects with emails
python -m copy_factory.cli list-prospects --has-email

# Create a campaign
python -m copy_factory.cli create-campaign "Python Dev Outreach" icp01_pypi_maintainers icp01_pypi_maintainers_email_template

# Generate personalized copy
python -m copy_factory.cli generate-copy campaign_icp01_pypi_maintainers_20241229_120000

# Export campaign data
python -m copy_factory.cli export-campaign campaign_icp01_pypi_maintainers_20241229_120000 outreach_copy.csv
```

## Architecture

```
copy_factory/
├── core/
│   ├── models.py          # Data models (ICPProfile, ProspectData, etc.)
│   ├── storage.py         # File-based storage system
│   ├── copy_generator.py  # Template processing and copy generation
│   └── factory.py        # Main orchestration engine
├── cli.py                 # Command-line interface
├── setup.py              # Setup and initialization script
└── README.md             # This file
```

## Data Models

### ICP Profile

- **ID**: Unique identifier
- **Name**: Human-readable name
- **Personas**: Target personas and titles
- **Firmographics**: Company size, geography, industry
- **Technographics**: Technologies, frameworks, tools
- **Triggers**: Behavioral signals and disqualifiers
- **GitHub Queries**: Search criteria for finding prospects

### Prospect Data

- **Lead ID**: Unique identifier
- **Contact Info**: Name, company, location, emails
- **GitHub Data**: Profile info, repositories, activity
- **ICP Matches**: Associated ICP profiles
- **Intelligence Score**: Lead quality scoring

### Copy Templates

- **Template Types**: Email, LinkedIn, Twitter
- **Variables**: Dynamic content insertion
- **ICP-Specific**: Tailored to specific customer profiles

## Template Variables

Available variables for copy generation:

- `${first_name}` - Prospect's first name
- `${last_name}` - Prospect's last name
- `${company}` - Company name
- `${repo_name}` - Repository name
- `${language}` - Programming language
- `${location}` - Geographic location
- `${icp_name}` - ICP profile name
- `${primary_language}` - Primary language from ICP

## Command Reference

### Import Commands

```bash
# Import ICP profiles from YAML
python -m copy_factory.cli import-icp configs/icp/options.yaml --auto-templates

# Import prospects from CSV
python -m copy_factory.cli import-prospects data/prospects_latest.csv --match-icps
```

### List Commands

```bash
# List all ICPs
python -m copy_factory.cli list-icps

# List prospects (with filters)
python -m copy_factory.cli list-prospects --icp icp01_pypi_maintainers --has-email --limit 10

# List templates
python -m copy_factory.cli list-templates --icp icp01_pypi_maintainers

# List campaigns
python -m copy_factory.cli list-campaigns --status active
```

### Create Commands

```bash
# Create template
python -m copy_factory.cli create-template icp01_pypi_maintainers "Custom Email Template" --type email

# Create campaign
python -m copy_factory.cli create-campaign "Q1 Outreach" icp01_pypi_maintainers template_123
```

### Generation Commands

```bash
# Generate copy for campaign
python -m copy_factory.cli generate-copy campaign_123 --preview

# Preview template
python -m copy_factory.cli preview-template template_123
```

### Export Commands

```bash
# Export campaign data
python -m copy_factory.cli export-campaign campaign_123 outreach_data.csv

# Export prospects
python -m copy_factory.cli export-prospects prospects_export.csv --icp icp01_pypi_maintainers
```

### Utility Commands

```bash
# Match prospects to ICPs
python -m copy_factory.cli match-prospects

# Show statistics
python -m copy_factory.cli stats

# Validate setup
python -m copy_factory.cli validate
```

## Example Template

```text
Subject: Question about your ${language} work at ${company}

Hi ${first_name},

I came across your ${repo_name} repository and was impressed by your work with ${language}.

As someone who helps ${icp_name} optimize their development workflows, I'd love to hear about your experience with ${frameworks}.

Are you open to a quick chat about how we might help your team?

Best regards,
[Your Name]
```

## Integration

Copy Factory integrates seamlessly with the existing lead intelligence system:

```python
from copy_factory.core.factory import CopyFactory

# Initialize
factory = CopyFactory()

# Import from intelligence system
factory.import_icp_from_yaml('configs/icp/options.yaml')
factory.import_prospects_from_csv('data/prospects_latest.csv')

# Generate copy for campaigns
campaign_copy = factory.generate_campaign_copy('campaign_id')
```

## Data Storage

Copy Factory uses a file-based storage system:

```
copy_factory/data/
├── icp/           # ICP profile JSON files
├── prospects/     # Prospect data JSON files
├── templates/     # Copy templates
├── campaigns/     # Campaign definitions
└── *.json         # Index files for quick lookup
```

## Best Practices

1. **ICP Definition**: Start with clear, specific ICP definitions
2. **Data Quality**: Regularly update and validate prospect data
3. **Template Testing**: Preview templates before large campaigns
4. **Campaign Segmentation**: Create focused campaigns for specific ICPs
5. **A/B Testing**: Test different copy variations for better results

## Troubleshooting

### Common Issues

1. **No ICP matches**: Run `match-prospects` to update prospect-ICP associations
2. **Template errors**: Use `preview-template` to validate template syntax
3. **Missing data**: Check data files and re-run imports if needed

### Validation

```bash
# Check setup health
python -m copy_factory.cli validate

# View statistics
python -m copy_factory.cli stats
```

## Development

To extend Copy Factory:

1. Add new variables in `copy_generator.py`
2. Create custom template types in `models.py`
3. Extend CLI commands in `cli.py`
4. Add new storage backends in `storage.py`

## License

Copyright 2024 Lead Intelligence Team
