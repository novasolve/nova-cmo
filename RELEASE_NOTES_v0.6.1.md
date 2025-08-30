# 🚀 v0.6.1 - The One That Actually Works™

## 🎉 It's Alive!

After battling the dreaded `422 Validation Failed` beast, we've emerged victorious! This release fixes the GitHub Search API compatibility issues that were preventing the scraper from doing its one job - scraping.

## 🐛 What Was Broken (And Now Isn't)

### The GitHub Search API Rebellion 
- **The Drama**: GitHub's API was throwing tantrums because it doesn't like `>=` in date filters
- **The Hero Move**: We switched to `>` and suddenly GitHub became our friend again
- **The Result**: No more 422 errors! The scraper actually scrapes now! 🎊

## ✨ New Superpowers

### Dynamic Date Magic 🪄
- Added smart date placeholder support with `{date:N}` syntax
- Automatically converts to proper `YYYY-MM-DD` format
- Makes your config files look cleaner and work better

## 🛠️ Technical Stuff
```diff
- pushed:>={date:60}  # GitHub: "I don't like this"
+ pushed:>{date:60}   # GitHub: "This sparks joy"
```

## 📦 What's Changed
- Fixed search query syntax in `configs/main.yaml`
- Added `_render_query()` method for date placeholder wizardry
- Made the scraper actually... scrape

## 🚀 Quick Start
```bash
git pull
./run_scraper.sh --leads 100  # Watch it actually work!
```

## 🎮 Testing Status
✅ Scraper finds repos without throwing fits  
✅ Date placeholders work like magic  
✅ Successfully collected leads without errors  
✅ Your sanity: Restored  

---

**TL;DR**: We fixed the thing. It works now. You're welcome. 🎉

**Full Changelog**: https://github.com/novasolve/leads/compare/v0.6.0...v0.6.1