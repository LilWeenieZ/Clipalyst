import sys
import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env if it exists
load_dotenv()

# Base paths
if getattr(sys, "frozen", False):
    # PyInstaller: assets are extracted alongside the executable
    BASE_DIR = Path(sys._MEIPASS)          # type: ignore[attr-defined]
else:
    BASE_DIR = Path(__file__).resolve().parent.parent

SRC_DIR  = BASE_DIR / "src"
DB_PATH  = BASE_DIR / "clipboard_history.db"
ICON_PATH = BASE_DIR / "assets" / "icon.ico"

# API Settings
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
AI_MODEL = "claude-4-5-haiku"

# App Settings
REFRESH_INTERVAL_MS = 500
MAX_HISTORY_ITEMS = 1000
HOTKEY = "ctrl+alt+v"

# UI Settings
THEME_COLOR = "#2563eb"   # Electric Blue
BG_COLOR = "#0a0a0a"      # True near-black
ACCENT_COLOR = "#1d4ed8"  # Darker Blue
TEXT_COLOR = "#f0f0f0"    # Off-white
