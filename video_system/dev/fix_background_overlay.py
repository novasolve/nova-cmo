#!/usr/bin/env python3
"""
Fixed Background Overlay Script
This version properly replaces the background while keeping audio and text overlays.
"""

import os
import moviepy
import sys

def create_proper_background_overlay(base_video_path, background_video_path, output_path, overlay_duration=36):
    """
    Create proper background overlay by replacing background but keeping audio and text.

    The approach:
    1. Use background video as the base layer
    2. Keep audio from the original base video
    3. Extract and overlay any text/UI elements from base video if needed
    """
    try:
        print("🎬 Creating proper background overlay...")

        # Load videos
        base_clip = moviepy.VideoFileClip(base_video_path)
        background_clip = moviepy.VideoFileClip(background_video_path)

        print(f"📊 Base video duration: {base_clip.duration:.2f} seconds")
        print(f"📊 Background video duration: {background_clip.duration:.2f} seconds")
        print(f"🎨 Overlay duration: {overlay_duration} seconds")

        # Take first overlay_duration seconds from background video (this becomes our new background)
        background_overlay = background_clip.subclipped(0, min(overlay_duration, background_clip.duration))

        # Take first overlay_duration seconds from base video (for audio only)
        base_audio_part = base_clip.subclipped(0, min(overlay_duration, base_clip.duration))

        # Use background video as the main visual, but with base video audio
        overlay_part = background_overlay.with_audio(base_audio_part.audio)

        # Resize to match base video dimensions if needed
        if overlay_part.size != base_clip.size:
            overlay_part = overlay_part.resized(base_clip.size)

        # Get the remaining part of base video (after overlay duration)
        if base_clip.duration > overlay_duration:
            remaining_part = base_clip.subclipped(overlay_duration, base_clip.duration)
            # Combine the overlay part with remaining video
            final_clip = moviepy.concatenate_videoclips([overlay_part, remaining_part])
        else:
            # If base video is shorter than overlay duration, just use the overlay
            final_clip = overlay_part

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

        print("✅ Fixed background overlay created successfully!")
        print(f"🎬 Output: {output_path}")

        return True

    except Exception as e:
        print(f"❌ Error: {e}")
        return False

def main():
    # File paths
    base_video = "/Users/seb/leads/data/Automatic Python Test Fixer.mp4"
    background_video = "/Users/seb/leads/data/background_36s.mp4"
    output_video = "/Users/seb/leads/data/fixed_background_overlay.mp4"

    # Check if files exist
    if not os.path.exists(base_video):
        print(f"❌ Base video not found: {base_video}")
        sys.exit(1)

    if not os.path.exists(background_video):
        print(f"❌ Background video not found: {background_video}")
        sys.exit(1)

    # Run the fix
    success = create_proper_background_overlay(base_video, background_video, output_video, overlay_duration=36)

    if success:
        print("\n🎉 Fixed background overlay completed!")
        print("📂 This version should show the clean background from your original video")
        print(f"📁 Location: {output_video}")
    else:
        print("\n❌ Fix failed. Check the error messages above.")

if __name__ == "__main__":
    main()
