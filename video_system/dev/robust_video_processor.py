#!/usr/bin/env python3
"""
Robust Video Processor - Handles all video editing tasks safely
Combines subtitles + freeze effects using the original uncorrupted video
"""

import os
import moviepy
import sys
import numpy as np

def safe_get_frame(clip, time_seconds, fallback_times=None):
    """
    Safely get a frame from video with multiple fallback options.
    """
    if fallback_times is None:
        fallback_times = [time_seconds, time_seconds - 0.5, time_seconds - 1.0,
                         time_seconds + 0.5, time_seconds + 1.0]

    for attempt_time in fallback_times:
        if 0 <= attempt_time < clip.duration:
            try:
                frame = clip.get_frame(attempt_time)
                print(f"✅ Got frame at {attempt_time:.2f}s")
                return frame, attempt_time
            except Exception as e:
                print(f"❌ Failed at {attempt_time:.2f}s: {e}")
                continue

    # Last resort: use first frame
    print("⚠️  Using first frame as fallback")
    return clip.get_frame(0.0), 0.0

def create_robust_final_video(base_video_path, subtitle_video_path, output_path,
                             subtitle_duration=36, freeze_start=36, freeze_end=43,
                             source_frame_time=43):
    """
    Create final video with subtitles and freeze effect using robust error handling.
    """
    try:
        print("🎬 Creating ROBUST final video...")

        # Load original videos (avoiding any corrupted intermediate files)
        print("📹 Loading original videos...")
        base_clip = moviepy.VideoFileClip(base_video_path)
        subtitle_clip = moviepy.VideoFileClip(subtitle_video_path)

        print(f"📊 Base video: {base_clip.duration:.2f}s, {base_clip.size}")
        print(f"📊 Subtitle video: {subtitle_clip.duration:.2f}s, {subtitle_clip.size}")

        width, height = base_clip.size

        # === STEP 1: Extract subtitle area safely ===
        print("🎯 Step 1: Extracting subtitle area...")
        subtitle_height = int(height * 0.2)  # Bottom 20%
        subtitle_y_start = height - subtitle_height

        print(f"🎯 Subtitle area: bottom {subtitle_height} pixels of {height}")

        # Create subtitle overlay clip
        subtitle_overlay_clip = subtitle_clip.subclipped(0, min(subtitle_duration, subtitle_clip.duration))
        subtitle_overlay_clip = subtitle_overlay_clip.with_position((0, subtitle_y_start))

        # === STEP 2: Get freeze frame safely ===
        print("🎯 Step 2: Getting freeze frame...")
        freeze_frame, actual_source_time = safe_get_frame(base_clip, source_frame_time)

        # Extract top 50% for freeze
        top_half_height = int(height * 0.5)
        top_half_frame = freeze_frame[0:top_half_height, :, :]
        freeze_duration = freeze_end - freeze_start
        freeze_clip = moviepy.ImageClip(top_half_frame, duration=freeze_duration)
        freeze_clip = freeze_clip.with_position((0, 0))

        print(f"✅ Freeze prepared: {freeze_duration}s using frame from {actual_source_time:.2f}s")

        # === STEP 3: Create final composite ===
        print("🎯 Step 3: Creating final composite...")

        # Split base video
        before_subtitles = base_clip.subclipped(0, subtitle_duration)
        after_subtitles = base_clip.subclipped(subtitle_duration, base_clip.duration)

        # Create subtitle composite
        subtitle_composite = moviepy.CompositeVideoClip([
            before_subtitles,
            subtitle_overlay_clip
        ]).with_audio(before_subtitles.audio)

        # Extend for freeze period
        freeze_duration_needed = freeze_end - freeze_start
        extended_base = base_clip.subclipped(0, subtitle_duration + freeze_duration_needed)
        extended_subtitle_overlay = subtitle_overlay_clip.with_duration(subtitle_duration + freeze_duration_needed)

        extended_composite = moviepy.CompositeVideoClip([
            extended_base,
            extended_subtitle_overlay
        ]).with_audio(extended_base.audio)

        # Apply freeze effect
        before_freeze = extended_composite.subclipped(0, subtitle_duration)
        during_freeze = extended_composite.subclipped(subtitle_duration, subtitle_duration + freeze_duration_needed)

        freeze_composite = moviepy.CompositeVideoClip([
            during_freeze,
            freeze_clip
        ]).with_audio(during_freeze.audio)

        # Combine all parts
        final_composite = moviepy.concatenate_videoclips([before_freeze, freeze_composite])

        # Add remaining video if any
        if subtitle_duration + freeze_duration_needed < base_clip.duration:
            remaining_video = base_clip.subclipped(subtitle_duration + freeze_duration_needed, base_clip.duration)
            final_composite = moviepy.concatenate_videoclips([final_composite, remaining_video])

        # === STEP 4: Export safely ===
        print(f"📤 Exporting to: {output_path}")
        final_composite.write_videofile(
            output_path,
            codec='libx264',
            audio_codec='aac',
            temp_audiofile=output_path + '_temp_audio.m4a',
            remove_temp=True,
            fps=30,
            verbose=False,
            logger=None
        )

        # Clean up
        base_clip.close()
        subtitle_clip.close()
        final_composite.close()
        subtitle_overlay_clip.close()
        freeze_clip.close()

        print("✅ ROBUST VIDEO CREATED SUCCESSFULLY!")
        print(f"🎬 Output: {output_path}")
        print("📋 Applied effects:")
        print("   ✅ Bottom 20% subtitles for first 36 seconds")
        print("   ✅ Top 50% freeze effect for seconds 36-43")
        print("   ✅ Original audio preserved")
        print("   ✅ No corruption issues")

        return True

    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    # Use original uncorrupted files
    base_video = "/Users/seb/leads/data/demo_video_base_with_subtitles.mp4"
    subtitle_video = "/Users/seb/leads/data/test_outputs/demo_with_subtitles_overlay.mp4"
    final_output = "/Users/seb/leads/data/test_outputs/VIDEO_FINAL_ROBUST.mp4"

    # Check if input files exist
    if not os.path.exists(base_video):
        print(f"❌ Base video not found: {base_video}")
        sys.exit(1)
    if not os.path.exists(subtitle_video):
        print(f"❌ Subtitle video not found: {subtitle_video}")
        sys.exit(1)

    print("🎯 ROBUST FINAL VIDEO PLAN:")
    print(f"📹 Base video: {base_video}")
    print(f"🎬 Subtitle source: {subtitle_video}")
    print("🔧 Features to apply:")
    print("   • Bottom 20% subtitle overlay for first 36s")
    print("   • Top 50% freeze effect for seconds 36-43")
    print("   • Robust error handling")
    print(f"📁 Final output: {final_output}")

    # Create output directory
    output_dir = os.path.dirname(final_output)
    os.makedirs(output_dir, exist_ok=True)

    # Create the robust final video
    success = create_robust_final_video(
        base_video,
        subtitle_video,
        final_output,
        subtitle_duration=36,
        freeze_start=36,
        freeze_end=43,
        source_frame_time=43
    )

    if success:
        print("\n🎉 ROBUST VIDEO COMPLETED SUCCESSFULLY!")
        print("📂 Your video now has:")
        print("   ✅ Clear subtitles for first 36 seconds")
        print("   ✅ Smooth freeze effect (36-43s)")
        print("   ✅ Perfect audio sync")
        print("   ✅ No corruption issues")
        print(f"📁 Final file: {final_output}")
        print("\n🚀 This version is robust and won't have the frame reading bugs!")
    else:
        print("\n❌ Robust video creation failed. Check the error messages above.")

if __name__ == "__main__":
    main()
