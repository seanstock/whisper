# Floating Widget Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Replace the hidden Tkinter GUI with a modern always-on-top floating widget using customtkinter, adding mic toggle, mute toggle, hotkey rebinding, model selection, and a microphone taskbar icon.

**Architecture:** Overhaul `pythonscript.pyw` in-place — all recording/transcription/flag-file logic stays the same, only the UI layer changes. `whisper.ahk` gets three targeted fixes: DetectHiddenWindows, mute-flag check, and dynamic hotkey rebinding. A new `config.json` persists all settings.

**Tech Stack:** Python 3.11, customtkinter, Pillow (already installed), AutoHotkey v2, flag-file IPC

---

## Pre-flight: Verify turbo model download

Before starting, confirm the background download completed:

```bash
ls -lh /c/Users/seang/whisper/models/
```

Expected: a file named `large-v3-turbo.pt`, ~1.58 GB.
If missing or incomplete, re-run:
```bash
"/c/Users/seang/whisper/whisper-env/Scripts/python.exe" -c \
  "import whisper; whisper.load_model('turbo', download_root='C:/Users/seang/whisper/models')"
```

---

## Task 1: Install customtkinter

**Files:**
- Modify: `requirements.txt`

**Step 1: Install the package**

```bash
"/c/Users/seang/whisper/whisper-env/Scripts/pip.exe" install customtkinter
```

Expected output: `Successfully installed customtkinter-X.X.X`

**Step 2: Verify import works**

```bash
"/c/Users/seang/whisper/whisper-env/Scripts/python.exe" -c "import customtkinter; print(customtkinter.__version__)"
```

Expected: prints a version number without error.

**Step 3: Add to requirements.txt**

Append `customtkinter` to `requirements.txt` (exact version from the install output, e.g. `customtkinter==5.3.2`).

**Step 4: Commit**

```bash
git add requirements.txt
git commit -m "feat: add customtkinter dependency"
```

---

## Task 2: Fix ffmpeg console flash

**Files:**
- Modify: `pythonscript.pyw` (top of file, before any other imports)

**Step 1: Add the subprocess patch at the very top of `pythonscript.pyw`**

Insert these lines as the first code in the file, before `import tkinter` or any other imports:

```python
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
```

**Step 2: Manual verify**

Kill any running `pythonw.exe` processes (Task Manager), then double-click `whisper.ahk` to restart. Press and release backtick. During transcription: no console window should flash. (You'll need audio data — say something while holding backtick.)

**Step 3: Commit**

```bash
git add pythonscript.pyw
git commit -m "fix: suppress ffmpeg console window flash on Windows"
```

---

## Task 3: Add config.json system

**Files:**
- Create: `config.py` (new helper module in project root)
- Modify: `pythonscript.pyw`

**Step 1: Create `config.py`**

```python
import json
import os

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(SCRIPT_DIR, "config.json")

DEFAULTS = {
    "model": "turbo",
    "mute_beeps": False,
    "mic_enabled": True,
    "hotkey": "`",
    "window_x": 100,
    "window_y": 100,
    "expanded": False,
}

def load() -> dict:
    """Load config from disk, filling missing keys with defaults."""
    if not os.path.exists(CONFIG_PATH):
        save(DEFAULTS.copy())
        return DEFAULTS.copy()
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    # Fill any missing keys added in future updates
    for k, v in DEFAULTS.items():
        data.setdefault(k, v)
    return data

def save(cfg: dict) -> None:
    """Write config dict to disk."""
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2)
```

**Step 2: Write a quick smoke test**

```bash
"/c/Users/seang/whisper/whisper-env/Scripts/python.exe" -c "
import sys; sys.path.insert(0, 'C:/Users/seang/whisper')
import config
cfg = config.load()
print('loaded:', cfg)
cfg['mute_beeps'] = True
config.save(cfg)
cfg2 = config.load()
assert cfg2['mute_beeps'] == True, 'save/load broken'
cfg2['mute_beeps'] = False
config.save(cfg2)
print('config OK')
"
```

Expected: prints `config OK` with no errors. Check that `config.json` appears in the project root.

**Step 3: Commit**

```bash
git add config.py config.json
git commit -m "feat: add config.json persistence system"
```

---

## Task 4: Generate microphone icon

**Files:**
- Create: `icon_gen.py` (helper module)

**Step 1: Create `icon_gen.py`**

```python
"""Generates icon.ico in the project directory using Pillow."""
import os
from PIL import Image, ImageDraw

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ICON_PATH = os.path.join(SCRIPT_DIR, "icon.ico")

def create_icon():
    """Draw a microphone icon and save as multi-res .ico."""
    sizes = [16, 32, 48]
    images = []
    for size in sizes:
        img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        s = size
        # Microphone body (rounded rectangle)
        bx = int(s * 0.33)
        bw = int(s * 0.34)
        bt = int(s * 0.08)
        bb = int(s * 0.58)
        draw.rounded_rectangle([bx, bt, bx + bw, bb], radius=int(bw * 0.5), fill=(220, 220, 220, 255))
        # Stand arc (bottom half circle)
        ax = int(s * 0.18)
        aw = int(s * 0.64)
        at = int(s * 0.48)
        ab = int(s * 0.80)
        draw.arc([ax, at, ax + aw, ab], start=0, end=180, fill=(180, 180, 180, 255), width=max(1, int(s * 0.07)))
        # Stand pole
        cx = s // 2
        draw.line([(cx, int(s * 0.78)), (cx, int(s * 0.90))], fill=(180, 180, 180, 255), width=max(1, int(s * 0.06)))
        # Base
        bsx = int(s * 0.28)
        bex = int(s * 0.72)
        by2 = int(s * 0.90)
        draw.line([(bsx, by2), (bex, by2)], fill=(180, 180, 180, 255), width=max(1, int(s * 0.06)))
        images.append(img)
    images[0].save(ICON_PATH, format="ICO", sizes=[(s, s) for s in sizes], append_images=images[1:])
    return ICON_PATH

if __name__ == "__main__":
    path = create_icon()
    print(f"Icon written to {path}")
```

**Step 2: Run it to verify**

```bash
"/c/Users/seang/whisper/whisper-env/Scripts/python.exe" "C:/Users/seang/whisper/icon_gen.py"
```

Expected: `Icon written to C:/Users/seang/whisper/icon.ico`
Open `icon.ico` in Windows Explorer to visually confirm it looks like a microphone.

**Step 3: Add icon.ico to .gitignore (generated file)**

Add to `.gitignore` (create it if it doesn't exist):
```
icon.ico
__pycache__/
*.pyc
output.txt
*.flag
recorded.wav
```

**Step 4: Commit**

```bash
git add icon_gen.py .gitignore
git commit -m "feat: add microphone icon generator"
```

---

## Task 5: Build the floating widget (full UI overhaul)

This is the main task. Replace the entire contents of `pythonscript.pyw` with the new implementation. The recording/transcription logic is preserved; only the UI is rewritten.

**Files:**
- Modify: `pythonscript.pyw` (full rewrite)

**Step 1: Write the new `pythonscript.pyw`**

Replace the entire file with:

```python
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
import sounddevice as sd
from scipy.io.wavfile import write
import whisper
import threading
import numpy as np
import os
import sys
import torch
import time
import json

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
        self.overrideredirect(True)          # no OS title bar
        self.attributes("-topmost", True)

        # ── icon ───────────────────────────────────────────────────────────────
        icon_path = icon_gen.create_icon()
        self.iconbitmap(icon_path)

        # ── config ─────────────────────────────────────────────────────────────
        self.cfg = config.load()

        # ── state ──────────────────────────────────────────────────────────────
        self.is_recording   = False
        self.recording_data = []
        self.stream         = None
        self.model          = None
        self.device         = "cuda" if torch.cuda.is_available() else "cpu"
        self._drag_x        = 0
        self._drag_y        = 0
        self._listening_hotkey = False
        self._current_model_name = self.cfg["model"]

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
        BAR_H = 44
        self.bar = ctk.CTkFrame(self, fg_color=BAR_BG, corner_radius=8, height=BAR_H)
        self.bar.pack(fill="x", padx=0, pady=0)
        self.bar.pack_propagate(False)

        # drag bindings on bar
        self.bar.bind("<ButtonPress-1>",   self._drag_start)
        self.bar.bind("<B1-Motion>",       self._drag_move)
        self.bar.bind("<ButtonRelease-1>", self._drag_end)

        # status dot
        self.dot_canvas = ctk.CTkCanvas(self.bar, width=14, height=14,
                                         bg=BAR_BG, highlightthickness=0)
        self.dot_canvas.pack(side="left", padx=(10, 4), pady=14)
        self.dot_id = self.dot_canvas.create_oval(1, 1, 13, 13, fill=GRAY, outline="")

        # status label
        self.status_lbl = ctk.CTkLabel(self.bar, text="Loading...", text_color=SUBTEXT,
                                        font=("Segoe UI", 11), anchor="w", width=130)
        self.status_lbl.pack(side="left", padx=(0, 8))
        self.status_lbl.bind("<ButtonPress-1>",   self._drag_start)
        self.status_lbl.bind("<B1-Motion>",       self._drag_move)

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
        hk_label = self.cfg.get("hotkey", "`")
        self.hotkey_btn = ctk.CTkButton(
            self.bar, text=f"⌨ {hk_label}", width=54, height=28,
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

        # expand button
        self.expand_btn = ctk.CTkButton(
            self.bar, text="▼" if not self.cfg["expanded"] else "▲",
            width=28, height=28,
            fg_color=BTN_BG, hover_color=BTN_HOVER, corner_radius=6,
            command=self._toggle_expand, font=("Segoe UI", 11)
        )
        self.expand_btn.pack(side="left", padx=2)

        # close button
        ctk.CTkButton(
            self.bar, text="✕", width=28, height=28,
            fg_color=BTN_BG, hover_color="#8B0000", corner_radius=6,
            command=self._hide, font=("Segoe UI", 11)
        ).pack(side="left", padx=(2, 8))

    def _build_panel(self):
        self.panel = ctk.CTkFrame(self, fg_color=PANEL_BG, corner_radius=8)
        # not packed yet — _apply_expanded handles that

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
        x = e.x_root - self._drag_x
        y = e.y_root - self._drag_y
        self.geometry(f"+{x}+{y}")

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
        self.bar.bind("<KeyPress>", self._capture_hotkey)
        self.bar.focus_set()

    def _capture_hotkey(self, e):
        if not self._listening_hotkey:
            return
        self._listening_hotkey = False
        key = e.keysym  # e.g. "grave" for backtick
        # Map tkinter keysym back to a display/AHK-friendly char
        KEY_MAP = {"grave": "`", "space": "Space"}
        display = KEY_MAP.get(key, key)
        self.cfg["hotkey"] = display
        config.save(self.cfg)
        self.hotkey_btn.configure(text=f"⌨ {display}")
        self.bar.unbind("<KeyPress>")
        # Signal AHK to reload hotkey
        open(HOTKEY_FLAG, "w").close()

    def _on_model_change(self, new_model: str):
        if new_model == self._current_model_name:
            return
        self._current_model_name = new_model
        self.cfg["model"] = new_model
        config.save(self.cfg)
        self.model = None
        threading.Thread(target=self._load_model, daemon=True).start()

    def _toggle_expand(self):
        expanded = not self.cfg["expanded"]
        self.cfg["expanded"] = expanded
        config.save(self.cfg)
        self._apply_expanded(expanded)

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
        self.status_lbl.configure(text=text,
                                   text_color=TEXT if state != "mic_off" else SUBTEXT)

    # ══════════════════════════════════════════════════════════════════════════
    # Model loading
    # ══════════════════════════════════════════════════════════════════════════

    def _load_model(self):
        name = self._current_model_name
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
```

**Step 2: Kill all running Python/AHK processes, then test manually**

1. Kill `pythonw.exe` and `AutoHotkey.exe` in Task Manager
2. Double-click `whisper.ahk` — the widget should appear immediately (not hidden)
3. Verify: floating bar with dot + status + buttons visible, always on top
4. Wait for status to change from "Loading turbo..." to "Ready (CUDA)" or "Ready (CPU)"
5. Press and hold backtick → dot turns red, status says "Recording..."
6. Release → dot turns amber, status says "Transcribing...", then "Done"
7. Click ▼ → text panel drops down showing transcribed text
8. Click 🔊 → changes to 🔇, check that `mute.flag` appears in project folder
9. Click 🎤 → turns gray, status shows "Mic off"; backtick now does nothing
10. Click 🎤 again → re-enables

**Step 3: Commit**

```bash
git add pythonscript.pyw
git commit -m "feat: rewrite UI as customtkinter floating widget"
```

---

## Task 6: Update whisper.ahk — multi-instance fix + remove --bg

**Files:**
- Modify: `whisper.ahk`

**Step 1: Read the current file and make these changes**

Change 1 — add `DetectHiddenWindows` right after `#SingleInstance Force`:
```ahk
#SingleInstance Force
DetectHiddenWindows True
```

Change 2 — remove `--bg` from the Run command:
```ahk
; was: Run('"' . PythonPath . '" "' . ScriptPath . '" --bg')
Run('"' . PythonPath . '" "' . ScriptPath . '"')
```

**Step 2: Verify**

Reload `whisper.ahk`. Only one Python process should appear in Task Manager. The widget should appear visible immediately.

**Step 3: Commit**

```bash
git add whisper.ahk
git commit -m "fix: DetectHiddenWindows prevents duplicate Python instances"
```

---

## Task 7: Update whisper.ahk — mute flag check

**Files:**
- Modify: `whisper.ahk`

**Step 1: Add MuteFlag path variable** near the other path declarations at the top:

```ahk
MuteFlag := A_ScriptDir . "\mute.flag"
```

**Step 2: Wrap both SoundBeep calls** with a mute check:

Key-down handler — replace:
```ahk
SoundBeep(750, 100) ; high beep for START
```
with:
```ahk
if !FileExist(MuteFlag)
    SoundBeep(750, 100)
```

Key-up handler — replace:
```ahk
SoundBeep(500, 100) ; Optional: lower beep for STOP
```
with:
```ahk
if !FileExist(MuteFlag)
    SoundBeep(500, 100)
```

**Step 3: Verify**

1. Click 🔇 in the widget → `mute.flag` appears
2. Press and release backtick → no beeps
3. Click 🔊 → `mute.flag` disappears
4. Press and release backtick → beeps return

**Step 4: Commit**

```bash
git add whisper.ahk
git commit -m "feat: AHK respects mute.flag for beep suppression"
```

---

## Task 8: Update whisper.ahk — dynamic hotkey rebinding

**Files:**
- Modify: `whisper.ahk`

**Step 1: Add hotkey state variables** near the top of the script (after the path declarations):

```ahk
HotkeyFlag   := A_ScriptDir . "\hotkey_change.flag"
ConfigFile   := A_ScriptDir . "\config.json"
CurrentHotkey := "``"   ; backtick (escaped)
```

**Step 2: Add a timer to poll for hotkey changes** (add near end of script, before functions):

```ahk
SetTimer(CheckHotkeyChange, 500)

CheckHotkeyChange() {
    global HotkeyFlag, ConfigFile, CurrentHotkey, IsRecording
    if !FileExist(HotkeyFlag)
        return
    FileDelete(HotkeyFlag)

    ; Read new hotkey from config.json
    raw := FileRead(ConfigFile)
    ; Simple JSON parse — find "hotkey": "X"
    if RegExMatch(raw, '"hotkey"\s*:\s*"([^"]+)"', &m) {
        newKey := m[1]
        if (newKey = CurrentHotkey)
            return
        ; Disable old hotkey pair
        try Hotkey("*" . CurrentHotkey, "Off")
        try Hotkey("*" . CurrentHotkey . " Up", "Off")
        CurrentHotkey := newKey
        ; Register new hotkey pair
        Hotkey("*" . newKey, HotkeyDown)
        Hotkey("*" . newKey . " Up", HotkeyUp)
    }
}
```

**Step 3: Extract the hotkey handlers into named functions**

The current `*`:: { ... }` block and `*` Up:: { ... }` block need to become named functions that can be referenced by the `Hotkey()` call. Refactor:

```ahk
; Initial registration (backtick)
Hotkey("*``", HotkeyDown)
Hotkey("*`` Up", HotkeyUp)

HotkeyDown(*) {
    global IsRecording, LastActiveWindow
    if IsRecording
        return
    IsRecording := true
    LastActiveWindow := WinActive("A")
    if FileExist(OutputFile)
        FileDelete(OutputFile)
    FileAppend("", StartFlag)
    if !FileExist(MuteFlag)
        SoundBeep(750, 100)
}

HotkeyUp(*) {
    global IsRecording
    IsRecording := false
    FileAppend("", StopFlag)
    if !FileExist(MuteFlag)
        SoundBeep(500, 100)
    if (WaitForResult())
        PasteText()
}
```

Remove the old `*`:: { }` and `*` Up:: { }` blocks entirely.

**Step 4: Verify**

1. Reload `whisper.ahk`
2. Click the hotkey button in the widget → it shows "Press a key..."
3. Press `F9` → button updates to "⌨ F9", `config.json` updates, `hotkey_change.flag` briefly appears
4. Press `F9` → recording starts; release → stops and transcribes
5. Confirm backtick no longer triggers recording

**Step 5: Commit**

```bash
git add whisper.ahk
git commit -m "feat: dynamic hotkey rebinding via config.json + hotkey_change.flag"
```

---

## Task 9: Final integration test + cleanup

**Step 1: Full end-to-end test**

With `whisper.ahk` running and widget visible:

- [ ] Widget appears on startup, always on top, draggable
- [ ] Model loads → status shows "Ready (CUDA)" or "Ready (CPU)"
- [ ] Hold backtick → red dot, "Recording..."
- [ ] Release → amber dot, "Transcribing..." → green dot, "Done"
- [ ] Text appears in expanded panel
- [ ] Copy button copies text to clipboard
- [ ] 🔇 mutes beeps, 🔊 restores them
- [ ] 🎤 off disables hotkey, 🎤 on re-enables
- [ ] Hotkey rebinding works
- [ ] Model dropdown switches model (shows "Loading..."), transcription works after reload
- [ ] Window position persists after drag + restart
- [ ] No ffmpeg console flash during transcription
- [ ] Taskbar shows microphone icon (not Python logo)
- [ ] Close button hides widget; Alt+G restores it
- [ ] Reloading AHK does NOT spawn a second Python instance

**Step 2: Add model download note to README**

Update `README.md` — add a note in Setup that `turbo` is pre-downloaded to `models/` and that other models download on first use.

**Step 3: Final commit**

```bash
git add README.md
git commit -m "docs: update README for new widget UI and local model storage"
```
