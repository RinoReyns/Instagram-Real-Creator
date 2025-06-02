from __future__ import annotations

import argparse
import os
import random
import shutil

import cv2
import numpy as np
from moviepy.editor import *
from moviepy.editor import AudioFileClip
from moviepy.editor import concatenate_videoclips
from moviepy.editor import ImageClip
from moviepy.editor import VideoFileClip
from moviepy.video.io.ffmpeg_tools import ffmpeg_extract_subclip
from PIL import Image


def create_video_from_image(image_path: str, output_path: str, duration: float, fps: int = 24):
    """
    Creates an MP4 video of specified duration from a single image.

    Args:
        image_path (str): Path to the source image file.
        output_path (str): Path where the output MP4 will be saved.
        duration (float): Duration of the output video in seconds.
        fps (int, optional): Frames per second of the video. Defaults to 24.
    """
    # Create an ImageClip and set its duration
    clip = ImageClip(image_path).set_duration(duration)

    # Write the video file
    clip.write_videofile(output_path, fps=fps)


def merge_videos(input_paths, output_path, method='concat', fps=None, output_folder='output_folder'):
    """
    Merge multiple MP4 videos into one output MP4.

    Args:
        input_paths (list of str): Paths to the source videos, in order.
        output_path (str): Path where the merged MP4 will be saved.
        method (str): 'concat' for simple concatenation, 'compose' to ensure matching properties.
        fps (int, optional): Frames per second for the output. Defaults to None (use source FPS).
    """
    # random.shuffle(input_paths)
    # Load all clips
    first_files = ['VID_1.mp4', 'VID_2.mp4']
    last_file = 'VID_Last.mp4'

    # Separate files
    start = [f for f in first_files if f in input_paths]
    end = [last_file] if last_file in input_paths else []
    middle = [f for f in input_paths if f not in start + end]
    random.shuffle(middle)
    # Sort or keep `middle` as-is depending on preference
    # middle.sort()  # Uncomment this if you want alphabetical sort

    # Final result
    sorted_files = start + middle + end

    clips = [
        VideoFileClip(os.path.join(output_folder, path))
        for path in input_paths
    ]

    # Concatenate clips
    if method == 'compose':
        final_clip = concatenate_videoclips(clips, method='compose')
    else:
        final_clip = concatenate_videoclips(clips, method='chain')

    # Write the final video file
    write_args = {'fps': fps} if fps else {}
    print(os.cpu_count())
    write_args['threads'] = os.cpu_count() - 2
    final_clip.write_videofile(output_path, **write_args)

    # Close all clips to release resources
    final_clip.close()
    for clip in clips:
        clip.close()


def main():
    parser = argparse.ArgumentParser(
        description='Generate an MP4 video of a given length from a single image.',
    )
    # parser.add_argument("image", help="Path to the source image")
    # parser.add_argument("output", help="Path for the output MP4 file")
    parser.add_argument(
        '--duration', type=float, default=5.0,
        help='Length of the output video in seconds (default: 5)',
    )
    parser.add_argument(
        '--fps', type=int, default=32,
        help='Frames per second for the video (default: 24)',
    )

    # TODO:
    # first resize all images to the same sizes, than generate wideo
    args = parser.parse_args()

    folder_path = ""
    output_folder = os.path.join(folder_path, 'output')
    os.makedirs(output_folder, exist_ok=True)
    for image_path in os.listdir(folder_path):
        image_full_path = os.path.join(folder_path, image_path)
        if not os.path.isdir(image_full_path):
            if 'jpg' in image_path:
                output_path = f"VID_{image_path.replace("jpg", "mp4")}"

                create_video_from_image(
                    image_full_path,
                    os.path.join(output_folder, output_path),
                    random.uniform(0.8, 2), args.fps,
                )
            else:
                try:
                    if 'VID_4' in image_full_path:
                        start = 2
                        end = 4
                    else:
                        start = 0
                        end = 2

                    # loading video gfg
                    clip = VideoFileClip(image_full_path)
                    # getting only first 5 seconds
                    clip = clip.subclip(start, end)

                    clip.write_videofile(
                        os.path.join(output_folder, image_path),
                    )

                   # ffmpeg_extract_subclip(image_full_path, start, end, targetname=os.path.join(output_folder, image_path))

                except Exception as e:
                    print(e)
    merge_videos(
        os.listdir(output_folder), os.path.join(
            output_folder, 'final.mp4',
        ), output_folder=output_folder,
    )  # , method="compose")


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


def create_slideshow_reel(photo_paths, output_path='slideshow_reel.mp4', duration_per_photo=3, fade_duration=1, audio_path=None):
    clips = []
    reel_size = (1080, 1920)
    fps = 30

    for i, photo_path in enumerate(photo_paths):
        formatted_img = format_photo_to_vertical(str(photo_path), reel_size)
        clip = ImageClip(formatted_img).set_duration(
            duration_per_photo,
        ).set_fps(fps)
        if i != 0:
            clip = clip.crossfadein(fade_duration)
        clips.append(clip)

        # Concatenate with crossfade
    final_clip = concatenate_videoclips(
        clips, method='compose', padding=-fade_duration,
    )

    if audio_path:
        audio = AudioFileClip(audio_path).subclip(0, final_clip.duration)
        final_clip = final_clip.set_audio(audio)

    final_clip.write_videofile(output_path, codec='libx264', audio_codec='aac')
    print(f"✅ Slideshow Reel saved to {output_path}")

# Example usage:
# create_slideshow_reel(["photo1.jpg", "photo2.jpg", "photo3.jpg"], "reel.mp4", duration_per_photo=4, audio_path="music.mp3")


if __name__ == '__main__':
    # # main()

    #
    #  audio = AudioFileClip("../audio_rolka.wav",
    #                                     buffersize=200000,
    #                                     fps=44100,
    #                                     nbytes=2)
    #
    #  combined_clip = clip_with_audio.set_audio(audio)
    #
    #  combined_clip.write_videofile(
    #     , audio_codec='aac',  preset='placebo', bitrate='3000k',
    # )
    import pathlib

    photos_list = [
        filepath.absolute() for filepath in pathlib.Path(

        ).glob('**/*')
    ]
    create_slideshow_reel(photos_list, 'reel.mp4', duration_per_photo=3)

