"""Vector icons drawn straight onto a Tk canvas.

No icon font, no image assets - just geometry, so every glyph shares the same
optical weight, stroke width and rounded caps.
"""
from __future__ import annotations

import math
import tkinter as tk

# Icons are authored in a 24x24 box and scaled to the requested size.
_STROKE = 1.9


def _pts(cx, cy, size, pts):
    """Scale 24x24 design coordinates into canvas pixels."""
    k = size / 24.0
    return [(cx + (x - 12) * k, cy + (y - 12) * k) for x, y in pts]


def _line(cv, cx, cy, size, pts, color, width, smooth=False, cap="round"):
    flat = _pts(cx, cy, size, pts)
    coords = [v for pair in flat for v in pair]
    return cv.create_line(*coords, fill=color, width=width, capstyle=cap,
                          joinstyle="round", smooth=smooth)


def _poly(cv, cx, cy, size, pts, color, outline=None, width=1):
    flat = _pts(cx, cy, size, pts)
    coords = [v for pair in flat for v in pair]
    return cv.create_polygon(coords, fill=color, outline=outline or "",
                             width=width, joinstyle="round")


def _rect(cv, cx, cy, size, box, color, outline="", width=1):
    x0, y0, x1, y1 = box
    flat = _pts(cx, cy, size, [(x0, y0), (x1, y1)])
    return cv.create_rectangle(flat[0][0], flat[0][1], flat[1][0], flat[1][1],
                               fill=color, outline=outline, width=width)


# ------------------------------------------------------------------ icons

def _cursor(cv, cx, cy, size, color, w):
    pts = [(7, 3), (7, 19), (11, 15), (14, 21), (17, 19.5), (14, 14),
           (19, 14)]
    _poly(cv, cx, cy, size, pts, color)


def _text(cv, cx, cy, size, color, w):
    _rect(cv, cx, cy, size, (5.5, 6, 18.5, 9), color)
    _rect(cv, cx, cy, size, (10.6, 6, 13.4, 18), color)


def _check(cv, cx, cy, size, color, w):
    _line(cv, cx, cy, size, [(4.5, 12.5), (9.5, 17.5), (19.5, 6.5)],
          color, w)


def _cross(cv, cx, cy, size, color, w):
    _line(cv, cx, cy, size, [(6, 6), (18, 18)], color, w)
    _line(cv, cx, cy, size, [(18, 6), (6, 18)], color, w)


def _signature(cv, cx, cy, size, color, w):
    _line(cv, cx, cy, size,
          [(3, 16), (7.5, 7), (11, 15), (14.5, 7.5), (18, 14), (21, 9)],
          color, w, smooth=True)
    _line(cv, cx, cy, size, [(4, 19.5), (20, 19.5)], color, w * 0.8)


def _folder(cv, cx, cy, size, color, w):
    # outlined folder: a tab on the left, body to the right
    _line(cv, cx, cy, size,
          [(3.5, 19), (3.5, 6.5), (9.5, 6.5), (12, 9.5), (20.5, 9.5),
           (20.5, 19), (3.5, 19)], color, w)


def _save(cv, cx, cy, size, color, w):
    # "export" metaphor: arrow down into a tray
    _line(cv, cx, cy, size, [(12, 3.5), (12, 14)], color, w)
    _line(cv, cx, cy, size, [(7.5, 9.5), (12, 14), (16.5, 9.5)], color, w)
    _line(cv, cx, cy, size, [(4, 17), (4, 20.5), (20, 20.5), (20, 17)],
          color, w)


def _undo(cv, cx, cy, size, color, w):
    _line(cv, cx, cy, size, [(8, 8), (4.5, 11.5), (8, 15)], color, w)
    _line(cv, cx, cy, size, [(5, 11.5), (14, 11.5), (17.5, 14.5),
                              (17.5, 18), (13.5, 20)], color, w, smooth=True)


def _trash(cv, cx, cy, size, color, w):
    _line(cv, cx, cy, size, [(4, 6.5), (20, 6.5)], color, w)
    _line(cv, cx, cy, size, [(9, 6.5), (9, 4.2), (15, 4.2), (15, 6.5)],
          color, w)
    _line(cv, cx, cy, size, [(6, 6.5), (7, 20), (17, 20), (18, 6.5)],
          color, w, smooth=True)
    _line(cv, cx, cy, size, [(10.3, 10), (10.6, 17)], color, w * 0.8)
    _line(cv, cx, cy, size, [(13.7, 10), (13.4, 17)], color, w * 0.8)


def _plus(cv, cx, cy, size, color, w):
    _line(cv, cx, cy, size, [(12, 5), (12, 19)], color, w)
    _line(cv, cx, cy, size, [(5, 12), (19, 12)], color, w)


def _minus(cv, cx, cy, size, color, w):
    _line(cv, cx, cy, size, [(5, 12), (19, 12)], color, w)


def _fit(cv, cx, cy, size, color, w):
    _line(cv, cx, cy, size, [(4, 8.5), (4, 4.5), (8, 4.5)], color, w)
    _line(cv, cx, cy, size, [(16, 4.5), (20, 4.5), (20, 8.5)], color, w)
    _line(cv, cx, cy, size, [(20, 15.5), (20, 19.5), (16, 19.5)], color, w)
    _line(cv, cx, cy, size, [(8, 19.5), (4, 19.5), (4, 15.5)], color, w)


def _chevron_left(cv, cx, cy, size, color, w):
    _line(cv, cx, cy, size, [(14.5, 5), (8, 12), (14.5, 19)], color, w)


def _chevron_right(cv, cx, cy, size, color, w):
    _line(cv, cx, cy, size, [(9.5, 5), (16, 12), (9.5, 19)], color, w)


def _close(cv, cx, cy, size, color, w):
    _line(cv, cx, cy, size, [(6, 6), (18, 18)], color, w)
    _line(cv, cx, cy, size, [(18, 6), (6, 18)], color, w)


def _pencil(cv, cx, cy, size, color, w):
    _line(cv, cx, cy, size, [(4, 20), (4.8, 16), (16, 4.8), (19.2, 8),
                              (8, 19.2)], color, w)
    _line(cv, cx, cy, size, [(14.5, 6.3), (17.7, 9.5)], color, w)


def _page(cv, cx, cy, size, color, w):
    _line(cv, cx, cy, size, [(6, 3.5), (14.5, 3.5), (18, 7), (18, 20.5),
                              (6, 20.5), (6, 3.5)], color, w)
    _line(cv, cx, cy, size, [(14, 4), (14, 7.5), (17.8, 7.5)], color, w)


def _image(cv, cx, cy, size, color, w):
    _line(cv, cx, cy, size, [(4, 5), (20, 5), (20, 19), (4, 19), (4, 5)],
          color, w)
    _line(cv, cx, cy, size, [(4, 16), (9.5, 10.5), (13.5, 14.5),
                              (16, 12), (20, 16)], color, w * 0.85)


def _grid(cv, cx, cy, size, color, w):
    _line(cv, cx, cy, size, [(4, 4), (11, 4), (11, 11), (4, 11), (4, 4)],
          color, w * 0.9)
    _line(cv, cx, cy, size, [(13, 4), (20, 4), (20, 11), (13, 11), (13, 4)],
          color, w * 0.9)
    _line(cv, cx, cy, size, [(4, 13), (11, 13), (11, 20), (4, 20), (4, 13)],
          color, w * 0.9)
    _line(cv, cx, cy, size, [(13, 13), (20, 13), (20, 20), (13, 20),
                              (13, 13)], color, w * 0.9)


def _arc_pts(r: float, a0: float, a1: float, steps: int = 16,
             cx: float = 12.0, cy: float = 12.0) -> list[tuple[float, float]]:
    """Points along a circle, in the 24x24 design box (y grows downwards)."""
    out = []
    for i in range(steps + 1):
        a = math.radians(a0 + (a1 - a0) * i / steps)
        out.append((cx + r * math.cos(a), cy + r * math.sin(a)))
    return out


def _arrow_head(cv, cx, cy, size, tip, direction, color,
                length: float = 4.4, half: float = 2.1) -> None:
    """A filled triangle pointing along ``direction``."""
    dx, dy = direction
    norm = math.hypot(dx, dy) or 1.0
    dx, dy = dx / norm, dy / norm
    px, py = -dy, dx
    base = (tip[0] - dx * length, tip[1] - dy * length)
    _poly(cv, cx, cy, size,
          [tip,
           (base[0] + px * half, base[1] + py * half),
           (base[0] - px * half, base[1] - py * half)], color)


def _rotate_right(cv, cx, cy, size, color, w):
    pts = _arc_pts(6.6, 200, 340)
    _line(cv, cx, cy, size, pts, color, w, smooth=True)
    tip = pts[-1]
    direction = (tip[0] - pts[-2][0], tip[1] - pts[-2][1])
    _arrow_head(cv, cx, cy, size, tip, direction, color)


def _rotate_left(cv, cx, cy, size, color, w):
    pts = _arc_pts(6.6, 340, 200)
    _line(cv, cx, cy, size, pts, color, w, smooth=True)
    tip = pts[-1]
    direction = (tip[0] - pts[-2][0], tip[1] - pts[-2][1])
    _arrow_head(cv, cx, cy, size, tip, direction, color)


def _flip_h(cv, cx, cy, size, color, w):
    # a vertical mirror line with the two halves swapping places
    _line(cv, cx, cy, size, [(12, 4.5), (12, 19.5)], color, w * 0.75)
    _poly(cv, cx, cy, size, [(4.2, 12), (8.8, 8.8), (8.8, 15.2)], color)
    _poly(cv, cx, cy, size, [(19.8, 12), (15.2, 8.8), (15.2, 15.2)], color)


def _flip_v(cv, cx, cy, size, color, w):
    # a horizontal mirror line with the two halves swapping places
    _line(cv, cx, cy, size, [(4.5, 12), (19.5, 12)], color, w * 0.75)
    _poly(cv, cx, cy, size, [(12, 4.2), (8.8, 8.8), (15.2, 8.8)], color)
    _poly(cv, cx, cy, size, [(12, 19.8), (8.8, 15.2), (15.2, 15.2)], color)


def _help(cv, cx, cy, size, color, w):
    # a question mark in a circle
    _line(cv, cx, cy, size,
          [(9.6, 9.4), (10.4, 7.8), (12, 6.8), (13.7, 7.6), (14.5, 9.2),
           (13.3, 10.8), (12, 11.6), (12, 13.2)], color, w, smooth=True)
    _line(cv, cx, cy, size, [(12, 16.2), (12, 16.4)], color, w)
    _line(cv, cx, cy, size,
          [(12, 3.6), (18.2, 6.2), (20.4, 12), (18.2, 17.8), (12, 20.4),
           (5.8, 17.8), (3.6, 12), (5.8, 6.2), (12, 3.6)], color, w,
          smooth=True)


ICONS = {
    "cursor": _cursor,
    "text": _text,
    "check": _check,
    "cross": _cross,
    "signature": _signature,
    "folder": _folder,
    "save": _save,
    "undo": _undo,
    "trash": _trash,
    "plus": _plus,
    "minus": _minus,
    "fit": _fit,
    "chevron_left": _chevron_left,
    "chevron_right": _chevron_right,
    "close": _close,
    "pencil": _pencil,
    "page": _page,
    "image": _image,
    "grid": _grid,
    "help": _help,
    "rotate_left": _rotate_left,
    "rotate_right": _rotate_right,
    "flip_h": _flip_h,
    "flip_v": _flip_v,
}


def draw_icon(cv: tk.Canvas, name: str, cx: float, cy: float, size: float,
              color: str, weight: float = 1.0) -> None:
    """Draw ``name`` centred on (cx, cy) with the given box size."""
    fn = ICONS.get(name)
    if fn is None:
        return
    fn(cv, cx, cy, size, color, _STROKE * weight * (size / 18.0) ** 0.55)
