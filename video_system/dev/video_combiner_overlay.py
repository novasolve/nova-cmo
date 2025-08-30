#!/usr/bin/env python3
"""
Video Overlay Combiner Script for Open Source Maintainers Outreach
Combines 87 custom intro videos with a base video using overlay approach:
- First 36 seconds: Intro visuals + Base audio + Background video
- Rest: Original base video
"""

import os
import sys
from pathlib import Path
import moviepy
import argparse

def get_video_info(video_path):
    """Get basic information about a video file."""
    try:
        clip = moviepy.VideoFileClip(video_path)
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

def combine_videos_overlay(intro_path, base_video_path, background_video_path, output_path, overlay_duration=36):
    """
    Combine intro video with base video using overlay approach with background video.

    Args:
        intro_path: Path to the intro video (provides main visuals)
        base_video_path: Path to the base video (provides audio/subtitles)
        background_video_path: Path to the background video (36-second background)
        output_path: Path to save the combined video
        overlay_duration: Duration in seconds to overlay (default 36)
    """
    try:
        # Load videos
        intro_clip = moviepy.VideoFileClip(intro_path)
        base_clip = moviepy.VideoFileClip(base_video_path)
        background_clip = moviepy.VideoFileClip(background_video_path)

        # Take first overlay_duration seconds from intro video (main visuals)
        intro_visuals = intro_clip.subclipped(0, min(overlay_duration, intro_clip.duration))

        # Take first overlay_duration seconds from base video (audio and subtitles)
        base_audio_part = base_clip.subclipped(0, min(overlay_duration, base_clip.duration))

        # Take first overlay_duration seconds from background video
        background_part = background_clip.subclipped(0, min(overlay_duration, background_clip.duration))

        # Create composite: background + intro visuals + base audio
        composite_clip = moviepy.CompositeVideoClip([
            background_part.with_position('center'),  # Background layer
            intro_visuals.with_position('center')     # Intro visuals on top
        ]).with_audio(base_audio_part.audio)  # Base video audio

        # Resize composite to match base video dimensions if needed
        if composite_clip.size != base_clip.size:
            composite_clip = composite_clip.resize(base_clip.size)

        # Get the remaining part of base video (after overlay duration)
        if base_clip.duration > overlay_duration:
            remaining_part = base_clip.subclipped(overlay_duration, base_clip.duration)
            # Combine the overlay part with remaining video
            final_clip = moviepy.concatenate_videoclips([composite_clip, remaining_part])
        else:
            # If base video is shorter than overlay duration, just use the composite
            final_clip = composite_clip

        # Export the combined video
        final_clip.write_videofile(
            output_path,
            codec='libx264',
            audio_codec='aac',
            temp_audiofile=output_path + '_temp_audio.m4a',
            remove_temp=True
        )

        # Clean up
        intro_clip.close()
        base_clip.close()
        background_clip.close()
        final_clip.close()

        print(f"✅ Successfully created overlay video: {output_path}")
        return True

    except Exception as e:
        print(f"❌ Error combining videos with overlay: {e}")
        return False

def batch_combine_videos_overlay(intros_dir, base_video_path, background_video_path, output_dir, overlay_duration=36):
    """
    Batch process all intro videos with the base video using overlay approach.

    Args:
        intros_dir: Directory containing intro videos
        base_video_path: Path to the base video
        background_video_path: Path to the background video
        output_dir: Directory to save combined videos
        overlay_duration: Duration in seconds for overlay (default 36)
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
    print(f"Overlay duration: {overlay_duration} seconds")
    print(f"Using background video: {background_video_path}")

    # Process each intro video
    success_count = 0
    for i, intro_file in enumerate(intro_files, 1):
        intro_path = os.path.join(intros_dir, intro_file)
        output_filename = "02d"
        output_path = os.path.join(output_dir, output_filename)

        print(f"\nProcessing {i}/{len(intro_files)}: {intro_file}")

        if combine_videos_overlay(intro_path, base_video_path, background_video_path, output_path, overlay_duration):
            success_count += 1

    print(f"\n🎉 Completed! Successfully created {success_count}/{len(intro_files)} overlay videos")

def main():
    parser = argparse.ArgumentParser(description='Combine intro videos with base video using overlay approach')
    parser.add_argument('--intros-dir', required=True, help='Directory containing intro videos')
    parser.add_argument('--base-video', required=True, help='Path to base video file (provides audio)')
    parser.add_argument('--background-video', required=True, help='Path to background video file (36-second background)')
    parser.add_argument('--output-dir', required=True, help='Directory to save combined videos')
    parser.add_argument('--overlay-duration', type=int, default=36, help='Duration in seconds for overlay (default 36)')

    args = parser.parse_args()

    # Validate inputs
    if not os.path.exists(args.intros_dir):
        print(f"❌ Intros directory not found: {args.intros_dir}")
        sys.exit(1)

    if not os.path.exists(args.base_video):
        print(f"❌ Base video not found: {args.base_video}")
        sys.exit(1)

    if not os.path.exists(args.background_video):
        print(f"❌ Background video not found: {args.background_video}")
        sys.exit(1)

    # Analyze videos
    print("📊 Analyzing videos...")
    base_info = get_video_info(args.base_video)
    background_info = get_video_info(args.background_video)

    if base_info:
        print(f"Base video duration: {base_info['duration']:.2f} seconds")
        print(f"Base video size: {base_info['size']}")

    if background_info:
        print(f"Background video duration: {background_info['duration']:.2f} seconds")
        print(f"Background video size: {background_info['size']}")

    if not base_info or not background_info:
        print("⚠️ Could not analyze some videos, proceeding anyway...")

    # Start batch processing with overlay approach
    batch_combine_videos_overlay(
        args.intros_dir,
        args.base_video,
        args.background_video,
        args.output_dir,
        args.overlay_duration
    )

if __name__ == "__main__":
    main()
