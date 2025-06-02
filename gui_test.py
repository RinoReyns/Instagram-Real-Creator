import tkinter as tk
from tkinter import filedialog, messagebox
from tkinter import scrolledtext
from tkinter import ttk
import subprocess
import threading
from utils.json_handler import pars_config
import os
from main import create_instagram_reel, arg_paser


# Optional: Better theming
try:
    import ttkbootstrap as ttkb
    ThemedTk = ttkb.Window
except ImportError:
    ThemedTk = tk.Tk

class InstagramReelCreatorGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Instagram Reel Creator")
        self.root.geometry("700x500")

        self.config_path = tk.StringVar()
        self.media_dir = tk.StringVar()
        self.convert_cfr = tk.BooleanVar(value=True)

        self.build_ui()

    def build_ui(self):
        # CONFIG selection
        frame_top = ttk.LabelFrame(self.root, text="Configuration", padding=10)
        frame_top.pack(fill='x', padx=10, pady=10)

        ttk.Label(frame_top, text="Config file:").grid(row=0, column=0, sticky='w')
        ttk.Entry(frame_top, textvariable=self.config_path, width=60).grid(row=0, column=1, padx=5)
        ttk.Button(frame_top, text="Browse", command=self.select_config_file).grid(row=0, column=2)

        ttk.Label(frame_top, text="Media folder:").grid(row=1, column=0, sticky='w')
        ttk.Entry(frame_top, textvariable=self.media_dir, width=60).grid(row=1, column=1, padx=5)
        ttk.Button(frame_top, text="Browse", command=self.select_media_dir).grid(row=1, column=2)

        # Options
        frame_opts = ttk.LabelFrame(self.root, text="Options", padding=10)
        frame_opts.pack(fill='x', padx=10, pady=5)

        ttk.Checkbutton(frame_opts, text="Convert to 30 FPS CFR (if needed)", variable=self.convert_cfr).pack(anchor='w')

        # Controls
        frame_controls = ttk.Frame(self.root)
        frame_controls.pack(fill='x', padx=10, pady=5)

        ttk.Button(frame_controls, text="Create Reel", command=self.run_main_script).pack(side='left', padx=5)
        ttk.Button(frame_controls, text="Exit", command=self.root.quit).pack(side='right', padx=5)

        # Timeline (move this above log_output)
        self.timeline_frame = ttk.LabelFrame(self.root, text="Timeline")
        self.timeline_frame.pack(fill="x", padx=10, pady=10)

        self.canvas = tk.Canvas(self.timeline_frame, height=80, bg="#fafafa")
        self.scrollbar = ttk.Scrollbar(self.timeline_frame, orient="horizontal", command=self.canvas.xview)
        self.canvas.configure(xscrollcommand=self.scrollbar.set)

        self.canvas.pack(side="top", fill="x")
        self.scrollbar.pack(side="bottom", fill="x")

        # Output log (now below timeline)
        ttk.Label(self.root, text="Log Output:").pack(anchor='w', padx=10)
        self.log_output = scrolledtext.ScrolledText(self.root, height=15)
        self.log_output.pack(fill='both', expand=True, padx=10, pady=5)

    def draw_timeline(self):
        config_path = self.config_path.get()

        if not config_path or not os.path.exists(config_path):
            messagebox.showerror("Error", "Please select a valid config JSON file.")
            return

        try:
            config_data = pars_config(config_path)
            self.canvas.delete("all")

            x = 10  # start offset
            y = 20
            height = 40
            pixels_per_second = 30
            start = 0
            end = 0
            for filename, info in config_data.items():
                start += info.get("start", 0)
                end += info.get("end", 10)
                duration = end - start

                width = duration * pixels_per_second
                color = "#91c9f7" if info["type"] == "video" else "#f9d58c"

                self.canvas.create_rectangle(x, y, x + width, y + height, fill=color, outline="#333")
                self.canvas.create_text(x + 5, y + 20, anchor="w", text=f"{filename}\n{start}-{end}s",
                                        font=("Arial", 8))

                x += width + 10
                start = end
            self.canvas.config(scrollregion=self.canvas.bbox("all"))

        except Exception as e:
            messagebox.showerror("Timeline Error", f"Failed to load timeline: {e}")

    def select_config_file(self):
        path = filedialog.askopenfilename(title="Select Config JSON", filetypes=[("JSON files", "*.json")])
        if path:
            self.config_path.set(path)
            self.draw_timeline()

    def select_media_dir(self):
        path = filedialog.askdirectory(title="Select Media Directory")
        if path:
            self.media_dir.set(path)

    def run_main_script(self):
        if not self.config_path.get() or not self.media_dir.get():
            messagebox.showerror("Error", "Please select both config file and media folder.")
            return

       # self.draw_timeline(pars_config(self.config_path.get()))
        self.log_output.delete('1.0', tk.END)
        self.append_log("Starting reel creation...")

        threading.Thread(target=self.execute_script, daemon=True).start()

    def execute_script(self):
        try:

            json_file = pars_config(self.config_path.get())
            create_instagram_reel(json_file, self.media_dir.get(), 'test_output.mp4')

            self.append_log("✅ Reel creation finished.")
        except Exception as e:
            self.append_log(f"❌ Error: {e}")

    def append_log(self, text):
        self.log_output.insert(tk.END, text)
        self.log_output.see(tk.END)


if __name__ == "__main__":
    root = ThemedTk(themename="journal")  # 'cosmo', 'journal', etc., if using ttkbootstrap
    app = InstagramReelCreatorGUI(root)
    root.mainloop()