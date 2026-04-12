import sys
import os
from pathlib import Path
from dotenv import load_dotenv

# Base paths
if getattr(sys, "frozen", False):
    # PyInstaller: assets are extracted alongside the executable (in a temp folder)
    BASE_DIR = Path(sys._MEIPASS)          # type: ignore[attr-defined]
else:
    BASE_DIR = Path(__file__).resolve().parent.parent

# Load .env if it exists
load_dotenv(dotenv_path=BASE_DIR / ".env")

# Secondary fallback: check next to the .exe if frozen (not in sys._MEIPASS)
if getattr(sys, "frozen", False):
    EXE_DIR = Path(sys.executable).parent
    env_next_to_exe = EXE_DIR / ".env"
    if env_next_to_exe.exists():
        load_dotenv(dotenv_path=env_next_to_exe, override=True)

# Base paths
if getattr(sys, "frozen", False):
    # User data should be in AppData to avoid permission issues in Program Files
    DATA_ROOT = Path(os.getenv("APPDATA", "")) / "Clipalyst"
else:
    DATA_ROOT = BASE_DIR / "data"

SRC_DIR  = BASE_DIR / "src"
DB_PATH  = DATA_ROOT / "clipboard_history.db"
ICON_PATH = BASE_DIR / "assets" / "icon.ico"

# API Settings
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
GUMROAD_PRODUCT_ID = os.getenv("GUMROAD_PRODUCT_ID", "")
GUMROAD_ACCESS_TOKEN = os.getenv("GUMROAD_ACCESS_TOKEN", "")



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
