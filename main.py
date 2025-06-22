from __future__ import annotations

import argparse
import logging

from components.video_processing.video_preprocessing import VideoPreprocessing
from components.video_processing.video_postprocessing import VideoPostProcessing

from utils.json_handler import json_template_generator, pars_config

logging.basicConfig(level=logging.INFO, format="%(levelname)s:%(message)s")
logger = logging.getLogger(__name__)

MAX_DURATION = 90  # seconds
GENERATE_JSON = 0


def create_instagram_reel(config_file, media_dir, output_path, preview=False):
    video_preprocessing = VideoPreprocessing()
    video_preprocessing.cleanup_temp_files()
    clips = []
    total_duration = 0
    for filename, entry in config_file.items():
        try:
            clip = video_preprocessing.process_entry(filename, entry, media_dir)
            duration = clip.clip.duration
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
    video_postprocessing = VideoPostProcessing()
    if preview:
        video_postprocessing.preview(clips)
    else:
        video_postprocessing.final_render(output_path, clips)
    video_preprocessing.cleanup_temp_files()

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
