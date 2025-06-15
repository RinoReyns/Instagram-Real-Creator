from __future__ import annotations

import io
import logging
import tkinter as tk


class TextRedirector(io.TextIOBase):
    def __init__(self, text_widget):
        self.text_widget = text_widget
        self.last_line = ""

    def write(self, s):
        if "\r" in s:
            self.last_line = s.strip()
            self._overwrite_last_line(self.last_line)
        else:
            self.text_widget.insert(tk.END, s)
            self.text_widget.see(tk.END)
            self.text_widget.update_idletasks()

    def _overwrite_last_line(self, text):
        self.text_widget.delete("end-2l", "end-1l")
        self.text_widget.insert(tk.END, text + "\n")
        self.text_widget.see(tk.END)
        self.text_widget.update_idletasks()

    def flush(self):
        pass


class TextWidgetHandler(logging.Handler):
    def __init__(self, text_widget):
        super().__init__()
        self.text_widget = text_widget

    def emit(self, record):
        msg = self.format(record)
        self.text_widget.insert(tk.END, msg + "\n")
        self.text_widget.see(tk.END)
        self.text_widget.update_idletasks()
