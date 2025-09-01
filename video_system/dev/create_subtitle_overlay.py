#!/usr/bin/env python3
"""
Subtitle-Aware Background Overlay Script
This version crops and preserves the subtitle area from the base video
while replacing the background with the clean demo background.
"""

import os
import moviepy
import sys

def create_subtitle_aware_overlay(base_video_path, background_video_path, output_path, overlay_duration=36):
    """
    Create background overlay while preserving subtitles by cropping subtitle area.

    Approach:
    1. Use background video as main layer for first 36 seconds
    2. Crop subtitle area from base video and overlay it
    3. Keep original audio from base video
    4. Continue with original base video after 36 seconds
    """
    try:
        print("🎬 Creating subtitle-aware background overlay...")

        # Load videos
        base_clip = moviepy.VideoFileClip(base_video_path)
        background_clip = moviepy.VideoFileClip(background_video_path)

        print(f"📊 Base video duration: {base_clip.duration:.2f} seconds")
        print(f"📊 Base video size: {base_clip.size}")
        print(f"📊 Background video duration: {background_clip.duration:.2f} seconds")
        print(f"🎨 Overlay duration: {overlay_duration} seconds")

        # Get video dimensions
        width, height = base_clip.size

        # Take first overlay_duration seconds from background video
        background_overlay = background_clip.subclipped(0, min(overlay_duration, background_clip.duration))

        # Take first overlay_duration seconds from base video
        base_overlay_part = base_clip.subclipped(0, min(overlay_duration, base_clip.duration))

        # Resize background to match base video if needed
        if background_overlay.size != base_clip.size:
            background_overlay = background_overlay.resized(base_clip.size)

        # Crop subtitle area from base video (bottom portion of screen)
        # Assuming subtitles are in bottom 20% of screen
        subtitle_height = int(height * 0.2)  # Bottom 20% for subtitles
        subtitle_y_start = height - subtitle_height

        print(f"📐 Cropping subtitle area: bottom {subtitle_height}px (from y={subtitle_y_start})")

        # Crop just the subtitle area from the base video
        subtitle_area = base_overlay_part.cropped(
            x1=0,
            y1=subtitle_y_start,
            x2=width,
            y2=height
        )

        # Position the subtitle area at the bottom of the background
        subtitle_positioned = subtitle_area.with_position(('center', 'bottom'))

        # Create composite: background + subtitle area
        composite_clip = moviepy.CompositeVideoClip([
            background_overlay,  # Clean background
            subtitle_positioned  # Subtitles on top
        ]).with_audio(base_overlay_part.audio)

        # Get the remaining part of base video (after overlay duration)
        if base_clip.duration > overlay_duration:
            remaining_part = base_clip.subclipped(overlay_duration, base_clip.duration)
            # Combine the overlay part with remaining video
            final_clip = moviepy.concatenate_videoclips([composite_clip, remaining_part])
        else:
            # If base video is shorter than overlay duration, just use the composite
            final_clip = composite_clip

        # Export the video
        print(f"📤 Exporting to: {output_path}")
        final_clip.write_videofile(
            output_path,
            codec='libx264',
            audio_codec='aac',
            temp_audiofile=output_path + '_temp_audio.m4a',
            remove_temp=True
        )

        # Clean up
        base_clip.close()
        background_clip.close()
        final_clip.close()

        print("✅ Subtitle-aware overlay created successfully!")
        print(f"🎬 Output: {output_path}")

        return True

    except Exception as e:
        print(f"❌ Error: {e}")
        return False

def main():
    # File paths - using new base video with subtitles
    base_video = "/Users/seb/leads/data/demo_video_base_with_subtitles.mp4"
    background_video = "/Users/seb/leads/data/demo_video_base_with_subtitles.mp4"  # Use same video as background source
    output_video = "/Users/seb/leads/data/demo_with_subtitles_overlay.mp4"

    # Check if files exist
    if not os.path.exists(base_video):
        print(f"❌ Base video not found: {base_video}")
        sys.exit(1)

    if not os.path.exists(background_video):
        print(f"❌ Background video not found: {background_video}")
        sys.exit(1)

    print(f"🎯 Using new base video: {base_video}")
    print("🎯 This will preserve subtitles by cropping the subtitle area")

    # Run the subtitle-aware overlay
    success = create_subtitle_aware_overlay(base_video, background_video, output_video, overlay_duration=36)

    if success:
        print("\n🎉 Subtitle-aware overlay completed!")
        print("📂 This version should show clean background + preserved subtitles")
        print(f"📁 Location: {output_video}")
    else:
        print("\n❌ Process failed. Check the error messages above.")

if __name__ == "__main__":
    main()
