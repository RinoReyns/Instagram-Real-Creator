from __future__ import annotations


import cv2
import numpy as np
from PIL import Image

from moviepy.video.VideoClip import ColorClip
from moviepy.video.compositing.CompositeVideoClip import CompositeVideoClip


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
        size=target_size,
        color=(
            0,
            0,
            0,
        ),
        duration=clip.duration,
    )

    # Overlay the resized clip in the center of the background
    composed = CompositeVideoClip(
        [background, resized_clip.set_position("center")],
        size=target_size,
    )

    return composed.set_duration(clip.duration).set_audio(resized_clip.audio)


def format_photo_to_vertical(photo_path, reel_size=(1080, 1920)):
    # Load image
    img = cv2.imread(photo_path)
    img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)

    # Create blurred background
    bg = cv2.resize(img_rgb * 0, reel_size)
    bg = cv2.GaussianBlur(bg, (51, 51), 0)

    # Convert to PIL and resize foreground photo
    foreground = Image.fromarray(img_rgb)
    foreground.thumbnail(reel_size, Image.Resampling.LANCZOS)

    fg_w, fg_h = foreground.size
    bg_pil = Image.fromarray(bg)
    offset = ((reel_size[0] - fg_w) // 2, (reel_size[1] - fg_h) // 2)
    bg_pil.paste(foreground, offset)

    return np.array(bg_pil)
