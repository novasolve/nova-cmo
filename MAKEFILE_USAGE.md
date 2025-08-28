# Makefile Usage Guide

This project includes a comprehensive Makefile to simplify common operations.

## Quick Start

```bash
# Setup project
make setup

# Generate Attio-ready exports
make attio

# Quick URL analysis
make url URL=@username
```

## Available Commands

Run `make help` to see all available commands:

### Setup & Installation

- `make install` - Install Python dependencies
- `make setup` - Full setup (install + check token)
- `make check-token` - Verify GitHub token is configured

### Main Scraping Commands

- `make scrape` - Run default scraper
- `make attio` - Generate Attio-ready CSVs (People, Repos, Memberships, Signals)
- `make segments` - Run all configured segments
- `make production` - Full production run with backup

### URL Scraping

- `make url URL=@username` - Quick user analysis
- `make url URL=https://github.com/user/repo` - Repository analysis
- `make url-save URL=@username` - Save results to CSV

### Specific Segments

- `make ai-startups` - Scrape AI/ML segment
- `make devtools` - Scrape developer tools segment
- `make web3` - Scrape blockchain/Web3 segment

### Development & Testing

- `make test` - Small test scrape (2 repos)
- `make quick` - Quick scrape (5 repos)
- `make lint` - Run code linting
- `make clean` - Clean up generated files

### Data Management

- `make show-data` - List current data files
- `make show-exports` - List export files
- `make backup` - Create backup archive
- `make rate-limit` - Check GitHub API limits

## Examples

### Basic Usage

```bash
# Setup and run Attio export
make setup
make attio

# Quick user analysis
make url URL=@octocat

# Run specific segment
make ai-startups
```

### Production Workflow

```bash
# Full production run
make production

# This runs:
# 1. Token check
# 2. Clean exports
# 3. All segments
# 4. Attio export
# 5. Backup creation
```

### Development Workflow

```bash
# Test changes
make test
make lint

# Clean up
make clean
```

## Configuration

The Makefile uses these default configurations:

- Main config: `config.yaml`
- Output directory: `data/`
- Export directory: `exports/`
- Attio exports: `exports/attio/`

## GitHub Actions

The project includes automated workflows:

### Attio Export Pipeline (`.github/workflows/attio-export.yml`)

- Runs daily at 6 AM UTC
- Generates Attio-ready exports
- Uploads artifacts for 30-90 days
- Manual trigger available

### Weekly Scrape (`.github/workflows/weekly-scrape.yml`)

- Runs every Monday at 8 AM UTC
- Full production scrape
- 60-day artifact retention

## Tips

1. **Always check your token**: `make check-token`
2. **Start small**: `make test` before full runs
3. **Monitor rate limits**: `make rate-limit`
4. **Clean regularly**: `make clean` to free space
5. **Use segments**: Target specific audiences with segment configs
