from moviepy.editor import concatenate_videoclips
from utils.data_structures import TransitionTypeEnum
from moviepy.editor import ImageSequenceClip
import numpy as np
import cv2
from tqdm import tqdm


class VideoTransitions:
    FPS = 30

    def __init__(self):
        self.transitions = {
            TransitionTypeEnum.SLIDE: self.slide_transition,
            TransitionTypeEnum.ZOOM: self.zoom_transition,
            TransitionTypeEnum.FADE: self.fade_transition,
            TransitionTypeEnum.NONE: self.no_transition,
            TransitionTypeEnum.SPIN: self.spin_transition,
        }

    @staticmethod
    def clip_to_frames(clip, fps=FPS):
        """Render all frames of a clip to a list of numpy arrays (RGB)."""
        duration = clip.duration
        frames = []
        for t in np.arange(0, duration, 1 / fps):
            frame = clip.get_frame(t)  # returns (H,W,3) RGB numpy array
            frames.append(frame)
        return frames

    def slide_transition(self, clip1, clip2, duration=0.1, fps=30, blend_width=0):
        # slide direction
        frames1 = self.clip_to_frames(clip1, fps)
        frames2 = self.clip_to_frames(clip2, fps)

        w = frames1[0].shape[1]
        transition_frames = int(duration * fps)

        output_frames = []

        # Write frames1 until transition start
        output_frames.extend(frames1[:-transition_frames])

        for i in range(transition_frames):
            progress = i / transition_frames
            x_offset = int(w * (1 - progress))

            frame1 = frames1[-transition_frames + i]
            frame2 = frames2[i]

            frame = np.zeros_like(frame1)

            # Slide clip1 out left
            if x_offset > blend_width:
                frame[:, : x_offset - blend_width] = frame1[
                    :, w - x_offset + blend_width : w
                ]

            # Slide clip2 in right
            if x_offset + blend_width < w:
                frame[:, x_offset + blend_width :] = frame2[
                    :, : w - (x_offset + blend_width)
                ]

            # Blend seam area with linear alpha
            if 0 < x_offset < w:
                for bw in range(blend_width):
                    alpha = bw / blend_width
                    col1 = w - x_offset + bw
                    col2 = x_offset - blend_width + bw

                    if 0 <= col1 < w and 0 <= col2 < w:
                        # Blend the two columns at seam
                        frame[:, col2] = (
                            frame1[:, col1] * (1 - alpha) + frame2[:, col2] * alpha
                        ).astype(np.uint8)

            output_frames.append(frame)

        # Append remaining frames2 after transition
        output_frames.extend(frames2[transition_frames:])

        final_clip = ImageSequenceClip(output_frames, fps=fps)
        return final_clip

    @staticmethod
    def rotate_frame(frame, angle, output_size):
        """
        Rotate a frame around its center and resize/pad/crop to output_size.
        """
        h, w = frame.shape[:2]
        center = (w // 2, h // 2)

        # Rotation matrix
        M = cv2.getRotationMatrix2D(center, angle, 1.0)
        rotated = cv2.warpAffine(
            frame,
            M,
            (w, h),
            flags=cv2.INTER_LINEAR,
            borderMode=cv2.BORDER_CONSTANT,
            borderValue=0,
        )

        # Ensure final size is output_size (crop or pad as needed)
        out_w, out_h = output_size
        resized = cv2.resize(rotated, (out_w, out_h))
        return resized

    @staticmethod
    def frame_generator(clip, fps):
        t = 0
        while t < clip.duration:
            yield clip.get_frame(t)
            t += 1 / fps

    def spin_transition(self, clip1, clip2, duration=0.1, fps=30):
        transition_frames = int(duration * fps)
        output_frames = []

        w, h = clip1.size
        output_size = (w, h)

        frames1_gen = self.frame_generator(clip1, fps)
        frames2_gen = self.frame_generator(clip2, fps)

        # Pre-transition frames from clip1
        for _ in tqdm(
            range(int(clip1.duration * fps) - transition_frames),
            desc="Pre-transition in spin transition",
        ):
            output_frames.append(next(frames1_gen))

        # Transition frames
        for i in tqdm(range(transition_frames), desc="Generating spin transition"):
            progress = i / transition_frames

            frame1 = next(frames1_gen)
            frame2 = next(frames2_gen)

            angle1 = 360 * progress
            alpha1 = 1 - progress
            rotated1 = self.rotate_frame(frame1, angle1, output_size)

            angle2 = -360 + 360 * progress
            alpha2 = progress
            rotated2 = self.rotate_frame(frame2, angle2, output_size)

            blended = (
                rotated1.astype(np.float32) * alpha1
                + rotated2.astype(np.float32) * alpha2
            ).astype(np.uint8)
            output_frames.append(blended)

        # Post-transition frames from clip2
        for frame in frames2_gen:
            frame_resized = cv2.resize(frame, output_size)
            output_frames.append(frame_resized)

        return ImageSequenceClip(output_frames, fps=fps)

    def zoom_frame(self, frame, scale):
        """
        Zoom in/out frame by scale factor keeping output size same by cropping/padding.
        scale >1 = zoom in, scale <1 = zoom out
        """
        h, w = frame.shape[:2]
        new_w, new_h = int(w * scale), int(h * scale)

        # Resize frame
        resized = cv2.resize(frame, (new_w, new_h), interpolation=cv2.INTER_LINEAR)

        if scale > 1:
            # Crop center to original size
            x_start = (new_w - w) // 2
            y_start = (new_h - h) // 2
            cropped = resized[y_start : y_start + h, x_start : x_start + w]
            return cropped
        else:
            # Pad resized to original size
            pad_x1 = (w - new_w) // 2
            pad_y1 = (h - new_h) // 2
            pad_x2 = w - new_w - pad_x1
            pad_y2 = h - new_h - pad_y1
            padded = cv2.copyMakeBorder(
                resized, pad_y1, pad_y2, pad_x1, pad_x2, cv2.BORDER_CONSTANT, value=0
            )
            return padded

    def zoom_transition(self, clip1, clip2, duration=0.1, fps=30, direction="in_out"):
        transition_frames = int(duration * fps)

        frames1_gen = (
            clip1.get_frame(t) for t in np.arange(0, clip1.duration, 1 / fps)
        )
        frames2_gen = (
            clip2.get_frame(t) for t in np.arange(0, clip2.duration, 1 / fps)
        )

        output_frames = []
        total_frames1 = int(clip1.duration * fps)

        for _ in range(total_frames1 - transition_frames):
            output_frames.append(next(frames1_gen))

        for i in tqdm(range(transition_frames), desc="Generating zoom transition"):
            progress = i / transition_frames
            frame1 = next(frames1_gen)
            frame2 = next(frames2_gen)

            # Determine zoom scale and alpha based on direction
            if direction == "in_out":
                scale1 = 1.2 - 0.2 * progress  # zoom out
                scale2 = 0.8 + 0.2 * progress  # zoom in
            elif direction == "out_in":
                scale1 = 0.8 + 0.2 * progress  # zoom in
                scale2 = 1.2 - 0.2 * progress  # zoom out
            elif direction == "in":
                scale1 = 1.0 + 0.2 * progress
                scale2 = 1.0 + 0.2 * progress
            elif direction == "out":
                scale1 = 1.2 - 0.2 * progress
                scale2 = 1.2 - 0.2 * progress
            else:
                raise ValueError(
                    "Invalid direction. Use 'in_out', 'out_in', 'in', or 'out'."
                )

            alpha1 = 1 - progress
            alpha2 = progress

            zoomed1 = self.zoom_frame(frame1, scale1)
            zoomed2 = self.zoom_frame(frame2, scale2)

            blended = (
                zoomed1.astype(np.float32) * alpha1
                + zoomed2.astype(np.float32) * alpha2
            ).astype(np.uint8)
            output_frames.append(blended)

        for frame in frames2_gen:
            output_frames.append(frame)

        return ImageSequenceClip(output_frames, fps=fps)

    @staticmethod
    def fade_transition(clip1, clip2, duration=0.1):
        # Only apply fade effects and concatenate — more efficient than composite
        clip1_fade = clip1.fadeout(duration)
        clip2_fade = clip2.fadein(duration)
        return concatenate_videoclips([clip1_fade, clip2_fade], method="compose")

    @staticmethod
    def no_transition(clip1, clip2, duration=0):
        return concatenate_videoclips([clip1, clip2], method="compose")
