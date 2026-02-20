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

import customtkinter as ctk
import tkinter as tk
import sounddevice as sd
from scipy.io.wavfile import write
import whisper
import threading
import numpy as np
import os
import sys
import torch
import time

import config
import icon_gen

# ── paths ──────────────────────────────────────────────────────────────────────
SCRIPT_DIR      = os.path.dirname(os.path.abspath(__file__))
OUTPUT_AUDIO    = os.path.join(SCRIPT_DIR, "recorded.wav")
OUTPUT_TXT      = os.path.join(SCRIPT_DIR, "output.txt")
START_FLAG      = os.path.join(SCRIPT_DIR, "start.flag")
STOP_FLAG       = os.path.join(SCRIPT_DIR, "stop.flag")
SHOW_FLAG       = os.path.join(SCRIPT_DIR, "show.flag")
MUTE_FLAG       = os.path.join(SCRIPT_DIR, "mute.flag")
HOTKEY_FLAG     = os.path.join(SCRIPT_DIR, "hotkey_change.flag")
MODELS_DIR      = os.path.join(SCRIPT_DIR, "models")

SAMPLE_RATE = 16000
CHANNELS    = 1
DTYPE       = 'int16'

ALL_MODELS = ["tiny.en", "base.en", "small.en", "medium.en", "turbo", "large-v3"]

# ── colours ────────────────────────────────────────────────────────────────────
BG          = "#1a1a1a"
BAR_BG      = "#222222"
PANEL_BG    = "#2a2a2a"
TEXT        = "#e8e8e8"
SUBTEXT     = "#888888"
ACCENT      = "#1E90FF"
RED         = "#C70039"
AMBER       = "#FFA500"
GREEN       = "#28A745"
GRAY        = "#555555"
BTN_BG      = "#333333"
BTN_HOVER   = "#444444"

DOT_COLORS = {
    "loading":      GRAY,
    "ready":        GREEN,
    "recording":    RED,
    "transcribing": AMBER,
    "mic_off":      GRAY,
    "error":        RED,
}


class WhisperWidget(ctk.CTk):
    def __init__(self):
        super().__init__()

        # ── window setup ───────────────────────────────────────────────────────
        self.title("Whisper")
        ctk.set_appearance_mode("dark")
        self.configure(fg_color=BG)
        self.overrideredirect(True)
        self.attributes("-topmost", True)

        # ── icon ───────────────────────────────────────────────────────────────
        icon_path = icon_gen.create_icon()
        self.iconbitmap(icon_path)

        # ── config ─────────────────────────────────────────────────────────────
        self.cfg = config.load()

        # ── state ──────────────────────────────────────────────────────────────
        self.is_recording      = False
        self.recording_data    = []
        self.stream            = None
        self.model             = None
        self.device            = "cuda" if torch.cuda.is_available() else "cpu"
        self._drag_x           = 0
        self._drag_y           = 0
        self._listening_hotkey = False
        self._current_model    = self.cfg["model"]

        # ── apply saved mute state ─────────────────────────────────────────────
        if self.cfg["mute_beeps"]:
            open(MUTE_FLAG, "w").close()
        elif os.path.exists(MUTE_FLAG):
            os.remove(MUTE_FLAG)

        # ── build UI ───────────────────────────────────────────────────────────
        self._build_bar()
        self._build_panel()
        self._apply_expanded(self.cfg["expanded"], animate=False)

        # ── position ───────────────────────────────────────────────────────────
        self.geometry(f"+{self.cfg['window_x']}+{self.cfg['window_y']}")

        # ── background threads ─────────────────────────────────────────────────
        threading.Thread(target=self._load_model, daemon=True).start()
        threading.Thread(target=self._flag_listener, daemon=True).start()

    # ══════════════════════════════════════════════════════════════════════════
    # UI construction
    # ══════════════════════════════════════════════════════════════════════════

    def _build_bar(self):
        self.bar = ctk.CTkFrame(self, fg_color=BAR_BG, corner_radius=8, height=44)
        self.bar.pack(fill="x")
        self.bar.pack_propagate(False)

        self.bar.bind("<ButtonPress-1>",   self._drag_start)
        self.bar.bind("<B1-Motion>",       self._drag_move)
        self.bar.bind("<ButtonRelease-1>", self._drag_end)

        # status dot
        self.dot_canvas = tk.Canvas(self.bar, width=14, height=14,
                                     bg=BAR_BG, highlightthickness=0)
        self.dot_canvas.pack(side="left", padx=(10, 4), pady=15)
        self.dot_id = self.dot_canvas.create_oval(1, 1, 13, 13, fill=GRAY, outline="")

        # status label — also draggable
        self.status_lbl = ctk.CTkLabel(self.bar, text="Loading...", text_color=SUBTEXT,
                                        font=("Segoe UI", 11), anchor="w", width=130)
        self.status_lbl.pack(side="left", padx=(0, 6))
        self.status_lbl.bind("<ButtonPress-1>", self._drag_start)
        self.status_lbl.bind("<B1-Motion>",     self._drag_move)

        # mic toggle
        self.mic_btn = ctk.CTkButton(
            self.bar, text="🎤", width=32, height=28,
            fg_color=ACCENT if self.cfg["mic_enabled"] else BTN_BG,
            hover_color=BTN_HOVER, corner_radius=6,
            command=self._toggle_mic, font=("Segoe UI", 13)
        )
        self.mic_btn.pack(side="left", padx=2)

        # mute toggle
        self.mute_btn = ctk.CTkButton(
            self.bar, text="🔇" if self.cfg["mute_beeps"] else "🔊",
            width=32, height=28,
            fg_color=BTN_BG, hover_color=BTN_HOVER, corner_radius=6,
            command=self._toggle_mute, font=("Segoe UI", 13)
        )
        self.mute_btn.pack(side="left", padx=2)

        # hotkey button
        self.hotkey_btn = ctk.CTkButton(
            self.bar, text=f"⌨ {self.cfg.get('hotkey', '`')}",
            width=54, height=28,
            fg_color=BTN_BG, hover_color=BTN_HOVER, corner_radius=6,
            command=self._start_hotkey_capture, font=("Segoe UI", 11)
        )
        self.hotkey_btn.pack(side="left", padx=2)

        # model dropdown
        self.model_var = ctk.StringVar(value=self.cfg["model"])
        self.model_menu = ctk.CTkOptionMenu(
            self.bar, values=ALL_MODELS, variable=self.model_var,
            width=100, height=28, corner_radius=6,
            fg_color=BTN_BG, button_color=BTN_BG, button_hover_color=BTN_HOVER,
            dropdown_fg_color=PANEL_BG, font=("Segoe UI", 11),
            command=self._on_model_change
        )
        self.model_menu.pack(side="left", padx=2)

        # expand/collapse
        self.expand_btn = ctk.CTkButton(
            self.bar, text="▼" if not self.cfg["expanded"] else "▲",
            width=28, height=28,
            fg_color=BTN_BG, hover_color=BTN_HOVER, corner_radius=6,
            command=self._toggle_expand, font=("Segoe UI", 11)
        )
        self.expand_btn.pack(side="left", padx=2)

        # close
        ctk.CTkButton(
            self.bar, text="✕", width=28, height=28,
            fg_color=BTN_BG, hover_color="#8B0000", corner_radius=6,
            command=self._hide, font=("Segoe UI", 11)
        ).pack(side="left", padx=(2, 8))

    def _build_panel(self):
        self.panel = ctk.CTkFrame(self, fg_color=PANEL_BG, corner_radius=8)

        self.text_box = ctk.CTkTextbox(
            self.panel, width=340, height=140,
            fg_color="#1e1e1e", text_color=TEXT,
            font=("Segoe UI", 11), corner_radius=6, wrap="word"
        )
        self.text_box.pack(padx=8, pady=(8, 4), fill="both", expand=True)

        ctk.CTkButton(
            self.panel, text="Copy", width=60, height=26,
            fg_color=BTN_BG, hover_color=BTN_HOVER, corner_radius=6,
            command=self._copy, font=("Segoe UI", 11)
        ).pack(side="right", padx=8, pady=(0, 8))

    # ══════════════════════════════════════════════════════════════════════════
    # Drag
    # ══════════════════════════════════════════════════════════════════════════

    def _drag_start(self, e):
        self._drag_x = e.x_root - self.winfo_x()
        self._drag_y = e.y_root - self.winfo_y()

    def _drag_move(self, e):
        self.geometry(f"+{e.x_root - self._drag_x}+{e.y_root - self._drag_y}")

    def _drag_end(self, e):
        self.cfg["window_x"] = self.winfo_x()
        self.cfg["window_y"] = self.winfo_y()
        config.save(self.cfg)

    # ══════════════════════════════════════════════════════════════════════════
    # Button handlers
    # ══════════════════════════════════════════════════════════════════════════

    def _toggle_mic(self):
        self.cfg["mic_enabled"] = not self.cfg["mic_enabled"]
        config.save(self.cfg)
        if self.cfg["mic_enabled"]:
            self.mic_btn.configure(fg_color=ACCENT)
            if self.model:
                self._set_status("Ready", "ready")
        else:
            self.mic_btn.configure(fg_color=BTN_BG)
            self._set_status("Mic off", "mic_off")

    def _toggle_mute(self):
        self.cfg["mute_beeps"] = not self.cfg["mute_beeps"]
        config.save(self.cfg)
        if self.cfg["mute_beeps"]:
            open(MUTE_FLAG, "w").close()
            self.mute_btn.configure(text="🔇")
        else:
            if os.path.exists(MUTE_FLAG):
                os.remove(MUTE_FLAG)
            self.mute_btn.configure(text="🔊")

    def _start_hotkey_capture(self):
        if self._listening_hotkey:
            return
        self._listening_hotkey = True
        self.hotkey_btn.configure(text="Press a key...")
        self.bind("<KeyPress>", self._capture_hotkey)
        self.focus_set()

    def _capture_hotkey(self, e):
        if not self._listening_hotkey:
            return
        self._listening_hotkey = False
        KEY_MAP = {"grave": "`", "space": "Space"}
        display = KEY_MAP.get(e.keysym, e.keysym)
        self.cfg["hotkey"] = display
        config.save(self.cfg)
        self.hotkey_btn.configure(text=f"⌨ {display}")
        self.unbind("<KeyPress>")
        open(HOTKEY_FLAG, "w").close()

    def _on_model_change(self, new_model: str):
        if new_model == self._current_model:
            return
        self._current_model = new_model
        self.cfg["model"] = new_model
        config.save(self.cfg)
        self.model = None
        threading.Thread(target=self._load_model, daemon=True).start()

    def _toggle_expand(self):
        self.cfg["expanded"] = not self.cfg["expanded"]
        config.save(self.cfg)
        self._apply_expanded(self.cfg["expanded"])

    def _apply_expanded(self, expanded: bool, animate: bool = True):
        if expanded:
            self.panel.pack(fill="x", padx=4, pady=(0, 4))
            self.expand_btn.configure(text="▲")
        else:
            self.panel.pack_forget()
            self.expand_btn.configure(text="▼")

    def _hide(self):
        self.withdraw()

    def show(self):
        self.deiconify()
        self.attributes("-topmost", True)

    def _copy(self):
        text = self.text_box.get("1.0", "end").strip()
        self.clipboard_clear()
        self.clipboard_append(text)

    # ══════════════════════════════════════════════════════════════════════════
    # Status dot
    # ══════════════════════════════════════════════════════════════════════════

    def _set_status(self, text: str, state: str):
        color = DOT_COLORS.get(state, GRAY)
        self.dot_canvas.itemconfig(self.dot_id, fill=color)
        self.status_lbl.configure(
            text=text,
            text_color=TEXT if state != "mic_off" else SUBTEXT
        )

    # ══════════════════════════════════════════════════════════════════════════
    # Model loading
    # ══════════════════════════════════════════════════════════════════════════

    def _load_model(self):
        name = self._current_model
        self.after(0, self._set_status, f"Loading {name}...", "loading")
        try:
            self.model = whisper.load_model(name, device=self.device,
                                             download_root=MODELS_DIR)
            if not self.cfg["mic_enabled"]:
                self.after(0, self._set_status, "Mic off", "mic_off")
            else:
                self.after(0, self._set_status,
                           f"Ready ({self.device.upper()})", "ready")
        except Exception as exc:
            self.after(0, self._set_status, f"Error: {exc}", "error")

    # ══════════════════════════════════════════════════════════════════════════
    # Recording
    # ══════════════════════════════════════════════════════════════════════════

    def _audio_callback(self, indata, frames, t, status):
        if self.is_recording:
            self.recording_data.append(indata.copy())

    def start_recording(self):
        if self.is_recording or self.model is None:
            return
        if not self.cfg["mic_enabled"]:
            return
        self.is_recording   = True
        self.recording_data = []
        self._set_status("Recording...", "recording")
        self.stream = sd.InputStream(
            samplerate=SAMPLE_RATE, channels=CHANNELS,
            dtype=DTYPE, callback=self._audio_callback
        )
        self.stream.start()

    def stop_recording(self):
        if not self.is_recording:
            return
        self.is_recording = False
        if self.stream:
            self.stream.stop()
            self.stream.close()
        if self.recording_data:
            self._set_status("Transcribing...", "transcribing")
            threading.Thread(target=self._transcribe, daemon=True).start()
        else:
            self._set_status("Ready", "ready")

    def _transcribe(self):
        try:
            audio = np.concatenate(self.recording_data, axis=0)
            write(OUTPUT_AUDIO, SAMPLE_RATE, audio)
            result = self.model.transcribe(OUTPUT_AUDIO,
                                            fp16=torch.cuda.is_available())
            text = result["text"].strip()
            self.after(0, self._show_result, text)
        except Exception as exc:
            self.after(0, self._set_status, f"Failed: {exc}", "error")

    def _show_result(self, text: str):
        self.text_box.delete("1.0", "end")
        self.text_box.insert("end", text)
        self._set_status("Done", "ready")
        with open(OUTPUT_TXT, "w", encoding="utf-8") as f:
            f.write(text)

    # ══════════════════════════════════════════════════════════════════════════
    # Flag listener
    # ══════════════════════════════════════════════════════════════════════════

    def _flag_listener(self):
        while True:
            if os.path.exists(START_FLAG):
                os.remove(START_FLAG)
                self.after(0, self.start_recording)

            if os.path.exists(STOP_FLAG):
                os.remove(STOP_FLAG)
                self.after(0, self.stop_recording)

            if os.path.exists(SHOW_FLAG):
                os.remove(SHOW_FLAG)
                self.after(0, self.show)

            time.sleep(0.02)


if __name__ == "__main__":
    app = WhisperWidget()
    app.mainloop()
