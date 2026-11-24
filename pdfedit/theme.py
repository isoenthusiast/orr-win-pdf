"""Visual language for the app - a light, calm, "Apple-like" system.

Everything visual is defined here so the whole app can be re-skinned from one
place.  Colours follow Apple's system palette, type follows the macOS type
scale, and spacing follows an 8pt grid.
"""
from __future__ import annotations

import tkinter as tk
from tkinter import font as tkfont

# ---------------------------------------------------------------- palette
BG = "#E8E8ED"            # window / workspace
SURFACE = "#FFFFFF"       # panels, cards
SURFACE_2 = "#F5F5F7"     # inset panels, segmented tracks
SURFACE_3 = "#FAFAFC"     # subtle hover

TEXT = "#1D1D1F"          # primary label
TEXT_2 = "#6E6E73"        # secondary label
TEXT_3 = "#86868B"        # tertiary / section headers
TEXT_ON_ACCENT = "#FFFFFF"

SEPARATOR = "#D8D8DC"     # hairline
SEPARATOR_SOFT = "#E8E8ED"

ACCENT = "#007AFF"        # system blue
ACCENT_HOVER = "#0A6CFF"
ACCENT_PRESSED = "#0062CC"

FILL = "#E3E3E6"          # segmented track / neutral button
FILL_HOVER = "#D8D8DD"

DESTRUCTIVE = "#FF3B30"
SUCCESS = "#34C759"

CANVAS_BG = "#E8E8ED"
PAGE_EDGE = "#C7C7CC"
PAGE_SHADOW = "#D3D3D8"

SELECT = ACCENT          # selection outline
SELECT_FILL = "#007AFF"
OVERLAY_BOX = "#007AFF"   # dashed box around an editable overlay

# ---------------------------------------------------------------- metrics
UNIT = 4
RADIUS_CARD = 10
RADIUS_CTRL = 6
RADIUS_PILL = 8

TITLEBAR_H = 52
RAIL_W = 60
INSPECTOR_W = 272
TOOLBAR_H = 28

# ---------------------------------------------------------------- type
_FAMILY_TEXT = "Segoe UI Variable Text"
_FAMILY_DISPLAY = "Segoe UI Variable Display"
_FAMILY_FALLBACK = "Segoe UI"


def _pick(*candidates: str) -> str:
    import tkinter
    root = tkinter._default_root
    families = set(tkfont.families(root)) if root else set()
    for name in candidates:
        if name in families:
            return name
    return _FAMILY_FALLBACK


class Fonts:
    """Named type styles, created once the Tk root exists."""

    def __init__(self) -> None:
        family = _pick(_FAMILY_TEXT, _FAMILY_FALLBACK)
        display = _pick(_FAMILY_DISPLAY, family)
        self.family = family
        self.display = display

        # macOS-ish type scale, in Tk points (1pt ~= 1.33px at 96dpi).
        # Tk only accepts integer point sizes.
        self.title = tkfont.Font(family=display, size=12, weight="bold")
        self.headline = tkfont.Font(family=display, size=11, weight="bold")
        self.body = tkfont.Font(family=family, size=10)
        self.body_emphasis = tkfont.Font(family=family, size=10, weight="bold")
        self.caption = tkfont.Font(family=family, size=9)
        self.caption_emphasis = tkfont.Font(family=family, size=9, weight="bold")
        self.section = tkfont.Font(family=family, size=9, weight="bold")
        self.mono = tkfont.Font(family="Cascadia Mono", size=9)
        self.icon = tkfont.Font(family="Segoe Fluent Icons", size=11)


_FONTS: Fonts | None = None


def fonts() -> Fonts:
    """Shared font set (created on first call, after the root exists)."""
    global _FONTS
    if _FONTS is not None:
        try:
            _FONTS.title.actual()      # cheap liveness check
            return _FONTS
        except Exception:
            # the Tk interpreter was replaced (a new root was created)
            _FONTS = None
    _FONTS = Fonts()
    return _FONTS


def reset_fonts() -> None:
    """Forget the cached font set - used when the Tk root is replaced."""
    global _FONTS
    _FONTS = None
