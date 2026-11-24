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
CTRL_H = 28          # the height of a standard button
ICON_SIZE = 30       # a square icon button
ROW_H = 26           # a compact row (steppers, chips)

# ---------------------------------------------------------------- type
_FAMILY_TEXT = "Segoe UI Variable Text"
_FAMILY_DISPLAY = "Segoe UI Variable Display"
_FAMILY_FALLBACK = "Segoe UI"

# The interface text size, as a multiple of the designed size.  Everything
# that draws text - and the controls around it - follows this number.
_SCALE = 1.0

# The sizes offered in the interface, from smallest to largest.
SCALE_STEPS: tuple[tuple[str, float], ...] = (
    ("Small", 0.9),
    ("Normal", 1.0),
    ("Large", 1.15),
    ("Larger", 1.35),
    ("Largest", 1.6),
)


def scale() -> float:
    """The current interface text size."""
    return _SCALE


def set_scale(value: float) -> bool:
    """Change the interface text size.

    The fonts are resized in place rather than replaced, so every widget
    that already holds a reference follows along.  Returns True when
    something actually changed.
    """
    global _SCALE
    try:
        value = float(value)
    except (TypeError, ValueError):
        return False
    value = max(0.75, min(2.0, value))
    if abs(value - _SCALE) < 0.001:
        return False
    _SCALE = value
    if _FONTS is not None:
        _FONTS.apply_scale(value)
    return True


def scaled(value: float) -> int:
    """Scale a pixel measurement along with the text size."""
    return max(1, int(value * _SCALE + 0.5))


def design(value: float) -> float:
    """Convert a measurement taken now back to its design size.

    Widgets remember their size in design units, so changing the scale up
    and back again returns them to exactly where they started.
    """
    return value / _SCALE if _SCALE else value


def ctrl_h() -> int:
    """Height of a standard button."""
    return scaled(CTRL_H)


def titlebar_h() -> int:
    return scaled(TITLEBAR_H)


def rail_w() -> int:
    return scaled(RAIL_W)


def inspector_w() -> int:
    return scaled(INSPECTOR_W)


def toolbar_h() -> int:
    return scaled(TOOLBAR_H)


def icon_size() -> int:
    return scaled(ICON_SIZE)


def row_h() -> int:
    return scaled(ROW_H)


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

    # The size each style was designed at, before the interface is scaled.
    BASE_SIZES = {
        "title": 12,
        "headline": 11,
        "body": 10,
        "body_emphasis": 10,
        "caption": 9,
        "caption_emphasis": 9,
        "section": 9,
        "mono": 9,
    }

    def __init__(self) -> None:
        family = _pick(_FAMILY_TEXT, _FAMILY_FALLBACK)
        display = _pick(_FAMILY_DISPLAY, family)
        self.family = family
        self.display = display
        self.scale = _SCALE

        # macOS-ish type scale, in Tk points (1pt ~= 1.33px at 96dpi).
        # Tk only accepts integer point sizes.
        self.title = tkfont.Font(family=display, size=self._size(12), weight="bold")
        self.headline = tkfont.Font(family=display, size=self._size(11), weight="bold")
        self.body = tkfont.Font(family=family, size=self._size(10))
        self.body_emphasis = tkfont.Font(family=family, size=self._size(10), weight="bold")
        self.caption = tkfont.Font(family=family, size=self._size(9))
        self.caption_emphasis = tkfont.Font(family=family, size=self._size(9), weight="bold")
        self.section = tkfont.Font(family=family, size=self._size(9), weight="bold")
        self.mono = tkfont.Font(family="Cascadia Mono", size=self._size(9))
        self.icon = tkfont.Font(family="Segoe Fluent Icons", size=self._size(11))

    def _size(self, base: int) -> int:
        """A point size for the current interface scale."""
        return max(7, int(base * self.scale + 0.5))

    def apply_scale(self, factor: float) -> None:
        """Resize every font in place, so live widgets follow along."""
        self.scale = factor
        for name, base in self.BASE_SIZES.items():
            font = getattr(self, name, None)
            if font is not None:
                try:
                    font.configure(size=self._size(base))
                except Exception:
                    pass


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
