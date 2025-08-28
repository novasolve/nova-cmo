# Makefile Usage Guide

Simple Makefile with essential commands for the GitHub prospect scraper.

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

Run `make help` to see all commands:

### Setup
- `make install` - Install dependencies
- `make setup` - Setup project (install + check token)

### Main Commands
- `make scrape` - Run default scraper
- `make attio` - Generate Attio-ready CSVs ⭐
- `make url URL=@username` - Quick URL analysis

### Development
- `make test` - Small test scrape (2 repos)
- `make clean` - Clean up files

## Examples

### Basic Usage
```bash
# Setup and run Attio export
make setup
make attio

# Quick user analysis
make url URL=@octocat

# Test your setup
make test
```

## GitHub Actions

The project includes one automated workflow:

### Attio Export (`.github/workflows/attio-export.yml`)
- Runs weekly on Mondays at 8 AM UTC
- Generates Attio-ready exports automatically
- Manual trigger available in Actions tab
- 30-day artifact retention

## Configuration

- Main config: `config.yaml`
- Output directory: `data/`
- Export directory: `exports/attio/`

## Tips

1. **Always check your token**: `make setup`
2. **Start small**: `make test` before full runs
3. **Clean regularly**: `make clean` to free space