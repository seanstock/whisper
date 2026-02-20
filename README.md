# Whisper Transcription Assistant

Optimized for agentic coding workflows; not designed for ADA compliance.

Hold a hotkey anywhere on Windows → release → transcribed text is pasted into the previously active window. Powered by OpenAI Whisper running locally.

## Features

- **Floating widget** — always-on-top dark bar that stays out of the way until you need it
- **Hold-to-record** — hold the hotkey (default: backtick) to record, release to transcribe and paste
- **GPU accelerated** — automatically uses CUDA if an NVIDIA GPU is available, otherwise falls back to CPU
- **Local model storage** — models are saved to the `models/` folder; turbo is pre-downloaded, others download on first use
- **In-widget controls** — mic toggle, mute toggle, hotkey rebinder, model selector, expand/collapse, copy button
- **Persistent config** — window position, model choice, mute state, and hotkey survive restarts

## Prerequisites

1. **Python 3.9+** — must be on your system PATH
2. **AutoHotkey v2** — [autohotkey.com](https://www.autohotkey.com/)
3. **FFmpeg** — required by Whisper for audio processing:
   ```powershell
   choco install ffmpeg -y
   ```

## Setup

1. Clone or download the repository.
2. Create and activate a virtual environment:
   ```powershell
   python -m venv whisper-env
   .\whisper-env\Scripts\Activate.ps1
   ```
3. Install dependencies:
   ```powershell
   pip install -r requirements.txt
   ```

## How to Use

1. **Start the script** — double-click `whisper.ahk`. An AHK icon appears in the system tray and the floating widget opens automatically.
2. **Position the widget** — drag it anywhere by its title bar. Position is saved on release.
3. **Transcribe** — click into any text field, then hold the hotkey (default: backtick). The dot turns red while recording. Release the key; the dot turns amber while transcribing, then the text is pasted into the window you were in.
4. **Show the widget** — press `Alt+G` if you closed or lost the widget.

## Widget Controls

| Control | Description |
|---|---|
| Status dot | Gray = loading, Green = ready, Red = recording, Amber = transcribing |
| Mic button (🎤) | Enable or disable recording |
| Mute button (🔊/🔇) | Silence the start/stop beeps |
| Hotkey button (⌨) | Click, then press any key to reassign the record hotkey |
| Model dropdown | Switch Whisper model; new model loads immediately |
| Expand/Collapse (▼/▲) | Show or hide the transcript text box |
| Copy button | Copy the last transcript to the clipboard |
| X button | Hide the widget (it keeps running; use Alt+G to restore) |

## Models

| Model | Speed | Accuracy | Notes |
|---|---|---|---|
| turbo | Fastest | High | Pre-downloaded to `models/` |
| medium.en | Fast | High | English only |
| small.en | Very fast | Good | English only |
| base.en | Fastest | Adequate | English only |
| large-v3 | Slow | Best | Downloads on first use (~3 GB) |

All models are stored in the `models/` folder. Switching models in the dropdown triggers an immediate download if the model is not already cached.

## Configuration

Settings are stored in `config.json` (auto-created on first run). You can edit it directly or use the widget controls. Keys: `model`, `hotkey`, `mute_beeps`, `mic_enabled`, `window_x`, `window_y`, `expanded`.
