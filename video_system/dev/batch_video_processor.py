#!/usr/bin/env python3
"""
Batch Video Processor - Combines intro videos with main video
Creates videos with intro + frozen first frame background + subtitles from main video
"""

import moviepy
import os
import sys
from pathlib import Path
import numpy as np

def create_video_with_intro(intro_path, main_video_path, output_path):
    """
    Create a video with:
    - Intro video at the beginning
    - Frozen first frame from intro as background
    - Subtitles (bottom 20%) from main video
    """
    print(f"\n🎬 Processing: {os.path.basename(intro_path)}")
    
    try:
        # Load videos
        intro_clip = moviepy.VideoFileClip(intro_path)
        main_clip = moviepy.VideoFileClip(main_video_path)
        
        print(f"📊 Intro: {intro_clip.duration:.2f}s, {intro_clip.size}")
        print(f"📊 Main: {main_clip.duration:.2f}s, {main_clip.size}")
        
        # Get first frame from intro video for background
        first_frame = intro_clip.get_frame(0.0)
        print("✅ Got first frame from intro for background")
        
        # Extract bottom 20% for subtitles from main video
        height = main_clip.size[1]
        subtitle_height = int(height * 0.2)
        subtitle_y_start = height - subtitle_height
        
        print(f"🎯 Subtitle area: bottom {subtitle_height} pixels")
        
        # Create background clip (frozen first frame for entire duration)
        total_duration = intro_clip.duration + main_clip.duration
        background_clip = moviepy.ImageClip(first_frame, duration=total_duration)
        
        # Create subtitle overlay from main video (positioned at bottom)
        # Extract bottom 20% of each frame
        def make_frame(t):
            if t < intro_clip.duration:
                # During intro, return transparent/black frame
                return np.zeros((height, main_clip.size[0], 3), dtype=np.uint8)
            else:
                # After intro, get frame from main video and extract bottom 20%
                main_t = t - intro_clip.duration
                if main_t < main_clip.duration:
                    frame = main_clip.get_frame(main_t)
                    # Create blank frame
                    result = np.zeros_like(frame)
                    # Copy only bottom 20%
                    result[subtitle_y_start:, :] = frame[subtitle_y_start:, :]
                    return result
                else:
                    return np.zeros((height, main_clip.size[0], 3), dtype=np.uint8)
        
        # Create subtitle clip with custom make_frame function
        subtitle_clip = moviepy.VideoClip(make_frame, duration=total_duration)
        
        # Create final composite
        final_clip = moviepy.CompositeVideoClip([
            background_clip,                    # Frozen first frame background
            intro_clip.with_position((0, 0)),   # Intro video on top (plays then disappears)
            subtitle_clip                       # Subtitles from main video (bottom 20% only)
        ])
        
        # Handle audio: intro audio first, then main video audio
        if intro_clip.audio and main_clip.audio:
            combined_audio = moviepy.concatenate_audioclips([intro_clip.audio, main_clip.audio])
            final_clip = final_clip.with_audio(combined_audio)
        elif main_clip.audio:
            # If intro has no audio, pad with silence
            silence = moviepy.AudioClip(lambda t: 0, duration=intro_clip.duration)
            combined_audio = moviepy.concatenate_audioclips([silence, main_clip.audio])
            final_clip = final_clip.with_audio(combined_audio)
        
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
        subtitle_clip.close()
        
        print(f"✅ Successfully created: {os.path.basename(output_path)}")
        return True
        
    except Exception as e:
        print(f"❌ Error processing {intro_path}: {e}")
        import traceback
        traceback.print_exc()
        return False

def process_batch_videos(intro_folder, main_video_path, output_folder):
    """
    Process all intro videos in a folder
    """
    # Create output folder
    os.makedirs(output_folder, exist_ok=True)
    
    # Get all video files from intro folder
    video_extensions = ['.mp4', '.mov', '.avi', '.mkv']
    intro_files = []
    
    for ext in video_extensions:
        intro_files.extend(Path(intro_folder).glob(f'*{ext}'))
    
    if not intro_files:
        print(f"❌ No video files found in {intro_folder}")
        return
    
    print(f"📂 Found {len(intro_files)} intro videos to process")
    
    # Process each intro video
    successful = 0
    for intro_path in intro_files:
        # Create output filename
        intro_name = intro_path.stem  # filename without extension
        output_name = f"{intro_name}_FINAL_WITH_SUBTITLES.mp4"
        output_path = os.path.join(output_folder, output_name)
        
        # Process the video
        if create_video_with_intro(str(intro_path), main_video_path, output_path):
            successful += 1
    
    print(f"\n🎉 Batch processing complete!")
    print(f"✅ Successfully processed: {successful}/{len(intro_files)} videos")
    print(f"📁 Output folder: {output_folder}")

def main():
    # Configuration
    main_video = "/Users/seb/leads/data/test_outputs/final_fixed_video.mp4"
    
    # Create organized folder structure
    videos_base = "/Users/seb/leads/videos"
    intro_folder = os.path.join(videos_base, "intros")
    output_folder = os.path.join(videos_base, "final_outputs")
    
    # Create folders
    os.makedirs(intro_folder, exist_ok=True)
    os.makedirs(output_folder, exist_ok=True)
    
    print("🎯 Batch Video Processor")
    print(f"📹 Main video: {main_video}")
    print(f"📂 Intro folder: {intro_folder}")
    print(f"📁 Output folder: {output_folder}")
    
    # Check if main video exists
    if not os.path.exists(main_video):
        print(f"❌ Main video not found: {main_video}")
        sys.exit(1)
    
    # Copy the example intro to the intro folder if it doesn't exist
    example_intro = "/Users/seb/Downloads/Automated Test Fixes.mp4"
    if os.path.exists(example_intro):
        import shutil
        dest_path = os.path.join(intro_folder, "Automated_Test_Fixes.mp4")
        if not os.path.exists(dest_path):
            print(f"📥 Copying example intro to: {dest_path}")
            shutil.copy2(example_intro, dest_path)
    
    print("\n🔧 Processing features:")
    print("   • Intro video at start")
    print("   • Background: frozen first frame from intro")
    print("   • Subtitles: bottom 20% from main video")
    print("   • Combined audio from both videos")
    
    # Process all videos
    process_batch_videos(intro_folder, main_video, output_folder)
    
    print("\n💡 To add more intro videos:")
    print(f"   1. Copy them to: {intro_folder}")
    print("   2. Run this script again")
    print("\n📺 All output videos will be in:")
    print(f"   {output_folder}")

if __name__ == "__main__":
    main()
