# Enhanced GitHub Prospect Scraper - Attio Integration

## ✨ New Fields Added

The scraper now includes all the fields needed for Attio CRM integration:

### Core Fields (Original)

- `lead_id` - Unique identifier for deduplication (MD5 hash)
- `login` - GitHub username
- `name` - Full name from GitHub profile
- `company` - Company from GitHub profile
- `email_public_commit` - Email extracted from commits (if public)
- `repo_full_name` - Repository where activity was found
- `signal` - The specific activity (PR title or commit message)
- `signal_type` - Type of activity: 'pr' or 'commit'
- `signal_at` - Timestamp of the activity
- `topics` - Repository topics (comma-separated)
- `language` - Primary repository language
- `stars` - Repository star count

### New Fields for Attio

- `github_user_url` - Direct link to user's GitHub profile (e.g., https://github.com/username)
- `github_repo_url` - Direct link to the repository (e.g., https://github.com/owner/repo)
- `bio` - User's bio from GitHub profile
- `location` - User's location
- `twitter_username` - Twitter/X username (if provided)
- `blog` - Personal website/blog URL
- `hireable` - Whether user is open to job opportunities
- `public_repos` - Number of public repositories
- `followers` - Number of GitHub followers
- `created_at` - When the GitHub account was created

## 🔧 Usage with Attio

The `lead_id` field serves as the unique record identifier for Attio. When importing:

1. Map `lead_id` as the unique identifier
2. Map `email_public_commit` to the email field
3. Map `github_user_url` and `github_repo_url` as custom fields
4. Use `signal` and `signal_at` for engagement tracking
5. Map social fields (`twitter_username`, `blog`) for enrichment

## 📊 Example Output

```csv
lead_id,login,name,company,email_public_commit,repo_full_name,signal,signal_type,signal_at,topics,language,stars,github_user_url,github_repo_url,bio,location,twitter_username,blog,hireable,public_repos,followers,created_at
413f4b83846d,kS-crane,,,kscrane@tesla.com,0xBallpoint/trapster-community,opened PR #123: Add new feature,pr,2024-08-27T10:30:00Z,ai,ml,Python,150,https://github.com/kS-crane,https://github.com/0xBallpoint/trapster-community,"AI Engineer",San Francisco,kscrane,https://kscrane.dev,true,42,523,2019-03-15T08:00:00Z
```

## 🚀 Quick Test

```bash
# Test with just 2 repos
./run_scraper.sh -n 2

# Check the output
head -5 data/prospects_latest.csv
```
