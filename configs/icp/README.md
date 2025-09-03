# ICP Campaign & Linear Issue Configs

This directory contains configuration for ICP campaign segments and their corresponding planning issues.

## Files

- `options.yaml`: Global defaults and ICP options used across campaigns
- `campaigns.yaml`: ICP campaign segments (each entry keyed by `key`)
- `linear_issues.yaml`: Execution plan items mapped to campaign segments

## Segment: c11_platform_midmarket

- key: `c11_platform_midmarket`
- name: Mid‑Market SaaS — Platform Engineering (100–1k emp)
- icp:
  - uses_actions: true
  - company_size: "100-1000"
  - industries: [Software & Internet, SaaS]
  - personas.titles_contains: Platform, Developer Productivity, DevEx, Developer Experience, Developer Effectiveness, Developer Enablement, SRE, Build, Release, Engineering Manager
  - personas.levels: Senior, Staff, Principal, Manager, Director
  - exclude_title_or_company: Consultant, Contractor, Agency, Services, MSP, VAR, Staffing, Recruiter, Instructor, Training, Evangelist, Advocate, Partnerships, Partner
- instantly:
  - one_lead_per_company: true
  - skip_already_owned: true
  - saved_segment_name: "OS-4200 Platform Eng Mid‑Market"

## Linear Issues

- Parent issue: `OS-4200` → `campaign_key: c11_platform_midmarket`
- Sub-issues (via `parent_key: OS-4200`):
  - `OS-4200-1`: Define Instantly segment & filters
  - `OS-4200-2`: Validate 25 lead samples for fit
  - `OS-4200-3`: Prepare outreach sequence & tokens
  - `OS-4200-4`: Seed send to 50 leads
  - `OS-4200-5`: Report results & finalize segment

Workflow: update YAMLs, commit with `OS-4200: <summary>`, push to `main`. Optionally sync to Linear and set up Instantly.
