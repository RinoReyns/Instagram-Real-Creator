from __future__ import annotations

import argparse
import logging
import os

from moviepy.editor import (
    concatenate_videoclips,
)

from components.video_processing.video_processing_utils import resize_and_center
from components.video_processing.video_processing import VideoProcessing

from utils.json_handler import json_template_generator, pars_config

logging.basicConfig(level=logging.INFO, format="%(levelname)s:%(message)s")
logger = logging.getLogger(__name__)


# Constants for Instagram Reels format
MAX_DURATION = 90  # seconds
FPS = 30

GENERATE_JSON = 0


def create_instagram_reel(config_file, media_dir, output_path):
    video_processing = VideoProcessing()
    video_processing.cleanup_temp_files()
    clips = []
    total_duration = 0
    for filename, entry in config_file.items():
        try:
            clip = video_processing.process_entry(filename, entry, media_dir)
            duration = clip.duration
            if total_duration + duration > MAX_DURATION:
                logger.info(f"Skipping {filename}, would exceed max duration.")
                continue

            clips.append(clip)
            total_duration += duration
        except Exception as e:
            logger.info(f"Error processing {filename}: {e}")

    if not clips:
        logger.info("No valid clips to process.")
        return
    final_clips = [resize_and_center(c) for c in clips]
    final_clip = concatenate_videoclips(final_clips, method="compose")
    final_clip.write_videofile(
        output_path,
        codec="libx264",
        audio_codec="aac",
        threads=os.cpu_count() - 2,
        fps=FPS,
    )

    # Close all clips to release resources
    final_clip.close()
    for clip in clips:
        clip.close()
    video_processing.cleanup_temp_files()

    # TODO:
    # handle audio
    # if audio_path:
    #     audio = AudioFileClip(audio_path).subclip(0, final_clip.duration)
    #     final_clip = final_clip.set_audio(audio)


def arg_paser():
    parser = argparse.ArgumentParser(
        description="Validate JSON config file structure.",
    )
    parser.add_argument(
        "--config_path",
        type=str,
        required=True,
        help="Path to the config JSON file.",
    )
    parser.add_argument(
        "--media_dir",
        type=str,
        required=True,
        help="Full path to the dir with media.",
    )
    return parser.parse_args()


if __name__ == "__main__":
    if GENERATE_JSON:
        json_template_generator()
    else:
        args = arg_paser()
        json_file = pars_config(args.config_path)
        create_instagram_reel(json_file, args.media_dir, "test_output.mp4")
