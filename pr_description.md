# Attio CRM Integration

## 🎯 Overview

This PR adds comprehensive Attio CRM integration to the lead intelligence system, enabling automatic syncing of qualified leads to Attio with full intelligence data.

## ✨ Features Added

### 🔗 Attio Integration

- **Automatic Lead Syncing**: `make intelligence` now pushes qualified leads to Attio
- **Object Creation**: Automated setup of People, Repos, Signals, and Membership objects
- **Data Mapping**: Comprehensive mapping from intelligence pipeline to Attio format
- **Error Handling**: Graceful degradation and helpful error messages

### 🛠️ New Tools

- **Setup Scripts**: Easy configuration with `make attio-setup` and `make attio-objects`
- **Testing Suite**: Comprehensive test suite with `make attio-test`
- **Object Management**: Automated Attio object creation and validation

## 🚀 Usage

### 1. Configure Attio Credentials

```bash
export ATTIO_API_TOKEN='your_token_here'
export ATTIO_WORKSPACE_ID='your_workspace_id_here'
```

### 2. Setup Attio Objects

```bash
make attio-objects  # Creates required objects in Attio
```

### 3. Run Intelligence Pipeline

```bash
make intelligence  # Automatically pushes to Attio
```

## 📊 Integration Points

### Attio Objects Created

- **People Object**: OSS maintainers with intelligence scores, engagement potential, and GitHub stats
- **Repos Object**: GitHub repositories with activity data, topics, and CI status
- **Signals Object**: GitHub events and engagement signals (PRs, issues, commits)
- **Repo Membership Object**: Person-repository relationships with contribution data

### Data Mapping

- **Intelligence Scores**: Priority scores, deliverability risk, engagement potential
- **GitHub Data**: Followers, contributions, repository activity, CI status
- **Enrichment Data**: Technology stack, company info, activity patterns
- **Signal Data**: Recent commits, PR activity, issue engagement

## 🧪 Testing

- ✅ Demo mode works without Attio token
- ✅ Proper logging and error handling
- ✅ Graceful degradation when Attio is unavailable
- ✅ Comprehensive data mapping to Attio format
- ✅ Connection validation and retry logic

## 📁 Files Changed

### New Files

- `setup_attio.sh` - Attio setup helper script
- `setup_attio_objects.py` - Script to create required Attio objects
- `test_attio.py` - Attio integration testing script

### Modified Files

- `lead_intelligence/core/intelligence_engine.py` - Added Attio integration logic
- `lead_intelligence/scripts/run_intelligence.py` - Enhanced with Attio support
- `Makefile` - Added Attio-related targets (`attio-setup`, `attio-objects`, `attio-test`)
- `README.md` - Updated with Attio integration documentation
- `setup_token.sh` - Enhanced with Attio setup instructions

## 🔒 Security

- Environment variables used for all sensitive data
- No tokens committed to repository
- Graceful handling when tokens are missing
- Clear error messages for configuration issues

## 🎉 Benefits

1. **Seamless CRM Integration**: Leads automatically sync to Attio with full intelligence
2. **Rich Data Model**: Comprehensive OSS maintainer profiles with GitHub signals
3. **Easy Setup**: Simple commands to configure and test the integration
4. **Robust Error Handling**: System continues to work even if Attio is unavailable
5. **Complete Transparency**: Full logging and reporting of integration status

## 🏃‍♂️ Quick Test

You can test the integration immediately:

```bash
# Test without Attio (demo mode)
make intelligence-demo

# Test with Attio (if configured)
make attio-test
make intelligence
```

The integration is production-ready and will enhance your lead management workflow significantly!
