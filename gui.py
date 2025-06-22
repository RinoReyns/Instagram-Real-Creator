from __future__ import annotations

import logging
import os
import threading
import tkinter as tk
from contextlib import redirect_stderr, redirect_stdout
from tkinter import filedialog, messagebox, scrolledtext, ttk
from utils.gui_utils import format_time
import ttkbootstrap as ttkb

from components.gui_components.text_handler import TextRedirector, TextWidgetHandler
from main import create_instagram_reel
from utils.data_structures import VisionDataTypeEnum
from utils.json_handler import media_clips_to_json, pars_config

import cv2
from PIL import Image, ImageTk

# Optional: Better theming
ThemedTk = ttkb.Window


class InstagramReelCreatorGUI:
    MOVE_PIXEL = 5
    INITIAL_HEIGHT = 1200
    INITIAL_WIDTH = 1600
    PADDING_10 = 10
    MIN_TIMELINE_ELEMENT_WIDTH = 20
    TIMELINE_START_STR = "start"
    TIMELINE_END_STR = "end"
    TIMELINE_BOX_HEIGHT = 120
    GRID_LENGTH_IN_SEC = 90
    ZERO_OFFSET = 0
    PREVIEW_WIDTH = 240
    PREVIEW_HEIGHT = 320
    PREVIEW_FPS = 30
    MAIN_WINDOW_Y_SHIFT = 50

    def __init__(self, root):
        self.root = root
        self.root.title("Instagram Reel Creator")
        self.center_window()
        self.config_path = tk.StringVar()
        self.media_dir = tk.StringVar()
        self.convert_cfr = tk.BooleanVar(value=True)
        self.selected_box_id = None
        self.pixels_per_second = 50
        self.timeline_data = {}
        # Preview
        self.preview_paused = True
        self.user_seeking = False
        self.frame_preview = None
        self.frames = []
        self.frame_timestamps = []
        self.current_frame_index = 0
        self.preview_reset()
        ######
        self.build_ui()

    def center_window(self):
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()
        x = (screen_width // 2) - (self.INITIAL_WIDTH // 2)
        y = (screen_height // 2) - (self.INITIAL_HEIGHT // 2) - self.MAIN_WINDOW_Y_SHIFT
        self.root.geometry(f"{self.INITIAL_WIDTH}x{self.INITIAL_HEIGHT}+{x}+{y}")

    def build_ui(self):
        self.top_frame()
        self.controls_frame()
        self.preview_frame()
        self.create_timeline_frame()

        # Output log (now below timeline)
        ttk.Label(self.root, text="Log Output:").pack(
            anchor="w",
            padx=self.PADDING_10,
        )
        self.log_output = scrolledtext.ScrolledText(self.root, height=15)
        self.log_output.pack(
            fill="both",
            expand=True,
            padx=self.PADDING_10,
            pady=5,
        )
        self.root.bind("<Left>", self.move_selected_left)
        self.root.bind("<Right>", self.move_selected_right)

    def top_frame(self):
        # CONFIG selection
        frame_top = ttk.LabelFrame(
            self.root,
            text="Configuration",
            padding=self.PADDING_10,
        )
        frame_top.pack(fill="x", padx=self.PADDING_10, pady=self.PADDING_10)

        ttk.Label(frame_top, text="Config file:").grid(
            row=0,
            column=0,
            sticky="w",
        )
        ttk.Entry(
            frame_top,
            textvariable=self.config_path,
            width=60,
        ).grid(row=0, column=1, padx=5)
        ttk.Button(
            frame_top,
            text="Browse",
            command=self.select_config_file,
        ).grid(row=0, column=2)

        ttk.Label(frame_top, text="Media folder:").grid(
            row=1,
            column=0,
            sticky="w",
        )
        ttk.Entry(
            frame_top,
            textvariable=self.media_dir,
            width=60,
        ).grid(row=1, column=1, padx=5)
        ttk.Button(
            frame_top,
            text="Browse",
            command=self.select_media_dir,
        ).grid(row=1, column=2)

    def controls_frame(self):
        # Controls
        frame_controls = ttk.Frame(self.root)
        frame_controls.pack(fill="x", padx=self.PADDING_10, pady=5)

        ttk.Button(
            frame_controls,
            text="Create Reel",
            command=self.run_main_script,
        ).pack(side="left", padx=5)
        ttk.Button(
            frame_controls,
            text="Create Reel Preview",
            command=self.render_video_preview,
        ).pack(side="left", padx=5)
        ttk.Button(
            frame_controls,
            text="Save Timeline",
            command=self.save_updated_config,
        ).pack(side="left", padx=5)
        ttk.Button(
            frame_controls,
            text="Exit",
            command=self.root.quit,
        ).pack(side="left", padx=5)

    def preview_frame(self):
        self.frame_preview = ttk.LabelFrame(
            self.root,
            text="Video Preview",
            padding=self.PADDING_10,
        )
        self.frame_preview.pack(fill="x", padx=self.PADDING_10, pady=self.PADDING_10)

        self.preview_canvas = tk.Canvas(
            self.frame_preview,
            width=self.PREVIEW_WIDTH,
            height=self.PREVIEW_HEIGHT,
            bg="black",
        )
        self.preview_canvas.pack(side="left", padx=10)
        bottom_frame = ttk.Frame(self.frame_preview)
        bottom_frame.pack(side="bottom", fill="x")

        self.preview_time_label = ttk.Label(self.frame_preview, text="00:00 / 00:00")
        self.preview_time_label.pack(side="bottom", pady=(2, 0))
        self.play_pause_button = ttk.Button(
            self.frame_preview, text="Play", command=self.toggle_play_pause
        )
        self.play_pause_button.pack(side="bottom", pady=5)

    def create_timeline_frame(self):
        # Timeline (move this above log_output)
        self.timeline_frame = ttk.LabelFrame(self.root, text="Timeline")
        self.timeline_frame.pack(
            fill="x",
            padx=self.PADDING_10,
            pady=self.PADDING_10,
        )

        self.canvas = tk.Canvas(self.timeline_frame, height=200, bg="#fafafa")
        scrollbar = ttk.Scrollbar(
            self.timeline_frame,
            orient="horizontal",
            command=self.canvas.xview,
        )
        self.canvas.configure(xscrollcommand=scrollbar.set)
        self.canvas.pack(side="top", fill="x")
        scrollbar.pack(side="bottom", fill="x")

    def create_timeline_grid(self):
        # Draw grid
        for second in range(self.GRID_LENGTH_IN_SEC + 1):
            x1 = second * self.pixels_per_second
            self.canvas.create_line(
                x1, 0, x1, self.TIMELINE_BOX_HEIGHT + 40, fill="gray"
            )
            self.canvas.create_text(
                x1,
                self.TIMELINE_BOX_HEIGHT + 40,
                text=str(
                    second,
                ),
                anchor="n",
                font=("Arial", 10),
            )

    def preview_reset(self):
        self.preview_paused = True
        self.user_seeking = False
        self.frames = []
        self.frame_timestamps = []
        self.current_frame_index = 0

    def _round_timestamp_with_pixels(self, value):
        return round(value / self.pixels_per_second, 1)

    def move_selected_left(self, event):
        self.move_selected_box(-self.MOVE_PIXEL)

    def move_selected_right(self, event):
        self.move_selected_box(self.MOVE_PIXEL)

    def select_media_dir(self):
        path = filedialog.askdirectory(title="Select Media Directory")
        if path:
            self.media_dir.set(path)

    def move_all_components(self, box_id, dx, data):
        # Move all components
        self.canvas.move(box_id, dx, 0)
        self.canvas.move(data["text"], dx, 0)
        self.canvas.move(data["left"], dx, 0)
        self.canvas.move(data["right"], dx, 0)

    def update_text(self, box_id):
        data = self.timeline_data[box_id]
        text = (
            f"{data['filename']}\nOn Timeline:\n{data[self.TIMELINE_START_STR]}-{data[self.TIMELINE_END_STR]}s"
            f"\nVideo Time:\n{data['info'].start}-{data['info'].end}s"
        )
        self.canvas.itemconfig(data["text"], text=text)

    def move_selected_box(self, dx):
        if self.selected_box_id is None:
            return

        data = self.timeline_data[self.selected_box_id]
        self.move_all_components(self.selected_box_id, dx, data)

        # Update timing
        x1 = self.canvas.coords(self.selected_box_id)[0]  # only x coord
        new_start = round(x1 / self.pixels_per_second, 1)
        duration = data[self.TIMELINE_END_STR] - data[self.TIMELINE_START_STR]
        data[self.TIMELINE_START_STR] = new_start
        data[self.TIMELINE_END_STR] = round(new_start + duration, 1)
        self.update_text(self.selected_box_id)

    def is_overlapping(self, box_id, proposed_start, proposed_end):
        for other_id, data in self.timeline_data.items():
            if other_id == box_id:
                continue
            other_start = data[self.TIMELINE_START_STR]
            other_end = data[self.TIMELINE_END_STR]
            if not (proposed_end <= other_start or proposed_start >= other_end):
                return True
        return False

    def save_updated_config(self):
        if len(self.timeline_data) == 0:
            messagebox.showerror(
                "Error",
                "Please select both config file first.",
            )
            return

        updated = {}
        for box_id, data in self.timeline_data.items():
            info = data["info"]
            updated[data["filename"]] = info

        out_path = filedialog.asksaveasfilename(defaultextension=".json")
        if out_path:
            media_clips_to_json(updated, out_path)
            messagebox.showinfo(
                "Saved",
                f"Updated config saved to:\n{out_path}",
            )
        self.config_path.set(out_path)

    def make_resizable(self, left_handle, right_handle, box_id):
        def resize_left(event):
            x1, y1, x2, y2 = self.canvas.coords(box_id)
            dx = event.x - x1
            dx = round(dx / 10) * 10

            if x2 - (x1 + dx) > self.MIN_TIMELINE_ELEMENT_WIDTH:
                # Update start time
                new_start = self._round_timestamp_with_pixels(x1 + dx)
                if self.is_overlapping(
                    box_id,
                    new_start,
                    self.timeline_data[box_id][self.TIMELINE_END_STR],
                ):
                    return
                self.canvas.coords(box_id, x1 + dx, y1, x2, y2)
                self.canvas.move(self.timeline_data[box_id]["text"], dx, 0)
                self.canvas.coords(
                    left_handle,
                    x1 + dx - self.PADDING_10,
                    y1,
                    x1 + dx + 2,
                    y2,
                )

                diff = new_start - self.timeline_data[box_id][self.TIMELINE_START_STR]
                self.timeline_data[box_id]["info"].start = round(
                    self.timeline_data[box_id]["info"].start + diff, 1
                )
                self.timeline_data[box_id][self.TIMELINE_START_STR] = new_start
                self.update_text(box_id)

        def resize_right(event):
            x1, y1, x2, y2 = self.canvas.coords(box_id)
            dx = event.x - x2
            dx = round(dx / 10) * 10

            if (x2 + dx) - x1 > self.MIN_TIMELINE_ELEMENT_WIDTH:
                # Update end time
                new_end = round((x2 + dx) / self.pixels_per_second, 1)
                if self.is_overlapping(
                    box_id,
                    self.timeline_data[box_id][self.TIMELINE_START_STR],
                    new_end,
                ):
                    return
                self.canvas.coords(box_id, x1, y1, x2 + dx, y2)
                self.canvas.coords(
                    right_handle,
                    x2 + dx - 2,
                    y1,
                    x2 + dx + self.PADDING_10,
                    y2,
                )

                diff = new_end - self.timeline_data[box_id][self.TIMELINE_END_STR]
                self.timeline_data[box_id]["info"].end = round(
                    self.timeline_data[box_id]["info"].end + diff, 1
                )
                self.timeline_data[box_id][self.TIMELINE_END_STR] = new_end
                self.update_text(box_id)

        self.canvas.tag_bind(left_handle, "<B1-Motion>", resize_left)
        self.canvas.tag_bind(right_handle, "<B1-Motion>", resize_right)

    def make_draggable(self, item_id):
        def on_start(event):
            self.drag_data = {
                "item": item_id,
                "x": event.x_root,
            }
            self.selected_box_id = item_id  # Track selected item

            # Reset outline for all boxes
            for box_id in self.timeline_data:
                self.canvas.itemconfig(box_id, outline="#333")
            self.canvas.itemconfig(item_id, outline="red")

            # Raise all components of the selected item
            data = self.timeline_data[item_id]
            self.canvas.tag_raise(data["left"])
            self.canvas.tag_raise(data["right"])
            self.canvas.tag_raise(item_id)
            self.canvas.tag_raise(data["text"])  # Make sure text is on toplevel

        def on_drag(event):
            dx = event.x_root - self.drag_data["x"]
            self.drag_data["x"] = event.x_root

            dx = round(dx / 10) * 10
            if dx == 0:
                return

            box_id = self.drag_data["item"]
            data = self.timeline_data[box_id]
            x1, y1, x2, y2 = self.canvas.coords(box_id)
            new_x1 = x1 + dx
            new_x2 = x2 + dx

            new_start = round(new_x1 / self.pixels_per_second, 1)
            new_end = round(new_x2 / self.pixels_per_second, 1)

            if self.is_overlapping(box_id, new_start, new_end):
                return  # block move if it overlaps

            self.move_all_components(box_id, dx, data)
            data[self.TIMELINE_START_STR] = new_start
            data[self.TIMELINE_END_STR] = new_end
            self.update_text(box_id)

        self.canvas.tag_bind(item_id, "<ButtonPress-1>", on_start)
        self.canvas.tag_bind(item_id, "<B1-Motion>", on_drag)
        self.canvas.tag_bind(
            item_id,
            "<Enter>",
            lambda e: self.canvas.config(cursor="fleur"),
        )
        self.canvas.tag_bind(
            item_id,
            "<Leave>",
            lambda e: self.canvas.config(cursor=""),
        )

    def draw_timeline(self):
        config_path = self.config_path.get()

        if not config_path or not os.path.exists(config_path):
            messagebox.showerror(
                "Error",
                "Please select a valid config JSON file.",
            )
            return

        try:
            config_data = pars_config(config_path)
            self.canvas.delete("all")
            self.timeline_data = {}
            x = self.ZERO_OFFSET  # start offset
            y = 20

            start = self.ZERO_OFFSET
            end = self.ZERO_OFFSET
            for filename, info in config_data.items():
                # we need to show grid with 1 second resolution and duration which part of given file is takes
                start += info.start
                end += info.end
                duration = end - start
                width = duration * self.pixels_per_second
                color = (
                    "#91c9f7" if info.type == VisionDataTypeEnum.VIDEO else "#f9d58c"
                )

                # Main box
                rect = self.canvas.create_rectangle(
                    x,
                    y,
                    x + width,
                    y + self.TIMELINE_BOX_HEIGHT,
                    fill=color,
                    outline="#333",
                )
                text = self.canvas.create_text(
                    x + 10,
                    y + 55,
                    anchor="w",
                    font=("Arial", 8),
                )

                # Resize handles (left + right edges)
                left_handle = self.canvas.create_rectangle(
                    x - self.PADDING_10,
                    y,
                    x + 2,
                    y + self.TIMELINE_BOX_HEIGHT,
                    fill="#666",
                )
                right_handle = self.canvas.create_rectangle(
                    x + width - 2,
                    y,
                    x + width + self.PADDING_10,
                    y + self.TIMELINE_BOX_HEIGHT,
                    fill="#666",
                )

                # TODO:
                # create data structure that has field "preview render ready"
                self.timeline_data[rect] = {
                    "filename": filename,
                    self.TIMELINE_START_STR: start,
                    self.TIMELINE_END_STR: end,
                    "text": text,
                    "left": left_handle,
                    "right": right_handle,
                    "info": info,
                }
                self.update_text(rect)

                self.create_timeline_grid()

                self.make_draggable(rect)
                self.make_resizable(left_handle, right_handle, rect)

                x += width
                start = end
            self.canvas.config(scrollregion=self.canvas.bbox("all"))

        except Exception as e:
            self.config_path.set("")
            messagebox.showerror(
                "Timeline Error",
                f"Failed to load timeline: {e}",
            )

    def select_config_file(self):
        path = filedialog.askopenfilename(
            title="Select Config JSON",
            filetypes=[
                ("JSON files", "*.json"),
            ],
        )
        if path:
            self.config_path.set(path)
            self.draw_timeline()

    def render_video_preview(self):
        self.preview_reset()
        self.run_main_script(True)

    def play_video_on_canvas(self, video_path_dir="preview"):
        # TODO:
        # 1. run on the separated thread
        # 2. On slider move stop video
        # 3. On slider not touch start
        # 4. Don't render files that don't need rerender
        # 5. Add option to detach window with preview

        # Load all frames and timestamps
        # Skip loading if already loaded
        if len(self.frames) == 0:
            # Gather and sort all video files
            video_files = sorted(
                [
                    os.path.join(video_path_dir, f)
                    for f in os.listdir(video_path_dir)
                    if f.lower().endswith((".mp4", ".avi", ".mov"))
                ]
            )

            if not video_files:
                print("No video files found.")
                return
            self.current_frame_index = 0

            for video_path in video_files:
                cap = cv2.VideoCapture(video_path)
                frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

                for i in range(frame_count):
                    ret, frame = cap.read()
                    if not ret:
                        break
                    resized = cv2.resize(
                        frame, (self.PREVIEW_WIDTH, self.PREVIEW_HEIGHT)
                    )
                    self.frames.append(resized)
                    self.frame_timestamps.append(len(self.frames) / self.PREVIEW_FPS)

                cap.release()

        if not hasattr(self, "preview_seek"):
            self.preview_seek = ttk.Scale(
                self.frame_preview,
                from_=0,
                to=len(self.frames) - 1,
                orient="horizontal",
                command=self.seek_frame,
            )
            self.preview_seek.pack(side="bottom", fill="x", padx=10)

        # Start playback
        self.playback_loop()

    def render_one_frame(self):
        frame = self.frames[self.current_frame_index]
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        img = ImageTk.PhotoImage(Image.fromarray(rgb))
        self.preview_canvas.create_image(0, 0, anchor="nw", image=img)
        self.preview_canvas.image = img  # prevent GC

    def playback_loop(self):
        if len(self.frames) == 0 or self.preview_paused:
            return

        if self.current_frame_index >= len(self.frames):
            return  # End of video

        self.preview_seek.set(self.current_frame_index)
        self.update_time_label()
        self.current_frame_index += 1

        self.root.after(int(1000 / self.PREVIEW_FPS), self.playback_loop)

    def update_time_label(self):
        current_sec = self.current_frame_index / self.PREVIEW_FPS
        total_sec = len(self.frames) / self.PREVIEW_FPS
        self.preview_time_label.config(
            text=f"{format_time(current_sec)} / {format_time(total_sec)}"
        )

    def toggle_play_pause(self):
        self.preview_paused = not self.preview_paused
        self.play_pause_button.config(text="Play" if self.preview_paused else "Pause")
        if not self.preview_paused:
            self.play_video_on_canvas()

    def seek_frame(self, val):
        self.current_frame_index = int(float(val))
        self.update_time_label()
        self.render_one_frame()

    def run_main_script(self, preview: bool = False):
        if not self.config_path.get() or not self.media_dir.get():
            messagebox.showerror(
                "Error",
                "Please select both config file and media folder.",
            )
            return

        self.log_output.delete("1.0", tk.END)
        self.append_log("Starting reel creation...")
        threading.Thread(
            target=self.execute_script, args=(preview,), daemon=True
        ).start()

    def execute_script(self, preview):
        try:
            # Setup stdout/stderr redirection
            stdout_redirector = TextRedirector(self.log_output)
            stderr_redirector = TextRedirector(self.log_output)

            # Setup logging redirection
            text_handler = TextWidgetHandler(self.log_output)
            text_handler.setLevel(logging.INFO)
            formatter = logging.Formatter(
                "%(asctime)s - %(levelname)s - %(message)s",
            )
            text_handler.setFormatter(formatter)

            # Target the logger used in create_instagram_reel
            # use the exact name used in create_instagram_reel
            logger = logging.getLogger("main")
            logger.addHandler(text_handler)
            logger.setLevel(logging.INFO)
            logger.propagate = False  # Optional: Avoid double logs from parent handlers

            with redirect_stdout(stdout_redirector), redirect_stderr(stderr_redirector):
                json_file = pars_config(self.config_path.get())
                create_instagram_reel(
                    json_file, self.media_dir.get(), "test_output.mp4", preview
                )

            self.append_log("✅ Reel creation finished.\n")

            logger.removeHandler(text_handler)  # cleanup handler
        except Exception as e:
            self.append_log(f"❌ Error: {e}\n")

    def append_log(self, text):
        self.log_output.insert(tk.END, text)
        self.log_output.see(tk.END)


if __name__ == "__main__":
    root = ThemedTk(themename="journal")  # 'cosmo', 'journal', 'superhero'

    app = InstagramReelCreatorGUI(root)
    root.mainloop()
