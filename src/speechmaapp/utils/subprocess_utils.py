from __future__ import annotations

import subprocess
import sys

_PATCHED = False


def ensure_no_cmd_window() -> None:
    global _PATCHED
    if _PATCHED:
        return
    _PATCHED = True

    if sys.platform != "win32":
        return

    create_no_window = 0x08000000
    original_init = subprocess.Popen.__init__

    def patched_init(self, *args, **kwargs):
        creationflags = kwargs.get("creationflags", 0) or 0
        kwargs["creationflags"] = creationflags | create_no_window
        if kwargs.get("startupinfo") is None:
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            startupinfo.wShowWindow = subprocess.SW_HIDE
            kwargs["startupinfo"] = startupinfo
        return original_init(self, *args, **kwargs)

    subprocess.Popen.__init__ = patched_init  # type: ignore[assignment]
