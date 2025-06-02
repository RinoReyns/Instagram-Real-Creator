from __future__ import annotations

import argparse
import json
import logging
import os

# Configure logger
logging.basicConfig(level=logging.INFO, format='%(levelname)s:%(message)s')
logger = logging.getLogger(__name__)

# File extensions for type detection
VIDEO_EXTENSIONS = {'.mp4', '.mov', '.avi', '.mkv'}
PHOTO_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.bmp', '.gif'}


# Path to your JSON file
def pars_config(file_path):
    # Load JSON and validate structure
    try:
        with open(file_path, encoding='utf-8') as file:
            data = json.load(file)
        logger.info(f"Loaded JSON file: {file_path}")
    except FileNotFoundError:
        logger.error(f"File not found: {file_path}")
        raise
    except json.JSONDecodeError as e:
        logger.error(f"Error decoding JSON: {e}")
        raise

    # Required keys for each file entry
    required_keys = {'start', 'end', 'crossfade', 'type'}
    valid_types = {'video', 'photo'}

    # Validate each entry
    for file_path_key, properties in data.items():
        if not isinstance(properties, dict):
            raise ValueError(
                f"Entry for '{file_path_key}' is not a dictionary.",
            )

        missing_keys = required_keys - properties.keys()
        if missing_keys:
            raise ValueError(
                f"Missing keys in '{file_path_key}': {missing_keys}",
            )

        if properties['type'] not in valid_types:
            raise ValueError(
                f"Invalid type in '{file_path_key}': {properties['type']}",
            )

    logger.info('JSON structure is valid.')
    return data


def detect_type(filename):
    ext = os.path.splitext(filename)[1].lower()
    if ext in VIDEO_EXTENSIONS:
        return 'video'
    elif ext in PHOTO_EXTENSIONS:
        return 'photo'
    else:
        return None


def create_config_from_folder(folder_path):
    config = {}
    for filename in os.listdir(folder_path):
        full_path = os.path.join(folder_path, filename)
        if os.path.isfile(full_path):
            file_type = detect_type(filename)
            if file_type:
                config[filename] = {
                    'start': 0,
                    'end': 10,
                    'crossfade': 1,
                    'type': file_type,
                    'video_resampling': 0,
                }
            else:
                logger.warning(f"Skipped unsupported file type: {filename}")
    return config


def json_template_generator():
    # Argument parser setup
    parser = argparse.ArgumentParser(
        description='Generate JSON config from a folder of media files.',
    )
    parser.add_argument(
        '--folder', required=True, type=str,
        help='Path to the folder containing media files',
    )
    parser.add_argument(
        '--output', required=True, type=str,
        help='Path to save the generated JSON config file',
    )
    args = parser.parse_args()

    # Generate config
    logger.info(f"Scanning folder: {args.folder}")
    config = create_config_from_folder(args.folder)

    # Save config
    with open(args.output, 'w', encoding='utf-8') as f:
        json.dump(config, f, indent=4)
    logger.info(f"✅ Config saved to {args.output}")
