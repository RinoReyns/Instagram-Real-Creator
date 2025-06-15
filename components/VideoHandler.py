from __future__ import annotations

import os.path
from enum import Enum

from components.YoutubeDownloader import download_youtube_video


class VideoSource(Enum):
    YOU_TUBE = 1
    LOCAL = 2

    @classmethod
    def list_values(cls):
        return list(map(lambda c: c.value, cls))

    @classmethod
    def list_names(cls):
        return list(map(lambda c: c.name, cls))

    @classmethod
    def has_value(cls, value):
        return value in cls._value2member_map_


class VideoHandler:
    def __init__(self, option_id: int):
        self._option_id = option_id

    def extract_video(self, source_string) -> str:
        if self._option_id == VideoSource.YOU_TUBE.value:
            vid = download_youtube_video(source_string)
            if vid in [None, ""]:
                raise ValueError("Unable to Download the video")

            vid = vid.replace(".webm", ".mp4")
            print(f"Downloaded video and audio files successfully! at {vid}")
        if self._option_id == VideoSource.LOCAL.value:
            if not os.path.exists(source_string):
                raise ValueError("Path doesn't exists")
            return source_string

        raise ValueError(f"Unsupported option id {self._option_id}")
