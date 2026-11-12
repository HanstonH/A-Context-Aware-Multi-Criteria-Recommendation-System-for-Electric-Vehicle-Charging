"""
Global F-key listener (Windows) to recenter SUMO-GUI on the main vehicle.
"""
from __future__ import annotations

import ctypes
import sys
import threading
import time
from ctypes import wintypes

WM_HOTKEY = 0x0312
PM_REMOVE = 0x0001
MOD_NOREPEAT = 0x4000
VK_F = 0x46
HOTKEY_ID = 0x4D43  # "MC"


class MainVehicleHotkey:
    """Press F anywhere (including while SUMO-GUI is focused) to request recenter."""

    def __init__(self) -> None:
        self._requested = threading.Event()
        self._thread: threading.Thread | None = None
        self._registered = False
        self._user32 = ctypes.windll.user32 if sys.platform == "win32" else None

    def start(self) -> bool:
        if self._user32 is None or self._thread is not None:
            return False
        ok = bool(
            self._user32.RegisterHotKey(None, HOTKEY_ID, MOD_NOREPEAT, VK_F)
        )
        self._registered = ok
        if not ok:
            return False
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()
        return True

    def _loop(self) -> None:
        msg = wintypes.MSG()
        while self._registered:
            while self._user32.PeekMessageW(ctypes.byref(msg), None, 0, 0, PM_REMOVE):
                if msg.message == WM_HOTKEY and msg.wParam == HOTKEY_ID:
                    self._requested.set()
            time.sleep(0.03)

    def consume(self) -> bool:
        if self._requested.is_set():
            self._requested.clear()
            return True
        return False

    def stop(self) -> None:
        if self._user32 is not None and self._registered:
            self._user32.UnregisterHotKey(None, HOTKEY_ID)
        self._registered = False
