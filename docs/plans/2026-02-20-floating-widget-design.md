# Whisper Floating Widget — Design Document

**Date:** 2026-02-20
**Status:** Approved

## Summary

Overhaul `pythonscript.pyw` into a modern always-on-top floating widget using `customtkinter`. The backtick push-to-talk hotkey via AHK remains the primary interaction mechanism. New controls are added for mic toggle, mute beeps, hotkey rebinding, model selection, and expand/collapse transcript view. Default model switches from `medium.en` to `turbo`, stored locally in `models/`.

---

## Window Behavior

- Always visible, always-on-top
- No OS title bar (`overrideredirect(True)`), custom drag on bar
- Compact bar: ~340×44px (default)
- Expanded: bar + text panel ~340×220px total
- Close button withdraws window; taskbar click or Alt+G restores it
- Window position persisted in `config.json`
- Starts visible — remove `--bg` flag from AHK launch command

---

## Layout

### Compact bar (left → right)
```
[ ● ] [ Ready              ] [ 🎤 ] [ 🔇 ] [ ` ▾ ] [ Model ▾ ] [ ▼ ] [ ✕ ]
```

| Element | Behavior |
|---------|----------|
| **●** status dot | gray=loading, green=ready, red=recording, amber=transcribing, dark=mic off |
| **Status text** | "Loading…" / "Ready" / "Recording…" / "Transcribing…" / "Mic off" |
| **🎤 mic toggle** | On/off. When off, flag_listener ignores `start.flag`. Persisted in config. |
| **🔇 mute toggle** | Writes/deletes `mute.flag`. AHK checks before `SoundBeep()`. Persisted in config. |
| **`` ` ▾`` hotkey button** | Shows current hotkey char. Click → "Press a key…" → capture → save to config + write `hotkey_change.flag` |
| **Model ▾ dropdown** | tiny.en / base.en / small.en / medium.en / turbo / large-v3. Triggers async model reload. |
| **▼/▲ expand** | Toggles transcript panel. State persisted in config. |
| **✕ close** | Hides window (process keeps running) |

### Expanded panel (below bar)
```
┌─────────────────────────────────────────┐
│  transcribed text scrollable area       │
│                              [ Copy ]   │
└─────────────────────────────────────────┘
```

---

## Styling

- Library: `customtkinter` (add to requirements)
- Theme: dark, `#1a1a1a` background, `#2a2a2a` panel
- Rounded corners on all buttons and panels
- Status dot: colored `Canvas` circle, 12px diameter
- Accent: `#1E90FF` (blue) for active states
- Recording accent: `#C70039` (red)

---

## Taskbar Icon

- Generated programmatically at startup using Pillow (already installed)
- Microphone shape drawn as simple geometry at 16×16, 32×32, 48×48
- Written to `icon.ico` in project root on first run
- Set via `root.iconbitmap("icon.ico")`

---

## Model Storage

- Default model: `turbo`
- All models loaded with `download_root=<script_dir>/models/`
- `turbo` model pre-downloaded to `models/` before first run (done manually, ~1.6 GB)
- Model change: async reload with "Loading [model]…" status, then persisted to config
- Model selector shows all options regardless of download state; downloads on first use

---

## Config (`config.json`)

```json
{
  "model": "turbo",
  "mute_beeps": false,
  "mic_enabled": true,
  "hotkey": "`",
  "window_x": 100,
  "window_y": 100,
  "expanded": false
}
```

Loaded on startup, written on any change.

---

## ffmpeg Flash Fix

Monkey-patch `subprocess.Popen` before importing `whisper` to suppress console windows on all child processes:

```python
import subprocess, os
if os.name == 'nt':
    _orig_popen = subprocess.Popen.__init__
    def _popen_no_window(self, *args, **kwargs):
        kwargs.setdefault('creationflags', 0)
        kwargs['creationflags'] |= 0x08000000  # CREATE_NO_WINDOW
        _orig_popen(self, *args, **kwargs)
    subprocess.Popen.__init__ = _popen_no_window
```

---

## AHK Changes (`whisper.ahk`)

1. **Multi-instance fix:** Add `DetectHiddenWindows True` so `WinExist("Whisper Transcription")` correctly finds the hidden/withdrawn Python window and doesn't spawn duplicates.
2. **Remove `--bg`:** Window starts visible so no need to hide it on launch.
3. **Mute beeps:** Check `FileExist(MuteFlag)` before each `SoundBeep()` call.
4. **Dynamic hotkey:** Poll for `hotkey_change.flag` in a timer. On detection: read new key from `config.json`, call `Hotkey(oldKey . " Up", "Off")` and `Hotkey(oldKey, "Off")`, then register new bindings.

---

## Flag Files (unchanged + additions)

| File | Writer | Reader | Purpose |
|------|--------|--------|---------|
| `start.flag` | AHK | Python | Begin recording |
| `stop.flag` | AHK | Python | Stop recording |
| `show.flag` | AHK | Python | Show window |
| `output.txt` | Python | AHK | Transcription result |
| `mute.flag` | Python | AHK | Suppress beeps |
| `hotkey_change.flag` | Python | AHK | Trigger hotkey rebind |

---

## Files Changed

| File | Change |
|------|--------|
| `pythonscript.pyw` | Full UI overhaul — customtkinter widget, all new controls, config, icon gen, ffmpeg fix |
| `whisper.ahk` | DetectHiddenWindows, mute check, hotkey change polling, remove --bg |
| `config.json` | New file — persisted settings |
| `icon.ico` | Generated on first run |
| `models/` | Local model storage, turbo pre-downloaded |
| `requirements.txt` | Add `customtkinter` |
