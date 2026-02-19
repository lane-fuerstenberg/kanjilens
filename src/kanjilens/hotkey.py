"""Global hotkey registration for native Windows using ctypes.

Falls back to a no-op on non-Windows platforms.
"""

from __future__ import annotations

import ctypes
import ctypes.wintypes
import sys
import threading
from collections.abc import Callable

# Win32 constants
MOD_CONTROL = 0x0002
MOD_SHIFT = 0x0004
WM_HOTKEY = 0x0312

# Virtual key codes
VK_MAP: dict[str, int] = {
    "a": 0x41, "b": 0x42, "c": 0x43, "d": 0x44, "e": 0x45,
    "f": 0x46, "g": 0x47, "h": 0x48, "i": 0x49, "j": 0x4A,
    "k": 0x4B, "l": 0x4C, "m": 0x4D, "n": 0x4E, "o": 0x4F,
    "p": 0x50, "q": 0x51, "r": 0x52, "s": 0x53, "t": 0x54,
    "u": 0x55, "v": 0x56, "w": 0x57, "x": 0x58, "y": 0x59,
    "z": 0x5A,
}


def _parse_hotkey(hotkey_str: str) -> tuple[int, int]:
    """Parse a hotkey string like 'ctrl+shift+z' into (modifiers, vk)."""
    parts = [p.strip().lower() for p in hotkey_str.split("+")]
    modifiers = 0
    vk = 0
    for part in parts:
        if part == "ctrl":
            modifiers |= MOD_CONTROL
        elif part == "shift":
            modifiers |= MOD_SHIFT
        elif part in VK_MAP:
            vk = VK_MAP[part]
        else:
            raise ValueError(f"Unknown hotkey component: {part}")
    if vk == 0:
        raise ValueError(f"No key found in hotkey string: {hotkey_str}")
    return modifiers, vk


class HotkeyListener:
    """Registers a global hotkey and calls a callback when pressed.

    Usage:
        listener = HotkeyListener("ctrl+shift+z", my_callback)
        listener.start()  # runs message loop in background thread
        ...
        listener.stop()
    """

    def __init__(self, hotkey: str, callback: Callable[[], None]) -> None:
        self._hotkey = hotkey
        self._callback = callback
        self._modifiers, self._vk = _parse_hotkey(hotkey)
        self._thread: threading.Thread | None = None
        self._running = False
        self._hotkey_id = 1

    def start(self) -> None:
        """Start listening for the hotkey in a background thread."""
        if self._thread is not None:
            return
        self._running = True
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        """Stop listening and unregister the hotkey."""
        self._running = False
        if self._thread is not None:
            self._thread.join(timeout=2)
            self._thread = None

    def _run(self) -> None:
        user32 = ctypes.windll.user32  # type: ignore[attr-defined]

        if not user32.RegisterHotKey(None, self._hotkey_id, self._modifiers, self._vk):
            print(
                f"Failed to register hotkey {self._hotkey}. "
                "Is another instance running?",
                file=sys.stderr,
            )
            return

        try:
            msg = ctypes.wintypes.MSG()
            while self._running:
                # PeekMessage with PM_REMOVE so we don't block forever
                if user32.PeekMessageW(
                    ctypes.byref(msg), None, WM_HOTKEY, WM_HOTKEY, 1
                ):
                    if msg.message == WM_HOTKEY:
                        self._callback()
                else:
                    # Avoid busy-waiting
                    import time
                    time.sleep(0.1)
        finally:
            user32.UnregisterHotKey(None, self._hotkey_id)
