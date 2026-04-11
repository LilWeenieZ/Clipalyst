"""
startup.py - Windows registry helpers for launch-at-startup.

Uses HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Run so no
administrator privileges are required.

When running as a PyInstaller frozen bundle, ``sys.executable`` is the
packaged .exe.  When running from source, the registry value is NOT
written (startup only makes sense for the installed/released binary).
"""

import sys
import winreg
import logging

log = logging.getLogger(__name__)

_REG_PATH = r"Software\Microsoft\Windows\CurrentVersion\Run"
_REG_NAME = "Clipalyst"


def _resolve_exe() -> str | None:
    """Return the path of the executable that should be registered.

    • Frozen bundle  → sys.executable  (e.g. …\\release\\Clipalyst.exe)
    • Dev / source   → None  (startup from a raw Python interpreter is
                               not useful and would break on the user's
                               machine)
    """
    if getattr(sys, "frozen", False):
        return sys.executable
    return None


def enable_startup(exe_path: str | None = None) -> None:
    """Write a registry value that launches Clipalyst when the user logs in.

    *exe_path* is optional.  When omitted the path is determined
    automatically via :func:`_resolve_exe`.  Logs a warning and returns
    without writing when running from source (no frozen binary available).
    """
    path = exe_path or _resolve_exe()
    if not path:
        log.warning(
            "Startup registration skipped: not running as a frozen executable. "
            "Build and install the release binary first."
        )
        return
    try:
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            _REG_PATH,
            0,
            winreg.KEY_SET_VALUE,
        )
        with key:
            winreg.SetValueEx(key, _REG_NAME, 0, winreg.REG_SZ, path)
        log.info("Startup enabled: %s", path)
    except OSError as exc:
        log.error("Failed to enable startup: %s", exc)
        raise


def disable_startup() -> None:
    """Delete the registry value so Clipalyst no longer launches at login."""
    try:
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            _REG_PATH,
            0,
            winreg.KEY_SET_VALUE,
        )
        with key:
            winreg.DeleteValue(key, _REG_NAME)
        log.info("Startup disabled.")
    except FileNotFoundError:
        # Value was already absent – treat as success.
        log.debug("Startup key was not present; nothing to remove.")
    except OSError as exc:
        log.error("Failed to disable startup: %s", exc)
        raise


def is_startup_enabled() -> bool:
    """Return True if the registry value currently exists."""
    try:
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            _REG_PATH,
            0,
            winreg.KEY_READ,
        )
        with key:
            winreg.QueryValueEx(key, _REG_NAME)
        return True
    except FileNotFoundError:
        return False
    except OSError:
        return False
