# Whisper Transcription Assistant

Optimized for agentic coding workflows; not designed for ADA compliance.

Hold a hotkey anywhere on Windows → release → transcribed text is pasted into the previously active window. Powered by OpenAI Whisper running locally.

## Features

- **Floating widget** — always-on-top dark bar that stays out of the way until you need it
- **Hold-to-record** — hold the hotkey (default: backtick) to record, release to transcribe and paste
- **GPU accelerated** — automatically uses CUDA if an NVIDIA GPU is available, otherwise falls back to CPU
- **Local model storage** — models are saved to the `models/` folder and download on first use
- **In-widget controls** — mic toggle, mute toggle, hotkey rebinder, model selector, expand/collapse, copy button
- **Persistent config** — window position, model choice, mute state, and hotkey survive restarts

## Quick Start (Pre-built)

1. Download the latest release zip from [Releases](https://github.com/seanstock/whisper/releases)
2. Extract it anywhere
3. Run `Whisper Transcription/Whisper Transcription.exe`
4. A shortcut is auto-created in the project folder on first launch

**Requirement:** [FFmpeg](https://ffmpeg.org/) must be on your system PATH (e.g. `choco install ffmpeg -y`).

## Build from Source

1. Clone the repo and create a virtual environment:
   ```powershell
   git clone https://github.com/seanstock/whisper.git
   cd whisper
   python -m venv whisper-env
   .\whisper-env\Scripts\Activate.ps1
   ```
2. Install dependencies:
   ```powershell
   pip install -r requirements.txt
   ```
3. Build the exe:
   ```powershell
   pyinstaller -y --noconsole --onedir --icon=icon.ico --name "Whisper Transcription" --distpath . --collect-all torch --collect-all whisper --collect-data certifi pythonscript.pyw
   ```
4. Run `Whisper Transcription/Whisper Transcription.exe`

## How to Use

1. **Launch the exe** — double-click `Whisper Transcription.exe` (inside the `Whisper Transcription/` folder). A floating widget appears.
2. **Position the widget** — drag it anywhere by its bar. Position is saved on release.
3. **Transcribe** — click into any text field, then hold the hotkey (default: backtick). The dot turns red while recording. Release the key; the dot turns amber while transcribing, then the text is pasted into the window you were in.

## Widget Controls

| Control | Description |
|---|---|
| Status dot | Gray = loading, Green = ready, Red = recording, Amber = transcribing |
| Mic button | Enable or disable recording |
| Mute button | Silence the start/stop beeps |
| Hotkey button | Click, then press any key to reassign the record hotkey |
| Model dropdown | Switch Whisper model (VRAM estimates shown); ★ = recommended |
| Expand/Collapse | Show or hide the transcript text box |
| Copy button | Copy the last transcript to the clipboard |

## Models

| Model | VRAM | Speed | Accuracy |
|---|---|---|---|
| tiny.en | ~1 GB | Fastest | Basic |
| base.en | ~1 GB | Very fast | Good |
| small.en ★ | ~2 GB | Fast | Better |
| medium.en | ~5 GB | Moderate | High |
| turbo ★ | ~6 GB | Fast | High |
| large-v3 | ~10 GB | Slow | Best |

★ = recommended. **small.en** is the best pick for GPUs with 8 GB VRAM or less — fast and accurate for everyday dictation. If you have 10 GB+ VRAM, **turbo** delivers near-large-v3 accuracy at much higher speed. Models download automatically on first use and are stored in the `models/` folder.

## Configuration

Settings are stored in `config.json` (auto-created on first run). You can edit it directly or use the widget controls. Keys: `model`, `hotkey`, `mute_beeps`, `mic_enabled`, `window_x`, `window_y`, `expanded`.
