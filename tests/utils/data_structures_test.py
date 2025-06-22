from __future__ import annotations

import unittest
from dataclasses import fields

from utils.data_structures import MediaClip


class TestMediaClipFieldOrder(unittest.TestCase):
    def test_field_order(self):
        expected_order = [
            "start",
            "end",
            "crossfade",
            "type",
            "video_resampling",
        ]
        actual_order = [field.name for field in fields(MediaClip)]
        self.assertEqual(actual_order, expected_order)
