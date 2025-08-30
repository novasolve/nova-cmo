# 🎬 Open Source Maintainers Video System

This directory contains the complete video processing system for creating personalized outreach videos for the Open Source Maintainers campaign.

## 📁 Directory Structure

```
video_system/
├── 📂 core/                          # Main production scripts
│   ├── video_combiner_with_subtitles.py
│   └── run_video_combiner.sh
├── 📂 dev/                           # Development & debug scripts
│   ├── batch_video_processor.py
│   ├── debug_freeze.py
│   ├── freeze_top_half.py
│   └── ... (other development scripts)
├── 📂 assets/                        # Video assets
│   ├── intros/                      # Input: Intro videos (87 videos)
│   └── base_videos/                 # Input: Base demo videos
├── 📂 outputs/                       # Generated videos
│   ├── combined/                    # Final personalized videos
│   ├── tests/                       # Test outputs
│   └── archive/                     # Old/unused videos
├── 📂 tools/                        # External tools
│   ├── ffmpeg                      # Video processing binary
│   └── ffmpeg.tar.xz               # FFmpeg archive
└── 📖 *.md                         # Documentation
```

## 🚀 Quick Start

1. **Place your intro videos** in `assets/intros/` (87 videos)
2. **Place your base video** in `assets/base_videos/`
3. **Run the system**:
   ```bash
   cd core
   ./run_video_combiner.sh
   ```
4. **Get results** in `outputs/combined/` (87 personalized videos)

## 🎯 What It Does

**First 36 seconds of each video:**

- ✅ Your custom intro video content
- ✅ Clean background from base video
- ✅ Preserved subtitles from base video
- ✅ Original audio from base video

**After 36 seconds:**

- ✅ Original base video continues normally

## 📊 System Components

### Core Production System

- `video_combiner_with_subtitles.py` - Main video processing script
- `run_video_combiner.sh` - Easy-to-use runner script

### Development Tools

- Various debug and development scripts in `dev/`
- Test scripts for background overlays, subtitle handling, etc.

### Documentation

- `README_VIDEO_SYSTEM.md` - Original system overview
- `VIDEO_COMBINER_README.md` - Detailed usage instructions

## 🔧 Requirements

- Python 3.12+
- MoviePy
- OpenCV & Pillow
- FFmpeg (included in `tools/`)

## 📈 File Organization Benefits

✅ **Clean separation** of production vs development code
✅ **Logical asset organization** (inputs, outputs, tools)
✅ **Easy maintenance** - know where everything belongs
✅ **Scalable structure** for future video processing needs
✅ **Backup-friendly** - clear archive locations

## 🎬 Production Workflow

1. **Input**: Place 87 intro videos in `assets/intros/`
2. **Process**: Run `./core/run_video_combiner.sh`
3. **Output**: 87 personalized videos in `outputs/combined/`
4. **Archive**: Move old videos to `outputs/archive/`

---

**Ready to create personalized outreach videos!** 🎬✨
