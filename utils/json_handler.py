from __future__ import annotations

import argparse
import json
import logging
import os
from dataclasses import asdict, fields

from utils.data_structures import MediaClip, VisionDataTypeEnum, TransitionTypeEnum

# Configure logger
logging.basicConfig(level=logging.INFO, format="%(levelname)s:%(message)s")
logger = logging.getLogger(__name__)

# File extensions for type detection
VIDEO_EXTENSIONS = {".mp4", ".mov", ".avi", ".mkv"}
PHOTO_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".gif"}


# Path to your JSON file
def pars_config(file_path):
    # Load JSON and validate structure
    try:
        data = media_clips_from_json(file_path)
        logger.info(f"Loaded JSON file: {file_path}")
    except FileNotFoundError:
        logger.error(f"File not found: {file_path}")
        raise
    except json.JSONDecodeError as e:
        logger.error(f"Error decoding JSON: {e}")
        raise

    logger.info("JSON structure is valid.")
    return data


def detect_type(filename):
    ext = os.path.splitext(filename)[1].lower()
    if ext in VIDEO_EXTENSIONS:
        return VisionDataTypeEnum.VIDEO
    elif ext in PHOTO_EXTENSIONS:
        return VisionDataTypeEnum.PHOTO
    else:
        return None


def create_config_from_folder(folder_path):
    config = {}
    for filename in os.listdir(folder_path):
        full_path = os.path.join(folder_path, filename)
        if os.path.isfile(full_path):
            file_type = detect_type(filename)
            if file_type:
                config[filename] = MediaClip(
                    start=0,
                    end=10,
                    transition=TransitionTypeEnum(0),
                    type=file_type,
                    video_resampling=0,
                )
            else:
                logger.warning(f"Skipped unsupported file type: {filename}")
    return config


def media_clips_to_json(data: dict[str, MediaClip], filepath: str):
    json_ready = {
        key: {
            **asdict(clip),
            "type": clip.type.value,  # Serialize Enum to string
        }
        for key, clip in data.items()
    }

    with open(filepath, "w") as f:
        json.dump(json_ready, f, indent=4)


def media_clips_from_json(filepath: str) -> dict[str, MediaClip]:
    with open(filepath) as f:
        raw_data = json.load(f)

    return {
        key: MediaClip(
            start=value[fields(MediaClip)[0].name],
            end=value[fields(MediaClip)[1].name],
            transition=TransitionTypeEnum(value[fields(MediaClip)[2].name]),
            # Convert string to Enum
            type=VisionDataTypeEnum(value[fields(MediaClip)[3].name]),
            video_resampling=value[fields(MediaClip)[4].name],
        )
        for key, value in raw_data.items()
    }


def json_template_generator():
    # Argument parser setup
    parser = argparse.ArgumentParser(
        description="Generate JSON config from a folder of media files.",
    )
    parser.add_argument(
        "--folder",
        required=True,
        type=str,
        help="Path to the folder containing media files",
    )
    parser.add_argument(
        "--output",
        required=True,
        type=str,
        help="Path to save the generated JSON config file",
    )
    args = parser.parse_args()

    # Generate config
    logger.info(f"Scanning folder: {args.folder}")
    config = create_config_from_folder(args.folder)
    media_clips_to_json(config, args.output)
