"""
tray.py — System tray icon for Clipalyst.

Creates a 64×64 programmatic clipboard icon and exposes a right-click menu
with open, pause/resume monitoring, clear history, and quit actions.
"""

from __future__ import annotations

import ctypes
import sys
import threading
from pathlib import Path
from typing import Callable, Optional

import pystray
from PIL import Image, ImageDraw


# ---------------------------------------------------------------------------
# Icon path resolution (dev + PyInstaller frozen)
# ---------------------------------------------------------------------------

def _assets_dir() -> Path:
    """Return the assets/ directory regardless of execution context."""
    if getattr(sys, "frozen", False):
        # PyInstaller extracts files under sys._MEIPASS
        return Path(sys._MEIPASS) / "assets"  # type: ignore[attr-defined]
    # Development: assets/ sits next to the src/ package directory
    return Path(__file__).resolve().parent.parent / "assets"


# ---------------------------------------------------------------------------
# Icon generation
# ---------------------------------------------------------------------------

def _build_icon_image(size: int = 64) -> Image.Image:
    """Draw a simple clipboard icon on a dark background."""
    img = Image.new("RGBA", (size, size), (30, 30, 30, 255))
    draw = ImageDraw.Draw(img)

    # Proportional measurements
    pad = size // 8                    # outer padding
    clip_l = pad
    clip_r = size - pad
    clip_t = size // 5
    clip_b = size - pad
    clip_w = size // 20 + 1            # line width
    corner = size // 10

    # --- Clipboard body (rounded-rect outline) ---
    draw.rounded_rectangle(
        [clip_l, clip_t, clip_r, clip_b],
        radius=corner,
        outline=(220, 220, 220, 255),
        width=clip_w,
    )

    # --- Clip tab at the top-centre ---
    tab_w = size // 4
    tab_h = size // 8
    tab_l = (size - tab_w) // 2
    tab_r = tab_l + tab_w
    tab_t = pad // 2
    tab_b = clip_t + tab_h // 2

    draw.rounded_rectangle(
        [tab_l, tab_t, tab_r, tab_b],
        radius=corner // 2,
        outline=(220, 220, 220, 255),
        width=clip_w,
        fill=(30, 30, 30, 255),
    )

    # --- Three horizontal lines representing text ---
    line_x1 = clip_l + size // 8
    line_x2 = clip_r - size // 8
    line_color = (180, 180, 180, 255)
    lw = max(1, size // 32)

    y_start = clip_t + size // 4
    spacing = size // 9
    for i in range(3):
        y = y_start + i * spacing
        draw.line([(line_x1, y), (line_x2, y)], fill=line_color, width=lw)

    return img


# ---------------------------------------------------------------------------
# TrayIcon
# ---------------------------------------------------------------------------

class TrayIcon:
    """Manages the system tray icon and its context menu.

    Parameters
    ----------
    show_search_callback:
        Called when the user clicks "Open Clipalyst".
    toggle_monitor_callback:
        Called when the user toggles "Pause / Resume monitoring".
    quit_callback:
        Called when the user clicks "Quit". If *None*, ``sys.exit`` is used.
    """

    _TOOLTIP_BASE = "Clipalyst"

    def __init__(
        self,
        show_search_callback: Callable[[], None],
        show_settings_callback: Callable[[], None],
        toggle_monitor_callback: Callable[[], None],
        clear_history_callback: Callable[[], None],
        quit_callback: Optional[Callable[[], None]] = None,
    ) -> None:
        self._show_search = show_search_callback
        self._show_settings = show_settings_callback
        self._toggle_monitor = toggle_monitor_callback
        self._clear_history = clear_history_callback
        self._quit_callback = quit_callback

        self._monitoring: bool = True          # tracks current monitor state
        self._icon: Optional[pystray.Icon] = None
        self._thread: Optional[threading.Thread] = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def start(self) -> None:
        """Create the tray icon and run it in a background daemon thread."""
        ico_path = _assets_dir() / "icon.ico"
        try:
            image = Image.open(ico_path)
            # Use the largest available size in the .ico for best quality
            image.load()
        except Exception:
            # Fall back to the programmatic icon if the file is missing
            image = _build_icon_image()
        menu = self._build_menu()

        self._icon = pystray.Icon(
            name="Clipalyst",
            icon=image,
            title=self._TOOLTIP_BASE,
            menu=menu,
        )

        self._thread = threading.Thread(
            target=self._icon.run,
            name="tray-thread",
            daemon=True,
        )
        self._thread.start()

    def update_tooltip(self, text: str) -> None:
        """Update the tray icon tooltip, e.g. 'Clipalyst — 142 items captured'."""
        if self._icon is not None:
            self._icon.title = text

    def stop(self) -> None:
        """Stop the tray icon (removes it from the system tray)."""
        if self._icon is not None:
            self._icon.stop()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _build_menu(self) -> pystray.Menu:
        return pystray.Menu(
            pystray.MenuItem(
                "Open Clipalyst",
                self._on_open,
                default=True,
            ),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem(
                self._monitor_label,
                self._on_toggle_monitor,
            ),
            pystray.MenuItem(
                "Settings",
                self._on_settings,
            ),
            pystray.MenuItem(
                "Clear history",
                self._on_clear_history,
            ),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem(
                "Quit",
                self._on_quit,
            ),
        )

    # pystray calls item text callables each time the menu is shown, so this
    # acts as a dynamic label for the pause/resume toggle.
    def _monitor_label(self, _item: pystray.MenuItem) -> str:
        return "Resume monitoring" if not self._monitoring else "Pause monitoring"

    def _on_open(self, _icon: pystray.Icon, _item: pystray.MenuItem) -> None:
        self._show_search()

    def _on_settings(self, _icon: pystray.Icon, _item: pystray.MenuItem) -> None:
        self._show_settings()

    def _on_toggle_monitor(
        self, _icon: pystray.Icon, _item: pystray.MenuItem
    ) -> None:
        self._monitoring = not self._monitoring
        self._toggle_monitor()

    def _on_clear_history(
        self, _icon: pystray.Icon, _item: pystray.MenuItem
    ) -> None:
        """Show a Win32 confirmation dialog before clearing history.

        Uses ``MessageBoxW`` instead of ``tkinter.messagebox`` to avoid
        creating a second ``tk.Tk()`` root from a non-Tkinter thread.
        """
        MB_YESNO       = 0x04
        MB_ICONWARNING = 0x30
        IDYES          = 6

        result = ctypes.windll.user32.MessageBoxW(
            0,
            "Are you sure you want to clear all clipboard history?\nThis cannot be undone.",
            "Clear history",
            MB_YESNO | MB_ICONWARNING,
        )
        if result == IDYES:
            self._clear_history()
            self.update_tooltip(f"{self._TOOLTIP_BASE} — history cleared")

    def _on_quit(self, _icon: pystray.Icon, _item: pystray.MenuItem) -> None:
        self.stop()
        if self._quit_callback is not None:
            self._quit_callback()
        else:
            import sys  # noqa: PLC0415
            sys.exit(0)
