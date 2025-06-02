from __future__ import annotations

import argparse
import logging
import os
import subprocess
import tempfile

import cv2
import numpy as np
from moviepy.editor import ColorClip
from moviepy.editor import CompositeVideoClip
from moviepy.editor import concatenate_videoclips
from moviepy.editor import ImageClip
from moviepy.editor import VideoFileClip
from PIL import Image
from sympy import floor

from utils.json_handler import json_template_generator
from utils.json_handler import pars_config

logging.basicConfig(level=logging.INFO, format='%(levelname)s:%(message)s')
logger = logging.getLogger(__name__)


# Constants for Instagram Reels format
INSTAGRAM_RESOLUTION = (1080, 1920)
MAX_DURATION = 90  # seconds
FPS = 30

GENERATE_JSON = 0

cfr_cache = {}  # {original_path: converted_path}
temp_cfr_files = []  # For cleanup


def is_variable_framerate(video_path):
    """
    Returns a tuple: (is_variable, avg_framerate_float)
    - is_variable: True if variable framerate detected
    - avg_framerate_float: average framerate as float, or None on failure
    """
    cmd = [
        'ffprobe', '-v', 'error', '-select_streams', 'v:0',
        '-show_entries', 'stream=r_frame_rate,avg_frame_rate',
        '-of', 'default=noprint_wrappers=1:nokey=1',
        video_path,
    ]
    try:
        output = subprocess.check_output(
            cmd, stderr=subprocess.DEVNULL,
        ).decode().split()
        if len(output) >= 2:
            r_fps = eval(output[0])  # example: '30000/1001'
            avg_fps = eval(output[1])
            is_var = not (r_fps == avg_fps)
            if is_var:
                logger.warning(f"Variable framerate detected in: {video_path}")
            test = floor(avg_fps)
            return is_var, floor(avg_fps)
    except Exception as e:
        logger.error(f"ffprobe failed on {video_path}: {e}")
        return False, None


def cleanup_temp_files():
    for path in temp_cfr_files:
        try:
            os.remove(path)
            logger.info(f"Deleted temp CFR file: {path}")
        except Exception as e:
            logger.warning(f"Failed to delete {path}: {e}")


def convert_to_cfr(input_path, target_fps=30):
    """Convert a VFR video to CFR and return cached path if already done."""
    if input_path in cfr_cache:
        return cfr_cache[input_path]

    # Use temp file with name derived from input for reuse
    temp_dir = tempfile.gettempdir()
    base_name = os.path.basename(input_path)
    name_no_ext = os.path.splitext(base_name)[0]
    output_path = os.path.join(
        temp_dir, f"{name_no_ext}_cfr_{target_fps}fps.mp4",
    )

    if os.path.exists(output_path):
        logger.info(f"Using cached CFR file: {output_path}")
        cfr_cache[input_path] = output_path
        return output_path

    cmd = [
        'ffmpeg', '-i', input_path,
        '-r', str(target_fps),
        '-vsync', 'cfr',
        '-pix_fmt', 'yuv420p',
        '-c:v', 'libx264',
        '-preset', 'slow',
        '-crf', '18',
        '-c:a', 'aac',
        '-b:a', '192k',
        '-y', output_path,
    ]
    subprocess.run(
        cmd, stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL, check=True,
    )
    logger.info(f"Converted to CFR: {output_path}")

    cfr_cache[input_path] = output_path
    temp_cfr_files.append(output_path)
    return output_path


def format_photo_to_vertical(photo_path, reel_size=(1080, 1920)):
    # Load image
    img = cv2.imread(photo_path)
    img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)

    # Create blurred background
    bg = cv2.resize(img_rgb*0, reel_size)
    bg = cv2.GaussianBlur(bg, (51, 51), 0)

    # Convert to PIL and resize foreground photo
    foreground = Image.fromarray(img_rgb)
    foreground.thumbnail(reel_size, Image.Resampling.LANCZOS)

    fg_w, fg_h = foreground.size
    bg_pil = Image.fromarray(bg)
    offset = ((reel_size[0] - fg_w) // 2, (reel_size[1] - fg_h) // 2)
    bg_pil.paste(foreground, offset)

    return np.array(bg_pil)


def process_entry(file_path, entry, media_dir):
    full_path = os.path.join(media_dir, file_path)
    media_type = entry['type']
    start = entry.get('start', 0)
    end = entry.get('end', 10)
    crossfade = entry.get('crossfade', 1)
    video_resampling = entry.get('video_resampling', 1)

    if media_type == 'video':
        # Detect and convert VFR to CFR
        status, avg_fps = is_variable_framerate(full_path)
        if status and video_resampling:
            logger.info(f"Converting {file_path} to CFR.")
            full_path = convert_to_cfr(full_path, avg_fps)

        clip = VideoFileClip(full_path)
        if end > clip.duration:
            logger.warning(
                f"End time {end}s exceeds video duration {clip.duration:.2f}s for file: {file_path}",
            )
            end = clip.duration
        clip = clip.subclip(start, end)

    elif media_type == 'photo':
        duration = end - start
        formatted_img = format_photo_to_vertical(
            full_path, INSTAGRAM_RESOLUTION,
        )
        clip = ImageClip(formatted_img).set_duration(duration)
    else:
        raise ValueError(f"Unsupported media type: {media_type}")

    clip = clip.set_duration(end - start)
    return clip


def resize_and_center(clip, target_size=(1080, 1920)):
    target_w, target_h = target_size
    clip_w, clip_h = clip.size
    clip_ar = clip_w / clip_h
    target_ar = target_w / target_h

    # Determine new size to preserve aspect ratio
    if clip_ar > target_ar:
        # Too wide, match width and scale height
        new_w = target_w
        new_h = int(target_w / clip_ar)
    else:
        # Too tall, match height and scale width
        new_h = target_h
        new_w = int(target_h * clip_ar)

    # Now actually resize the clip
    resized_clip = clip.resize(newsize=(new_w, new_h))

    # Create a background (black)
    background = ColorClip(
        size=target_size, color=(
            0, 0, 0,
        ), duration=clip.duration,
    )

    # Overlay the resized clip in the center of the background
    composed = CompositeVideoClip(
        [background, resized_clip.set_position('center')], size=target_size,
    )

    return composed.set_duration(clip.duration).set_audio(resized_clip.audio)


def create_instagram_reel(config_file, media_dir, output_path):
    cleanup_temp_files()
    clips = []
    total_duration = 0
    for filename, entry in config_file.items():
        try:
            clip = process_entry(filename, entry, media_dir)
            duration = clip.duration
            if total_duration + duration > MAX_DURATION:
                print(f"Skipping {filename}, would exceed max duration.")
                continue

            clips.append(clip)
            total_duration += duration
        except Exception as e:
            print(f"Error processing {filename}: {e}")

    if not clips:
        print('No valid clips to process.')
        return
    final_clips = [resize_and_center(c) for c in clips]
    final_clip = concatenate_videoclips(final_clips, method='compose')
    final_clip.write_videofile(
        output_path, codec='libx264',
        audio_codec='aac', threads=os.cpu_count() - 2, fps=FPS,
    )

    # Close all clips to release resources
    final_clip.close()
    for clip in clips:
        clip.close()
    cleanup_temp_files()

    # TODO:
    # handle audio
    # if audio_path:
    #     audio = AudioFileClip(audio_path).subclip(0, final_clip.duration)
    #     final_clip = final_clip.set_audio(audio)


def arg_paser():
    parser = argparse.ArgumentParser(
        description='Validate JSON config file structure.',
    )
    parser.add_argument(
        '--config_path', type=str,
        required=True, help='Path to the config JSON file.',
    )
    parser.add_argument(
        '--media_dir', type=str, required=True,
        help='Full path to the dir with media.',
    )
    return parser.parse_args()


if __name__ == '__main__':
    if GENERATE_JSON:
        json_template_generator()
    else:
        args = arg_paser()
        json_file = pars_config(args.config_path)
        create_instagram_reel(json_file, args.media_dir, 'test_output.mp4')
