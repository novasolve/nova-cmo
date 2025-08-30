#!/usr/bin/env python3
"""
Simple Subtitle Overlay Script
Takes the bottom 20% of the subtitle video and overlays it on top of the base video.
"""

import os
import moviepy
import sys

def overlay_subtitles_only(base_video_path, subtitle_video_path, output_path, overlay_duration=36):
    """
    Overlay just the bottom 20% (subtitle area) from subtitle video onto the base video.

    Args:
        base_video_path: Path to the base video
        subtitle_video_path: Path to the video containing subtitles in bottom 20%
        output_path: Path to save the result
        overlay_duration: Duration in seconds for overlay (default 36)
    """
    try:
        print("🎬 Creating subtitle overlay...")

        # Load videos
        base_clip = moviepy.VideoFileClip(base_video_path)
        subtitle_clip = moviepy.VideoFileClip(subtitle_video_path)

        print(f"📊 Base video duration: {base_clip.duration:.2f} seconds")
        print(f"📊 Subtitle video duration: {subtitle_clip.duration:.2f} seconds")
        print(f"🎨 Overlay duration: {overlay_duration} seconds")

        # Get video dimensions
        width, height = base_clip.size

        # Take first overlay_duration seconds from both videos
        base_overlay_part = base_clip.subclipped(0, min(overlay_duration, base_clip.duration))
        subtitle_overlay_part = subtitle_clip.subclipped(0, min(overlay_duration, subtitle_clip.duration))

        # Resize subtitle video to match base video if needed
        if subtitle_overlay_part.size != base_clip.size:
            subtitle_overlay_part = subtitle_overlay_part.resized(base_clip.size)

        # Extract bottom 20% of subtitle video (subtitle area)
        subtitle_height = int(height * 0.20)  # Bottom 20% for subtitles
        subtitle_y_start = height - subtitle_height

        print(f"📐 Extracting bottom {subtitle_height}px from subtitle video")

        subtitle_area = subtitle_overlay_part.cropped(
            x1=0,
            y1=subtitle_y_start,
            x2=width,
            y2=height
        )

        # Position the subtitle area at the bottom of the base video
        subtitle_positioned = subtitle_area.with_position(('center', 'bottom'))

        # Create composite: base video + subtitle overlay
        composite_clip = moviepy.CompositeVideoClip([
            base_overlay_part,      # Base video
            subtitle_positioned     # Subtitle area overlay
        ]).with_audio(base_overlay_part.audio)

        # Get the remaining part of base video (after overlay duration)
        if base_clip.duration > overlay_duration:
            remaining_part = base_clip.subclipped(overlay_duration, base_clip.duration)
            final_clip = moviepy.concatenate_videoclips([composite_clip, remaining_part])
        else:
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
        subtitle_clip.close()
        final_clip.close()

        print("✅ Subtitle overlay created successfully!")
        print(f"🎬 Output: {output_path}")

        return True

    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    # File paths
    base_video = "/Users/seb/leads/data/test_outputs/final_fixed_video.mp4"  # The video we want to add subtitles to
    subtitle_video = "/Users/seb/leads/data/test_outputs/demo_with_subtitles_overlay.mp4"  # Source of subtitles
    output_video = "/Users/seb/leads/data/test_outputs/video_with_subtitles.mp4"

    # Check if files exist
    if not os.path.exists(base_video):
        print(f"❌ Base video not found: {base_video}")
        sys.exit(1)

    if not os.path.exists(subtitle_video):
        print(f"❌ Subtitle video not found: {subtitle_video}")
        sys.exit(1)

    print("🎯 Subtitle Overlay Plan:")
    print(f"📹 Base video: {base_video}")
    print(f"📝 Subtitle source: {subtitle_video}")
    print("🔧 Extracting bottom 20% for subtitles")
    print("⏱️  Duration: First 36 seconds")

    # Create output directory if it doesn't exist
    output_dir = os.path.dirname(output_video)
    os.makedirs(output_dir, exist_ok=True)

    # Run the overlay
    success = overlay_subtitles_only(base_video, subtitle_video, output_video, overlay_duration=36)

    if success:
        print("\n🎉 Subtitle overlay completed successfully!")
        print("📂 The output video should now have:")
        print("   ✅ Subtitles from the bottom 20% of the subtitle video")
        print("   ✅ Overlayed on the base video for first 36 seconds")
        print(f"📁 Location: {output_video}")
    else:
        print("\n❌ Process failed. Check the error messages above.")

if __name__ == "__main__":
    main()
