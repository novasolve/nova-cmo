# Agents

This project can be driven by agents that automate scraping, enrichment, and Attio sync.

## Roles

- Research Agent: builds search queries and identifies target ecosystems.
- Scraper Agent: runs `github_prospect_scraper.py` and `github_repo_scraper.py` on schedules.
- Enrichment Agent: augments People with predicted emails, LinkedIn, and company mapping.
- Import Agent: prepares CSVs aligned to `docs/attio_oss_model.md` and uploads to Attio.
- Outreach Agent: triggers sequences based on Signals and recent activity.

## Data Contracts

All agents must adhere to the Attio schema documented in `docs/attio_oss_model.md`. Upsert keys:

- People → `login`
- Repos → `repo_full_name`
- Membership → `membership_id`
- Signals → `signal_id`

## Schedules

- Repos/People scrape: daily
- Signals: hourly for tracked repos
- Imports to Attio: after each successful scrape/enrichment cycle


