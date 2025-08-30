#!/usr/bin/env python3
"""
Freeze Top Half Script
Freezes the top 50% of frame 43 and overlays it for seconds 36-43.
"""

import os
import moviepy
import sys

def freeze_top_half(video_path, output_path, freeze_start=36, freeze_end=43, source_frame_time=43):
    """
    Freeze the top 50% of a specific frame and overlay it for a time range.

    Args:
        video_path: Path to the input video
        output_path: Path to save the result
        freeze_start: Start time for freeze overlay (default 36)
        freeze_end: End time for freeze overlay (default 43)
        source_frame_time: Time to get the source frame from (default 43)
    """
    try:
        print("🎬 Creating freeze overlay...")

        # Load video
        clip = moviepy.VideoFileClip(video_path)

        print(f"📊 Video duration: {clip.duration:.2f} seconds")
        print(f"📊 Video size: {clip.size}")
        print(f"🎯 Freeze overlay: {freeze_start}s - {freeze_end}s using frame from {source_frame_time}s")

        # Get video dimensions
        width, height = clip.size

        # Get the frame at source_frame_time (handle potential issues)
        try:
            frame_at_time = clip.get_frame(source_frame_time)
        except Exception as e:
            print(f"⚠️  Warning getting frame at {source_frame_time}s: {e}")
            # Try to get a frame slightly earlier if possible
            if source_frame_time > 1:
                source_frame_time -= 0.5
                frame_at_time = clip.get_frame(source_frame_time)
                print(f"✅ Using frame at {source_frame_time}s instead")
            else:
                raise

        # Extract top 50% of the frame
        top_half_height = int(height * 0.5)
        print(f"🎯 Extracting top {top_half_height} pixels (50%) of {height} total height")
        top_half_frame = frame_at_time[0:top_half_height, :, :]

        # Create an image clip from the top half
        top_half_clip = moviepy.ImageClip(top_half_frame, duration=freeze_end - freeze_start)

        # Position it at the top (0, 0 coordinates)
        top_half_positioned = top_half_clip.with_position((0, 0))

        # Split the original video
        before_freeze = clip.subclipped(0, freeze_start)
        during_freeze = clip.subclipped(freeze_start, freeze_end)
        after_freeze = clip.subclipped(freeze_end, clip.duration) if freeze_end < clip.duration else None

        # Create composite for the freeze period
        freeze_composite = moviepy.CompositeVideoClip([
            during_freeze,        # Original video during freeze period
            top_half_positioned    # Frozen top half overlay
        ]).with_audio(during_freeze.audio)

        # Combine all parts
        if after_freeze:
            final_clip = moviepy.concatenate_videoclips([before_freeze, freeze_composite, after_freeze])
        else:
            final_clip = moviepy.concatenate_videoclips([before_freeze, freeze_composite])

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
        clip.close()
        final_clip.close()
        top_half_clip.close()

        print("✅ Freeze overlay created successfully!")
        print(f"🎬 Output: {output_path}")

        return True

    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    # File paths
    input_video = "/Users/seb/leads/data/test_outputs/video_with_subtitles.mp4"
    output_video = "/Users/seb/leads/data/test_outputs/video_with_freeze.mp4"

    # Check if input file exists
    if not os.path.exists(input_video):
        print(f"❌ Input video not found: {input_video}")
        sys.exit(1)

    print("🎯 Freeze Top Half Plan:")
    print(f"📹 Input video: {input_video}")
    print("🔧 Freeze top 50% of frame at 43s")
    print("⏱️  Apply freeze for seconds 36-43")
    print("📁 Output: " + output_video)

    # Create output directory if it doesn't exist
    output_dir = os.path.dirname(output_video)
    os.makedirs(output_dir, exist_ok=True)

    # Run the freeze
    success = freeze_top_half(input_video, output_video,
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
