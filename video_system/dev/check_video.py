#!/usr/bin/env python3
"""Quick check of video properties"""

import moviepy
import sys

def check_video(video_path):
    try:
        clip = moviepy.VideoFileClip(video_path)
        print(f"Duration: {clip.duration:.2f}s")
        print(f"Size: {clip.size}")
        print(f"FPS: {clip.fps}")
        clip.close()
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    check_video("/Users/seb/leads/data/test_outputs/video_with_freeze.mp4")
