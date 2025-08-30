#!/usr/bin/env python3
"""Detailed Debug Freeze Script"""

import os
import moviepy
import sys
import numpy as np

def debug_freeze_detailed(video_path):
    try:
        print("🔍 DETAILED DEBUG: Loading video...")
        clip = moviepy.VideoFileClip(video_path)

        print(f"📊 Video duration: {clip.duration:.2f} seconds")
        print(f"📊 Video size: {clip.size}")
        print(f"📊 Video FPS: {clip.fps}")

        # Check timing
        freeze_start = 36
        freeze_end = 43
        source_frame_time = 43

        print(f"⏱️  Freeze period: {freeze_start}s - {freeze_end}s")
        print(f"🎯 Source frame time: {source_frame_time}s")

        # Validate timing
        if source_frame_time >= clip.duration:
            print(f"❌ ERROR: Can't get frame at {source_frame_time}s, video is only {clip.duration:.2f}s long!")
            return False

        # Try to get frame
        print("🎯 Getting frame at 43s...")
        frame_at_time = clip.get_frame(source_frame_time)
        print(f"✅ Got frame with shape: {frame_at_time.shape}")

        # Extract top 50%
        height = clip.size[1]
        top_half_height = int(height * 0.5)
        top_half_frame = frame_at_time[0:top_half_height, :, :]
        print(f"🎯 Extracted top half: {top_half_frame.shape}")

        # Create image clip
        duration_needed = freeze_end - freeze_start
        top_half_clip = moviepy.ImageClip(top_half_frame, duration=duration_needed)
        print(f"✅ Created image clip, duration: {top_half_clip.duration}s")

        # Position it
        top_half_positioned = top_half_clip.with_position((0, 0))
        print("✅ Positioned at top-left corner")

        # Split video
        print("✂️  Splitting video...")
        before_freeze = clip.subclipped(0, freeze_start)
        during_freeze = clip.subclipped(freeze_start, freeze_end)
        after_freeze = clip.subclipped(freeze_end, clip.duration)

        print(f"📊 Before freeze: {before_freeze.duration:.2f}s")
        print(f"📊 During freeze: {during_freeze.duration:.2f}s")
        print(f"📊 After freeze: {after_freeze.duration:.2f}s")

        # Create composite
        print("🎬 Creating composite...")
        freeze_composite = moviepy.CompositeVideoClip([
            during_freeze,
            top_half_positioned
        ]).with_audio(during_freeze.audio)

        print(f"✅ Composite created, duration: {freeze_composite.duration:.2f}s")

        # Test the composite by saving just the freeze part
        print("🧪 Testing freeze composite...")
        test_output = "/Users/seb/leads/data/test_outputs/test_freeze_only.mp4"
        freeze_composite.write_videofile(
            test_output,
            codec='libx264',
            audio_codec='aac',
            fps=30,
            verbose=False,
            logger=None
        )
        print(f"✅ Test freeze saved to: {test_output}")

        clip.close()
        return True

    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    debug_freeze_detailed("/Users/seb/leads/data/test_outputs/video_with_subtitles.mp4")
