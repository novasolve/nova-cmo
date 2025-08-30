# 🎬 Open Source Maintainers Video System

## 📁 **Organized File Structure**

```
/Users/seb/leads/
├── 📂 data/
│   ├── 🎥 demo_video_base_with_subtitles.mp4    # Main base video (NEW)
│   ├── 📂 intros/                               # Place your 87 intro videos here
│   ├── 📂 combined_videos/                      # Final output videos
│   ├── 📂 test_outputs/                         # Test videos for development
│   │   ├── test_background_overlay.mp4
│   │   ├── fixed_background_overlay.mp4
│   │   └── demo_with_subtitles_overlay.mp4
│   └── 📂 archive/                              # Old/unused files
│       ├── Automatic Python Test Fixer.mp4     # Original base video
│       └── background_36s.mp4                   # Old background video
├── 📂 scripts/                                  # Development scripts
│   ├── video_combiner.py                       # Original combiner
│   ├── video_combiner_overlay.py               # Overlay version
│   ├── test_background_overlay.py              # Background test
│   ├── fix_background_overlay.py               # Background fix
│   └── create_subtitle_overlay.py              # Subtitle test
├── 🎬 video_combiner_with_subtitles.py         # MAIN PRODUCTION SCRIPT
├── 🚀 run_video_combiner.sh                    # MAIN RUNNER SCRIPT
└── 📖 VIDEO_COMBINER_README.md                 # User documentation
```

## 🎯 **Production System (Ready to Use)**

### **Main Files:**

- `video_combiner_with_subtitles.py` - Production video combiner
- `run_video_combiner.sh` - Easy-to-use runner script
- `data/demo_video_base_with_subtitles.mp4` - Your new base video

### **Input/Output:**

- **Input**: Place 87 intro videos in `data/intros/`
- **Output**: `data/combined_videos/personalized_demo_01.mp4` through `personalized_demo_87.mp4`

## 🚀 **How to Use**

1. **Add Intro Videos**: Place all 87 intro videos in `data/intros/`
2. **Run System**: `./run_video_combiner.sh`
3. **Get Results**: 87 personalized videos in `data/combined_videos/`

## 🎨 **What It Does**

**First 36 seconds of each video:**

- ✅ Your intro video content (main visuals)
- ✅ Clean background from demo base video
- ✅ Preserved subtitles from base video
- ✅ Original audio from base video

**After 36 seconds:**

- ✅ Original demo base video continues normally

## 📊 **System Status**

- ✅ Base video updated to new version with subtitles
- ✅ Subtitle preservation implemented
- ✅ Clean background overlay working
- ✅ Batch processing ready for 87 videos
- ✅ Output naming: `personalized_demo_XX.mp4`
- ✅ All test files organized and archived

## 🛠️ **Development Files (Archived)**

All development and test scripts have been moved to `scripts/` and `data/test_outputs/` for organization. The main production system is clean and ready to use.

---

**Ready to create 87 personalized demo videos!** 🎬✨
