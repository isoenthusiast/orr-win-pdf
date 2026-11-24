"""Small themed dialogs that are not part of the main shell.

Kept apart from :mod:`pdfedit.widgets` because these are app-level windows
rather than reusable controls.
"""
from __future__ import annotations

import tkinter as tk

from . import theme
from .icons import draw_icon
from .widgets import RoundedButton


class DefaultAppPrompt(tk.Toplevel):
    """The one-off offer to become the default program for .pdf files.

    Three answers: set it, not now, or never ask again.  The answer is
    reported through the callbacks, so the caller decides what to remember.
    """

    def __init__(self, master, on_set=None, on_dismiss=None, on_never=None):
        super().__init__(master)
        self.title("Open PDFs with PDF Sign & Fill")
        self.configure(bg=theme.SURFACE)
        self.resizable(False, False)
        self.transient(master)
        self._on_set = on_set
        self._on_dismiss = on_dismiss
        self._on_never = on_never

        fonts = theme.fonts()
        body = tk.Frame(self, bg=theme.SURFACE)
        body.pack(fill="both", expand=True, padx=24, pady=(22, 8))

        badge = tk.Canvas(body, width=46, height=46, bg=theme.SURFACE,
                          highlightthickness=0, bd=0)
        badge.pack(side="left", anchor="n", padx=(0, 16))
        draw_icon(badge, "page", 23, 23, 30, theme.ACCENT)
        rounded = tk.Frame(body, bg=theme.SURFACE)
        rounded.pack(side="left", fill="both", expand=True)

        tk.Label(rounded, text="Open PDFs with PDF Sign & Fill?",
                 font=fonts.headline, bg=theme.SURFACE, fg=theme.TEXT,
                 anchor="w", justify="left").pack(anchor="w")
        tk.Label(rounded,
                 text="Double-click any PDF and it opens here, ready to\n"
                      "sign. You can change this later in\n"
                      "Settings > Apps > Default apps.",
                 font=fonts.body, bg=theme.SURFACE, fg=theme.TEXT_2,
                 anchor="w", justify="left").pack(anchor="w", pady=(6, 0))

        buttons = tk.Frame(self, bg=theme.SURFACE)
        buttons.pack(fill="x", padx=24, pady=(0, 20))

        RoundedButton(buttons, text="Set as default", variant="accent",
                      command=self._set, bg=theme.SURFACE).pack(side="right")
        RoundedButton(buttons, text="Not now", variant="gray",
                      command=self._dismiss, bg=theme.SURFACE).pack(
                          side="right", padx=(0, 8))
        RoundedButton(buttons, text="Don't ask again", variant="plain",
                      command=self._never, bg=theme.SURFACE).pack(side="left")

        self.bind("<Escape>", lambda _e: self._dismiss())
        self.protocol("WM_DELETE_WINDOW", self._dismiss)
        self.update_idletasks()
        self._center_over(master)

    # ------------------------------------------------------------------
    def _center_over(self, master) -> None:
        """Sit in the middle of the window it belongs to."""
        try:
            x = master.winfo_rootx() + (master.winfo_width() - self.winfo_width()) // 2
            y = master.winfo_rooty() + (master.winfo_height() - self.winfo_height()) // 2
            self.geometry(f"+{max(0, x)}+{max(0, y)}")
        except tk.TclError:
            pass

    # ------------------------------------------------------------------
    def _set(self) -> None:
        self.destroy()
        if self._on_set:
            self._on_set()

    def _dismiss(self) -> None:
        self.destroy()
        if self._on_dismiss:
            self._on_dismiss()

    def _never(self) -> None:
        self.destroy()
        if self._on_never:
            self._on_never()


class DefaultAppResult(tk.Toplevel):
    """Shown after the shell has been asked to make this app the default.

    It cannot know whether the user actually ticked "Always use this app",
    so it says what happens next rather than claiming success.
    """

    def __init__(self, master, on_open_settings=None):
        super().__init__(master)
        self.title("Almost there")
        self.configure(bg=theme.SURFACE)
        self.resizable(False, False)
        self.transient(master)

        fonts = theme.fonts()
        body = tk.Frame(self, bg=theme.SURFACE)
        body.pack(fill="both", expand=True, padx=24, pady=(22, 8))

        badge = tk.Canvas(body, width=46, height=46, bg=theme.SURFACE,
                          highlightthickness=0, bd=0)
        badge.pack(side="left", anchor="n", padx=(0, 16))
        draw_icon(badge, "page", 23, 23, 30, theme.SUCCESS)
        text = tk.Frame(body, bg=theme.SURFACE)
        text.pack(side="left", fill="both", expand=True)

        tk.Label(text, text="Tick 'Always use this app'",
                 font=fonts.headline, bg=theme.SURFACE, fg=theme.TEXT,
                 anchor="w", justify="left").pack(anchor="w")
        tk.Label(text,
                 text="Windows has opened its 'Open with' dialog.\n"
                      "Choose PDF Sign & Fill and tick\n"
                      "'Always use this app' to finish.\n\n"
                      "Or set it by hand in Settings > Apps > Default apps.",
                 font=fonts.body, bg=theme.SURFACE, fg=theme.TEXT_2,
                 anchor="w", justify="left").pack(anchor="w", pady=(6, 0))

        buttons = tk.Frame(self, bg=theme.SURFACE)
        buttons.pack(fill="x", padx=24, pady=(0, 20))
        RoundedButton(buttons, text="Open Default apps", variant="accent",
                      command=self._open_settings, bg=theme.SURFACE).pack(
                          side="right")
        RoundedButton(buttons, text="Close", variant="gray",
                      command=self.destroy, bg=theme.SURFACE).pack(
                          side="right", padx=(0, 8))

        self._on_open_settings = on_open_settings
        self.bind("<Escape>", lambda _e: self.destroy())
        self.protocol("WM_DELETE_WINDOW", self.destroy)
        self.update_idletasks()
        self._center_over(master)

    def _center_over(self, master) -> None:
        try:
            x = master.winfo_rootx() + (master.winfo_width() - self.winfo_width()) // 2
            y = master.winfo_rooty() + (master.winfo_height() - self.winfo_height()) // 2
            self.geometry(f"+{max(0, x)}+{max(0, y)}")
        except tk.TclError:
            pass

    def _open_settings(self) -> None:
        self.destroy()
        if self._on_open_settings:
            self._on_open_settings()
