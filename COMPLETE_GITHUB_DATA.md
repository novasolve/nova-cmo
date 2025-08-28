# Complete GitHub Data Scraper

## 🎯 Key Features

1. **Email-Only Filtering**: Only includes prospects who have a public email (either from commits or profile)
2. **Complete GitHub Profile**: Pulls EVERYTHING available from GitHub API
3. **Social Media Extraction**: Automatically extracts LinkedIn from blog URLs
4. **Pronoun Detection**: Extracts pronouns from bio (he/him, she/her, they/them)
5. **Incremental Writing**: Writes to CSV as prospects are found

## 📊 All Fields Captured

### Core Identification

- `lead_id` - Unique identifier (MD5 hash)
- `login` - GitHub username
- `id` - GitHub user ID
- `node_id` - GitHub GraphQL node ID

### Personal Information

- `name` - Full name
- `company` - Company name
- `email_public_commit` - Email from public commits
- `email_profile` - Email from GitHub profile
- `location` - Geographic location
- `bio` - User biography
- `pronouns` - Extracted pronouns (he/him, she/her, they/them)

### Repository Context

- `repo_full_name` - Repository where activity was found
- `repo_description` - Repository description
- `signal` - The specific activity (PR title or commit message)
- `signal_type` - Type of activity: 'pr' or 'commit'
- `signal_at` - Timestamp of the activity
- `topics` - Repository topics (comma-separated)
- `language` - Primary repository language
- `stars` - Repository star count
- `forks` - Repository fork count
- `watchers` - Repository watcher count

### URLs (All Available)

- `github_user_url` - Direct link to user's GitHub profile
- `github_repo_url` - Direct link to the repository
- `avatar_url` - Profile picture URL
- `html_url` - HTML URL for the user
- `api_url` - API endpoint URL
- `followers_url` - API URL for followers
- `following_url` - API URL for following
- `gists_url` - API URL for gists
- `starred_url` - API URL for starred repos
- `subscriptions_url` - API URL for subscriptions
- `organizations_url` - API URL for organizations
- `repos_url` - API URL for repos
- `events_url` - API URL for events
- `received_events_url` - API URL for received events

### Social/Professional

- `twitter_username` - Twitter/X username
- `blog` - Personal website/blog URL
- `linkedin_username` - LinkedIn username (extracted from blog if LinkedIn URL)
- `hireable` - Whether user is open to job opportunities

### GitHub Statistics

- `public_repos` - Number of public repositories
- `public_gists` - Number of public gists
- `followers` - Number of GitHub followers
- `following` - Number of users they follow
- `total_private_repos` - Total private repositories
- `owned_private_repos` - Owned private repositories
- `private_gists` - Number of private gists
- `disk_usage` - Disk usage in KB
- `collaborators` - Number of collaborators

### Contribution Data

- `contributions_last_year` - Contributions in the last year (requires GraphQL)
- `total_contributions` - Total contributions (requires GraphQL)
- `longest_streak` - Longest contribution streak (requires GraphQL)
- `current_streak` - Current contribution streak (requires GraphQL)

### Account Metadata

- `created_at` - When the GitHub account was created
- `updated_at` - Last profile update
- `type` - User type (User, Organization, etc.)
- `site_admin` - Whether user is a GitHub site admin
- `gravatar_id` - Gravatar ID
- `suspended_at` - If suspended, when

### Plan Information

- `plan_name` - GitHub plan name
- `plan_space` - Plan space allocation
- `plan_collaborators` - Plan collaborator limit
- `plan_private_repos` - Plan private repo limit

### Additional Flags

- `two_factor_authentication` - Whether 2FA is enabled
- `has_organization_projects` - Has organization projects enabled
- `has_repository_projects` - Has repository projects enabled

## 🚀 Usage

```bash
# Quick test with 2 repos (only prospects with emails)
./run_scraper.sh -n 2

# Full run
./run_scraper.sh

# Check the output
head -5 data/prospects_latest.csv | cut -d',' -f1-10
```

## 📧 Email Filtering

The scraper will automatically skip any prospects without an email address:

- First checks for email in commits (`email_public_commit`)
- Then checks GitHub profile (`email_profile`)
- If neither exists, the prospect is skipped with a warning:
  ```
  ⚠️  Skipping username - no email found
  ```

## 🔗 LinkedIn Extraction

If a user has a LinkedIn URL in their blog field, the scraper will:

1. Detect the LinkedIn URL
2. Extract the username portion
3. Store it in the `linkedin_username` field

Example: `https://linkedin.com/in/johndoe` → `linkedin_username: johndoe`

## 💡 Pro Tips

1. **Test First**: Always test with `-n 2` to verify your token works
2. **Email Focus**: The scraper now only returns prospects with emails
3. **Rich Data**: Every field from GitHub API is captured
4. **Attio Ready**: All fields needed for CRM import are included
5. **Social Enrichment**: LinkedIn extraction happens automatically

## 🔒 Required GitHub Token Scopes

Your GitHub token needs these scopes:

- `public_repo` - Read public repositories
- `read:user` - Read user profile information
- `user:email` - Read user email addresses (if available)

Create a token at: https://github.com/settings/tokens
