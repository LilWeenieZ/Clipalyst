"""
build.py — Clipalyst build script.

Packages src/main.py into a standalone Windows application using PyInstaller.

Usage
-----
    python build.py

Output
------
  dist/Clipalyst/   — PyInstaller output directory
  release/          — Final distributable (contents of dist/Clipalyst/ copied here)
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

ROOT      = Path(__file__).resolve().parent
ENTRY     = ROOT / "src" / "main.py"
ICON      = ROOT / "assets" / "icon.ico"
APP_NAME  = "Clipalyst"
DIST_DIR  = ROOT / "dist" / APP_NAME
RELEASE   = ROOT / "release"

HIDDEN_IMPORTS = [
    "pystray",
    "pystray._win32",         # platform backend
    "customtkinter",
    "win32con",
    "win32clipboard",
    "win32gui",
    "win32process",
    "keyboard",
    "anthropic",
    "anthropic._client",
    "anthropic.types",
]

# ---------------------------------------------------------------------------
# Pre-flight checks
# ---------------------------------------------------------------------------

def _check_prerequisites() -> None:
    if not ENTRY.exists():
        sys.exit(f"[ERROR] Entry point not found: {ENTRY}")
    if not ICON.exists():
        sys.exit(f"[ERROR] Icon file not found: {ICON}")

    try:
        import PyInstaller  # noqa: F401
    except ImportError:
        sys.exit(
            "[ERROR] PyInstaller is not installed.\n"
            "Run:  pip install pyinstaller  (or activate your venv first)"
        )

# ---------------------------------------------------------------------------
# Build
# ---------------------------------------------------------------------------

def _run_pyinstaller() -> None:
    hidden = []
    for imp in HIDDEN_IMPORTS:
        hidden.extend(["--hidden-import", imp])

    import os
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--noconfirm",           # overwrite previous build without asking
        "--clean",               # remove PyInstaller cache before building
        "--onedir",              # directory output (faster startup than --onefile)
        "--windowed",            # no console window
        f"--name={APP_NAME}",
        f"--icon={ICON}",
        # Bundle assets/ so icon.ico is available under sys._MEIPASS/assets/
        f"--add-data={ICON}{os.pathsep}assets",
        *hidden,
        str(ENTRY),
    ]

    print(f"\n[build] Running PyInstaller for '{APP_NAME}'…")
    print(f"[build] Command: {' '.join(cmd)}\n")

    result = subprocess.run(cmd, cwd=ROOT)
    if result.returncode != 0:
        sys.exit(f"[ERROR] PyInstaller exited with code {result.returncode}")

# ---------------------------------------------------------------------------
# Copy to release/
# ---------------------------------------------------------------------------

def _copy_to_release() -> None:
    if not DIST_DIR.exists():
        sys.exit(f"[ERROR] Expected dist output not found: {DIST_DIR}")

    if RELEASE.exists():
        print(f"[build] Removing existing release directory: {RELEASE}")
        shutil.rmtree(RELEASE)

    print(f"[build] Copying {DIST_DIR} -> {RELEASE}")
    shutil.copytree(DIST_DIR, RELEASE)
    print(f"[build] Release ready at: {RELEASE}")

# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    print(f"[build] Clipalyst build script starting…")
    print(f"[build] Root:  {ROOT}")
    print(f"[build] Entry: {ENTRY}")
    print(f"[build] Icon:  {ICON}")

    _check_prerequisites()
    _run_pyinstaller()
    _copy_to_release()

    print(f"\n[build] Build complete.  Distributable: {RELEASE}")


if __name__ == "__main__":
    main()
