#!/usr/bin/env python3
"""
Video Combiner Script for Open Source Maintainers Outreach
Combines 87 custom intro videos with a base video to create personalized outreach content.
"""

import os
import sys
from pathlib import Path
from moviepy.editor import VideoFileClip, concatenate_videoclips, ColorClip
import argparse

def get_video_info(video_path):
    """Get basic information about a video file."""
    try:
        clip = VideoFileClip(video_path)
        info = {
            'duration': clip.duration,
            'size': clip.size,
            'fps': clip.fps
        }
        clip.close()
        return info
    except Exception as e:
        print(f"Error analyzing video {video_path}: {e}")
        return None

def create_background_overlay(base_video_path, duration_seconds=5, color=(0, 0, 0)):
    """
    Create a static background overlay for the first N seconds of the video.

    Args:
        base_video_path: Path to the base video
        duration_seconds: How many seconds to overlay (default 5)
        color: RGB tuple for background color (default black)
    """
    base_clip = VideoFileClip(base_video_path)

    # Create a colored background clip for the first duration_seconds
    background = ColorClip(
        size=base_clip.size,
        color=color,
        duration=min(duration_seconds, base_clip.duration)
    )

    # Composite the background with the original video
    final_clip = base_clip.set_start(0)
    background = background.set_start(0)

    # Overlay the background on the video
    composite = base_clip.set_position('center').set_start(0)
    background_composite = background.set_position('center').set_start(0)

    result = background_composite.set_duration(min(duration_seconds, base_clip.duration))
    result = result.set_audio(base_clip.audio.subclip(0, min(duration_seconds, base_clip.duration)))

    # Combine with the rest of the video
    if base_clip.duration > duration_seconds:
        remaining_video = base_clip.subclip(duration_seconds)
        final_clip = concatenate_videoclips([result, remaining_video])
    else:
        final_clip = result

    base_clip.close()
    return final_clip

def combine_videos_overlay(intro_path, base_video_path, output_path, overlay_duration=36):
    """
    Combine intro video with base video using overlay approach for first 36 seconds.

    Args:
        intro_path: Path to the intro video (provides visuals for first 36 seconds)
        base_video_path: Path to the base video (provides audio/subtitles and rest of video)
        output_path: Path to save the combined video
        overlay_duration: Duration in seconds to overlay intro visuals (default 36)
    """
    try:
        # Load videos
        intro_clip = VideoFileClip(intro_path)
        base_clip = VideoFileClip(base_video_path)

        # Take first 36 seconds from intro video (visuals only)
        intro_visuals = intro_clip.subclip(0, min(overlay_duration, intro_clip.duration))
        intro_visuals = intro_visuals.set_audio(None)  # Remove intro audio

        # Take first 36 seconds from base video (audio and any subtitles)
        base_audio_part = base_clip.subclip(0, min(overlay_duration, base_clip.duration))

        # Combine intro visuals with base audio for first 36 seconds
        overlay_part = intro_visuals.set_audio(base_audio_part.audio)

        # Get the remaining part of base video (after 36 seconds)
        if base_clip.duration > overlay_duration:
            remaining_part = base_clip.subclip(overlay_duration)
            # Combine the overlay part with remaining video
            combined_clip = concatenate_videoclips([overlay_part, remaining_part])
        else:
            # If base video is shorter than 36 seconds, just use the overlay
            combined_clip = overlay_part

        # Export the combined video
        combined_clip.write_videofile(
            output_path,
            codec='libx264',
            audio_codec='aac',
            temp_audiofile=output_path + '_temp_audio.m4a',
            remove_temp=True,
            verbose=False,
            logger=None
        )

        # Clean up
        intro_clip.close()
        base_clip.close()
        combined_clip.close()

        print(f"✅ Successfully created overlay video: {output_path}")
        return True

    except Exception as e:
        print(f"❌ Error combining videos with overlay: {e}")
        return False

def combine_videos(intro_path, base_video_path, output_path, background_duration=None, overlay_duration=36):
    """
    Combine an intro video with the base video.

    Args:
        intro_path: Path to the intro video
        base_video_path: Path to the base video
        output_path: Path to save the combined video
        background_duration: If specified, add background overlay for first N seconds
        overlay_duration: Duration for overlay approach (default 36 seconds)
    """
    # Use overlay approach by default for the first 36 seconds
    return combine_videos_overlay(intro_path, base_video_path, output_path, overlay_duration)

def batch_combine_videos(intros_dir, base_video_path, output_dir, overlay_duration=36):
    """
    Batch process all intro videos with the base video using overlay approach.

    Args:
        intros_dir: Directory containing intro videos
        base_video_path: Path to the base video
        output_dir: Directory to save combined videos
        overlay_duration: Duration in seconds to overlay intro visuals (default 36)
    """
    # Create output directory
    Path(output_dir).mkdir(parents=True, exist_ok=True)

    # Get all video files from intros directory
    video_extensions = ['.mp4', '.mov', '.avi', '.mkv', '.webm']
    intro_files = []

    for file in os.listdir(intros_dir):
        if any(file.lower().endswith(ext) for ext in video_extensions):
            intro_files.append(file)

    intro_files.sort()  # Sort for consistent ordering

    print(f"Found {len(intro_files)} intro videos")
    print(f"Overlay duration: {overlay_duration} seconds (intro visuals with base audio/subtitles)")

    # Process each intro video
    success_count = 0
    for i, intro_file in enumerate(intro_files, 1):
        intro_path = os.path.join(intros_dir, intro_file)
        output_filename = "02d"
        output_path = os.path.join(output_dir, output_filename)

        print(f"\nProcessing {i}/{len(intro_files)}: {intro_file}")

        if combine_videos(intro_path, base_video_path, output_path, overlay_duration=overlay_duration):
            success_count += 1

    print(f"\n🎉 Completed! Successfully created {success_count}/{len(intro_files)} overlay videos")

def main():
    parser = argparse.ArgumentParser(description='Combine intro videos with base video using overlay approach')
    parser.add_argument('--intros-dir', required=True, help='Directory containing intro videos')
    parser.add_argument('--base-video', required=True, help='Path to base video file')
    parser.add_argument('--output-dir', required=True, help='Directory to save combined videos')
    parser.add_argument('--overlay-duration', type=int, default=36, help='Duration in seconds to overlay intro visuals with base audio (default 36)')

    args = parser.parse_args()

    # Validate inputs
    if not os.path.exists(args.intros_dir):
        print(f"❌ Intros directory not found: {args.intros_dir}")
        sys.exit(1)

    if not os.path.exists(args.base_video):
        print(f"❌ Base video not found: {args.base_video}")
        sys.exit(1)

    # Analyze base video
    print("📊 Analyzing base video...")
    base_info = get_video_info(args.base_video)
    if base_info:
        print(f"Base video duration: {base_info['duration']:.2f} seconds")
        print(f"Base video size: {base_info['size']}")
        print(f"Base video fps: {base_info['fps']}")
    else:
        print("⚠️ Could not analyze base video, proceeding anyway...")

    # Start batch processing with overlay approach
    batch_combine_videos(
        args.intros_dir,
        args.base_video,
        args.output_dir,
        args.overlay_duration
    )

if __name__ == "__main__":
    main()
