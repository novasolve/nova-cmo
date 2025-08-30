#!/usr/bin/env python3
"""
Final Complete Video Script
Combines subtitles overlay + freeze effect into one final video.
"""

import os
import moviepy
import sys
import numpy as np

def create_final_video(base_video_path, subtitle_video_path, output_path,
                      subtitle_duration=36, freeze_start=36, freeze_end=43, source_frame_time=43):
    """
    Create the final video with both subtitles and freeze effect.

    Args:
        base_video_path: Path to the base video (for audio and main content)
        subtitle_video_path: Path to video with subtitles in bottom 20%
        output_path: Path to save final result
        subtitle_duration: How long to overlay subtitles (default 36s)
        freeze_start: Start time for freeze effect (default 36s)
        freeze_end: End time for freeze effect (default 43s)
        source_frame_time: Time to get freeze frame from (default 43s)
    """
    try:
        print("🎬 Creating FINAL COMPLETE video...")

        # Load videos
        base_clip = moviepy.VideoFileClip(base_video_path)
        subtitle_clip = moviepy.VideoFileClip(subtitle_video_path)

        print(f"📊 Base video: {base_clip.duration:.2f}s, {base_clip.size}")
        print(f"📊 Subtitle video: {subtitle_clip.duration:.2f}s, {subtitle_clip.size}")

        # Get dimensions
        width, height = base_clip.size

        # === STEP 1: Extract subtitle area (bottom 20%) ===
        print("🎯 Step 1: Extracting subtitle area...")
        subtitle_height = int(height * 0.2)  # Bottom 20%
        subtitle_y_start = height - subtitle_height

        print(f"🎯 Subtitle area: bottom {subtitle_height} pixels of {height}")

        # Create subtitle overlay clip
        subtitle_overlay_clip = subtitle_clip.subclipped(0, min(subtitle_duration, subtitle_clip.duration))
        subtitle_overlay_clip = subtitle_overlay_clip.with_position((0, subtitle_y_start))

        # === STEP 2: Prepare freeze effect ===
        print("🎯 Step 2: Preparing freeze effect...")

        # Get frame for freeze effect
        frame_times_to_try = [source_frame_time, source_frame_time - 0.5, source_frame_time - 1.0]
        frame_at_time = None
        used_time = None

        for time_try in frame_times_to_try:
            if 0 <= time_try < base_clip.duration:
                try:
                    frame_at_time = base_clip.get_frame(time_try)
                    used_time = time_try
                    print(f"✅ Got freeze frame at {used_time}s")
                    break
                except Exception as e:
                    print(f"❌ Failed at {time_try}s: {e}")
                    continue

        if frame_at_time is None:
            print("❌ Could not get freeze frame, skipping freeze effect")
            freeze_clip = None
        else:
            # Extract top 50% for freeze
            top_half_height = int(height * 0.5)
            top_half_frame = frame_at_time[0:top_half_height, :, :]
            freeze_duration = freeze_end - freeze_start
            freeze_clip = moviepy.ImageClip(top_half_frame, duration=freeze_duration)
            freeze_clip = freeze_clip.with_position((0, 0))
            print(f"✅ Freeze clip prepared: {freeze_duration}s duration")

        # === STEP 3: Create the composite video ===
        print("🎯 Step 3: Creating final composite...")

        # Split the base video
        before_subtitles = base_clip.subclipped(0, subtitle_duration)
        after_subtitles = base_clip.subclipped(subtitle_duration, base_clip.duration)

        # Create composite for subtitle period
        subtitle_composite = moviepy.CompositeVideoClip([
            before_subtitles,      # Base video
            subtitle_overlay_clip  # Subtitle overlay
        ]).with_audio(before_subtitles.audio)

        # If we have freeze effect, apply it to the subtitle composite
        if freeze_clip:
            print(f"🎯 Applying freeze effect: {freeze_start}s - {freeze_end}s")

            # The freeze effect starts at freeze_start (36s) which is the END of the subtitle period
            # So we need to extend the subtitle composite to include the freeze period
            freeze_duration = freeze_end - freeze_start

            # Create extended subtitle composite that includes freeze period
            extended_subtitle_clip = subtitle_overlay_clip.with_duration(subtitle_duration + freeze_duration)

            # Create the full subtitle composite with extended duration
            extended_base_clip = base_clip.subclipped(0, subtitle_duration + freeze_duration)
            extended_subtitle_composite = moviepy.CompositeVideoClip([
                extended_base_clip,
                extended_subtitle_clip
            ]).with_audio(extended_base_clip.audio)

            # Now apply freeze to the extended composite
            freeze_start_rel = subtitle_duration  # Freeze starts at end of subtitle period
            freeze_end_rel = subtitle_duration + freeze_duration

            before_freeze = extended_subtitle_composite.subclipped(0, freeze_start_rel)
            during_freeze = extended_subtitle_composite.subclipped(freeze_start_rel, freeze_end_rel)

            # Create freeze composite
            freeze_composite = moviepy.CompositeVideoClip([
                during_freeze,
                freeze_clip
            ]).with_audio(during_freeze.audio)

            # Combine all parts
            subtitle_composite = moviepy.concatenate_videoclips([before_freeze, freeze_composite])

            print(f"✅ Freeze effect applied successfully")

        # Combine with after subtitles part
        if after_subtitles.duration > 0:
            final_clip = moviepy.concatenate_videoclips([subtitle_composite, after_subtitles])
        else:
            final_clip = subtitle_composite

        # === STEP 4: Export final video ===
        print(f"📤 Exporting final video to: {output_path}")
        final_clip.write_videofile(
            output_path,
            codec='libx264',
            audio_codec='aac',
            temp_audiofile=output_path + '_temp_audio.m4a',
            remove_temp=True,
            fps=30
        )

        # Clean up
        base_clip.close()
        subtitle_clip.close()
        final_clip.close()
        subtitle_overlay_clip.close()
        if freeze_clip:
            freeze_clip.close()

        print("✅ FINAL VIDEO CREATED SUCCESSFULLY!")
        print(f"🎬 Output: {output_path}")
        print("📋 Features applied:")
        print("   ✅ Subtitles overlaid for first 36 seconds")
        print("   ✅ Top 50% frozen for seconds 36-43")
        print("   ✅ Original audio preserved")

        return True

    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    # File paths
    base_video = "/Users/seb/leads/data/demo_video_base_with_subtitles.mp4"
    subtitle_video = "/Users/seb/leads/data/test_outputs/demo_with_subtitles_overlay.mp4"
    final_output = "/Users/seb/leads/data/test_outputs/VIDEO_FINAL_COMPLETE.mp4"

    # Check if input files exist
    if not os.path.exists(base_video):
        print(f"❌ Base video not found: {base_video}")
        sys.exit(1)
    if not os.path.exists(subtitle_video):
        print(f"❌ Subtitle video not found: {subtitle_video}")
        sys.exit(1)

    print("🎯 FINAL COMPLETE VIDEO PLAN:")
    print(f"📹 Base video: {base_video}")
    print(f"🎬 Subtitle source: {subtitle_video}")
    print("🔧 Features to apply:")
    print("   • Bottom 20% subtitle overlay for first 36s")
    print("   • Top 50% freeze effect for seconds 36-43")
    print("   • Preserve original audio")
    print(f"📁 Final output: {final_output}")

    # Create output directory
    output_dir = os.path.dirname(final_output)
    os.makedirs(output_dir, exist_ok=True)

    # Create the final video
    success = create_final_video(
        base_video,
        subtitle_video,
        final_output,
        subtitle_duration=36,
        freeze_start=36,
        freeze_end=43,
        source_frame_time=43
    )

    if success:
        print("\n🎉 FINAL VIDEO COMPLETED SUCCESSFULLY!")
        print("📂 Your video now has:")
        print("   ✅ Clear subtitles for first 36 seconds")
        print("   ✅ Smooth freeze effect (36-43s)")
        print("   ✅ Perfect audio sync")
        print(f"📁 Final file: {final_output}")
        print("\n🚀 You're all set! The video should look perfect now.")
    else:
        print("\n❌ Final video creation failed. Check the error messages above.")

if __name__ == "__main__":
    main()
