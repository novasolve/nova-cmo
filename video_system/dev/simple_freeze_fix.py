#!/usr/bin/env python3
"""
Simple Freeze Fix - Seconds 36-43 using Frame 44
"""

import moviepy
import sys

def apply_freeze_effect(video_path, output_path, freeze_start=36, freeze_end=44, source_frame_time=44):
    """
    Apply freeze effect: use frame 44 to freeze top 80% of screen for seconds 36-44
    (bottom 20% continues playing with subtitles)
    """
    print(f"🎬 Applying freeze: seconds {freeze_start}-{freeze_end} using frame {source_frame_time}")

    # Load video
    clip = moviepy.VideoFileClip(video_path)
    print(f"📊 Video: {clip.duration:.2f}s, {clip.size}")

    # Get frame 44
    try:
        freeze_frame = clip.get_frame(source_frame_time)
        print(f"✅ Got frame at {source_frame_time}s")
    except:
        # Fallback to nearest valid frame
        for offset in [-0.5, 0.5, -1.0, 1.0]:
            try:
                alt_time = source_frame_time + offset
                freeze_frame = clip.get_frame(alt_time)
                print(f"✅ Got frame at {alt_time}s (fallback)")
                break
            except:
                continue
        else:
            print("❌ Could not get any frame")
            return False

    # Create freeze overlay (top 80% only)
    height = clip.size[1]
    top_80_percent = int(height * 0.8)
    top_80_frame = freeze_frame[0:top_80_percent, :, :]  # Extract top 80%

    freeze_duration = freeze_end - freeze_start
    freeze_clip = moviepy.ImageClip(top_80_frame, duration=freeze_duration)
    freeze_clip = freeze_clip.with_position((0, 0))  # Position at top

    # Split video
    before = clip.subclipped(0, freeze_start)
    after = clip.subclipped(freeze_end, clip.duration) if freeze_end < clip.duration else None

    # Create composite
    freeze_composite = moviepy.CompositeVideoClip([
        clip.subclipped(freeze_start, freeze_end),
        freeze_clip
    ]).with_audio(clip.subclipped(freeze_start, freeze_end).audio)

    # Combine
    if after:
        final = moviepy.concatenate_videoclips([before, freeze_composite, after])
    else:
        final = moviepy.concatenate_videoclips([before, freeze_composite])

    # Export
    print(f"📤 Saving to: {output_path}")
    final.write_videofile(
        output_path,
        codec='libx264',
        audio_codec='aac',
        temp_audiofile=output_path + '_temp.m4a',
        remove_temp=True,
        fps=30
    )

    clip.close()
    final.close()
    print("✅ Freeze effect applied successfully!")
    return True

if __name__ == "__main__":
    input_video = "/Users/seb/leads/data/test_outputs/final_fixed_video.mp4"
    output_video = "/Users/seb/leads/data/test_outputs/final_with_freeze.mp4"

    success = apply_freeze_effect(
        input_video,
        output_video,
        freeze_start=36,
        freeze_end=44,
        source_frame_time=44
    )

    if success:
        print("\n🎉 DONE! Video with freeze effect saved.")
        print(f"📁 Location: {output_video}")
    else:
        print("❌ Failed")
        sys.exit(1)
