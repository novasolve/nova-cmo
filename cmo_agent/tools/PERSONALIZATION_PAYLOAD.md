## Personalization Payload (Spec)

This document defines the stable schema used by the personalization stage to describe a lead and suggested talking points. It is produced by `RenderCopy` in `cmo_agent/tools/personalization.py` and returned as `data["personalization"]` in the tool result.

- Stability: additive-only. Downstream tools may rely on existing fields; new fields may be added over time.
- Source: constructed from the input `lead` dictionary (see field mappings below).

### JSON Schema (structure)

```json
{
  "login": "string",
  "name": "string",
  "best_email": "string",
  "signals": {
    "maintainer_of": ["org/repo"],
    "recent_pr_titles": ["string"],
    "topics": ["string"],
    "primary_language": "string",
    "activity_90d_commits": 0,
    "followers": 0
  },
  "snippets": {
    "why_now": "string",
    "hook": "string"
  }
}
```

### Field definitions and mappings

- login: GitHub username. Maps from `lead["login"]` (default: empty string).
- name: Display name. Maps from `lead["name"]` (default: empty string).
- best_email: Preferred email. Maps from `lead["best_email"]` or falls back to `lead["email"]` (default: empty string).
- signals:
  - maintainer_of: Repositories the lead maintains. Maps from `lead["maintainer_repos"]` (default: []).
  - recent_pr_titles: Recent PR subjects. Maps from `lead["recent_pr_titles"]` (default: []).
  - topics: Repository/user topics. Maps from `lead["topics"]` (default: []).
  - primary_language: Main language. Maps from `lead["primary_language"]` (default: "Python").
  - activity_90d_commits: Commit activity count (90 days). Maps from `lead["activity_90d"]` (default: 0).
  - followers: GitHub followers. Maps from `lead["followers"]` (default: 0).
- snippets:
  - why_now: Time-relevance explanation. Maps from `lead["why_now"]` (default: "Recent activity shows active development").
  - hook: Value proposition line. Maps from `lead["hook"]` (default: "Nova can help optimize your development workflow").

### Relationship to template variables

`RenderCopy` also prepares Jinja2 variables for subject/body templates (these are separate from the JSON payload above):

- first_name: Derived from `lead["name"]` (first token) or `lead["login"]`; default "there".
- full_name: `lead["name"]` or `lead["login"]`; default "there".
- company: `lead["company"]`; default "your company".
- repo: `lead["primary_repo"]`; default "your project".
- language: `lead["primary_language"]`; default "Python".
- activity_days: `lead["activity_90d"]`; default 30.
- stars: `lead["total_stars"]`; default 100.
- followers: `lead["followers"]`; default 0.
- recent_pr: `lead["recent_pr_title"]`; default "performance improvements".
- why_now: `lead["why_now"]`; default "recent activity in your project".
- hook: `lead["hook"]`; default "Nova can help with your development workflow".

Notes:

- You can pass additional template variables by extending `_prepare_template_vars` or by providing them via the `campaign` templates.
- Jinja2 is configured with `autoescape=True`, `trim_blocks=True`, `lstrip_blocks=True`.

### Example

Input `lead` (excerpt):

```json
{
  "login": "octocat",
  "name": "Octo Cat",
  "email": "octo@example.com",
  "maintainer_repos": ["octo/ci-bot", "octo/awesome-lib"],
  "recent_pr_titles": ["Fix flaky test", "Improve CI cache"],
  "topics": ["ci", "testing", "github-actions"],
  "primary_language": "Python",
  "activity_90d": 42,
  "followers": 120,
  "why_now": "Saw sustained CI activity over the last 2 weeks",
  "hook": "Small GitHub App that proposes minimal CI fix PRs"
}
```

Produced personalization payload:

```json
{
  "login": "octocat",
  "name": "Octo Cat",
  "best_email": "octo@example.com",
  "signals": {
    "maintainer_of": ["octo/ci-bot", "octo/awesome-lib"],
    "recent_pr_titles": ["Fix flaky test", "Improve CI cache"],
    "topics": ["ci", "testing", "github-actions"],
    "primary_language": "Python",
    "activity_90d_commits": 42,
    "followers": 120
  },
  "snippets": {
    "why_now": "Saw sustained CI activity over the last 2 weeks",
    "hook": "Small GitHub App that proposes minimal CI fix PRs"
  }
}
```

Rendered email example (using defaults):

- Subject: `Quick fix for {{repo}} CI flakes`
- Body:
  - Greets `{{first_name}}`
  - Mentions `{{repo}}` and `{{language}}`
  - Includes `{{why_now}}` and `{{hook}}`

### Using the tool

```python
from cmo_agent.tools.personalization import RenderCopy

renderer = RenderCopy()
result = await renderer.execute(lead=my_lead_dict, campaign={
  "id": "ci-fix-demo",
  "subject_template": "{{first_name}}, quick CI fix idea for {{repo}}",
  "body_template": "Hi {{first_name}}, we noticed {{why_now}}. {{hook}}\n\n— Team"
})

if result.success:
    payload = result.data["personalization"]
    subject = result.data["subject"]
    body = result.data["body"]
```

### Extension points

- To add new signals/snippets, extend `_create_personalization_payload` conservatively (only additions).
- To enrich template variables, extend `_prepare_template_vars`.
- Keep fallbacks sensible to preserve deliverability and tone when data is missing.
