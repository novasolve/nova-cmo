#!/usr/bin/env python3
"""
Final Video Combiner with Subtitle Preservation
Combines intro videos with base video while preserving subtitles in the first 36 seconds.
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

def combine_with_subtitle_preservation(intro_path, base_video_path, background_video_path, output_path, overlay_duration=36):
    """
    Combine intro video with base video while preserving subtitles.
    
    Args:
        intro_path: Path to the intro video (provides main visuals for first 36s)
        base_video_path: Path to the base video (provides audio and subtitles)
        background_video_path: Path to the background video (clean background)
        output_path: Path to save the combined video
        overlay_duration: Duration in seconds for overlay (default 36)
    """
    try:
        # Load videos
        intro_clip = moviepy.VideoFileClip(intro_path)
        base_clip = moviepy.VideoFileClip(base_video_path)
        background_clip = moviepy.VideoFileClip(background_video_path)

        # Get video dimensions
        width, height = base_clip.size

        # Take first overlay_duration seconds from each video
        intro_visuals = intro_clip.subclipped(0, min(overlay_duration, intro_clip.duration))
        base_audio_part = base_clip.subclipped(0, min(overlay_duration, base_clip.duration))
        background_part = background_clip.subclipped(0, min(overlay_duration, background_clip.duration))

        # Resize all clips to match base video dimensions
        if intro_visuals.size != base_clip.size:
            intro_visuals = intro_visuals.resized(base_clip.size)
        if background_part.size != base_clip.size:
            background_part = background_part.resized(base_clip.size)

        # Crop subtitle area from base video (bottom 20% of screen)
        subtitle_height = int(height * 0.2)
        subtitle_y_start = height - subtitle_height
        
        subtitle_area = base_audio_part.cropped(
            x1=0, 
            y1=subtitle_y_start, 
            x2=width, 
            y2=height
        )

        # Position subtitle area at bottom
        subtitle_positioned = subtitle_area.with_position(('center', 'bottom'))

        # Create composite for first 36 seconds:
        # 1. Background video as base layer
        # 2. Intro video as main content (positioned in center/top area)
        # 3. Subtitle area from base video at bottom
        # 4. Audio from base video
        
        # Position intro video in the main content area (not covering subtitles)
        intro_positioned = intro_visuals.with_position('center')
        
        composite_clip = moviepy.CompositeVideoClip([
            background_part,      # Clean background
            intro_positioned,     # Intro video content
            subtitle_positioned   # Subtitles from base video
        ]).with_audio(base_audio_part.audio)

        # Get remaining part of base video (after overlay duration)
        if base_clip.duration > overlay_duration:
            remaining_part = base_clip.subclipped(overlay_duration, base_clip.duration)
            final_clip = moviepy.concatenate_videoclips([composite_clip, remaining_part])
        else:
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

        print(f"✅ Successfully created: {output_path}")
        return True

    except Exception as e:
        print(f"❌ Error combining videos: {e}")
        return False

def batch_combine_with_subtitles(intros_dir, base_video_path, background_video_path, output_dir, overlay_duration=36):
    """
    Batch process all intro videos with subtitle preservation.
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
    print(f"Overlay duration: {overlay_duration} seconds (with subtitle preservation)")
    print(f"Using base video: {base_video_path}")
    print(f"Using background video: {background_video_path}")

    # Process each intro video
    success_count = 0
    for i, intro_file in enumerate(intro_files, 1):
        intro_path = os.path.join(intros_dir, intro_file)
        output_filename = f"personalized_demo_{i:02d}.mp4"
        output_path = os.path.join(output_dir, output_filename)

        print(f"\nProcessing {i}/{len(intro_files)}: {intro_file}")

        if combine_with_subtitle_preservation(intro_path, base_video_path, background_video_path, output_path, overlay_duration):
            success_count += 1

    print(f"\n🎉 Completed! Successfully created {success_count}/{len(intro_files)} personalized demo videos")

def main():
    parser = argparse.ArgumentParser(description='Combine intro videos with base video preserving subtitles')
    parser.add_argument('--intros-dir', required=True, help='Directory containing intro videos')
    parser.add_argument('--base-video', required=True, help='Path to base video file (with subtitles)')
    parser.add_argument('--background-video', required=True, help='Path to background video file')
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

    # Start batch processing
    batch_combine_with_subtitles(
        args.intros_dir,
        args.base_video,
        args.background_video,
        args.output_dir,
        args.overlay_duration
    )

if __name__ == "__main__":
    main()
