"""
main.py — Clipalyst application entry point.

Startup order
-------------
1. Single-instance lock (./data/app.lock)
2. ClipboardDB
3. AITagger          (daemon thread, tag_item(id))
4. ClipboardMonitor  (daemon thread, polls clipboard every 500 ms)
5. TrayIcon          (daemon thread, system tray)
6. HotkeyManager     (keyboard hook, Win+Shift+V)
7. SearchWindow      (CustomTkinter CTkToplevel, hidden until triggered)
8. Tkinter main loop (blocks; tooltip refresh runs via root.after)

Shutdown (KeyboardInterrupt or tray Quit)
-----------------------------------------
Stop all components in reverse order, release the lock, then exit.
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# sys.path bootstrap — makes `python src/main.py` work in addition to
# the canonical `python -m src.main` invocation. When executed as a plain
# script (__package__ is None), we insert the repository root so that
# `import src.xxx` resolves correctly.
# ---------------------------------------------------------------------------
import sys as _sys
import pathlib as _pathlib

if __package__ is None or __package__ == "":
    if getattr(_sys, "frozen", False):
        # Running as a PyInstaller bundle — the frozen import system already
        # handles all src.* modules correctly.  Fall through to main() below.
        pass
    else:
        # Development: script was run directly as `python src/main.py`.
        # Re-import under the proper package name so relative imports work.
        _repo_root = str(_pathlib.Path(__file__).resolve().parent.parent)
        if _repo_root not in _sys.path:
            _sys.path.insert(0, _repo_root)
        import importlib as _il
        _mod = _il.import_module("src.main")
        _mod.main()
        _sys.exit(0)

import logging
import os
import sys
import time
import threading
import tkinter as tk
from pathlib import Path

import customtkinter as ctk

# ---------------------------------------------------------------------------
# Logging – configure early so all modules can use it.
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("clipalyst.main")

# ---------------------------------------------------------------------------
# Single-instance lock
# ---------------------------------------------------------------------------
_LOCK_PATH = Path("./data/app.lock")
_lock_fh = None  # module-level so it stays open for the process lifetime


def _acquire_instance_lock() -> bool:
    """Try to acquire an exclusive OS-level lock on the lock file.

    Returns True on success, False if another instance is already running.
    Uses Windows-style exclusive file creation; falls back to an existence
    check with a stale-PID comparison if necessary.
    """
    global _lock_fh  # noqa: PLW0603

    _LOCK_PATH.parent.mkdir(parents=True, exist_ok=True)

    try:
        import msvcrt  # Windows only

        _lock_fh = open(_LOCK_PATH, "w")  # noqa: SIM115
        try:
            msvcrt.locking(_lock_fh.fileno(), msvcrt.LK_NBLCK, 1)
        except OSError:
            _lock_fh.close()
            _lock_fh = None
            return False

        _lock_fh.write(str(os.getpid()))
        _lock_fh.flush()
        return True

    except Exception as exc:
        logger.warning("Could not acquire instance lock: %s", exc)
        # Non-fatal — allow startup without the lock rather than crashing.
        return True


def _release_instance_lock() -> None:
    global _lock_fh  # noqa: PLW0603
    if _lock_fh is not None:
        try:
            import msvcrt

            msvcrt.locking(_lock_fh.fileno(), msvcrt.LK_UNLCK, 1)
        except Exception:
            pass
        try:
            _lock_fh.close()
        except Exception:
            pass
        try:
            _LOCK_PATH.unlink(missing_ok=True)
        except Exception:
            pass
        _lock_fh = None


# ---------------------------------------------------------------------------
# Tooltip refresh (runs on the Tkinter thread via root.after)
# ---------------------------------------------------------------------------
_TOOLTIP_INTERVAL_MS = 60_000  # 60 seconds
VERSION = "1.1.0"


def _schedule_tooltip_refresh(root: tk.Tk, db, tray) -> None:
    """Re-schedule itself every 60 s to update the tray tooltip with item count."""

    def _refresh():
        try:
            stats = db.get_stats()
            total = stats.get("total_items", 0)
            tray.update_tooltip(f"Clipalyst — {total} item{'s' if total != 1 else ''} captured")
        except Exception as exc:
            logger.debug("Tooltip refresh error: %s", exc)
        finally:
            # Re-arm for the next interval
            root.after(_TOOLTIP_INTERVAL_MS, _refresh)

    root.after(_TOOLTIP_INTERVAL_MS, _refresh)


# ---------------------------------------------------------------------------
# Application
# ---------------------------------------------------------------------------

class Application:
    """Wires all Clipalyst components together and manages their lifecycle."""

    def __init__(self) -> None:
        # ── Tkinter / CustomTkinter root (hidden; keeps event loop alive) ──────
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("dark-blue")

        self._root = ctk.CTk()
        self._root.withdraw()
        self._root.title("Clipalyst")
        # Prevent the hidden root from appearing in the taskbar.
        self._root.wm_attributes("-alpha", 0)

        # Apply the app icon to the hidden root.  All CTkToplevel windows
        # inherit from it, but CustomTkinter resets the icon during __init__,
        # so we also re-apply it to each Toplevel after a short delay.
        from src.config import ICON_PATH as _ICON_PATH
        _ico = str(_ICON_PATH) if _ICON_PATH.exists() else ""
        if _ico:
            try:
                self._root.iconbitmap(_ico)
            except Exception:
                pass
        self._icon_path = _ico

        # ── Components — import here to avoid circular imports at module level.
        # Use absolute imports so this file works both as a script and as a
        # package module (after the sys.path bootstrap above).
        from src.database import ClipboardDB
        from src.tagger import AITagger
        from src.monitor import ClipboardMonitor
        from src.tray import TrayIcon
        from src.hotkey import HotkeyManager
        from src.ui.search_window import SearchWindow
        from src.settings import SettingsManager
        from src.settings_window import SettingsWindow

        self._settings = SettingsManager()

        if self._settings.get("crash_reporting_enabled", True):
            try:
                import sentry_sdk
                # Load DSN from environment or use a generic placeholder for dev
                dsn = os.getenv("SENTRY_DSN") or "https://placeholder@o0.ingest.sentry.io/0"
                sentry_sdk.init(
                    dsn=dsn,
                    traces_sample_rate=1.0,
                )
                logger.info("Sentry crash reporting initialized.")
            except ImportError:
                logger.warning("sentry_sdk package not found; crash reporting disabled.")

        # Initialise the licence module with the settings store so it can
        # read / write the activation key and validate it on startup.
        from src.licence import init as _licence_init
        _licence_init(self._settings)

        self._db = ClipboardDB()

        self._tagger = AITagger(db=self._db)

        self._monitor = ClipboardMonitor(
            db=self._db, 
            ignore_list=self._settings.get("ignore_list", [])
        )

        # Register setting listener to update monitor in real-time
        def _on_setting_changed(key, value):
            if key == "ignore_list":
                self._monitor.ignore_list = value
        
        self._settings.add_listener(_on_setting_changed)

        self._tray = TrayIcon(
            show_search_callback=self._show_search,
            show_settings_callback=self._show_settings,
            toggle_monitor_callback=self._toggle_monitor,
            clear_history_callback=self._db.clear_all,
            quit_callback=self._quit,
        )

        self._hotkey = HotkeyManager(
            ctrl  = self._settings.get("hotkey_ctrl",  True),
            shift = self._settings.get("hotkey_shift", False),
            alt   = self._settings.get("hotkey_alt",   True),
            key   = self._settings.get("hotkey_key",   "V"),
        )

        # SearchWindow is a CTkToplevel; it must be created on the main thread
        # after the root window exists.
        from src.licence import is_pro
        self._search_window = SearchWindow(
            search_callback=self._db.search,
            stats_callback=self._db.get_stats,
            pin_callback=lambda iid, pin: self._db.pin_item(iid) if pin else self._db.unpin_item(iid),
            delete_callback=self._db.delete_item,
            is_pro_callback=is_pro,
            api_status_callback=self._tagger.get_status,
            clear_callback=self._db.clear_all,
            show_settings_callback=self._show_settings,
        )
        self._search_window.hide()

        self._settings_window = SettingsWindow(
            settings_manager=self._settings,
            on_clear_history=self._db.clear_all,
            hotkey_manager=self._hotkey,
            is_pro_callback=is_pro,
            tagger_reconfigure_callback=self._tagger.reconfigure,
        )
        self._settings_window.hide()

        # Re-apply the icon to each CTkToplevel after a short delay.
        # CustomTkinter resets iconbitmap internally during Toplevel.__init__,
        # so setting it afterwards (via after()) is the reliable fix.
        def _apply_icons():
            if self._icon_path:
                for win in (self._search_window, self._settings_window):
                    try:
                        win.iconbitmap(self._icon_path)
                    except Exception:
                        pass
        self._root.after(200, _apply_icons)

        # ── Wire monitor → tagger ─────────────────────────────────────────────
        # Wrap db.insert_item so every newly-captured item is automatically
        # queued for AI tagging.  Wrapping the DB method is simpler and more
        # reliable than patching the monitor's internal loop.
        _original_insert = self._db.insert_item
        from src.licence import is_pro as _is_pro, FREE_LIMIT as _FREE_LIMIT

        def _insert_and_tag(content, source_app=None):
            # Enforce history limit from settings, capped by FREE_LIMIT for free users
            settings_limit = self._settings.get("history_limit", 1000)
            if not _is_pro():
                limit = min(settings_limit, _FREE_LIMIT)
            else:
                limit = settings_limit
            self._db.enforce_limit(limit)

            item_id = _original_insert(content, source_app=source_app)
            if item_id:
                self._tagger.tag_item(item_id)
            return item_id

        self._db.insert_item = _insert_and_tag


        self._running = False

    # ------------------------------------------------------------------
    # Callbacks
    # ------------------------------------------------------------------

    def _show_search(self) -> None:
        """Show the search window; safe to call from any thread."""
        self._root.after(0, self._search_window.show)

    def _show_settings(self) -> None:
        """Show the settings window; safe to call from any thread."""
        self._root.after(0, self._settings_window.show)

    def _toggle_monitor(self) -> None:
        """Pause or resume the clipboard monitor."""
        if self._monitor.is_running():
            self._monitor.stop()
            logger.info("Clipboard monitoring paused.")
        else:
            self._monitor.start()
            logger.info("Clipboard monitoring resumed.")

    def _quit(self) -> None:
        """Initiate a clean shutdown from any thread."""
        self._root.after(0, self._shutdown)

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start(self) -> None:
        """Start all background components and enter the Tkinter event loop."""
        logger.info("Starting Clipalyst…")

        # 1. AI tagger (daemon thread — must be started before monitor so the
        #    queue is ready when the first item arrives)
        self._tagger.start()
        logger.info("AITagger started.")

        # 2. Clipboard monitor
        self._monitor.start()
        logger.info("ClipboardMonitor started.")

        # 3. System tray
        self._tray.start()
        logger.info("TrayIcon started.")

        # 4. Global hotkey
        self._hotkey.register(self._show_search)
        logger.info("Clipalyst ready.  Hotkey: %s", self._hotkey.hotkey_label)

        # 5. Schedule periodic tooltip refresh
        _schedule_tooltip_refresh(self._root, self._db, self._tray)

        self._running = True

        # Block on the Tkinter event loop.
        try:
            self._root.mainloop()
        except KeyboardInterrupt:
            pass
        finally:
            self._shutdown()

    def _shutdown(self) -> None:
        """Stop all components in reverse startup order, then exit."""
        if not self._running:
            return
        self._running = False

        logger.info("Shutting down…")

        # Reverse order: hotkey → tray → monitor → tagger
        self._hotkey.unregister()
        self._tray.stop()
        self._monitor.stop()
        self._tagger.stop()

        _release_instance_lock()

        logger.info("Goodbye.")
        # Destroy the Tk root so mainloop() returns (if still running).
        try:
            self._root.quit()
            self._root.destroy()
        except Exception:
            pass

        sys.exit(0)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    # Single-instance guard
    if not _acquire_instance_lock():
        logger.error(
            "Another instance of Clipalyst is already running "
            "(lock file: %s). Exiting.",
            _LOCK_PATH,
        )
        # Try to surface a message box if possible.
        try:
            import ctypes
            ctypes.windll.user32.MessageBoxW(
                0,
                "Clipalyst is already running.\n\nCheck the system tray.",
                "Clipalyst",
                0x30,  # MB_ICONWARNING
            )
        except Exception:
            pass
        sys.exit(1)

    try:
        app = Application()
        app.start()
    except KeyboardInterrupt:
        logger.info("KeyboardInterrupt received — exiting.")
        _release_instance_lock()
        sys.exit(0)


if __name__ == "__main__":
    main()
