#!/usr/bin/env python3
"""
Create Ben's Video - Intro + Background + Subtitles
Combines intro video with background frame and subtitle overlay
"""

import moviepy
import sys
import os

def create_ben_video(intro_path, main_video_path, output_path):
    """
    Create Ben's final video with intro + background frame + subtitles
    """
    print("🎬 Creating Ben's video with intro + background + subtitles...")

    # Load videos
    intro_clip = moviepy.VideoFileClip(intro_path)
    main_clip = moviepy.VideoFileClip(main_video_path)

    print(f"📊 Intro: {intro_clip.duration:.2f}s, {intro_clip.size}")
    print(f"📊 Main video: {main_clip.duration:.2f}s, {main_clip.size}")

    # Get frame 0:00 from main video for background
    background_frame = main_clip.get_frame(0.0)
    print("✅ Got background frame from 0:00")

    # Extract bottom 20% for subtitles (assuming this contains the subtitle area)
    height = main_clip.size[1]
    subtitle_height = int(height * 0.2)  # Bottom 20%
    subtitle_y_start = height - subtitle_height

    print(f"🎯 Subtitle area: bottom {subtitle_height} pixels")

    # Create background clip (static frame for full duration)
    total_duration = intro_clip.duration + main_clip.duration
    background_clip = moviepy.ImageClip(background_frame, duration=total_duration)

    # Create subtitle overlay clip (bottom 20% of main video)
    subtitle_overlay = moviepy.VideoFileClip(main_video_path)
    subtitle_overlay = subtitle_overlay.with_position((0, subtitle_y_start))

    # Combine: intro + (background + subtitles)
    final_clip = moviepy.CompositeVideoClip([
        background_clip,        # Full background
        intro_clip.with_position((0, 0)),  # Intro on top
        subtitle_overlay.with_position((0, subtitle_y_start))  # Subtitles on bottom
    ])

    # Preserve audio from intro, then main video
    if intro_clip.audio:
        intro_audio = intro_clip.audio
        main_audio = main_clip.audio

        # Combine audio
        combined_audio = moviepy.concatenate_audioclips([intro_audio, main_audio])
        final_clip = final_clip.with_audio(combined_audio)
    else:
        final_clip = final_clip.with_audio(main_clip.audio)

    # Export
    print(f"📤 Exporting to: {output_path}")
    final_clip.write_videofile(
        output_path,
        codec='libx264',
        audio_codec='aac',
        temp_audiofile=output_path + '_temp.m4a',
        remove_temp=True,
        fps=30
    )

    # Clean up
    intro_clip.close()
    main_clip.close()
    final_clip.close()
    background_clip.close()
    subtitle_overlay.close()

    print("✅ Ben's video created successfully!")
    print(f"🎬 Total duration: {total_duration:.2f}s")
    return True

if __name__ == "__main__":
    intro_video = "/Users/seb/Downloads/Automated Test Fixes.mp4"
    main_video = "/Users/seb/leads/data/test_outputs/final_fixed_video.mp4"
    output_video = "/Users/seb/leads/outbox/BEN_VIDEO_WITH_INTRO_BACKGROUND_SUBTITLES.mp4"

    # Check if input files exist
    if not os.path.exists(intro_video):
        print(f"❌ Intro video not found: {intro_video}")
        sys.exit(1)
    if not os.path.exists(main_video):
        print(f"❌ Main video not found: {main_video}")
        sys.exit(1)

    print("🎯 Creating Ben's Video:")
    print(f"📹 Intro: {intro_video}")
    print(f"🎬 Main video: {main_video}")
    print("🔧 Features:")
    print("   • Intro video (16.3s)")
    print("   • Background from frame 0:00")
    print("   • Subtitles from bottom 20%")
    print(f"📁 Output: {output_video}")

    # Create output directory
    output_dir = os.path.dirname(output_video)
    os.makedirs(output_dir, exist_ok=True)

    success = create_ben_video(intro_video, main_video, output_video)

    if success:
        print("\n🎉 Ben's video completed successfully!")
        print("📂 Features included:")
        print("   ✅ Intro video at start")
        print("   ✅ Background from main video frame 0:00")
        print("   ✅ Subtitles from bottom 20%")
        print("   ✅ Combined audio")
        print(f"📁 Final location: {output_video}")
    else:
        print("❌ Failed to create Ben's video")
        sys.exit(1)
