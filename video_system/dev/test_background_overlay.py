#!/usr/bin/env python3
"""
Test script to apply background overlay to the base video only.
Shows how the 36-second background overlay will look.
"""

import os
import moviepy
import sys

def test_background_overlay(base_video_path, background_video_path, output_path, overlay_duration=36):
    """
    Apply background overlay to base video for first N seconds.
    """
    try:
        print("🎬 Testing background overlay...")

        # Load videos
        base_clip = moviepy.VideoFileClip(base_video_path)
        background_clip = moviepy.VideoFileClip(background_video_path)

        print(f"📊 Base video duration: {base_clip.duration:.2f} seconds")
        print(f"📊 Background video duration: {background_clip.duration:.2f} seconds")
        print(f"🎨 Overlay duration: {overlay_duration} seconds")

        # Take first overlay_duration seconds from background video
        background_overlay = background_clip.subclipped(0, min(overlay_duration, background_clip.duration))

        # Take first overlay_duration seconds from base video (for audio/subtitles)
        base_overlay_part = base_clip.subclipped(0, min(overlay_duration, base_clip.duration))

        # Create composite: background + base video content
        composite_clip = moviepy.CompositeVideoClip([
            background_overlay.with_position('center'),  # Background layer
            base_overlay_part.with_position('center')    # Base content on top
        ]).with_audio(base_overlay_part.audio)  # Base video audio

        # Get the remaining part of base video (after overlay duration)
        if base_clip.duration > overlay_duration:
            remaining_part = base_clip.subclipped(overlay_duration, base_clip.duration)
            # Combine the overlay part with remaining video
            final_clip = moviepy.concatenate_videoclips([composite_clip, remaining_part])
        else:
            # If base video is shorter than overlay duration, just use the composite
            final_clip = composite_clip

        # Export the test video
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

        print("✅ Test video created successfully!")
        print(f"🎬 Output: {output_path}")

        return True

    except Exception as e:
        print(f"❌ Error: {e}")
        return False

def main():
    # File paths
    base_video = "/Users/seb/leads/data/Automatic Python Test Fixer.mp4"
    background_video = "/Users/seb/leads/data/background_36s.mp4"
    output_video = "/Users/seb/leads/data/test_background_overlay.mp4"

    # Check if files exist
    if not os.path.exists(base_video):
        print(f"❌ Base video not found: {base_video}")
        sys.exit(1)

    if not os.path.exists(background_video):
        print(f"❌ Background video not found: {background_video}")
        sys.exit(1)

    # Run the test
    success = test_background_overlay(base_video, background_video, output_video, overlay_duration=36)

    if success:
        print("\n🎉 Background overlay test completed!")
        print("📂 Check the output file to see how the background looks")
        print(f"📁 Location: {output_video}")
    else:
        print("\n❌ Test failed. Check the error messages above.")

if __name__ == "__main__":
    main()
