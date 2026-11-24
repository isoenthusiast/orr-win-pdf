"""Generate the icon sheet (docs/icon-sheet.png).

    python tools/make_icon_sheet.py

Draws every glyph in `pdfedit/icons.py` in one image, so the icon set can be
reviewed at a glance.
"""
from __future__ import annotations

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tests"))

import tkinter as tk  # noqa: E402

from pdfedit import theme  # noqa: E402
from pdfedit.icons import ICONS, draw_icon  # noqa: E402

OUT = os.path.join(ROOT, "docs", "icon-sheet.png")

COLS = 6
CELL_W = 130
CELL_H = 96


def main() -> None:
    names = sorted(ICONS)
    rows = (len(names) + COLS - 1) // COLS
    width = COLS * CELL_W + 40
    height = rows * CELL_H + 60

    root = tk.Tk()
    root.withdraw()
    win = tk.Toplevel(root)
    win.title("Icon sheet")
    win.configure(bg=theme.SURFACE)
    win.geometry(f"{width}x{height}+40+40")

    cv = tk.Canvas(win, width=width, height=height, bg=theme.SURFACE,
                   highlightthickness=0, bd=0)
    cv.pack()
    fonts = theme.fonts()

    cv.create_text(width / 2, 26, text="PDF Sign & Fill - icon sheet",
                   font=fonts.headline, fill=theme.TEXT)
    cv.create_line(20, 46, width - 20, 46, fill=theme.SEPARATOR)

    for i, name in enumerate(names):
        col, row = i % COLS, i // COLS
        cx = 20 + col * CELL_W + CELL_W / 2
        cy = 70 + row * CELL_H
        cv.create_rectangle(cx - 30, cy - 26, cx + 30, cy + 26,
                            fill=theme.FILL, outline=theme.SEPARATOR)
        draw_icon(cv, name, cx, cy, 30, theme.TEXT)
        cv.create_text(cx, cy + 40, text=name, font=fonts.caption,
                       fill=theme.TEXT_2)

    win.update_idletasks()
    win.update()
    win.lift()
    win.attributes("-topmost", True)
    win.update()

    from screenshot import capture_hwnd
    from PIL import Image

    ok = False
    for hwnd in (int(cv.winfo_id()), int(win.wm_frame(), 16)):
        if capture_hwnd(hwnd, OUT):
            try:
                extrema = Image.open(OUT).convert("L").getextrema()
            except Exception:
                extrema = (0, 0)
            if extrema[1] > 0:
                ok = True
                break
    print(("wrote " if ok else "FAILED to write ") + OUT)
    root.destroy()


if __name__ == "__main__":
    main()
