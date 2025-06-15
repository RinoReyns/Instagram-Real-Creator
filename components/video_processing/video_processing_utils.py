from __future__ import annotations


import cv2
import numpy as np
from PIL import Image
import subprocess


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


def has_nvenc_support():
    try:
        # Run ffmpeg -encoders and capture output
        result = subprocess.run(
            ["ffmpeg", "-hide_banner", "-encoders"],
            capture_output=True,
            text=True,
            check=True,
        )
        encoders = result.stdout.lower()
        # Check for NVENC encoders
        return "h264_nvenc" in encoders or "hevc_nvenc" in encoders
    except FileNotFoundError:
        print("FFmpeg is not installed or not found in PATH.")
        return False
    except subprocess.CalledProcessError as e:
        print("FFmpeg error:", e)
        return False


def has_nvidia_gpu():
    try:
        result = subprocess.run(
            ["nvidia-smi"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=True,
        )
        # Print basic GPU info (optional)
        print("🖥️ NVIDIA GPU detected:\n", result.stdout.split("\n")[2])
        return True
    except FileNotFoundError:
        print("⚠️ 'nvidia-smi' not found. Is the NVIDIA driver installed?")
    except subprocess.CalledProcessError as e:
        print("❌ 'nvidia-smi' failed to run. Error:\n", e.stderr)
    return False


def get_codec():
    if has_nvenc_support() and has_nvidia_gpu():
        codec = "h264_nvenc"
        print("✅ NVENC GPU acceleration is available.")
    else:
        codec = "libx264"
        # codec = "h264_qsv"
        print("⚠️ Falling back to CPU encoding.")
    return codec
