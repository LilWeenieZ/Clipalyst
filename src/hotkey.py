"""
hotkey.py — Native Windows global hotkey management for Clipalyst.

Registers a configurable hotkey (default Ctrl+Alt+V) using native Windows
APIs (ctypes + win32con) to avoid requiring Administrator privileges.
"""

import ctypes
from ctypes import wintypes
import logging
import threading
import win32con
from typing import Callable, Optional

logger = logging.getLogger(__name__)

_HOTKEY_ID = 1


def _build_mods(ctrl: bool, shift: bool, alt: bool) -> int:
    """Build a Windows MOD_* bitmask from boolean modifier flags."""
    mods = 0
    if ctrl:
        mods |= win32con.MOD_CONTROL
    if shift:
        mods |= win32con.MOD_SHIFT
    if alt:
        mods |= win32con.MOD_ALT
    return mods


def _key_to_vk(key: str) -> int:
    """Convert a single-character or named key string to a Windows virtual-key code.

    Supports single letters/digits and common named keys.
    Returns 0 if the key is not recognised.
    """
    key = key.strip().upper()
    if len(key) == 1:
        # VkKeyScanW returns the VK code in the low byte
        vk = ctypes.windll.user32.VkKeyScanW(ord(key)) & 0xFF
        return vk if vk != 0xFF else 0
    # Named keys
    named = {
        "F1": win32con.VK_F1,  "F2": win32con.VK_F2,  "F3": win32con.VK_F3,
        "F4": win32con.VK_F4,  "F5": win32con.VK_F5,  "F6": win32con.VK_F6,
        "F7": win32con.VK_F7,  "F8": win32con.VK_F8,  "F9": win32con.VK_F9,
        "F10": win32con.VK_F10, "F11": win32con.VK_F11, "F12": win32con.VK_F12,
        "TAB": win32con.VK_TAB, "SPACE": win32con.VK_SPACE,
        "HOME": win32con.VK_HOME, "END": win32con.VK_END,
        "PGUP": win32con.VK_PRIOR, "PGDN": win32con.VK_NEXT,
        "INSERT": win32con.VK_INSERT, "DELETE": win32con.VK_DELETE,
    }
    return named.get(key, 0)


class HotkeyManager:
    """Manages a single configurable global hotkey using native Windows APIs.

    Parameters
    ----------
    ctrl, shift, alt:
        Modifier flags (default: Ctrl+Alt).
    key:
        Trigger key character or name (default: 'V').
    """

    def __init__(
        self,
        ctrl: bool = True,
        shift: bool = False,
        alt: bool = True,
        key: str = "V",
    ) -> None:
        self._ctrl  = ctrl
        self._shift = shift
        self._alt   = alt
        self._key   = key

        self._callback: Optional[Callable[[], None]] = None
        self._thread:   Optional[threading.Thread]   = None
        self._stop_event = threading.Event()
        self._lock = threading.Lock()

    # ------------------------------------------------------------------
    # Public helpers
    # ------------------------------------------------------------------

    @property
    def hotkey_label(self) -> str:
        """Human-readable representation of the current hotkey."""
        parts = []
        if self._ctrl:  parts.append("Ctrl")
        if self._alt:   parts.append("Alt")
        if self._shift: parts.append("Shift")
        parts.append(self._key.upper())
        return "+".join(parts)

    def reconfigure(
        self,
        ctrl: bool,
        shift: bool,
        alt: bool,
        key: str,
        callback: Optional[Callable[[], None]] = None,
    ) -> bool:
        """Change the hotkey combo on the fly.

        Unregisters the current hotkey, stores the new config, then
        re-registers using the existing (or supplied) callback.
        Returns True on success.
        """
        cb = callback or self._callback
        self.unregister()
        self._ctrl  = ctrl
        self._shift = shift
        self._alt   = alt
        self._key   = key
        if cb:
            return self.register(cb)
        return True

    # ------------------------------------------------------------------
    # Core register / unregister
    # ------------------------------------------------------------------

    def register(self, callback: Callable[[], None]) -> bool:
        """Register the global hotkey and attach *callback*."""
        with self._lock:
            if self.is_registered:
                logger.debug("Hotkey already registered; ignoring duplicate call.")
                return True

            self._callback = callback
            self._stop_event.clear()

            self._thread = threading.Thread(
                target=self._run_message_loop,
                daemon=True,
                name="HotkeyThread",
            )
            self._thread.start()
            return True

    def unregister(self) -> None:
        """Unregister the global hotkey."""
        with self._lock:
            if not self.is_registered:
                return

            self._stop_event.set()
            if self._thread and self._thread.is_alive():
                self._thread.join(timeout=1.0)

            self._thread = None
            logger.info("Global hotkey unregistration requested.")

    @property
    def is_registered(self) -> bool:
        """True if the hotkey listener thread is active."""
        return self._thread is not None and self._thread.is_alive()

    # ------------------------------------------------------------------
    # Internal message loop
    # ------------------------------------------------------------------

    def _run_message_loop(self) -> None:
        """Loop running in a background thread to receive Windows messages."""
        user32 = ctypes.windll.user32

        mods = _build_mods(self._ctrl, self._shift, self._alt)
        vk   = _key_to_vk(self._key)

        if vk == 0:
            logger.error("Could not resolve virtual-key code for key %r; hotkey not registered.", self._key)
            return

        if not user32.RegisterHotKey(None, _HOTKEY_ID, mods, vk):
            logger.error(
                "Could not register global hotkey (%s) natively. "
                "Another application might be using it.",
                self.hotkey_label,
            )
            return

        logger.info("Global hotkey registered: %s (Native API, no admin required)", self.hotkey_label)

        try:
            msg = wintypes.MSG()
            while not self._stop_event.is_set():
                # PM_REMOVE = 1
                if user32.PeekMessageW(ctypes.byref(msg), None, 0, 0, 1):
                    if msg.message == win32con.WM_HOTKEY and msg.wParam == _HOTKEY_ID:
                        if self._callback:
                            try:
                                self._callback()
                            except Exception as exc:
                                logger.exception("Exception in hotkey callback: %s", exc)

                    user32.TranslateMessage(ctypes.byref(msg))
                    user32.DispatchMessageW(ctypes.byref(msg))
                else:
                    self._stop_event.wait(0.01)
        finally:
            user32.UnregisterHotKey(None, _HOTKEY_ID)
            logger.debug("Native hotkey unregistered internally.")
