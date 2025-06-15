import logging
import os

from components.video_processing.video_processing_utils import get_codec
from utils.data_structures import LoadedVideo
from moviepy.video.VideoClip import ColorClip
from moviepy.video.compositing.CompositeVideoClip import CompositeVideoClip
from moviepy.video.io.VideoFileClip import VideoFileClip
from components.video_processing.video_transitions import VideoTransitions

logging.basicConfig(level=logging.INFO, format="%(levelname)s:%(message)s")


class VideoPostProcessing:
    OUTPUT_FPS = 30

    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.video_transitions = VideoTransitions()

    @staticmethod
    def resize_and_center(clip: LoadedVideo, target_size=(1080, 1920)) -> LoadedVideo:
        target_w, target_h = target_size
        clip_w, clip_h = clip.clip.size
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
        resized_clip = clip.clip.resize(newsize=(new_w, new_h))

        # Create a background (black)
        background = ColorClip(
            size=target_size,
            color=(
                0,
                0,
                0,
            ),
            duration=clip.clip.duration,
        )

        # Overlay the resized clip in the center of the background
        composed = CompositeVideoClip(
            [background, resized_clip.set_position("center")],
            size=target_size,
        )
        clip.clip = composed.set_duration(clip.clip.duration).set_audio(
            resized_clip.audio
        )
        return clip

    def apply_transitions(self, clips: list[LoadedVideo]) -> VideoFileClip:
        final_clip = clips[0].clip

        for i in range(1, len(clips)):
            transition = self.video_transitions.transitions[clips[i - 1].transition]
            final_clip = transition(final_clip, clips[i].clip, duration=1)
        return final_clip

    def run(self, output_path: str, clips: list[LoadedVideo]):
        resized_clips_list = [self.resize_and_center(c) for c in clips]
        final_clip = self.apply_transitions(resized_clips_list)
        # final_clip = concatenate_videoclips(final_clips, method="compose")
        final_clip.write_videofile(
            output_path,
            codec=get_codec(),
            audio_codec="aac",
            threads=os.cpu_count() - 2,
            fps=self.OUTPUT_FPS,
        )

        # Close all clips to release resources
        final_clip.close()
        for clip in clips:
            clip.clip.close()
