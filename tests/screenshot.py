"""Capture a Tk window to a PNG without relying on the desktop compositor.

``PIL.ImageGrab.grab()`` reads the screen, which returns a black frame when
the session is not actively painting.  ``PrintWindow`` asks the window to
render itself into a bitmap, so it works even then.
"""
from __future__ import annotations

import ctypes
from ctypes import wintypes


class BITMAPINFOHEADER(ctypes.Structure):
    _fields_ = [
        ("biSize", wintypes.DWORD),
        ("biWidth", wintypes.LONG),
        ("biHeight", wintypes.LONG),
        ("biPlanes", wintypes.WORD),
        ("biBitCount", wintypes.WORD),
        ("biCompression", wintypes.DWORD),
        ("biSizeImage", wintypes.DWORD),
        ("biXPelsPerMeter", wintypes.LONG),
        ("biYPelsPerMeter", wintypes.LONG),
        ("biClrUsed", wintypes.DWORD),
        ("biClrImportant", wintypes.DWORD),
    ]


class BITMAPINFO(ctypes.Structure):
    _fields_ = [("bmiHeader", BITMAPINFOHEADER), ("bmiColors", wintypes.DWORD * 3)]


user32 = ctypes.windll.user32
gdi32 = ctypes.windll.gdi32


def capture_hwnd(hwnd: int, path: str) -> bool:
    """Write the window's contents to ``path``.  True on success."""
    rect = wintypes.RECT()
    if not user32.GetWindowRect(hwnd, ctypes.byref(rect)):
        return False
    w = rect.right - rect.left
    h = rect.bottom - rect.top
    if w <= 0 or h <= 0:
        return False

    hdc = user32.GetWindowDC(hwnd)
    mdc = gdi32.CreateCompatibleDC(hdc)
    bmp = gdi32.CreateCompatibleBitmap(hdc, w, h)
    gdi32.SelectObject(mdc, bmp)

    # PW_RENDERFULLCONTENT (2) captures composited/DWM content too
    ok = user32.PrintWindow(hwnd, mdc, 2)
    if not ok:
        ok = user32.PrintWindow(hwnd, mdc, 0)

    header = BITMAPINFO()
    header.bmiHeader.biSize = ctypes.sizeof(BITMAPINFOHEADER)
    header.bmiHeader.biWidth = w
    header.bmiHeader.biHeight = -h          # top-down
    header.bmiHeader.biPlanes = 1
    header.bmiHeader.biBitCount = 32
    header.bmiHeader.biCompression = 0      # BI_RGB

    buf = ctypes.create_string_buffer(w * h * 4)
    got = gdi32.GetDIBits(mdc, bmp, 0, h, buf, ctypes.byref(header), 0)

    gdi32.DeleteObject(bmp)
    gdi32.DeleteDC(mdc)
    user32.ReleaseDC(hwnd, hdc)

    if not got:
        return False

    from PIL import Image
    img = Image.frombuffer("RGBA", (w, h), buf, "raw", "BGRA", 0, 1)
    img.convert("RGB").save(path)
    return True


def capture_tk(widget, path: str) -> bool:
    """Capture a Tk toplevel (or any widget) to ``path``."""
    try:
        widget.update_idletasks()
        widget.update()
    except Exception:
        pass
    hwnd = int(widget.wm_frame(), 16) if widget.winfo_toplevel() is widget \
        else int(widget.winfo_id())
    if capture_hwnd(hwnd, path):
        return True
    # fall back to a screen grab
    try:
        from PIL import ImageGrab
        x = widget.winfo_rootx()
        y = widget.winfo_rooty()
        img = ImageGrab.grab(bbox=(x, y, x + widget.winfo_width(),
                                  y + widget.winfo_height()))
        if img.convert("L").getextrema()[1] > 0:
            img.save(path)
            return True
    except Exception:
        pass
    return False
