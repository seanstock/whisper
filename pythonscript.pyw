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

# --- Config ---
SAMPLE_RATE = 16000
CHANNELS = 1
DTYPE = 'int16'
# Using the medium English-only model for better performance in English.
# Change to "medium" for multilingual support.
MODEL_SIZE = "medium.en"

# Get the directory where the script is located
script_dir = os.path.dirname(os.path.abspath(__file__))
output_audio_path = os.path.join(script_dir, "recorded.wav")
output_txt_path = os.path.join(script_dir, "output.txt") # AHK script will read this

class WhisperApp:
    # --- Style Config ---
    BG_COLOR = "#2E2E2E"
    TEXT_COLOR = "#EAEAEA"
    BUTTON_COLOR = "#4A4A4A"
    ACCENT_COLOR = "#1E90FF"
    RECORD_COLOR = "#C70039"
    
    FONT_NAME = "Segoe UI"
    FONT_NORMAL = (FONT_NAME, 10)
    FONT_BOLD = (FONT_NAME, 11, "bold")
    
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
        
        # --- Theming ---
        self.style = ttk.Style(self.root)
        self.style.theme_use('clam')
        self.style.configure("TFrame", background=self.BG_COLOR)
        self.style.configure("TButton", 
            background=self.BUTTON_COLOR, 
            foreground=self.TEXT_COLOR, 
            font=self.FONT_NORMAL,
            borderwidth=0,
            focusthickness=3,
            focuscolor='none')
        self.style.map("TButton",
            background=[('active', self.ACCENT_COLOR)],
            foreground=[('active', self.TEXT_COLOR)])
        
        self.style.configure("Status.TLabel", 
            background=self.BG_COLOR, 
            foreground=self.TEXT_COLOR,
            font=(self.FONT_NAME, 9))
            
        self.style.configure("Record.TButton",
            font=self.FONT_BOLD,
            background=self.ACCENT_COLOR)

        self.is_recording = False
        self.recording_data = []
        self.stream = None

        main_frame = ttk.Frame(root, padding="10 10 10 10")
        main_frame.pack(fill=tk.BOTH, expand=True)

        self.status_label = ttk.Label(main_frame, text="Ready", style="Status.TLabel", anchor="center")
        self.status_label.pack(pady=5, fill=tk.X)

        self.record_button = ttk.Button(main_frame, text="Record", style="Record.TButton", command=self.toggle_recording)
        self.record_button.pack(pady=10, ipady=5)

        # Configure text box style
        self.transcription_box = scrolledtext.ScrolledText(main_frame, 
            width=60, height=10, wrap=tk.WORD, 
            bg=self.BUTTON_COLOR, fg=self.TEXT_COLOR,
            font=self.FONT_NORMAL, relief=tk.FLAT,
            insertbackground=self.TEXT_COLOR)
        self.transcription_box.pack(pady=10, padx=5, fill=tk.BOTH, expand=True)

        # --- Bottom frame for checkbox and send button ---
        bottom_frame = ttk.Frame(main_frame)
        bottom_frame.pack(fill=tk.X, pady=5)

        self.keep_open_var = tk.BooleanVar(value=True)
        self.keep_open_check = ttk.Checkbutton(bottom_frame, text="Keep window open after sending", variable=self.keep_open_var)
        self.keep_open_check.pack(side=tk.LEFT, padx=5)

        self.send_button = ttk.Button(bottom_frame, text="Send to Active Window", command=self.send_text_and_update_state)
        self.send_button.pack(side=tk.RIGHT, padx=5)

        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.set_status(f"Ready (Using {self.device})", "ready")
        
        # Load model at startup to avoid delay after first recording
        self.model = None
        threading.Thread(target=self.load_model_async, daemon=True).start()

    def set_status(self, text, status_key):
        color = self.STATUS_COLORS.get(status_key, self.TEXT_COLOR)
        self.status_label.config(text=text, foreground=color)

    def load_model_async(self):
        self.set_status("Loading model...", "loading")
        self.model = whisper.load_model(MODEL_SIZE, device=self.device)
        self.set_status(f"Ready (Using {self.device})", "ready")

    def toggle_recording(self):
        if self.is_recording:
            # --- Stop Recording ---
            self.is_recording = False
            self.style.configure("Record.TButton", background=self.ACCENT_COLOR)
            self.record_button.config(text="Record")
            self.set_status("Recording stopped.", "ready")
            
            if self.stream:
                self.stream.stop()
                self.stream.close()
            
            if not self.recording_data:
                self.set_status("No audio recorded.", "error")
                return

            self.set_status("Transcribing... (this may take a moment)", "transcribing")
            self.root.update() # Force GUI update
            threading.Thread(target=self.transcribe_audio, daemon=True).start()

        else:
            # --- Start Recording ---
            if self.model is None:
                self.set_status("Model not loaded yet, please wait.", "error")
                return

            self.is_recording = True
            self.recording_data = []
            self.style.configure("Record.TButton", background=self.RECORD_COLOR)
            self.record_button.config(text="Stop")
            self.set_status("🎤 Recording...", "recording")
            
            self.stream = sd.InputStream(samplerate=SAMPLE_RATE, channels=CHANNELS, dtype=DTYPE, callback=self.audio_callback)
            self.stream.start()

    def audio_callback(self, indata, frames, time, status):
        if self.is_recording:
            self.recording_data.append(indata.copy())

    def transcribe_audio(self):
        recording_np = np.concatenate(self.recording_data, axis=0)
        write(output_audio_path, SAMPLE_RATE, recording_np)

        result = self.model.transcribe(output_audio_path, fp16=torch.cuda.is_available())
        transcribed_text = result["text"].strip()

        # Schedule GUI update on the main thread
        self.root.after(0, self.update_transcription_box, transcribed_text)

    def update_transcription_box(self, text):
        self.transcription_box.delete('1.0', tk.END)
        self.transcription_box.insert(tk.END, text)
        self.set_status("Transcription complete.", "complete")

    def reset_ui_for_next_recording(self):
        self.transcription_box.delete('1.0', tk.END)
        self.set_status(f"Ready (Using {self.device})", "ready")
        self.record_button.config(state=tk.NORMAL)

    def send_text_and_update_state(self):
        final_text = self.transcription_box.get("1.0", tk.END).strip()
        with open(output_txt_path, "w", encoding="utf-8") as f:
            f.write(final_text)

        if self.keep_open_var.get():
            # If the user wants to keep the window open, just reset the UI.
            # The AHK script will see the file and send the text.
            self.reset_ui_for_next_recording()
        else:
            # Otherwise, close the application, which also signals the AHK script.
            self.root.destroy()

if __name__ == "__main__":
    root = tk.Tk()
    app = WhisperApp(root)
    root.mainloop() 