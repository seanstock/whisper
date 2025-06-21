# Whisper Transcription Assistant

This project replaces the default Windows speech-to-text functionality with a more powerful, accurate, and customizable transcription tool powered by OpenAI's Whisper model. It uses an AutoHotkey script to launch a stylish Python GUI, allowing for fast and efficient voice-to-text input in any application.

## Features

- **High-Quality Transcription:** Leverages the power of the Whisper `medium.en` model for accurate English transcription.
- **GPU Accelerated:** Automatically detects and uses a CUDA-enabled NVIDIA GPU for significantly faster transcription.
- **Stylish & Interactive GUI:** A clean, modern dark-themed interface that is launched via a system-wide hotkey.
- **Persistent & Reusable:** The transcription window can remain open for multiple back-to-back recordings.
- **Hotkey Integration:** Uses AutoHotkey (`!g` / `Alt+G`) to seamlessly launch the interface and send the final text to your active window.

## Prerequisites

1.  **Python 3.9+:** Make sure it's added to your system's PATH.
2.  **AutoHotkey v2:** The script is written for AutoHotkey v2.x. Can be downloaded from [autohotkey.com](https://www.autohotkey.com/).
3.  **FFmpeg:** A command-line tool required by Whisper for audio processing. The easiest way to install it is with the Chocolatey package manager:
    ```powershell
    choco install ffmpeg -y
    ```

## Setup

1.  **Clone or download the repository.**
2.  **Create a Python Virtual Environment:** Open a terminal in the project directory and run:
    ```powershell
    python -m venv whisper-env
    ```
3.  **Activate the Virtual Environment:**
    ```powershell
    .\whisper-env\Scripts\Activate.ps1
    ```
4.  **Install Python Packages:** With the virtual environment active, install all required packages from the `requirements.txt` file:
    ```powershell
    pip install -r requirements.txt
    ```

## How to Use

1.  **Run the Hotkey Script:** Double-click the `whisper.ahk` file. You will see an "H" icon appear in your system tray, which means the script is active.
2.  **Launch the GUI:** Click into any text field (in a web browser, notepad, etc.) and press `Alt+G`. The Whisper Transcription window will appear.
3.  **Record Your Voice:**
    - Click the **Record** button to start recording. The button will turn red.
    - Click the **Stop** button when you are finished.
4.  **Transcribe:** The application will transcribe your audio. This may take a moment, especially the first time. The transcribed text will appear in the text box.
5.  **Send Text:**
    - Click the **Send to Active Window** button.
    - The text will be typed into the window you were in before you launched the app.
    - By default, the transcription window will remain open, ready for another recording. Uncheck the "Keep window open" box if you want it to close automatically after sending text.

## Configuration

- **Change Whisper Model:** You can change the model size (e.g., to `base.en`, `small.en`, or `large`) by editing the `MODEL_SIZE` variable at the top of the `pythonscript.pyw` file. 