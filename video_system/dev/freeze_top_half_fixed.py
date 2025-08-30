#!/usr/bin/env python3
"""
Fixed Freeze Top Half Script
Works directly with the original video to avoid corruption issues.
"""

import os
import moviepy
import sys
import numpy as np

def freeze_top_half_fixed(video_path, output_path, freeze_start=36, freeze_end=43, source_frame_time=43):
    """
    Freeze the top 50% of a specific frame and overlay it for a time range.
    Fixed version that handles frame reading issues.
    """
    try:
        print("🎬 Creating freeze overlay (FIXED VERSION)...")

        # Load video
        clip = moviepy.VideoFileClip(video_path)

        print(f"📊 Video duration: {clip.duration:.2f} seconds")
        print(f"📊 Video size: {clip.size}")

        # Get video dimensions
        width, height = clip.size

        # Try multiple frame times to get a good frame
        frame_times_to_try = [source_frame_time, source_frame_time - 0.5, source_frame_time - 1.0,
                             source_frame_time + 0.5, source_frame_time + 1.0]

        frame_at_time = None
        used_time = None

        for time_try in frame_times_to_try:
            if 0 <= time_try < clip.duration:
                try:
                    print(f"🎯 Trying to get frame at {time_try}s...")
                    frame_at_time = clip.get_frame(time_try)
                    used_time = time_try
                    print(f"✅ Got good frame at {used_time}s")
                    break
                except Exception as e:
                    print(f"❌ Failed at {time_try}s: {e}")
                    continue

        if frame_at_time is None:
            print("❌ Could not get any valid frame!")
            return False

        # Extract top 50% of the frame
        top_half_height = int(height * 0.5)
        print(f"🎯 Extracting top {top_half_height} pixels (50%) of {height} total height")
        top_half_frame = frame_at_time[0:top_half_height, :, :]

        # Create an image clip from the top half
        freeze_duration = freeze_end - freeze_start
        top_half_clip = moviepy.ImageClip(top_half_frame, duration=freeze_duration)

        # Position it at the top (0, 0 coordinates)
        top_half_positioned = top_half_clip.with_position((0, 0))

        # Split the original video with better error handling
        print("✂️  Splitting video...")

        # Ensure we don't go beyond video duration
        actual_freeze_end = min(freeze_end, clip.duration)
        actual_freeze_start = min(freeze_start, actual_freeze_end - 0.1)  # Ensure positive duration

        before_freeze = clip.subclipped(0, actual_freeze_start)
        during_freeze = clip.subclipped(actual_freeze_start, actual_freeze_end)
        after_freeze = clip.subclipped(actual_freeze_end, clip.duration) if actual_freeze_end < clip.duration else None

        print(f"📊 Before freeze: {before_freeze.duration:.2f}s")
        print(f"📊 During freeze: {during_freeze.duration:.2f}s")
        if after_freeze:
            print(f"📊 After freeze: {after_freeze.duration:.2f}s")

        # Create composite for the freeze period
        print("🎬 Creating composite...")
        freeze_composite = moviepy.CompositeVideoClip([
            during_freeze,        # Original video during freeze period
            top_half_positioned    # Frozen top half overlay
        ]).with_audio(during_freeze.audio)

        # Combine all parts
        if after_freeze and after_freeze.duration > 0:
            final_clip = moviepy.concatenate_videoclips([before_freeze, freeze_composite, after_freeze])
        else:
            final_clip = moviepy.concatenate_videoclips([before_freeze, freeze_composite])

        # Export the video with safer settings
        print(f"📤 Exporting to: {output_path}")
        final_clip.write_videofile(
            output_path,
            codec='libx264',
            audio_codec='aac',
            temp_audiofile=output_path + '_temp_audio.m4a',
            remove_temp=True,
            fps=30
        )

        # Clean up
        clip.close()
        final_clip.close()
        top_half_clip.close()

        print("✅ Freeze overlay created successfully!")
        print(f"🎬 Output: {output_path}")
        print(f"🎯 Used frame from: {used_time}s")

        return True

    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    # Use the original video to avoid corruption issues
    input_video = "/Users/seb/leads/data/demo_video_base_with_subtitles.mp4"
    output_video = "/Users/seb/leads/data/test_outputs/video_with_freeze_fixed.mp4"

    # Check if input file exists
    if not os.path.exists(input_video):
        print(f"❌ Input video not found: {input_video}")
        sys.exit(1)

    print("🎯 FIXED Freeze Top Half Plan:")
    print(f"📹 Input video: {input_video}")
    print("🔧 Freeze top 50% of frame at 43s (with fallback times)")
    print("⏱️  Apply freeze for seconds 36-43")
    print("📁 Output: " + output_video)

    # Create output directory if it doesn't exist
    output_dir = os.path.dirname(output_video)
    os.makedirs(output_dir, exist_ok=True)

    # Run the freeze
    success = freeze_top_half_fixed(input_video, output_video,
                                   freeze_start=36, freeze_end=43, source_frame_time=43)

    if success:
        print("\n🎉 Freeze overlay completed successfully!")
        print("📂 The output video should now have:")
        print("   ✅ Top 50% frozen from frame at 43s")
        print("   ✅ Applied for seconds 36-43")
        print(f"📁 Location: {output_video}")
    else:
        print("\n❌ Process failed. Check the error messages above.")

if __name__ == "__main__":
    main()
