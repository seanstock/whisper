# Suppress console windows spawned by ffmpeg (called internally by whisper)
import subprocess as _subprocess
import os as _os
if _os.name == 'nt':
    _orig_popen_init = _subprocess.Popen.__init__
    def _popen_no_window(self, *args, **kwargs):
        kwargs.setdefault('creationflags', 0)
        kwargs['creationflags'] |= 0x08000000  # CREATE_NO_WINDOW
        _orig_popen_init(self, *args, **kwargs)
    _subprocess.Popen.__init__ = _popen_no_window

import tkinter as tk
from tkinter import scrolledtext, ttk, font
import sounddevice as sd
from scipy.io.wavfile import write
import whisper
import threading
import numpy as np
import os
import sys
import torch
import time

# --- Config ---
SAMPLE_RATE = 16000
CHANNELS = 1
DTYPE = 'int16'
MODEL_SIZE = "medium.en"

script_dir = os.path.dirname(os.path.abspath(__file__))
output_audio_path = os.path.join(script_dir, "recorded.wav")
output_txt_path = os.path.join(script_dir, "output.txt")
start_flag_path = os.path.join(script_dir, "start.flag")
stop_flag_path = os.path.join(script_dir, "stop.flag")
show_gui_flag_path = os.path.join(script_dir, "show.flag")

class WhisperApp:
    BG_COLOR = "#2E2E2E"
    TEXT_COLOR = "#EAEAEA"
    BUTTON_COLOR = "#4A4A4A"
    ACCENT_COLOR = "#1E90FF"
    RECORD_COLOR = "#C70039"
    FONT_NAME = "Segoe UI"
    
    STATUS_COLORS = {
        "ready": "#28A745",
        "loading": "#FFC107",
        "recording": RECORD_COLOR,
        "transcribing": "#17A2B8",
        "complete": "#28A745",
        "error": "#DC3545"
    }

    def __init__(self, root):
        self.root = root
        self.root.title("Whisper Transcription")
        self.root.configure(bg=self.BG_COLOR)
        self.root.protocol("WM_DELETE_WINDOW", self.hide_window) # Hide instead of close
        
        self.setup_styles()
        self.is_recording = False
        self.recording_data = []
        self.stream = None
        self.model = None

        # --- UI Layout ---
        main_frame = ttk.Frame(root, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)

        self.status_label = ttk.Label(main_frame, text="Loading Whisper...", style="Status.TLabel", anchor="center")
        self.status_label.pack(pady=5, fill=tk.X)

        self.record_button = ttk.Button(main_frame, text="Record", style="Record.TButton", command=self.toggle_recording)
        self.record_button.pack(pady=10, ipady=5)

        self.transcription_box = scrolledtext.ScrolledText(main_frame, width=60, height=10, wrap=tk.WORD, bg=self.BUTTON_COLOR, fg=self.TEXT_COLOR, font=(self.FONT_NAME, 10), relief=tk.FLAT, insertbackground=self.TEXT_COLOR)
        self.transcription_box.pack(pady=10, padx=5, fill=tk.BOTH, expand=True)

        bottom_frame = ttk.Frame(main_frame)
        bottom_frame.pack(fill=tk.X, pady=5)

        self.keep_open_var = tk.BooleanVar(value=True)
        self.keep_open_check = ttk.Checkbutton(bottom_frame, text="Keep window open", variable=self.keep_open_var)
        self.keep_open_check.pack(side=tk.LEFT, padx=5)

        self.send_button = ttk.Button(bottom_frame, text="Send to Window", command=self.send_text_and_update_state)
        self.send_button.pack(side=tk.RIGHT, padx=5)

        self.copy_button = ttk.Button(bottom_frame, text="Copy", command=self.copy_to_clipboard)
        self.copy_button.pack(side=tk.RIGHT, padx=5)

        # Startup logic
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        threading.Thread(target=self.load_model_async, daemon=True).start()
        threading.Thread(target=self.flag_listener, daemon=True).start()
        self.make_right_click_menu()

    def setup_styles(self):
        self.style = ttk.Style(self.root)
        self.style.theme_use('clam')
        self.style.configure("TFrame", background=self.BG_COLOR)
        self.style.configure("TButton", background=self.BUTTON_COLOR, foreground=self.TEXT_COLOR, borderwidth=0)
        self.style.map("TButton", background=[('active', self.ACCENT_COLOR)])
        self.style.configure("Status.TLabel", background=self.BG_COLOR, foreground=self.TEXT_COLOR)
        self.style.configure("Record.TButton", font=(self.FONT_NAME, 11, "bold"), background=self.ACCENT_COLOR)

    def load_model_async(self):
        try:
            self.model = whisper.load_model(MODEL_SIZE, device=self.device)
            self.root.after(0, lambda: self.set_status(f"Ready ({self.device})", "ready"))
        except Exception as e:
            self.root.after(0, lambda: self.set_status(f"Error: {e}", "error"))

    def flag_listener(self):
        """Instant signal listener for AHK."""
        while True:
            if os.path.exists(start_flag_path):
                os.remove(start_flag_path)
                self.root.after(0, self.start_recording)
            
            if os.path.exists(stop_flag_path):
                os.remove(stop_flag_path)
                self.root.after(0, self.stop_recording)

            if os.path.exists(show_gui_flag_path):
                os.remove(show_gui_flag_path)
                self.root.after(0, self.show_window)
                
            time.sleep(0.02) # Fast polling

    def start_recording(self):
        if self.is_recording or self.model is None: return
        self.is_recording = True
        self.recording_data = []
        self.style.configure("Record.TButton", background=self.RECORD_COLOR)
        self.record_button.config(text="Stop")
        self.set_status("🎤 Recording...", "recording")
        self.stream = sd.InputStream(samplerate=SAMPLE_RATE, channels=CHANNELS, dtype=DTYPE, callback=self.audio_callback)
        self.stream.start()

    def stop_recording(self):
        if not self.is_recording: return
        self.is_recording = False
        self.style.configure("Record.TButton", background=self.ACCENT_COLOR)
        self.record_button.config(text="Record")
        if self.stream:
            self.stream.stop()
            self.stream.close()
        
        if self.recording_data:
            self.set_status("Transcribing...", "transcribing")
            threading.Thread(target=self.transcribe_audio, daemon=True).start()
        else:
            self.set_status("Ready", "ready")

    def toggle_recording(self):
        if self.is_recording: self.stop_recording()
        else: self.start_recording()

    def audio_callback(self, indata, frames, time, status):
        if self.is_recording: self.recording_data.append(indata.copy())

    def transcribe_audio(self):
        try:
            recording_np = np.concatenate(self.recording_data, axis=0)
            write(output_audio_path, SAMPLE_RATE, recording_np)
            result = self.model.transcribe(output_audio_path, fp16=torch.cuda.is_available())
            text = result["text"].strip()
            self.root.after(0, self.update_ui_with_text, text)
        except Exception as e:
            self.root.after(0, lambda: self.set_status(f"Failed: {e}", "error"))

    def update_ui_with_text(self, text):
        self.transcription_box.delete('1.0', tk.END)
        self.transcription_box.insert(tk.END, text)
        self.set_status("Transcription complete.", "complete")
        # Automatically write to output file so AHK can see it
        with open(output_txt_path, "w", encoding="utf-8") as f:
            f.write(text)

    def set_status(self, text, status_key):
        color = self.STATUS_COLORS.get(status_key, self.TEXT_COLOR)
        self.status_label.config(text=text, foreground=color)

    def hide_window(self):
        self.root.withdraw()

    def show_window(self):
        self.root.deiconify()
        self.root.attributes("-topmost", True)
        self.root.attributes("-topmost", False)

    def send_text_and_update_state(self):
        # The transcription is already in the file from update_ui_with_text
        if not self.keep_open_var.get():
            self.hide_window()

    def copy_to_clipboard(self):
        self.root.clipboard_clear()
        self.root.clipboard_append(self.transcription_box.get("1.0", tk.END).strip())

    def make_right_click_menu(self):
        self.right_click_menu = tk.Menu(self.root, tearoff=0)
        self.right_click_menu.add_command(label="Copy", command=self.copy_to_clipboard)
        self.transcription_box.bind("<Button-3>", lambda e: self.right_click_menu.tk_popup(e.x_root, e.y_root))

if __name__ == "__main__":
    root = tk.Tk()
    app = WhisperApp(root)
    # Start hidden if launched with --bg
    if "--bg" in sys.argv:
        root.withdraw()
    root.mainloop()
