# Suppress console windows spawned by ffmpeg (called internally by whisper)
import os, sys
import subprocess as _subprocess
import ctypes as _ctypes

# PyInstaller --noconsole sets stdout/stderr to None, which crashes tqdm
# (used by whisper's model downloader) and any other library that writes to stderr.
if getattr(sys, 'frozen', False):
    if sys.stdout is None:
        sys.stdout = open(os.devnull, 'w')
    if sys.stderr is None:
        sys.stderr = open(os.devnull, 'w')
    # Ensure HTTPS downloads work by pointing SSL at bundled certificates
    import ssl, certifi
    ssl._create_default_https_context = lambda: ssl.create_default_context(cafile=certifi.where())

_AUMID = "WhisperTranscription.1"

if os.name == 'nt':
    _orig_popen_init = _subprocess.Popen.__init__
    def _popen_no_window(self, *args, **kwargs):
        kwargs.setdefault('creationflags', 0)
        kwargs['creationflags'] |= 0x08000000  # CREATE_NO_WINDOW
        _orig_popen_init(self, *args, **kwargs)
    _subprocess.Popen.__init__ = _popen_no_window

    # Give this process its own taskbar group (separate from pythonw.exe).
    # Must be called BEFORE the window is created so Windows uses it from the start.
    _ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(_AUMID)

import customtkinter as ctk
import tkinter as tk
from PIL import ImageTk
import sounddevice as sd
from scipy.io.wavfile import write as write_wav
import whisper
import threading
import numpy as np
import torch, time, ctypes, winsound, keyboard
import config
import icon_gen


# ── paths ──────────────────────────────────────────────────────────────────────
# --onedir: exe is in <project>/<appname>/ → go up one level to project root
if getattr(sys, 'frozen', False):
    _exe_dir = os.path.dirname(sys.executable)
    if os.path.exists(os.path.join(_exe_dir, 'config.py')):
        SCRIPT_DIR = _exe_dir
    else:
        SCRIPT_DIR = os.path.dirname(_exe_dir)
else:
    SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_AUDIO = os.path.join(SCRIPT_DIR, "recorded.wav")
MODELS_DIR   = os.path.join(SCRIPT_DIR, "models")

SAMPLE_RATE = 16000
CHANNELS    = 1
DTYPE       = 'int16'

ALL_MODELS = [
    "tiny.en (~1 GB VRAM)",
    "base.en (~1 GB)",
    "small.en (~2 GB) ★",
    "medium.en (~5 GB)",
    "turbo (~6 GB) ★",
    "large-v3 (~10 GB)",
]

def _model_id(display_name: str) -> str:
    """Extract the model ID from a display name like 'base.en (~1 GB) ★'."""
    return display_name.split("(")[0].strip().rstrip("★").strip()

def _model_display(model_id: str) -> str:
    """Find the display name for a model ID, or return the ID as-is."""
    for name in ALL_MODELS:
        if _model_id(name) == model_id:
            return name
    return model_id

# ── colours ────────────────────────────────────────────────────────────────────
BG        = "#1a1a1a"
BAR_BG    = "#222222"
PANEL_BG  = "#2a2a2a"
TEXT      = "#e8e8e8"
SUBTEXT   = "#888888"
ACCENT    = "#1E90FF"
RED       = "#C70039"
AMBER     = "#FFA500"
GREEN     = "#28A745"
GRAY      = "#555555"
BTN_BG    = "#333333"
BTN_HOVER = "#444444"

DOT_COLORS = {
    "loading":      GRAY,
    "ready":        GREEN,
    "recording":    RED,
    "transcribing": AMBER,
    "mic_off":      GRAY,
    "error":        RED,
}


def _create_shortcut(icon_path: str) -> None:
    """Create/update a pinnable .lnk in the project folder. Always recreated so
    the icon path stays current."""
    shortcut_path = os.path.join(SCRIPT_DIR, "Whisper Transcription.lnk")
    if getattr(sys, 'frozen', False):
        target = sys.executable
    else:
        target = os.path.join(SCRIPT_DIR, "pythonscript.pyw")
    ps = (
        f"$s=(New-Object -ComObject WScript.Shell).CreateShortcut('{shortcut_path}');"
        f"$s.TargetPath='{target}';"
        f"$s.IconLocation='{icon_path}';"
        f"$s.WorkingDirectory='{SCRIPT_DIR}';"
        f"$s.Save()"
    )
    try:
        _subprocess.run(
            ["powershell", "-NoProfile", "-Command", ps],
            creationflags=0x08000000, check=True, timeout=10
        )
    except Exception:
        pass  # non-fatal


class WhisperWidget(ctk.CTk):
    def __init__(self):
        super().__init__()

        # ── window ─────────────────────────────────────────────────────────────
        self.title("Whisper Transcription")
        ctk.set_appearance_mode("dark")
        self.configure(fg_color=BG)
        self.attributes("-topmost", True)
        self.minsize(480, 0)
        self.protocol("WM_DELETE_WINDOW", self._on_close)

        # ── icon & shortcut ────────────────────────────────────────────────────
        icon_path = icon_gen.create_icon()
        self._icon = ImageTk.PhotoImage(file=icon_path)  # keep ref to avoid GC
        self._apply_icon()
        self.after(500, self._apply_icon)  # re-apply after CTk's delayed icon callbacks
        threading.Thread(target=_create_shortcut, args=(icon_path,), daemon=True).start()

        # ── config ─────────────────────────────────────────────────────────────
        self.cfg = config.load()

        # ── state ──────────────────────────────────────────────────────────────
        self.is_recording      = False
        self.recording_data    = []
        self.stream            = None
        self.model             = None
        self.device            = "cuda" if torch.cuda.is_available() else "cpu"
        self._last_hwnd        = None
        self._kb_hooks         = []
        self._listening_hotkey = False
        self._current_model    = self.cfg["model"]

        # ── UI ─────────────────────────────────────────────────────────────────
        self._build_bar()
        self._build_panel()
        self._apply_expanded(self.cfg["expanded"])
        self.geometry(f"+{self.cfg['window_x']}+{self.cfg['window_y']}")

        # ── hotkey & model ─────────────────────────────────────────────────────
        self._register_hotkey(self.cfg.get("hotkey", "`"))
        threading.Thread(target=self._load_model, daemon=True).start()

    def _on_close(self):
        keyboard.unhook_all()
        self.destroy()

    def _apply_icon(self):
        """Set the window icon via Tkinter."""
        try:
            self.wm_iconbitmap()                    # clear CTk's default
            self.iconphoto(False, self._icon)       # set via Tkinter
        except Exception:
            pass

    # ══════════════════════════════════════════════════════════════════════════
    # Global hotkey (keyboard library)
    # ══════════════════════════════════════════════════════════════════════════

    def _register_hotkey(self, key: str):
        for h in self._kb_hooks:
            try:
                keyboard.unhook(h)
            except Exception:
                pass
        self._kb_hooks = []
        try:
            self._kb_hooks.append(
                keyboard.on_press_key(key, self._on_hotkey_press, suppress=True)
            )
            self._kb_hooks.append(
                keyboard.on_release_key(key, self._on_hotkey_release, suppress=True)
            )
        except Exception as exc:
            self.after(0, self._set_status, f"Hotkey error: {exc}", "error")

    def _on_hotkey_press(self, _e):
        if not self.cfg["mic_enabled"] or self.is_recording:
            return
        # Capture the active window NOW, before any focus changes
        self._last_hwnd = ctypes.windll.user32.GetForegroundWindow()
        self.after(0, self._begin_recording)

    def _on_hotkey_release(self, _e):
        if self.is_recording:
            self.after(0, self.stop_recording)

    def _begin_recording(self):
        if not self.cfg["mute_beeps"]:
            threading.Thread(target=lambda: winsound.Beep(750, 100), daemon=True).start()
        self.start_recording()

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

        self.dot_canvas = tk.Canvas(self.bar, width=14, height=14,
                                    bg=BAR_BG, highlightthickness=0)
        self.dot_canvas.pack(side="left", padx=(10, 4), pady=15)
        self.dot_id = self.dot_canvas.create_oval(1, 1, 13, 13, fill=GRAY, outline="")

        self.status_lbl = ctk.CTkLabel(self.bar, text="Loading...", text_color=SUBTEXT,
                                       font=("Segoe UI", 11), anchor="w", width=130)
        self.status_lbl.pack(side="left", padx=(0, 6))
        self.status_lbl.bind("<ButtonPress-1>", self._drag_start)
        self.status_lbl.bind("<B1-Motion>",     self._drag_move)

        self.mic_btn = ctk.CTkButton(
            self.bar, text="🎤", width=32, height=28,
            fg_color=ACCENT if self.cfg["mic_enabled"] else BTN_BG,
            hover_color=BTN_HOVER, corner_radius=6,
            command=self._toggle_mic, font=("Segoe UI", 13)
        )
        self.mic_btn.pack(side="left", padx=2)

        self.mute_btn = ctk.CTkButton(
            self.bar, text="🔇" if self.cfg["mute_beeps"] else "🔊",
            width=32, height=28,
            fg_color=BTN_BG, hover_color=BTN_HOVER, corner_radius=6,
            command=self._toggle_mute, font=("Segoe UI", 13)
        )
        self.mute_btn.pack(side="left", padx=2)

        self.hotkey_btn = ctk.CTkButton(
            self.bar, text=f"⌨ {self.cfg.get('hotkey', '`')}",
            width=54, height=28,
            fg_color=BTN_BG, hover_color=BTN_HOVER, corner_radius=6,
            command=self._start_hotkey_capture, font=("Segoe UI", 11)
        )
        self.hotkey_btn.pack(side="left", padx=2)

        self.model_var = ctk.StringVar(value=_model_display(self.cfg["model"]))
        self.model_menu = ctk.CTkOptionMenu(
            self.bar, values=ALL_MODELS, variable=self.model_var,
            width=170, height=28, corner_radius=6,
            fg_color=BTN_BG, button_color=BTN_BG, button_hover_color=BTN_HOVER,
            dropdown_fg_color=PANEL_BG, font=("Segoe UI", 11),
            command=self._on_model_change
        )
        self.model_menu.pack(side="left", padx=2)

        self.expand_btn = ctk.CTkButton(
            self.bar, text="▼" if not self.cfg["expanded"] else "▲",
            width=28, height=28,
            fg_color=BTN_BG, hover_color=BTN_HOVER, corner_radius=6,
            command=self._toggle_expand, font=("Segoe UI", 11)
        )
        self.expand_btn.pack(side="left", padx=2)

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
        self.mute_btn.configure(text="🔇" if self.cfg["mute_beeps"] else "🔊")

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
        self._register_hotkey(display)

    def _on_model_change(self, display_name: str):
        new_model = _model_id(display_name)
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

    def _apply_expanded(self, expanded: bool):
        if expanded:
            self.panel.pack(fill="x", padx=4, pady=(0, 4))
            self.expand_btn.configure(text="▲")
        else:
            self.panel.pack_forget()
            self.expand_btn.configure(text="▼")

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
        if self.is_recording or self.model is None or not self.cfg["mic_enabled"]:
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
            self.stream = None
        data  = self.recording_data
        self.recording_data = []
        model = self.model
        hwnd  = self._last_hwnd
        if not self.cfg["mute_beeps"]:
            threading.Thread(target=lambda: winsound.Beep(500, 100), daemon=True).start()
        if data and model is not None:
            self._set_status("Transcribing...", "transcribing")
            threading.Thread(
                target=self._transcribe, args=(data, model, hwnd), daemon=True
            ).start()
        else:
            self._set_status("Ready", "ready")

    def _transcribe(self, data, model, hwnd):
        try:
            audio = np.concatenate(data, axis=0)
            write_wav(OUTPUT_AUDIO, SAMPLE_RATE, audio)
            result = model.transcribe(
                OUTPUT_AUDIO,
                fp16=torch.cuda.is_available(),
                no_speech_threshold=0.75,
                condition_on_previous_text=False,
            )
            text = result["text"].strip()
            HALLUCINATIONS = {
                "thanks for watching.", "thanks for watching!",
                "thank you for watching.", "thank you for watching!",
            }
            if text.lower() in HALLUCINATIONS:
                text = ""
            self.after(0, self._show_result, text, hwnd)
        except Exception as exc:
            self.after(0, self._set_status, f"Failed: {exc}", "error")

    def _show_result(self, text: str, hwnd: int):
        self.text_box.delete("1.0", "end")
        self.text_box.insert("end", text)
        self._set_status("Done", "ready")
        if text and hwnd:
            self._paste(text, hwnd)

    def _paste(self, text: str, hwnd: int):
        # Write to clipboard
        self.clipboard_clear()
        self.clipboard_append(text)
        self.update()  # flush clipboard to OS

        # Restore focus to the original window.
        # AttachThreadInput is required to override Windows' focus-lock rules.
        user32  = ctypes.windll.user32
        kernel32 = ctypes.windll.kernel32
        fg_win  = user32.GetForegroundWindow()
        fg_tid  = user32.GetWindowThreadProcessId(fg_win, None)
        my_tid  = kernel32.GetCurrentThreadId()
        user32.AttachThreadInput(my_tid, fg_tid, True)
        user32.SetForegroundWindow(hwnd)
        user32.BringWindowToTop(hwnd)
        user32.AttachThreadInput(my_tid, fg_tid, False)

        time.sleep(0.15)
        keyboard.send("ctrl+v")
        time.sleep(0.3)


if __name__ == "__main__":
    import multiprocessing
    multiprocessing.freeze_support()
    app = WhisperWidget()
    app.mainloop()
