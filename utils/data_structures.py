from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from moviepy.video.io.VideoFileClip import VideoFileClip


class VisionDataTypeEnum(StrEnum):
    VIDEO = "video"
    PHOTO = "photo"


class TransitionTypeEnum(StrEnum):
    NONE = "none"
    ZOOM = "zoom"
    SLIDE = "slide"
    FADE = "fade"
    SPIN = "spin"


@dataclass
class MediaClip:
    start: float
    end: float
    transition: TransitionTypeEnum
    type: VisionDataTypeEnum  # 'video' or 'image'
    video_resampling: int


@dataclass
class LoadedVideo:
    clip: VideoFileClip = None
    transition: TransitionTypeEnum = None
