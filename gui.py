from __future__ import annotations

import logging
import os
import threading
import tkinter as tk
from contextlib import redirect_stderr, redirect_stdout
from tkinter import filedialog, messagebox, scrolledtext, ttk

import ttkbootstrap as ttkb

from components.gui_components.text_handler import TextRedirector, TextWidgetHandler
from main import create_instagram_reel
from utils.data_structures import VisionDataTypeEnum
from utils.json_handler import media_clips_to_json, pars_config

# Optional: Better theming
ThemedTk = ttkb.Window


class InstagramReelCreatorGUI:
    MOVE_PIXEL = 5
    INITIAL_HEIGHT = 1000
    INITIAL_WIDTH = 1600
    PADDING_10 = 10
    MIN_TIMELINE_ELEMENT_WIDTH = 20
    TIMELINE_START_STR = "start"
    TIMELINE_END_STR = "end"
    TIMELINE_BOX_HEIGHT = 120
    GRID_LENGTH_IN_SEC = 90

    def __init__(self, root):
        self.root = root
        self.root.title("Instagram Reel Creator")
        self.root.geometry(f"{self.INITIAL_WIDTH}x{self.INITIAL_HEIGHT}")

        self.config_path = tk.StringVar()
        self.media_dir = tk.StringVar()
        self.convert_cfr = tk.BooleanVar(value=True)
        self.selected_box_id = None
        self.pixels_per_second = 50
        self.timeline_data = {}
        self.build_ui()

    def build_ui(self):
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
            text="Save Timeline",
            command=self.save_updated_config,
        ).pack(side="left", padx=5)
        ttk.Button(
            frame_controls,
            text="Exit",
            command=self.root.quit,
        ).pack(side="right", padx=5)

        # Timeline (move this above log_output)
        self.timeline_frame = ttk.LabelFrame(self.root, text="Timeline")
        self.timeline_frame.pack(
            fill="x",
            padx=self.PADDING_10,
            pady=self.PADDING_10,
        )

        self.canvas = tk.Canvas(self.timeline_frame, height=200, bg="#fafafa")
        self.scrollbar = ttk.Scrollbar(
            self.timeline_frame,
            orient="horizontal",
            command=self.canvas.xview,
        )
        self.canvas.configure(xscrollcommand=self.scrollbar.set)

        self.canvas.pack(side="top", fill="x")
        self.scrollbar.pack(side="bottom", fill="x")

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
        x1, _, _, _ = self.canvas.coords(self.selected_box_id)
        new_start = round(x1 / self.pixels_per_second, 1)
        duration = data[self.TIMELINE_END_STR] - data[self.TIMELINE_START_STR]
        # TODO:
        # update also video time
        # if move update only time line position, not video start end
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
            # TODO:
            # update also video time
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
            x = 0  # start offset
            y = 20

            start = 0
            end = 0
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

    def run_main_script(self):
        if not self.config_path.get() or not self.media_dir.get():
            messagebox.showerror(
                "Error",
                "Please select both config file and media folder.",
            )
            return

        self.log_output.delete("1.0", tk.END)
        self.append_log("Starting reel creation...")

        threading.Thread(target=self.execute_script, daemon=True).start()

    def execute_script(self):
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
                    json_file,
                    self.media_dir.get(),
                    "test_output.mp4",
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
