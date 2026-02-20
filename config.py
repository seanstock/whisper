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
    for k, v in DEFAULTS.items():
        data.setdefault(k, v)
    return data

def save(cfg: dict) -> None:
    """Write config dict to disk."""
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2)
