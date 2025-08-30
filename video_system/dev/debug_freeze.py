#!/usr/bin/env python3
"""
Debug Freeze Top Half Script
Let's debug what's going wrong with the freeze effect.
"""

import os
import moviepy
import sys
import numpy as np

def debug_freeze(video_path):
    """Debug function to understand video properties and potential issues."""
    try:
        print("🔍 DEBUG: Loading video...")

        # Load video
        clip = moviepy.VideoFileClip(video_path)

        print(f"📊 Video duration: {clip.duration:.2f} seconds")
        print(f"📊 Video size: {clip.size}")
        print(f"📊 Video FPS: {clip.fps}")

        # Check if 43 seconds is within bounds
        if 43 >= clip.duration:
            print(f"❌ ERROR: Video is only {clip.duration:.2f}s long, can't get frame at 43s!")
            return False

        # Try to get frame at 43 seconds
        print("🎯 DEBUG: Getting frame at 43 seconds...")
        try:
            frame_at_time = clip.get_frame(43)
            print(f"✅ Frame shape: {frame_at_time.shape}")
            print(f"✅ Frame dtype: {frame_at_time.dtype}")
            print(f"✅ Frame min/max: {frame_at_time.min()}/{frame_at_time.max()}")
        except Exception as e:
            print(f"❌ ERROR getting frame: {e}")
            return False

        # Try to extract top half
        width, height = clip.size
        top_half_height = int(height * 0.5)
        print(f"🎯 DEBUG: Extracting top {top_half_height} pixels of {height} total height")

        try:
            top_half_frame = frame_at_time[0:top_half_height, :, :]
            print(f"✅ Top half shape: {top_half_frame.shape}")
        except Exception as e:
            print(f"❌ ERROR extracting top half: {e}")
            return False

        # Try to create image clip
        print("🎯 DEBUG: Creating image clip...")
        try:
            top_half_clip = moviepy.ImageClip(top_half_frame, duration=7)  # 43-36=7 seconds
            print(f"✅ Image clip created successfully")
            print(f"📊 Clip size: {top_half_clip.size}")
            print(f"📊 Clip duration: {top_half_clip.duration}")
        except Exception as e:
            print(f"❌ ERROR creating image clip: {e}")
            import traceback
            traceback.print_exc()
            return False

        print("✅ DEBUG: All operations successful!")
        return True

    except Exception as e:
        print(f"❌ DEBUG ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    input_video = "/Users/seb/leads/data/test_outputs/video_with_subtitles.mp4"

    if not os.path.exists(input_video):
        print(f"❌ Input video not found: {input_video}")
        return

    print("🔍 Starting debug process...")
    success = debug_freeze(input_video)

    if success:
        print("✅ Debug completed successfully!")
    else:
        print("❌ Debug revealed issues!")

if __name__ == "__main__":
    main()
