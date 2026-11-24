"""Verify a packaged build:  python tools/verify_exe.py

1. runs the exe headless (--selftest) and checks the PDF it writes
2. launches the GUI, waits for the window and captures a screenshot

Both prove the frozen bundle has everything it needs - the PyMuPDF DLLs, the
Tk runtime, Pillow's ImageTk and the app icon.
"""
from __future__ import annotations

import ctypes
import os
import subprocess
import sys
import time
from ctypes import wintypes

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tests"))

from screenshot import capture_hwnd  # noqa: E402

EXE = os.path.join(ROOT, "dist", "PDF Sign and Fill.exe")
DEMO = os.path.join(ROOT, "demo_form.pdf")
OUT = os.path.join(ROOT, "build_selftest.pdf")
SHOT = os.path.join(ROOT, "exe_screenshot.png")

user32 = ctypes.windll.user32


def find_window(title_part: str) -> int:
    """HWND of the first visible top-level window whose title matches."""
    found = []

    @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    def cb(hwnd, _lparam):
        if not user32.IsWindowVisible(hwnd):
            return True
        length = user32.GetWindowTextLengthW(hwnd)
        if length:
            buf = ctypes.create_unicode_buffer(length + 1)
            user32.GetWindowTextW(hwnd, buf, length + 1)
            if title_part.lower() in buf.value.lower():
                found.append(hwnd)
                return False
        return True

    user32.EnumWindows(cb, 0)
    return found[0] if found else 0


def kill_tree(proc) -> None:
    """Kill the exe *and* its children.

    A PyInstaller onefile exe runs as a parent process that unpacks the bundle
    and spawns a child; killing only the parent leaves the child holding the
    file lock (and the window open).
    """
    subprocess.run(["taskkill", "/F", "/T", "/PID", str(proc.pid)],
                   capture_output=True)
    try:
        proc.wait(timeout=30)
    except Exception:
        pass


def check_selftest() -> bool:
    if not os.path.exists(EXE):
        print(f"FAIL: exe not found at {EXE}")
        return False
    if os.path.exists(OUT):
        os.remove(OUT)
    proc = subprocess.run([EXE, "--selftest", DEMO, OUT],
                          capture_output=True, timeout=180)
    ok = os.path.exists(OUT)
    print(f"selftest exit={proc.returncode} output_written={ok}")
    if ok:
        import pymupdf
        chk = pymupdf.open(OUT)
        text = chk[0].get_text()
        chk.close()
        has_text = "Self Test OK" in text
        print(f"  text present in exported PDF: {has_text}")
        return has_text
    return False


def check_gui() -> bool:
    proc = subprocess.Popen([EXE, DEMO])
    hwnd = 0
    for _ in range(60):
        time.sleep(0.5)
        hwnd = find_window("PDF Sign & Fill")
        if hwnd:
            break
    if not hwnd:
        print("FAIL: no window appeared")
        kill_tree(proc)
        return False
    time.sleep(2.5)
    ok = capture_hwnd(hwnd, SHOT)
    kill_tree(proc)
    print(f"gui window found, screenshot={ok} -> {SHOT}")
    if ok:
        from PIL import Image
        img = Image.open(SHOT)
        extrema = img.convert("L").getextrema()
        print(f"  screenshot {img.size} brightness {extrema}")
        return extrema[1] > 0
    return False


if __name__ == "__main__":
    results = [("selftest", check_selftest()), ("gui", check_gui())]
    print()
    for name, ok in results:
        print(f"{'PASS' if ok else 'FAIL'}  {name}")
    sys.exit(0 if all(ok for _, ok in results) else 1)
