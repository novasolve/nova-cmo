# 🎬 Open Source Maintainers Video Overlay Combiner

This tool helps you combine your 87 custom intro videos with your base video using an **overlay approach** to create personalized outreach content for the Open Source Maintainers campaign.

## 🎯 How It Works

**Overlay Approach:**

- **First 36 seconds**: Intro video visuals + Base video audio/subtitles + Background video
- **Rest of video**: Original base video content
- **Result**: 87 personalized videos with custom intros but consistent messaging

## 📋 Setup Instructions

### 1. Place Your Videos

1. **Base Video**: Already in `/data/Automatic Python Test Fixer.mp4` (provides audio & main content)
2. **Background Video**: Already in `/data/background_36s.mp4` (36-second background layer)
3. **Intro Videos**: Place all 87 intro videos in `/data/intros/`
   - Supported formats: `.mp4`, `.mov`, `.avi`, `.mkv`, `.webm`
   - Name them descriptively (e.g., `intro_john_doe.mp4`, `intro_jane_smith.mp4`)

### 2. Run the Combiner

```bash
./run_video_combiner.sh
```

The script will:

- Count your intro videos
- Confirm 36-second overlay duration
- Process all videos automatically using overlay technique
- Save results to `/data/combined_videos/`

## 🎨 Overlay Configuration

The system uses:

- **Intro Videos**: Provide the main visual content for first 36 seconds
- **Base Video Audio**: Original audio track and subtitles from main video
- **Background Video**: 36-second background layer that matches subtitle area
- **Duration**: Fixed at 36 seconds for optimal overlay

## 📁 Output Structure

Combined videos will be saved as:

```
/data/combined_videos/
├── combined_01.mp4
├── combined_02.mp4
├── combined_03.mp4
...
└── combined_87.mp4
```

## ⚡ Features

- ✅ **Batch Processing**: Handles all 87 videos automatically
- ✅ **Background Modification**: Add static backgrounds to first N seconds
- ✅ **Format Support**: Works with multiple video formats
- ✅ **Progress Tracking**: Shows progress for each video
- ✅ **Error Handling**: Skips problematic videos and continues processing
- ✅ **Organized Output**: Numbered files for easy management

## 🛠️ Advanced Usage

If you want more control, you can run the Python script directly:

```bash
python3 video_combiner.py \
    --intros-dir /path/to/intros \
    --base-video /path/to/base/video.mp4 \
    --output-dir /path/to/output \
    --background-duration 5
```

## 📊 Requirements

- Python 3.12+
- MoviePy (automatically installed)
- OpenCV & Pillow (already installed)

## 🎯 Workflow

1. **Prepare**: Place all intro videos in `/data/intros/`
2. **Run**: Execute `./run_video_combiner.sh`
3. **Choose**: Select background overlay option
4. **Wait**: Script processes all 87 videos (may take time)
5. **Upload**: Use combined videos for your outreach campaign

## 💡 Tips

- **Video Quality**: All output videos match the base video's resolution and quality
- **File Naming**: Combined videos are numbered sequentially for easy reference
- **Processing Time**: Expect 1-2 minutes per video depending on length and hardware
- **Storage**: Ensure you have enough disk space for 87 additional video files

## 🚨 Troubleshooting

- **"No intro videos found"**: Check that videos are in `/data/intros/` with supported extensions
- **"Base video not found"**: Ensure the base video is at `/data/Automatic Python Test Fixer.mp4`
- **Processing errors**: Individual video errors won't stop the batch - check the output for details

---

Happy video combining! 🎬✨
