from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class VisionDataTypeEnum(StrEnum):
    VIDEO = "video"
    PHOTO = "photo"


@dataclass
class MediaClip:
    start: float
    end: float
    crossfade: float
    type: VisionDataTypeEnum  # 'video' or 'image'
    video_resampling: int
