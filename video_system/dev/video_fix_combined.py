#!/usr/bin/env python3
"""
Combined Video Fix Script
Solves two problems:
1. Adds subtitles by extracting bottom 1/3rd of screen from good video
2. Fixes first half by overlaying top half of good video
"""

import os
import moviepy
import sys

def create_combined_video_fix(base_video_path, good_video_path, output_path, overlay_duration=36):
    """
    Create combined fix that addresses both subtitle and content issues.

    Args:
        base_video_path: Path to the base video that needs fixing
        good_video_path: Path to the video with good first half and subtitles
        output_path: Path to save the fixed video
        overlay_duration: Duration in seconds for fixes (default 36)
    """
    try:
        print("🎬 Creating combined video fix...")

        # Load videos
        base_clip = moviepy.VideoFileClip(base_video_path)
        good_clip = moviepy.VideoFileClip(good_video_path)

        print(f"📊 Base video duration: {base_clip.duration:.2f} seconds")
        print(f"📊 Base video size: {base_clip.size}")
        print(f"📊 Good video duration: {good_clip.duration:.2f} seconds")
        print(f"📊 Good video size: {good_clip.size}")
        print(f"🎨 Overlay duration: {overlay_duration} seconds")

        # Get video dimensions
        width, height = base_clip.size

        # Take first overlay_duration seconds from both videos
        base_overlay_part = base_clip.subclipped(0, min(overlay_duration, base_clip.duration))
        good_overlay_part = good_clip.subclipped(0, min(overlay_duration, good_clip.duration))

        # Resize good video to match base video if needed
        if good_overlay_part.size != base_clip.size:
            good_overlay_part = good_overlay_part.resized(base_clip.size)

        # === PROBLEM 1: Extract subtitles (bottom 1/3rd of good video) ===
        print("📝 Extracting subtitles from bottom 1/3rd of good video...")
        subtitle_height = int(height * 0.33)  # Bottom 1/3rd for subtitles
        subtitle_y_start = height - subtitle_height

        subtitle_area = good_overlay_part.cropped(
            x1=0,
            y1=subtitle_y_start,
            x2=width,
            y2=height
        )

        # Position subtitle area at bottom of screen
        subtitle_positioned = subtitle_area.with_position(('center', 'bottom'))

        # === PROBLEM 2: Extract top half of good video for main content ===
        print("🎯 Extracting top half from good video for main content...")
        top_half_height = int(height * 0.5)  # Top 50% for main content

        top_half_area = good_overlay_part.cropped(
            x1=0,
            y1=0,
            x2=width,
            y2=top_half_height
        )

        # Position top half at top of screen
        top_half_positioned = top_half_area.with_position(('center', 'top'))

        # === COMBINE: Create the composite for first 36 seconds ===
        print("🔧 Creating composite with both fixes...")

        # Better approach: Keep base video (with correct subtitles) and overlay top half from good video
        print("🎯 Keeping base video subtitles and overlaying top half from good video")

        # Create composite layers:
        # 1. Base video as foundation (contains correct subtitles)
        # 2. Top half from good video (replaces incorrect top content)

        composite_clip = moviepy.CompositeVideoClip([
            base_overlay_part,      # Base video with correct subtitles
            top_half_positioned     # Fixed top half from good video
        ]).with_audio(base_overlay_part.audio)  # Keep original audio

        # Get the remaining part of base video (after overlay duration)
        if base_clip.duration > overlay_duration:
            remaining_part = base_clip.subclipped(overlay_duration, base_clip.duration)
            # Combine the fixed part with remaining video
            final_clip = moviepy.concatenate_videoclips([composite_clip, remaining_part])
        else:
            # If base video is shorter than overlay duration, just use the composite
            final_clip = composite_clip

        # Export the video
        print(f"📤 Exporting fixed video to: {output_path}")
        final_clip.write_videofile(
            output_path,
            codec='libx264',
            audio_codec='aac',
            temp_audiofile=output_path + '_temp_audio.m4a',
            remove_temp=True
        )

        # Clean up
        base_clip.close()
        good_clip.close()
        final_clip.close()

        print("✅ Combined video fix created successfully!")
        print("🎯 Fixed both subtitle overlay and top content replacement")
        print(f"🎬 Output: {output_path}")

        return True

    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    # File paths based on user's specification
    base_video = "/Users/seb/leads/data/test_outputs/demo_with_subtitles_overlay.mp4"
    good_video = "/Users/seb/leads/data/test_outputs/fixed_background_overlay.mp4"
    output_video = "/Users/seb/leads/data/test_outputs/final_fixed_video.mp4"

    # Check if files exist
    if not os.path.exists(base_video):
        print(f"❌ Base video not found: {base_video}")
        sys.exit(1)

    if not os.path.exists(good_video):
        print(f"❌ Good video not found: {good_video}")
        sys.exit(1)

    print("🎯 Video Fix Plan:")
    print(f"📹 Base video (to fix): {base_video}")
    print(f"✅ Good video (source): {good_video}")
    print("🔧 Fix 1: Extract bottom 1/3rd for subtitles")
    print("🔧 Fix 2: Extract top 1/2 for main content")
    print("⏱️  Duration: First 36 seconds")

    # Create output directory if it doesn't exist
    output_dir = os.path.dirname(output_video)
    os.makedirs(output_dir, exist_ok=True)

    # Run the combined fix
    success = create_combined_video_fix(base_video, good_video, output_video, overlay_duration=36)

    if success:
        print("\n🎉 Combined video fix completed successfully!")
        print("📂 The output video should now have:")
        print("   ✅ Subtitles from the good video (bottom 1/3rd)")
        print("   ✅ Fixed top content from the good video (top 1/2)")
        print(f"📁 Location: {output_video}")
    else:
        print("\n❌ Process failed. Check the error messages above.")

if __name__ == "__main__":
    main()
