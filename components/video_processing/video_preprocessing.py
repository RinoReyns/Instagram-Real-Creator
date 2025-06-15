import os
import logging
import subprocess
import tempfile
from utils.data_structures import VisionDataTypeEnum, MediaClip, LoadedVideo
from sympy import floor

from moviepy.editor import (
    ImageClip,
    VideoFileClip,
)

from components.video_processing.video_processing_utils import format_photo_to_vertical


logging.basicConfig(level=logging.INFO, format="%(levelname)s:%(message)s")


class VideoPreprocessing:
    INSTAGRAM_RESOLUTION = (1080, 1920)
    INSTAGRAM_FPS = 30

    def __init__(self):
        self.cfr_cache = {}  # {original_path: converted_path}
        self.temp_cfr_files = []  # For cleanup
        self.logger = logging.getLogger(__name__)

    def cleanup_temp_files(self):
        for path in self.temp_cfr_files:
            try:
                os.remove(path)
                self.logger.info(f"Deleted temp CFR file: {path}")
            except Exception as e:
                self.logger.warning(f"Failed to delete {path}: {e}")

    def convert_to_cfr(self, input_path, target_fps=30):
        """Convert a VFR video to CFR and return cached path if already done."""
        if input_path in self.cfr_cache:
            return self.cfr_cache[input_path]

        # Use temp file with name derived from input for reuse
        temp_dir = tempfile.gettempdir()
        base_name = os.path.basename(input_path)
        name_no_ext = os.path.splitext(base_name)[0]
        output_path = os.path.join(
            temp_dir,
            f"{name_no_ext}_cfr_{target_fps}fps.mp4",
        )

        if os.path.exists(output_path):
            self.logger.info(f"Using cached CFR file: {output_path}")
            self.cfr_cache[input_path] = output_path
            return output_path

        cmd = [
            "ffmpeg",
            "-i",
            input_path,
            "-r",
            str(target_fps),
            "-vsync",
            "cfr",
            "-pix_fmt",
            "yuv420p",
            "-c:v",
            "libx264",
            "-preset",
            "slow",
            "-crf",
            "18",
            "-c:a",
            "aac",
            "-b:a",
            "192k",
            "-y",
            output_path,
        ]
        subprocess.run(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=True,
        )
        self.logger.info(f"Converted to CFR: {output_path}")

        self.cfr_cache[input_path] = output_path
        self.temp_cfr_files.append(output_path)
        return output_path

    def is_variable_framerate(self, video_path):
        """
        Returns a tuple: (is_variable, avg_framerate_float)
        - is_variable: True if variable framerate detected
        - avg_framerate_float: average framerate as float, or None on failure
        """
        cmd = [
            "ffprobe",
            "-v",
            "error",
            "-select_streams",
            "v:0",
            "-show_entries",
            "stream=r_frame_rate,avg_frame_rate",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            video_path,
        ]
        try:
            output = (
                subprocess.check_output(
                    cmd,
                    stderr=subprocess.DEVNULL,
                )
                .decode()
                .split()
            )
            if len(output) >= 2:
                r_fps = eval(output[0])  # example: '30000/1001'
                avg_fps = eval(output[1])
                is_var = not (r_fps == avg_fps)
                if is_var:
                    self.logger.warning(
                        f"Variable frame rate detected in: {video_path}",
                    )

                return is_var, floor(avg_fps)
        except Exception as e:
            self.logger.error(f"ffprobe failed on {video_path}: {e}")
            return False, None

    def process_entry(self, file_path, entry: MediaClip, media_dir) -> LoadedVideo:
        full_path = os.path.join(media_dir, file_path)
        media_type = entry.type
        start = entry.start
        end = entry.end
        loaded_video = LoadedVideo(transition=entry.transition)

        if media_type == VisionDataTypeEnum.VIDEO.value:
            # Detect and convert VFR to CFR
            status, avg_fps = self.is_variable_framerate(full_path)
            if status and entry.video_resampling:
                self.logger.info(f"Converting {file_path} to CFR.")
                full_path = self.convert_to_cfr(full_path, avg_fps)

            clip = VideoFileClip(full_path)
            if end > clip.duration:
                self.logger.warning(
                    f"End time {end}s exceeds video duration {clip.duration:.2f}s for file: {file_path}",
                )
                end = clip.duration
            clip = clip.subclip(start, end)

        elif media_type == VisionDataTypeEnum.PHOTO.value:
            duration = end - start
            formatted_img = format_photo_to_vertical(
                full_path,
                self.INSTAGRAM_RESOLUTION,
            )
            clip = ImageClip(formatted_img).set_duration(duration)
        else:
            raise ValueError(f"Unsupported media type: {media_type}")

        loaded_video.clip = clip.set_duration(end - start).set_fps(self.INSTAGRAM_FPS)
        return loaded_video
