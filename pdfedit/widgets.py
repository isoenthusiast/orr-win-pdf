"""Small custom widget set: flat, hairline, rounded - the app's building blocks.

Tk's stock widgets look like 1995 Windows, so every control the app uses is
drawn here on a canvas instead.
"""
from __future__ import annotations

import tkinter as tk

from . import theme
from .icons import draw_icon


# ---------------------------------------------------------------- helpers
def _dim(widget: tk.Widget, which: str, fallback: int) -> int:
    """Real width/height of a widget, falling back before it is mapped.

    ``winfo_width()`` returns 1 (not 0) for an unmapped widget, so a plain
    ``or`` fallback silently yields 1 - which is how you end up with a
    negative icon size.
    """
    value = widget.winfo_width() if which == "w" else widget.winfo_height()
    if value <= 1:
        try:
            value = int(widget[which])
        except Exception:
            value = fallback
    return value or fallback


def rounded_rect(cv: tk.Canvas, x0, y0, x1, y1, r, **kw):
    """A rectangle with rounded corners (drawn as a smoothed polygon)."""
    r = max(0, min(r, (x1 - x0) / 2, (y1 - y0) / 2))
    points = [
        x0 + r, y0, x1 - r, y0, x1, y0, x1, y0 + r,
        x1, y1 - r, x1, y1, x1 - r, y1, x0 + r, y1,
        x0, y1, x0, y1 - r, x0, y0 + r, x0, y0,
    ]
    return cv.create_polygon(points, smooth=True, splinesteps=16, **kw)


def hairline(cv: tk.Canvas, x0, y0, x1, y1, color=None, width=1):
    """A crisp 1px separator (drawn on the half pixel to stay sharp)."""
    color = color or theme.SEPARATOR
    if abs(x1 - x0) >= abs(y1 - y0):
        y = y0 + 0.5
        return cv.create_line(x0, y, x1, y, fill=color, width=width)
    x = x0 + 0.5
    return cv.create_line(x, y0, x, y1, fill=color, width=width)


# ---------------------------------------------------------------- tooltip
class Tooltip:
    """A small dark tooltip that appears under a widget."""

    def __init__(self, widget: tk.Widget, text: str, delay: int = 500):
        self.widget = widget
        self.text = text
        self.delay = delay
        self._after = None
        self._win = None
        self._inside = False
        widget.bind("<Enter>", self._on_enter, add="+")
        widget.bind("<Leave>", self._on_leave, add="+")
        widget.bind("<ButtonPress>", self._hide, add="+")

    def set_text(self, text: str) -> None:
        """Change the wording (used by the floating bar)."""
        if text == self.text:
            return
        self.text = text
        if self._win:
            self._hide()
        elif self._inside:
            # re-arm the delay so the new wording shows straight away
            self._schedule()

    def _on_enter(self, _e=None):
        self._inside = True
        self._schedule()

    def _on_leave(self, _e=None):
        self._inside = False
        self._hide()

    def _schedule(self, _e=None):
        self._cancel()
        if self.text:
            self._after = self.widget.after(self.delay, self._show)

    def _cancel(self):
        if self._after:
            try:
                self.widget.after_cancel(self._after)
            except Exception:
                pass
            self._after = None

    def _show(self):
        self._cancel()
        try:
            x = self.widget.winfo_rootx() + self.widget.winfo_width() // 2
            y = self.widget.winfo_rooty() + self.widget.winfo_height() + 8
        except Exception:
            return
        win = tk.Toplevel(self.widget)
        win.wm_overrideredirect(True)
        win.configure(bg="#000000")
        cv = tk.Canvas(win, bg="#000000", highlightthickness=0,
                       height=22, bd=0)
        cv.pack()
        f = theme.fonts().caption
        tw = f.measure(self.text) + 16
        cv.configure(width=tw)
        rounded_rect(cv, 0, 0, tw, 22, 6, fill="#1C1C1E", outline="")
        cv.create_text(tw / 2, 11, text=self.text, fill="#FFFFFF", font=f)
        win.geometry(f"+{x - tw // 2}+{y}")
        self._win = win

    def _hide(self, _e=None):
        self._cancel()
        if self._win:
            try:
                self._win.destroy()
            except Exception:
                pass
            self._win = None


# ---------------------------------------------------------------- buttons
class IconButton(tk.Canvas):
    """A square icon button with a rounded hover highlight."""

    def __init__(self, parent, icon: str = "", command=None, tooltip: str = "",
                 size: int = 30, icon_size: float = 16, fg: str = theme.TEXT,
                 bg: str = theme.BG, toggle: bool = False,
                 active_color: str | None = None, command_on=True,
                 radius: int = 7, **kw):
        super().__init__(parent, width=size, height=size, bg=bg,
                         highlightthickness=0, bd=0, **kw)
        self.icon = icon
        self.command = command
        self.size = size
        self.icon_size = icon_size
        self._base_size = theme.design(size)
        self._base_icon_size = theme.design(icon_size)
        self.fg = fg
        self.bg = bg
        self.toggle = toggle
        self.active = False
        self.active_color = active_color or theme.ACCENT
        self._hover = False
        self._pressed = False
        self._radius = radius
        self._enabled = True

        self.bind("<Enter>", self._on_enter)
        self.bind("<Leave>", self._on_leave)
        self.bind("<ButtonPress-1>", self._on_press)
        self.bind("<ButtonRelease-1>", self._on_release)
        self.bind("<Configure>", lambda e: self.redraw())
        if tooltip:
            Tooltip(self, tooltip)
        self.after(0, self.redraw)

    # -- state -----------------------------------------------------------
    def set_enabled(self, enabled: bool) -> None:
        self._enabled = enabled
        self.configure(cursor="hand2" if enabled else "arrow")
        self.redraw()

    def set_active(self, active: bool) -> None:
        self.active = active
        self.redraw()

    def rescale(self) -> None:
        """Re-measure for the current interface text size."""
        self.size = theme.scaled(self._base_size)
        self.icon_size = theme.scaled(self._base_icon_size)
        self.configure(width=self.size, height=self.size)
        self.redraw()

    def _on_enter(self, _e=None):
        self._hover = True
        self.redraw()

    def _on_leave(self, _e=None):
        self._hover = False
        self._pressed = False
        self.redraw()

    def _on_press(self, _e=None):
        if not self._enabled:
            return
        self._pressed = True
        self.redraw()

    def _on_release(self, _e=None):
        if not self._enabled:
            return
        was = self._pressed
        self._pressed = False
        self.redraw()
        if was and self.command:
            self.command()

    # -- paint -----------------------------------------------------------
    def redraw(self) -> None:
        self.delete("all")
        w = _dim(self, "w", self.size)
        h = _dim(self, "h", self.size)
        if self.active:
            rounded_rect(self, 1, 1, w - 1, h - 1, self._radius,
                         fill=self.active_color, outline="")
            color = theme.TEXT_ON_ACCENT
        elif self._pressed:
            rounded_rect(self, 1, 1, w - 1, h - 1, self._radius,
                         fill=theme.FILL, outline="")
            color = self.fg
        elif self._hover and self._enabled:
            rounded_rect(self, 1, 1, w - 1, h - 1, self._radius,
                         fill=theme.FILL, outline="")
            color = self.fg
        else:
            color = self.fg if self._enabled else theme.TEXT_3
        if self.icon:
            draw_icon(self, self.icon, w / 2, h / 2, self.icon_size, color)


class RoundedButton(tk.Canvas):
    """A labelled pill button.  Variants: accent | gray | plain."""

    def __init__(self, parent, text: str = "", command=None, variant: str = "gray",
                 width: int = 0, height: int = 0, icon: str = "",
                 bg: str = theme.BG, font=None, tooltip: str = "", **kw):
        auto_width = not width
        if auto_width:
            f = font or theme.fonts().body_emphasis
            width = f.measure(text) + (46 if icon else 30)
        if not height:
            height = theme.ctrl_h()
        self._auto_width = auto_width
        self._base_width = theme.design(width)
        self._base_height = theme.design(height)
        super().__init__(parent, width=width, height=height, bg=bg,
                         highlightthickness=0, bd=0, **kw)
        self.text = text
        self.command = command
        self.variant = variant
        self.icon = icon
        self.bg = bg
        self.font = font or theme.fonts().body_emphasis
        self._hover = False
        self._pressed = False
        self._enabled = True

        self.bind("<Enter>", self._on_enter)
        self.bind("<Leave>", self._on_leave)
        self.bind("<ButtonPress-1>", self._on_press)
        self.bind("<ButtonRelease-1>", self._on_release)
        self.bind("<Configure>", lambda e: self.redraw())
        self.after(0, self.redraw)
        if tooltip:
            Tooltip(self, tooltip)

    def set_enabled(self, enabled: bool) -> None:
        self._enabled = enabled
        self.configure(cursor="hand2" if enabled else "arrow")
        self.redraw()

    def rescale(self) -> None:
        """Re-measure for the current interface text size."""
        width = theme.scaled(self._base_width)
        if self._auto_width:
            width = self.font.measure(self.text) + (46 if self.icon else 30)
        self.configure(width=width, height=theme.scaled(self._base_height))
        self.redraw()

    def _on_enter(self, _e=None):
        self._hover = True
        self.redraw()

    def _on_leave(self, _e=None):
        self._hover = False
        self._pressed = False
        self.redraw()

    def _on_press(self, _e=None):
        if not self._enabled:
            return
        self._pressed = True
        self.redraw()

    def _on_release(self, _e=None):
        if not self._enabled:
            return
        was = self._pressed
        self._pressed = False
        self.redraw()
        if was and self.command:
            self.command()

    def redraw(self) -> None:
        self.delete("all")
        w = _dim(self, "w", int(self["width"]))
        h = _dim(self, "h", int(self["height"]))
        if self.variant == "accent":
            fill = theme.ACCENT_PRESSED if self._pressed else (
                theme.ACCENT_HOVER if self._hover else theme.ACCENT)
            fg = theme.TEXT_ON_ACCENT
        elif self.variant == "gray":
            fill = theme.FILL_HOVER if (self._hover or self._pressed) else theme.FILL
            fg = theme.TEXT
        else:
            fill = theme.FILL_HOVER if (self._hover or self._pressed) else self.bg
            fg = theme.ACCENT
        if not self._enabled:
            fill = theme.SURFACE_2
            fg = theme.TEXT_3
        if self.variant != "plain":
            rounded_rect(self, 0, 0, w, h, h / 2, fill=fill, outline="")
        tx = w / 2
        if self.icon:
            tw = self.font.measure(self.text)
            icon_size = max(8, min(14, h - 10))
            draw_icon(self, self.icon, tx - tw / 2 - icon_size * 0.9, h / 2,
                      icon_size, fg)
            self.create_text(tx + icon_size * 0.25, h / 2, text=self.text,
                             fill=fg, font=self.font)
        else:
            self.create_text(tx, h / 2, text=self.text, fill=fg, font=self.font)


# ---------------------------------------------------------------- fields
class RoundedEntry(tk.Canvas):
    """A rounded text field with an embedded flat Entry."""

    def __init__(self, parent, textvariable=None, placeholder: str = "",
                 height: int = 0, bg: str = theme.SURFACE,
                 fg: str = theme.TEXT, tooltip: str = "", **kw):
        if not height:
            height = theme.ctrl_h()
        self._base_height = theme.design(height)
        super().__init__(parent, height=height, bg=bg, highlightthickness=0,
                         bd=0, **kw)
        self.variable = textvariable
        self.placeholder = placeholder
        self._focus = False
        self.var = tk.StringVar(master=self)
        if textvariable is not None:
            self.var.trace_add("write", lambda *a: self._sync())
            self.var.set(textvariable.get())
            textvariable.trace_add("write", lambda *a: self._set())
        self.entry = tk.Entry(self, textvariable=self.var, bd=0, relief=tk.FLAT,
                              bg=theme.SURFACE, fg=fg, font=theme.fonts().body,
                              highlightthickness=0, insertbackground=theme.ACCENT)
        self.entry.bind("<FocusIn>", self._on_focus_in)
        self.entry.bind("<FocusOut>", self._on_focus_out)
        self._win = self.create_window(10, height / 2, window=self.entry,
                                       anchor=tk.W)
        self.bind("<Configure>", lambda e: self._layout())
        self.bind("<Button-1>", lambda e: self.entry.focus_set())
        self.after(0, self.redraw)
        if tooltip:
            Tooltip(self.entry, tooltip)

    def _layout(self):
        h = _dim(self, "h", 28)
        w = _dim(self, "w", 200)
        eh = theme.scaled(24)
        self.entry.place(in_=self, x=10, y=(h - eh) / 2, width=max(10, w - 20),
                         height=eh)
        self.coords(self._win, 10, h / 2)

    def rescale(self) -> None:
        """Re-measure for the current interface text size."""
        self.configure(height=theme.scaled(self._base_height))
        self.redraw()

    def _set(self):
        if self.var.get() != self.variable.get():
            self.var.set(self.variable.get())

    def _sync(self):
        if self.variable is not None and self.variable.get() != self.var.get():
            self.variable.set(self.var.get())

    def _on_focus_in(self, _e=None):
        self._focus = True
        self.redraw()

    def _on_focus_out(self, _e=None):
        self._focus = False
        self.redraw()

    def redraw(self):
        self.delete("bg")
        w = _dim(self, "w", 200)
        h = _dim(self, "h", 28)
        outline = theme.ACCENT if self._focus else theme.SEPARATOR
        rounded_rect(self, 0.5, 0.5, w - 0.5, h - 0.5, theme.RADIUS_CTRL,
                     fill=theme.SURFACE, outline=outline, width=1)
        self.tag_lower("bg")
        self._layout()


class Stepper(tk.Canvas):
    """A compact numeric stepper: [-] value [+]"""

    def __init__(self, parent, variable=None, lo: float = 0, hi: float = 999,
                 step: float = 1, width: int = 92, height: int = 26,
                 decimals: int = 0, bg: str = theme.SURFACE,
                 tooltip: str = "", **kw):
        super().__init__(parent, width=width, height=height, bg=bg,
                         highlightthickness=0, bd=0, **kw)
        self.variable = variable
        self.lo, self.hi, self.step, self.decimals = lo, hi, step, decimals
        self.bg = bg
        self._hover = None
        self._base_width = theme.design(width)
        self._base_height = theme.design(height)
        self._zone = theme.scaled(20)
        self.bind("<Motion>", self._on_motion)
        self.bind("<Leave>", lambda e: self._set_hover(None))
        self.bind("<Button-1>", self._on_click)
        self.bind("<Configure>", lambda e: self.redraw())
        self.after(0, self.redraw)
        if tooltip:
            Tooltip(self, tooltip)

    def value(self) -> float:
        if self.variable is not None:
            try:
                return float(self.variable.get())
            except Exception:
                return self.lo
        return self.lo

    def _set_hover(self, which):
        if which != self._hover:
            self._hover = which
            self.redraw()

    def _on_motion(self, event):
        w = _dim(self, "w", 92)
        self._set_hover("-" if event.x < self._zone else
                        ("+" if event.x > w - self._zone else None))

    def _on_click(self, event):
        w = _dim(self, "w", 92)
        v = self.value()
        if event.x < self._zone:
            v -= self.step
        elif event.x > w - self._zone:
            v += self.step
        else:
            return
        v = max(self.lo, min(self.hi, v))
        if self.variable is not None:
            self.variable.set(round(v, self.decimals))
        self.redraw()

    def rescale(self) -> None:
        """Re-measure for the current interface text size."""
        self._zone = theme.scaled(20)
        self.configure(width=theme.scaled(self._base_width),
                       height=theme.scaled(self._base_height))
        self.redraw()

    def redraw(self):
        self.delete("all")
        w = _dim(self, "w", 92)
        h = _dim(self, "h", 26)
        rounded_rect(self, 0.5, 0.5, w - 0.5, h - 0.5, theme.RADIUS_CTRL,
                     fill=theme.SURFACE, outline=theme.SEPARATOR, width=1)
        color = theme.TEXT
        if self._hover == "-":
            color = theme.ACCENT
        draw_icon(self, "minus", 11, h / 2, 12, color)
        color = theme.TEXT
        if self._hover == "+":
            color = theme.ACCENT
        draw_icon(self, "plus", w - 11, h / 2, 12, color)
        val = self.value()
        text = f"{int(val)}" if float(val).is_integer() else f"{val:.1f}"
        self.create_text(w / 2, h / 2, text=text, fill=theme.TEXT,
                         font=theme.fonts().body)


class ColorSwatch(tk.Canvas):
    """A rounded colour chip that opens the system colour picker."""

    def __init__(self, parent, color=(0, 0, 0), command=None, width: int = 26,
                 height: int = 26, bg: str = theme.SURFACE, tooltip: str = "",
                 **kw):
        super().__init__(parent, width=width, height=height, bg=bg,
                         highlightthickness=0, bd=0, **kw)
        self.color = color
        self.command = command
        self.bg = bg
        self._hover = False
        self._base_width = theme.design(width)
        self._base_height = theme.design(height)
        self.bind("<Enter>", self._on_enter)
        self.bind("<Leave>", self._on_leave)
        self.bind("<Button-1>", self._on_click)
        self.bind("<Configure>", lambda e: self.redraw())
        self.after(0, self.redraw)
        if tooltip:
            Tooltip(self, tooltip)

    def set_color(self, color):
        self.color = color
        self.redraw()

    def rescale(self) -> None:
        """Re-measure for the current interface text size."""
        self.configure(width=theme.scaled(self._base_width),
                       height=theme.scaled(self._base_height))
        self.redraw()

    def _on_enter(self, _e=None):
        self._hover = True
        self.redraw()

    def _on_leave(self, _e=None):
        self._hover = False
        self.redraw()

    def _on_click(self, _e=None):
        if self.command:
            self.command()

    def redraw(self):
        self.delete("all")
        w = _dim(self, "w", 26)
        h = _dim(self, "h", 26)
        hexc = "#%02x%02x%02x" % tuple(max(0, min(255, int(round(c * 255))))
                                        for c in self.color)
        rounded_rect(self, 1, 1, w - 1, h - 1, 7,
                     fill=hexc, outline=theme.SEPARATOR, width=1)
        if self._hover:
            rounded_rect(self, 0, 0, w, h, 8, outline=theme.ACCENT, width=1.5)


class SectionHeader(tk.Canvas):
    """A small uppercase section header with a hairline rule."""

    def __init__(self, parent, text: str, bg: str = theme.SURFACE, **kw):
        self._base_height = theme.design(26)
        super().__init__(parent, height=26, bg=bg, highlightthickness=0, bd=0,
                         **kw)
        self.text = text
        self.bg = bg
        self.bind("<Configure>", lambda e: self.redraw())
        self.after(10, self.redraw)

    def rescale(self) -> None:
        """Re-measure for the current interface text size."""
        self.configure(height=theme.scaled(self._base_height))
        self.redraw()

    def redraw(self):
        self.delete("all")
        w = _dim(self, "w", 200)
        f = theme.fonts().section
        label = self.text.upper()
        self.create_text(0, 13, text=label, fill=theme.TEXT_3, font=f,
                         anchor="w")
        tw = f.measure(label)
        if tw + 20 < w:
            hairline(self, tw + 10, 13, w, 13, theme.SEPARATOR_SOFT)


class FloatingBar(tk.Canvas):
    """A translucent rounded bar that floats over the canvas."""

    def __init__(self, parent, height: int = 40, bg: str = theme.BG, **kw):
        self._base_height = theme.design(height)
        super().__init__(parent, height=height, bg=bg, highlightthickness=0,
                         bd=0, **kw)
        self.bar_bg = bg
        self.bind("<Configure>", lambda e: self.redraw())
        self.after(10, self.redraw)

    def rescale(self) -> None:
        """Re-measure for the current interface text size."""
        self.configure(height=theme.scaled(self._base_height))
        self.redraw()

    def redraw(self):
        self.delete("bg")
        w = _dim(self, "w", 400)
        h = _dim(self, "h", 40)
        rounded_rect(self, 2, 2, w - 2, h - 2, (h - 4) / 2,
                     fill=theme.SURFACE, outline=theme.SEPARATOR, width=1)
        self.tag_lower("bg")


# ---------------------------------------------------------------- floating bar
HINTS = {
    "prev": "Previous page  (PgUp)",
    "next": "Next page  (PgDn)",
    "zoomout": "Zoom out  (Ctrl −)",
    "zoomin": "Zoom in  (Ctrl +)",
    "fit": "Fit the page to the window",
    "pagelabel": "Current page",
    "zoomlabel": "Current zoom",
    "rotateleft": "Turn the page anticlockwise",
    "rotateright": "Turn the page clockwise",
    "flipv": "Flip the page upside down",
    "fliph": "Flip the page left to right",
}


class FloatingControls(tk.Canvas):
    """The context bar that floats over the page: page nav + zoom.

    Everything is painted on the canvas so the whole bar can be one rounded
    surface, the way a macOS floating control bar behaves.
    """
    def __init__(self, parent, on_prev=None, on_next=None, on_zoom_out=None,
                 on_zoom_in=None, on_fit=None, on_rotate_left=None,
                 on_rotate_right=None, on_flip_v=None, on_flip_h=None,
                 height: int = 40, **kw):
        self._base_width = theme.design(386)
        self._base_height = theme.design(height)
        super().__init__(parent, width=386, height=height, bg=theme.BG,
                         highlightthickness=0, bd=0, **kw)
        self.on_prev = on_prev
        self.on_next = on_next
        self.on_zoom_out = on_zoom_out
        self.on_zoom_in = on_zoom_in
        self.on_fit = on_fit
        self.on_rotate_left = on_rotate_left
        self.on_rotate_right = on_rotate_right
        self.on_flip_v = on_flip_v
        self.on_flip_h = on_flip_h
        self.page = 1
        self.total = 1
        self.zoom = 1.0
        self._hover = None
        self._hot = []

        self.bind("<Motion>", self._on_motion)
        self.bind("<Leave>", lambda e: self._set_hover(None))
        self.bind("<Button-1>", self._on_click)
        self.bind("<Configure>", lambda e: self.redraw())
        self.after(0, self.redraw)
        self.bind("<Configure>", lambda e: self.redraw())
        self.after(10, self.redraw)
        self._tooltip = Tooltip(self, "")
        self._tooltip.delay = 350

    # -- painting --------------------------------------------------------
    def update(self, page: int, total: int, zoom: float) -> None:
        self.page, self.total, self.zoom = page, total, zoom
        self.redraw()

    def _layout(self):
        """Return the hit regions as (key, x0, x1, kind, payload)."""
        h = _dim(self, "h", 40)
        pad = theme.scaled(6)
        icon = theme.scaled(26)
        page_w = theme.scaled(62)
        zoom_w = theme.scaled(46)
        sep = theme.scaled(13)
        fit = theme.scaled(32)
        regions = []
        x = pad
        regions.append(("prev", x, x + icon, "icon", "chevron_left"))
        x += icon
        regions.append(("pagelabel", x, x + page_w, "label", None))
        x += page_w
        regions.append(("next", x, x + icon, "icon", "chevron_right"))
        x += icon
        regions.append(("sep1", x, x + sep, "sep", None))
        x += sep
        regions.append(("zoomout", x, x + icon, "icon", "minus"))
        x += icon
        regions.append(("zoomlabel", x, x + zoom_w, "label", None))
        x += zoom_w
        regions.append(("zoomin", x, x + icon, "icon", "plus"))
        x += icon
        regions.append(("fit", x, x + fit, "icon", "fit"))
        x += fit
        regions.append(("sep2", x, x + sep, "sep", None))
        x += sep
        regions.append(("rotateleft", x, x + icon, "icon", "rotate_left"))
        x += icon
        regions.append(("rotateright", x, x + icon, "icon", "rotate_right"))
        x += icon
        regions.append(("flipv", x, x + icon, "icon", "flip_v"))
        x += icon
        regions.append(("fliph", x, x + icon, "icon", "flip_h"))
        x += icon
        return regions, x + pad, h

    def rescale(self) -> None:
        """Re-measure for the current interface text size."""
        self.configure(width=theme.scaled(self._base_width),
                       height=theme.scaled(self._base_height))
        self.redraw()

    def redraw(self):
        self.delete("all")
        w = _dim(self, "w", 386)
        h = _dim(self, "h", 40)
        regions, _end, _h = self._layout()
        # shadow + surface
        rounded_rect(self, 3, 3, w - 3, h - 1, (h - 4) / 2, fill="#D8D8DD",
                     outline="")
        rounded_rect(self, 2, 2, w - 4, h - 4, (h - 6) / 2, fill=theme.SURFACE,
                     outline=theme.SEPARATOR, width=1)

        f = theme.fonts().body
        fc = theme.fonts().caption
        self._hot = []
        for key, x0, x1, kind, payload in regions:
            hovered = (self._hover == key)
            if kind == "sep":
                hairline(self, x0 + 6, 10, x0 + 6, h - 10, theme.SEPARATOR)
                continue
            if kind == "icon":
                self._hot.append((key, x0, x1))
                color = theme.ACCENT if hovered else theme.TEXT_2
                draw_icon(self, payload, (x0 + x1) / 2, h / 2,
                          theme.scaled(14), color)
            else:
                if key == "pagelabel":
                    text = f"{self.page} of {self.total}"
                    self.create_text((x0 + x1) / 2, h / 2, text=text,
                                     fill=theme.TEXT, font=f)
                else:
                    text = f"{round(self.zoom * 100)}%"
                    self.create_text((x0 + x1) / 2, h / 2, text=text,
                                     fill=theme.TEXT_2, font=fc)

    def _set_hover(self, key):
        if key != self._hover:
            self._hover = key
            self.redraw()

    def _on_motion(self, event):
        for key, x0, x1 in self._hot:
            if x0 <= event.x <= x1:
                self._set_hover(key)
                self.configure(cursor="hand2")
                self._tooltip.set_text(HINTS.get(key, ""))
                return
        self._set_hover(None)
        self.configure(cursor="arrow")
        self._tooltip.set_text("")

    def _on_click(self, event):
        for key, x0, x1 in self._hot:
            if x0 <= event.x <= x1:
                {
                    "prev": self.on_prev,
                    "next": self.on_next,
                    "zoomout": self.on_zoom_out,
                    "zoomin": self.on_zoom_in,
                    "fit": self.on_fit,
                    "rotateleft": self.on_rotate_left,
                    "rotateright": self.on_rotate_right,
                    "flipv": self.on_flip_v,
                    "fliph": self.on_flip_h,
                }.get(key, lambda: None)()
                return
