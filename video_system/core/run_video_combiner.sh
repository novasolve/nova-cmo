#!/bin/bash

# Video Combiner Runner Script
# This script helps you combine your 87 intro videos with the base video

echo "🎬 Open Source Maintainers Video Combiner"
echo "========================================"

# Configuration
VIDEO_SYSTEM_DIR="/Users/seb/leads/video_system"
INTROS_DIR="$VIDEO_SYSTEM_DIR/assets/intros"
BASE_VIDEO="$VIDEO_SYSTEM_DIR/assets/base_videos/demo_video_base_with_subtitles.mp4"
BACKGROUND_VIDEO="$VIDEO_SYSTEM_DIR/assets/base_videos/demo_video_base_with_subtitles.mp4"
OUTPUT_DIR="$VIDEO_SYSTEM_DIR/outputs/combined"

echo "🎬 Open Source Maintainers Video Overlay Combiner"
echo "==============================================="
echo "📁 Intros directory: $INTROS_DIR"
echo "🎥 Base video: $BASE_VIDEO"
echo "🎨 Background source: $BACKGROUND_VIDEO"
echo "📤 Output directory: $OUTPUT_DIR"
echo ""

# Check if directories exist
if [ ! -d "$INTROS_DIR" ]; then
    echo "❌ Intros directory not found: $INTROS_DIR"
    echo "Please create the directory and add your intro videos"
    exit 1
fi

if [ ! -f "$BASE_VIDEO" ]; then
    echo "❌ Base video not found: $BASE_VIDEO"
    exit 1
fi

if [ ! -f "$BACKGROUND_VIDEO" ]; then
    echo "❌ Background source video not found: $BACKGROUND_VIDEO"
    echo "Please ensure the demo base video is available"
    exit 1
fi

# Count intro videos
INTRO_COUNT=$(find "$INTROS_DIR" -type f \( -iname "*.mp4" -o -iname "*.mov" -o -iname "*.avi" -o -iname "*.mkv" -o -iname "*.webm" \) | wc -l)
echo "📊 Found $INTRO_COUNT intro videos"
echo ""

if [ "$INTRO_COUNT" -eq 0 ]; then
    echo "⚠️  No intro videos found in $INTROS_DIR"
    echo "Please add your 87 intro videos to this directory first"
    echo ""
    echo "Supported formats: .mp4, .mov, .avi, .mkv, .webm"
    exit 1
fi

# Ask for overlay duration
echo "🎨 Overlay Configuration:"
echo "This will overlay your intro video visuals with:"
echo "- Audio from base video"
echo "- Clean background from demo base video"
echo "- Preserved subtitles from base video"
echo "- Rest of base video after overlay"
echo ""

read -p "Use default 36-second overlay? (y/n): " use_default

if [ "$use_default" = "y" ] || [ "$use_default" = "Y" ]; then
    echo "✅ Using 36-second overlay with subtitle preservation"
    python3 "$VIDEO_SYSTEM_DIR/core/video_combiner_with_subtitles.py" \
        --intros-dir "$INTROS_DIR" \
        --base-video "$BASE_VIDEO" \
        --background-video "$BACKGROUND_VIDEO" \
        --output-dir "$OUTPUT_DIR" \
        --overlay-duration 36
else
    read -p "Enter custom overlay duration in seconds: " duration
    echo "✅ Using $duration-second overlay with subtitle preservation"
    python3 "$VIDEO_SYSTEM_DIR/core/video_combiner_with_subtitles.py" \
        --intros-dir "$INTROS_DIR" \
        --base-video "$BASE_VIDEO" \
        --background-video "$BACKGROUND_VIDEO" \
        --output-dir "$OUTPUT_DIR" \
        --overlay-duration $duration
fi

echo ""
echo "🎉 Video combination complete!"
echo "📂 Check your combined videos in: $OUTPUT_DIR"
