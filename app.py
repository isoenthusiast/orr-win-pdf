"""Lightweight PDF viewer / editor for Windows.

Design goals: no build step, no web runtime, one PDF dependency.
The UI is plain Tkinter (ships with Python); every control is drawn by
`pdfedit.widgets` so the app looks like a modern native app rather than a
stock Tk one.  PyMuPDF does the PDF work.

Tools
  select    move / resize / delete existing overlays
  text      drop a text field on the page (for filling forms)
  check     drop a check mark
  cross     drop an X mark
  signature drop a transparent PNG signature
"""

from __future__ import annotations

import base64
import copy
import os
import sys
import tkinter as tk
from tkinter import colorchooser, filedialog, messagebox
from tkinter import font as tkfont

import pymupdf

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from pdfedit import assoc  # noqa: E402
from pdfedit import dnd  # noqa: E402
from pdfedit import prefs  # noqa: E402
from pdfedit import theme  # noqa: E402
from pdfedit.dialog import DefaultAppPrompt, DefaultAppResult  # noqa: E402
from pdfedit.engine import (  # noqa: E402
    CHECK,
    CROSS,
    DEFAULT_MARK_SIZE,
    DEFAULT_TEXT_SIZE,
    IMAGE,
    TEXT,
    Overlay,
    PdfDocument,
    check_segments,
    cross_segments,
    font_for,
    text_box_size,
)
from pdfedit.help import show_help as show_help_window  # noqa: E402
from pdfedit.icons import draw_icon  # noqa: E402
from pdfedit.transform import PageTransform  # noqa: E402
from pdfedit.widgets import (  # noqa: E402
    ColorSwatch,
    FloatingControls,
    IconButton,
    RoundedButton,
    RoundedEntry,
    SectionHeader,
    Stepper,
    hairline,
    rounded_rect,
)

APP_TITLE = "PDF Sign & Fill"
HANDLE = 6
PAD = 16


def _saved_scale() -> float:
    """The interface text size the user last chose.

    Anything outside the allowed range is ignored, so a hand-edited
    settings file cannot make the app unusable.
    """
    default = theme.SCALE_STEPS[1][1]
    try:
        value = float(prefs.get("interface_scale", default))
    except (TypeError, ValueError):
        return default
    return max(0.75, min(2.0, value))


def _pdf_error_message(path: str, exc: Exception) -> str:
    """Say what went wrong in words a person can act on."""
    text = str(exc)
    low = text.lower()
    name = os.path.basename(path)
    if "password" in low or "encrypted" in low:
        return (f"{name} is protected by a password.\n\n"
                "Open it in a reader that supports passwords, save an "
                "unprotected copy, and open that here.")
    if isinstance(exc, FileNotFoundError):
        return f"{name} no longer exists.\n\nIt may have been moved or deleted."
    if isinstance(exc, PermissionError):
        return (f"Windows will not let the app read {name}.\n\n"
                "It may be open in another program, or you may not have "
                "permission to read it.")
    if "no objects found" in low or "cannot open" in low or "damaged" in low \
            or "repair" in low or "not a pdf" in low:
        return (f"{name} could not be read as a PDF.\n\n"
                "It may be damaged, or it may not really be a PDF.")
    return f"{name}\n\n{text}"


def _dpi_awareness() -> None:
    """Crisp text on scaled Windows displays."""
    try:
        import ctypes
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except Exception:
        try:
            import ctypes
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass


def rgb_to_hex(color) -> str:
    r, g, b = [max(0, min(255, int(round(c * 255)))) for c in color]
    return f"#{r:02x}{g:02x}{b:02x}"


class PdfEditorApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        _dpi_awareness()
        # The interface text size is a preference, so it is applied before
        # anything is drawn - the fonts and the metrics follow from it.
        self._scale = _saved_scale()
        theme.set_scale(self._scale)
        self.fonts = theme.fonts()
        self.scale_var = tk.StringVar(value=str(self._scale))
        self.configure(bg=theme.BG)
        self.title(APP_TITLE)
        self.geometry("1360x880")
        self.minsize(1080, 700)
        self._set_app_icon()

        # --- state ------------------------------------------------------
        self.doc: PdfDocument | None = None
        self.page = 0
        self.zoom = 1.0
        self.tool = "select"
        self.selected: Overlay | None = None
        self.overlays: list[Overlay] = []
        self.undo_stack: list[list[Overlay]] = []
        self.saved_path: str | None = None
        self.sig_path: str | None = None
        self.dirty = False

        self.text_value = tk.StringVar()
        self.text_size = tk.DoubleVar(value=DEFAULT_TEXT_SIZE)
        self.text_color = (0.0, 0.0, 0.0)
        self.mark_size = tk.DoubleVar(value=DEFAULT_MARK_SIZE)
        self.mark_color = (0.20, 0.78, 0.35)    # Apple green
        self.cross_color = (1.0, 0.23, 0.19)     # Apple red

        self._photo = None            # page image (keep a reference!)
        self._sig_photos: dict[int, object] = {}
        self._ov_items: dict[int, list[int]] = {}
        self._drag: dict | None = None
        self._ox = 0.0                # page origin inside the scroll area
        self._oy = 0.0
        self._resize_job = None
        self._syncing_text = False    # True while we push values *into* fields
        self._text_edit_open = False  # True while a text edit session is live

        self._build_menu()
        self._build_shell()
        self.text_value.trace_add("write", self._on_text_changed)
        self.text_size.trace_add("write", self._on_text_size_changed)
        self._bind_keys()
        self._sync_tool_buttons()
        self._update_inspector()
        self._show_empty_state()
        # Offer to become the default PDF app once, after the window is up.
        self._default_prompt_job = self.after(900, self._maybe_offer_default)
        # Accept PDFs dropped from Explorer onto the window.
        self._drop_target = dnd.install(self)
        self._drop_hover = False
        self._poll_job = self.after(80, self._poll_drops)

    def _show_empty_state(self) -> None:
        """Friendly first-run screen instead of a blank canvas."""
        if self.doc:
            return
        self.canvas.delete("all")
        w = max(300, self.canvas.winfo_width())
        h = max(300, self.canvas.winfo_height())
        cx, cy = w / 2, h / 2 - 30
        rounded_rect(self.canvas, cx - 36, cy - 78, cx + 36, cy - 8, 16,
                     fill=theme.SURFACE, outline=theme.SEPARATOR, width=1)
        draw_icon(self.canvas, "folder", cx, cy - 43, 30, theme.TEXT_3)
        self.canvas.create_text(cx, cy + 20, text="Open a PDF to begin",
                                fill=theme.TEXT, font=self.fonts.headline)
        self.canvas.create_text(cx, cy + 46,
                                text="File ▸ Open, or press Ctrl + O",
                                fill=theme.TEXT_2, font=self.fonts.body)

    def _set_app_icon(self) -> None:
        """Use the generated app.ico for the window and taskbar."""
        if os.path.exists(self._resource_path("app.ico")):
            try:
                self.iconbitmap(self._resource_path("app.ico"))
            except Exception:
                pass

    @staticmethod
    def _resource_path(name: str) -> str:
        """Locate a bundled resource, in a PyInstaller build or from source."""
        base = getattr(sys, "_MEIPASS", None)
        if base:
            return os.path.join(base, name)
        return os.path.join(os.path.dirname(os.path.abspath(__file__)), name)

    # ==================================================================
    # shell
    # ==================================================================
    def _build_menu(self) -> None:
        menubar = tk.Menu(self)
        filemenu = tk.Menu(menubar, tearoff=0)
        filemenu.add_command(label="Open…", accelerator="Ctrl+O",
                             command=self.open_dialog)
        filemenu.add_command(label="Save", accelerator="Ctrl+S",
                             command=self.save)
        filemenu.add_command(label="Save As…", command=self.save_as)
        filemenu.add_separator()
        filemenu.add_command(label="Close document", command=self.close_doc)
        filemenu.add_separator()
        self.default_menu = filemenu
        filemenu.add_command(label="Make default PDF app…",
                             command=self.make_default_app)
        # add_command() does not hand back an index, so ask the menu where
        # the entry it just created ended up.
        self.default_item = filemenu.index("end")
        filemenu.add_command(label="Windows default apps…",
                             command=self.open_default_apps)
        filemenu.add_separator()
        filemenu.add_command(label="Exit", command=self.destroy)
        filemenu.postcommand = self._update_file_menu
        menubar.add_cascade(label="File", menu=filemenu)

        editmenu = tk.Menu(menubar, tearoff=0)
        editmenu.add_command(label="Undo", accelerator="Ctrl+Z",
                             command=self.undo)
        editmenu.add_command(label="Delete selected", accelerator="Del",
                             command=self.delete_selected)
        menubar.add_cascade(label="Edit", menu=editmenu)

        viewmenu = tk.Menu(menubar, tearoff=0)
        viewmenu.add_command(label="Zoom in", accelerator="Ctrl++",
                             command=lambda: self.set_zoom(self.zoom * 1.15))
        viewmenu.add_command(label="Zoom out", accelerator="Ctrl+-",
                             command=lambda: self.set_zoom(self.zoom / 1.15))
        viewmenu.add_command(label="Fit to window", command=self.fit_page)
        viewmenu.add_separator()
        sizemenu = tk.Menu(viewmenu, tearoff=0)
        for name, factor in theme.SCALE_STEPS:
            sizemenu.add_radiobutton(label=name, value=str(factor),
                                     variable=self.scale_var,
                                     command=self.set_interface_scale)
        viewmenu.add_cascade(label="Interface text size", menu=sizemenu)
        viewmenu.add_separator()
        viewmenu.add_command(label="Turn page left",
                             command=lambda: self.turn_page(-90))
        viewmenu.add_command(label="Turn page right",
                             command=lambda: self.turn_page(90))
        viewmenu.add_command(label="Flip page upside down",
                             command=lambda: self.flip_page(vertical=True))
        viewmenu.add_command(label="Flip page left to right",
                             command=lambda: self.flip_page(vertical=False))
        viewmenu.add_command(label="Reset page turn",
                             command=self.reset_page_turn)
        menubar.add_cascade(label="View", menu=viewmenu)

        helpmenu = tk.Menu(menubar, tearoff=0)
        helpmenu.add_command(label="How to use…", command=self.show_guide)
        helpmenu.add_command(label="Keyboard shortcuts", command=self.show_help)
        helpmenu.add_separator()
        helpmenu.add_command(label="About PDF Sign & Fill",
                             command=self.show_about)
        menubar.add_cascade(label="Help", menu=helpmenu)
        self.config(menu=menubar)

    def _build_shell(self) -> None:
        # ---------------- title bar ----------------
        bar = tk.Frame(self, bg=theme.SURFACE, height=theme.titlebar_h())
        bar.pack(side=tk.TOP, fill=tk.X)
        bar.pack_propagate(False)
        self.titlebar = bar

        left = tk.Frame(bar, bg=theme.SURFACE)
        left.pack(side=tk.LEFT, fill=tk.Y)
        icon_cv = tk.Canvas(left, width=22, height=22, bg=theme.SURFACE,
                            highlightthickness=0, bd=0)
        icon_cv.pack(side=tk.LEFT, padx=(18, 10))
        draw_icon(icon_cv, "page", 11, 11, 17, theme.TEXT_2)

        self.title_label = tk.Label(left, text="No document", bg=theme.SURFACE,
                                    fg=theme.TEXT, font=self.fonts.headline)
        self.title_label.pack(side=tk.LEFT)
        self.edited_dot = tk.Canvas(left, width=10, height=10,
                                    bg=theme.SURFACE, highlightthickness=0,
                                    bd=0)
        self.edited_dot.create_oval(1, 1, 9, 9, fill="#FF9500", outline="")

        right = tk.Frame(bar, bg=theme.SURFACE)
        right.pack(side=tk.RIGHT, fill=tk.Y, padx=(0, 18))
        self.undo_btn = IconButton(right, icon="undo", command=self.undo,
                                   tooltip="Undo  (Ctrl+Z)", size=32,
                                   icon_size=16, bg=theme.SURFACE,
                                   fg=theme.TEXT_2)
        self.undo_btn.pack(side=tk.RIGHT, padx=(6, 0))
        self.save_btn = RoundedButton(right, "Save as PDF", command=self.save_as,
                                      variant="accent", height=30,
                                      icon="save", bg=theme.SURFACE,
                                      font=self.fonts.body_emphasis,
                                      tooltip="Save as PDF  (Ctrl+S) - "
                                             "always writes a new file")
        self.save_btn.pack(side=tk.RIGHT)
        self.open_btn = IconButton(right, icon="folder",
                                   command=self.open_dialog,
                                   tooltip="Open…  (Ctrl+O)", size=32,
                                   icon_size=16, bg=theme.SURFACE,
                                   fg=theme.TEXT_2)
        self.open_btn.pack(side=tk.RIGHT, padx=(0, 4))
        self.help_btn = IconButton(right, icon="help", command=self.show_guide,
                                   tooltip="How to use", size=32,
                                   icon_size=17, bg=theme.SURFACE,
                                   fg=theme.TEXT_2)
        self.help_btn.pack(side=tk.RIGHT, padx=(0, 4))
        self.text_size_btn = IconButton(right, icon="text",
                                        command=self._show_text_size_menu,
                                        tooltip="Change the size of the "
                                                "interface text", size=32,
                                        icon_size=17, bg=theme.SURFACE,
                                        fg=theme.TEXT_2)
        self.text_size_btn.pack(side=tk.RIGHT, padx=(0, 4))

        # hairline under the title bar
        line = tk.Canvas(self, height=1, bg=theme.BG, highlightthickness=0,
                         bd=0)
        line.pack(side=tk.TOP, fill=tk.X)
        line.bind("<Configure>",
                  lambda e: hairline(line, 0, 0, e.width, 0, theme.SEPARATOR))

        # ---------------- body ----------------
        body = tk.Frame(self, bg=theme.BG)
        body.pack(side=tk.TOP, fill=tk.BOTH, expand=True)

        self._build_rail(body)
        self._build_center(body)
        self._build_inspector(body)

    # ------------------------------------------------------------------
    def _build_rail(self, parent) -> None:
        rail = tk.Frame(parent, bg=theme.SURFACE, width=theme.rail_w())
        rail.pack(side=tk.LEFT, fill=tk.Y)
        rail.pack_propagate(False)
        self.rail_frame = rail

        self.tool_buttons: dict[str, IconButton] = {}
        tools = (("select", "cursor", "Select and move  (V)"),
                 ("text", "text", "Add a text field  (T)"),
                 ("check", "check", "Add a check mark  (C)"),
                 ("cross", "cross", "Add a cross  (X)"),
                 ("signature", "signature", "Add your signature  (S)"))
        for key, icon, tip in tools:
            btn = IconButton(rail, icon=icon, size=38, icon_size=18,
                             bg=theme.SURFACE, fg=theme.TEXT_2,
                             tooltip=tip, radius=10,
                             command=lambda k=key: self.set_tool(k))
            btn.pack(pady=3)
            self.tool_buttons[key] = btn

        sep = tk.Canvas(rail, height=1, bg=theme.SURFACE, highlightthickness=0,
                        bd=0)
        sep.pack(fill=tk.X, padx=14, pady=12)
        sep.bind("<Configure>",
                 lambda e: hairline(sep, 0, 0, e.width, 0, theme.SEPARATOR))

    # ------------------------------------------------------------------
    def _build_center(self, parent) -> None:
        center = tk.Frame(parent, bg=theme.BG)
        center.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        wrap = tk.Frame(center, bg=theme.BG)
        wrap.pack(side=tk.TOP, fill=tk.BOTH, expand=True)

        self.canvas = tk.Canvas(wrap, bg=theme.CANVAS_BG,
                                highlightthickness=0, bd=0, takefocus=1)
        self.vbar = tk.Scrollbar(wrap, orient=tk.VERTICAL,
                                  command=self.canvas.yview,
                                  troughcolor=theme.BG, bd=0,
                                  highlightthickness=0, width=11,
                                  activebackground=theme.TEXT_3)
        self.hbar = tk.Scrollbar(wrap, orient=tk.HORIZONTAL,
                                  command=self.canvas.xview,
                                  troughcolor=theme.BG, bd=0,
                                  highlightthickness=0, width=11,
                                  activebackground=theme.TEXT_3)
        self.canvas.configure(yscrollcommand=self.vbar.set,
                              xscrollcommand=self.hbar.set)
        self.canvas.grid(row=0, column=0, sticky="nsew")
        self.vbar.grid(row=0, column=1, sticky="ns")
        self.hbar.grid(row=1, column=0, sticky="ew")
        wrap.grid_rowconfigure(0, weight=1)
        wrap.grid_columnconfigure(0, weight=1)

        self.canvas.bind("<ButtonPress-1>", self.on_press)
        self.canvas.bind("<B1-Motion>", self.on_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_release)
        self.canvas.bind("<Double-Button-1>", self.on_double_click)
        self.canvas.bind("<Button-3>", self.on_right_click)
        self.canvas.bind("<Motion>", self.on_motion)
        self.canvas.bind("<MouseWheel>", self.on_mousewheel)
        self.canvas.bind("<Configure>", self.on_canvas_configure)

        # floating context bar over the page
        self.floating = FloatingControls(
            center, on_prev=lambda: self.goto_page(self.page - 1),
            on_next=lambda: self.goto_page(self.page + 1),
            on_zoom_out=lambda: self.set_zoom(self.zoom / 1.15),
            on_zoom_in=lambda: self.set_zoom(self.zoom * 1.15),
            on_fit=self.fit_page,
            on_rotate_left=lambda: self.turn_page(-90),
            on_rotate_right=lambda: self.turn_page(90),
            on_flip_v=lambda: self.flip_page(vertical=True),
            on_flip_h=lambda: self.flip_page(vertical=False),
            height=40)
        self.floating.place(relx=0.5, rely=1.0, y=-16, anchor="s")

    # ------------------------------------------------------------------
    def _build_inspector(self, parent) -> None:
        panel = tk.Frame(parent, bg=theme.SURFACE, width=theme.inspector_w())
        panel.pack(side=tk.RIGHT, fill=tk.Y)
        panel.pack_propagate(False)
        self.inspector_frame = panel

        sep = tk.Canvas(panel, width=1, bg=theme.BG, highlightthickness=0, bd=0)
        sep.pack(side=tk.LEFT, fill=tk.Y)
        sep.bind("<Configure>",
                 lambda e: hairline(sep, 0, 0, 0, e.height, theme.SEPARATOR))

        inner = tk.Frame(panel, bg=theme.SURFACE)
        inner.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=PAD,
                   pady=10)

        # contextual hint for the active tool
        self.hint = tk.Label(inner, text="", bg=theme.SURFACE, fg=theme.TEXT_2,
                             font=self.fonts.caption, justify=tk.LEFT,
                             anchor="w", wraplength=theme.inspector_w() - 2 * theme.scaled(PAD))
        self.hint.pack(fill=tk.X, pady=(0, 2))

        # ---- text field ----
        SectionHeader(inner, "Text field").pack(fill=tk.X)
        self.text_entry = RoundedEntry(
            inner, textvariable=self.text_value,
            tooltip="Type here to fill the selected text field")
        self.text_entry.pack(fill=tk.X, pady=(0, 6))
        self.text_entry.entry.bind("<Return>",
                                   lambda e: self._apply_text_entry())
        self.text_entry.entry.bind("<FocusOut>",
                                   lambda e: self._apply_text_entry())

        row = tk.Frame(inner, bg=theme.SURFACE)
        row.pack(fill=tk.X, pady=(0, 4))
        tk.Label(row, text="Size", bg=theme.SURFACE, fg=theme.TEXT_2,
                 font=self.fonts.caption).pack(side=tk.LEFT)
        self.text_stepper = Stepper(row, variable=self.text_size, lo=4, hi=72,
                                    step=0.5, width=84, height=26,
                                    decimals=1, bg=theme.SURFACE,
                                    tooltip="Text size in points")
        self.text_stepper.pack(side=tk.LEFT, padx=(10, 0))
        self.text_swatch = ColorSwatch(row, color=self.text_color,
                                       command=self._pick_text_color,
                                       bg=theme.SURFACE,
                                       tooltip="Text colour")
        self.text_swatch.pack(side=tk.LEFT, padx=(10, 0))

        SectionHeader(inner, "Marks").pack(fill=tk.X, pady=(12, 0))
        row2 = tk.Frame(inner, bg=theme.SURFACE)
        row2.pack(fill=tk.X, pady=(0, 4))
        tk.Label(row2, text="Size", bg=theme.SURFACE, fg=theme.TEXT_2,
                 font=self.fonts.caption).pack(side=tk.LEFT)
        self.mark_stepper = Stepper(row2, variable=self.mark_size, lo=6, hi=80,
                                    step=1, width=84, height=26,
                                    bg=theme.SURFACE,
                                    tooltip="Size of the tick and the cross")
        self.mark_stepper.pack(side=tk.LEFT, padx=(10, 0))
        self.check_swatch = ColorSwatch(row2, color=self.mark_color,
                                        command=self._pick_check_color,
                                        bg=theme.SURFACE,
                                        tooltip="Tick colour")
        self.check_swatch.pack(side=tk.LEFT, padx=(10, 4))
        self.cross_swatch = ColorSwatch(row2, color=self.cross_color,
                                        command=self._pick_cross_color,
                                        bg=theme.SURFACE,
                                        tooltip="Cross colour")
        self.cross_swatch.pack(side=tk.LEFT)

        # ---- signature ----
        SectionHeader(inner, "Signature").pack(fill=tk.X, pady=(12, 0))
        inner_w = theme.inspector_w() - 2 * theme.scaled(PAD)
        RoundedButton(inner, "Load PNG file…", self.load_signature,
                      variant="gray", width=inner_w, height=28,
                      bg=theme.SURFACE, font=self.fonts.body,
                      tooltip="Choose a PNG to sign with").pack(fill=tk.X,
                                                                pady=(0, 4))
        RoundedButton(inner, "Paste from clipboard", self.paste_signature,
                      variant="gray", width=inner_w, height=28,
                      bg=theme.SURFACE, font=self.fonts.body,
                      tooltip="Paste an image you copied").pack(fill=tk.X,
                                                                pady=(0, 4))
        RoundedButton(inner, "Append as new page…",
                      self.append_signature_page, variant="gray",
                      width=inner_w, height=28, bg=theme.SURFACE,
                      font=self.fonts.body,
                      tooltip="Add the signature as a new page").pack(fill=tk.X)
        self.sig_label = tk.Label(inner, text="No signature loaded",
                                  bg=theme.SURFACE, fg=theme.TEXT_3,
                                  font=self.fonts.caption, anchor="w",
                                  justify=tk.LEFT)
        self.sig_label.pack(fill=tk.X, pady=(6, 0))

        # ---- page turn ----
        SectionHeader(inner, "Page turn").pack(fill=tk.X, pady=(14, 0))
        turn_row = tk.Frame(inner, bg=theme.SURFACE)
        turn_row.pack(fill=tk.X, pady=(0, 4))
        for icon, tip, cmd in (
                ("rotate_left", "Turn the page anticlockwise",
                 lambda: self.turn_page(-90)),
                ("rotate_right", "Turn the page clockwise",
                 lambda: self.turn_page(90)),
                ("flip_v", "Flip the page upside down",
                 lambda: self.flip_page(vertical=True)),
                ("flip_h", "Flip the page left to right",
                 lambda: self.flip_page(vertical=False))):
            btn = IconButton(turn_row, icon=icon, size=30, icon_size=15,
                             bg=theme.SURFACE, fg=theme.TEXT_2, tooltip=tip,
                             radius=8, command=cmd)
            btn.pack(side=tk.LEFT, padx=(0, 6))
        RoundedButton(turn_row, "Reset", self.reset_page_turn, variant="gray",
                      width=62, height=26, bg=theme.SURFACE,
                      font=self.fonts.caption).pack(side=tk.RIGHT)
        self.turn_label = tk.Label(inner, text="Straight", bg=theme.SURFACE,
                                   fg=theme.TEXT_3, font=self.fonts.caption,
                                   anchor="w", justify=tk.LEFT,
                                   wraplength=inner_w)
        self.turn_label.pack(fill=tk.X, pady=(2, 0))

        # ---- selection ----
        SectionHeader(inner, "Selection").pack(fill=tk.X, pady=(14, 0))
        self.sel_label = tk.Label(inner, text="Nothing selected",
                                  bg=theme.SURFACE, fg=theme.TEXT_2,
                                  font=self.fonts.caption, anchor="w",
                                  justify=tk.LEFT, wraplength=inner_w)
        self.sel_label.pack(fill=tk.X)
        self.delete_btn = RoundedButton(inner, "Delete", self.delete_selected,
                                        variant="gray", width=inner_w,
                                        height=28, bg=theme.SURFACE,
                                        font=self.fonts.body,
                                        tooltip="Delete the selected item  (Del)")
        self.delete_btn.pack(fill=tk.X, pady=(8, 0))
        self.delete_btn.set_enabled(False)

    # ==================================================================
    # document handling
    # ==================================================================
    def open_dialog(self) -> None:
        path = filedialog.askopenfilename(
            title="Open PDF",
            filetypes=[("PDF files", "*.pdf"), ("All files", "*.*")])
        if path:
            self.open_file(path)

    def open_file(self, path: str) -> None:
        try:
            doc = PdfDocument(path)
        except Exception as exc:
            messagebox.showerror("Cannot open",
                                 _pdf_error_message(path, exc))
            return
        if self.doc:
            self.doc.close()
        self.doc = doc
        self.overlays = []
        self.undo_stack = []
        self.selected = None
        self.saved_path = None
        self.dirty = False
        self.page = 0
        name = os.path.basename(path)
        self.title_label.config(text=name)
        self.title(f"{name} — {APP_TITLE}")
        self._set_edited(False)
        self.canvas.delete("all")
        self.fit_page()
        self._update_inspector()

    def close_doc(self) -> None:
        if self.doc:
            self.doc.close()
        self.doc = None
        self.overlays = []
        self.canvas.delete("all")
        self.title_label.config(text="No document")
        self.title(APP_TITLE)
        self._set_edited(False)
        self._update_inspector()
        self._show_empty_state()

    def _set_edited(self, edited: bool) -> None:
        self.dirty = edited
        if edited:
            self.edited_dot.pack(side=tk.LEFT, padx=(8, 0))
        else:
            self.edited_dot.pack_forget()

    # ==================================================================
    # rendering
    # ==================================================================
    def _cancel_resize_job(self) -> None:
        """Drop a pending layout redraw (it may target a stale state)."""
        if self._resize_job:
            try:
                self.after_cancel(self._resize_job)
            except Exception:
                pass
            self._resize_job = None

    def render_page(self) -> None:
        if not self.doc:
            return
        self._cancel_resize_job()
        try:
            png = self.doc.render_png(self.page, self.zoom)
        except Exception as exc:
            messagebox.showerror("Render failed", str(exc))
            return

        data = base64.b64encode(png).decode("ascii")
        self._photo = tk.PhotoImage(data=data)
        self.canvas.delete("all")
        self._ov_items.clear()
        self._sig_photos.clear()

        pw, ph = self._photo.width(), self._photo.height()
        self._ox = self._center_offset(pw, self.canvas.winfo_width())
        self._oy = self._center_offset(ph, self.canvas.winfo_height())

        # soft shadow under the page
        for i, col in enumerate(("#DCDCE1", "#D6D6DC", "#D0D0D7", "#CACAD1")):
            o = i * 0.9
            self.canvas.create_rectangle(
                self._ox - 2 + o, self._oy - 1 + o,
                self._ox + pw + 2 + o, self._oy + ph + 3 + o,
                fill=col, outline="")
        self.canvas.create_image(self._ox, self._oy, anchor=tk.NW,
                                 image=self._photo)
        self.canvas.create_rectangle(self._ox - 0.5, self._oy - 0.5,
                                     self._ox + pw + 0.5, self._oy + ph + 0.5,
                                     outline=theme.PAGE_EDGE, width=1)

        for ov in self.doc.overlays_on(self.page):
            self.draw_overlay(ov)
        self.draw_selection()
        self.canvas.configure(scrollregion=(0, 0, self._ox + pw + 24,
                                            self._oy + ph + 24))
        self.floating.update(self.page + 1, self.doc.page_count, self.zoom)

    @staticmethod
    def _center_offset(size: float, viewport: float) -> float:
        """Centre the page in the viewport when it fits, else pad it."""
        if viewport <= 1:
            return 0.0
        return max(0.0, (viewport - size) / 2)

    def draw_overlay(self, ov: Overlay) -> None:
        z = self.zoom
        ox, oy = self._ox, self._oy
        tag = f"ov{ov.oid}"
        ids: list[int] = []
        if ov.kind == TEXT:
            family = "Microsoft YaHei UI" if font_for(ov.text) == "china-s" \
                else "Segoe UI Variable Text"
            px = max(4, int(round(ov.font_size * z)))
            tk_font = tkfont.Font(family=family, size=-px)
            ascent = tk_font.metrics("ascent")
            ids.append(self.canvas.create_text(
                ox + ov.x0 * z, oy + ov.baseline * z - ascent,
                text=ov.text, anchor=tk.NW, fill=rgb_to_hex(ov.color),
                font=(family, -px), tags=(tag,)))
            ids.append(self.canvas.create_rectangle(
                ox + ov.x0 * z, oy + ov.y0 * z,
                ox + ov.x1 * z, oy + ov.y1 * z,
                outline=theme.OVERLAY_BOX, width=1, dash=(4, 3), tags=(tag,)))
        elif ov.kind == IMAGE:
            ids.append(self.canvas.create_image(
                ox + ov.x0 * z, oy + ov.y0 * z, anchor=tk.NW,
                image=self._signature_photo(ov), tags=(tag,)))
            ids.append(self.canvas.create_rectangle(
                ox + ov.x0 * z, oy + ov.y0 * z,
                ox + ov.x1 * z, oy + ov.y1 * z,
                outline=theme.OVERLAY_BOX, width=1, dash=(4, 3), tags=(tag,)))
        elif ov.kind in (CHECK, CROSS):
            cx = ox + (ov.x0 + ov.x1) / 2 * z
            cy = oy + (ov.y0 + ov.y1) / 2 * z
            size = min(ov.width, ov.height) * z
            segs = (check_segments(cx, cy, size) if ov.kind == CHECK
                    else cross_segments(cx, cy, size))
            color = rgb_to_hex(ov.color)
            width = max(1, ov.stroke * z)
            for (ax, ay), (bx, by) in segs:
                ids.append(self.canvas.create_line(ax, ay, bx, by, fill=color,
                                                   width=width,
                                                   capstyle=tk.ROUND))
        self._ov_items[ov.oid] = ids

    def _signature_photo(self, ov: Overlay):
        key = ov.oid
        if key in self._sig_photos:
            return self._sig_photos[key]
        w = max(1, int(round(ov.width * self.zoom)))
        h = max(1, int(round(ov.height * self.zoom)))
        try:
            from PIL import Image, ImageTk
            img = Image.open(ov.path).convert("RGBA")
            if ov.angle % 360:
                img = img.rotate(-(ov.angle % 360), expand=True)
            img = img.resize((w, h), Image.LANCZOS)
            photo = ImageTk.PhotoImage(img)
        except Exception:
            with open(ov.path, "rb") as fh:
                data = base64.b64encode(fh.read()).decode("ascii")
            photo = tk.PhotoImage(data=data)
        self._sig_photos[key] = photo
        return photo

    def draw_selection(self) -> None:
        self.canvas.delete("sel")
        if not self.selected:
            return
        ov = self.selected
        z, ox, oy = self.zoom, self._ox, self._oy
        self.canvas.create_rectangle(
            ox + ov.x0 * z, oy + ov.y0 * z, ox + ov.x1 * z, oy + ov.y1 * z,
            outline=theme.SELECT, width=2, tags=("sel",))
        self.canvas.create_rectangle(
            ox + ov.x1 * z - HANDLE, oy + ov.y1 * z - HANDLE,
            ox + ov.x1 * z + HANDLE, oy + ov.y1 * z + HANDLE,
            fill=theme.SELECT, outline=theme.SURFACE, width=1.5, tags=("sel",))

    def redraw_overlays(self) -> None:
        """Repaint overlays for the current page (after an edit)."""
        for ids in self._ov_items.values():
            for item in ids:
                self.canvas.delete(item)
        self._ov_items.clear()
        for ov in self.overlays:
            if ov.page == self.page:
                self.draw_overlay(ov)
        self.draw_selection()

    # ==================================================================
    # navigation & zoom
    # ==================================================================
    def goto_page(self, page: int) -> None:
        if not self.doc:
            return
        page = max(0, min(self.doc.page_count - 1, page))
        if page == self.page and self._photo is not None:
            return
        self.page = page
        self.deselect()
        self.render_page()
        self._update_turn_label()

    def set_zoom(self, zoom: float) -> None:
        self.zoom = max(0.2, min(6.0, zoom))
        self.render_page()

    def fit_page(self) -> None:
        if not self.doc:
            return
        w, h = self.doc.page_size(self.page)
        vw = max(200, self.canvas.winfo_width())
        vh = max(200, self.canvas.winfo_height())
        self.zoom = max(0.2, min(6.0, min(vw / w, vh / h) * 0.94))
        self.render_page()

    def on_canvas_configure(self, event) -> None:
        self._cancel_resize_job()
        if not self.doc:
            self._resize_job = self.after(80, self._show_empty_state)
            return
        self._resize_job = self.after(120, self.render_page)

    def on_mousewheel(self, event) -> None:
        if self.doc:
            self.set_zoom(self.zoom * (1.1 if event.delta > 0 else 1 / 1.1))

    # ==================================================================
    # tools
    # ==================================================================
    def set_tool(self, tool: str) -> None:
        self.tool = tool
        self._sync_tool_buttons()
        self._update_inspector()

    def _sync_tool_buttons(self) -> None:
        for key, btn in self.tool_buttons.items():
            btn.set_active(key == self.tool)

    def _update_inspector(self) -> None:
        hints = {
            "select": "Select — click an item to select it, drag to move it, "
                      "drag the blue handle to resize it. Del removes it.",
            "text": "Text — click a ruled line to add text. Click an existing "
                    "text item to edit it instead.",
            "check": "Check — click where the tick should go. Clicking an "
                     "existing item selects it instead.",
            "cross": "Cross — click where the X should go.",
            "signature": "Signature — click to drop the PNG on the page.",
        }
        self.hint.config(text=hints.get(self.tool, ""))
        has_doc = self.doc is not None
        self.undo_btn.set_enabled(has_doc)
        self.save_btn.set_enabled(has_doc)
        self.delete_btn.set_enabled(has_doc and self.selected is not None)
        self._update_turn_label()
        if has_doc:
            self.floating.place(relx=0.5, rely=1.0, y=-16, anchor="s")
        else:
            self.floating.place_forget()

    # ==================================================================
    # mouse handling
    # ==================================================================
    def canvas_to_pdf(self, cx: float, cy: float) -> tuple[float, float]:
        return (cx - self._ox) / self.zoom, (cy - self._oy) / self.zoom

    def hit_test(self, px: float, py: float) -> Overlay | None:
        if not self.doc:
            return None
        tol = 4.0 / self.zoom
        for ov in reversed(self.doc.overlays_on(self.page)):
            if (ov.x0 - tol <= px <= ov.x1 + tol
                    and ov.y0 - tol <= py <= ov.y1 + tol):
                return ov
        return None

    def _hit_handle(self, ov: Overlay, event) -> bool:
        """True when the click landed on the object's bottom-right handle."""
        hx = self._ox + ov.x1 * self.zoom
        hy = self._oy + ov.y1 * self.zoom
        return (abs(event.x - hx) <= HANDLE + 6
                and abs(event.y - hy) <= HANDLE + 6)

    def on_press(self, event) -> None:
        if not self.doc:
            return
        self.canvas.focus_set()
        px, py = self.canvas_to_pdf(event.x, event.y)
        hit = self.hit_test(px, py)

        # Clicking an existing object always *selects* it - it never appends.
        # Dragging moves it; grabbing the corner handle resizes it.
        if hit is not None:
            was_selected = self.selected is hit
            self.select(hit)
            if self._hit_handle(hit, event):
                self._drag = {"mode": "resize", "ov": hit,
                              "sx": event.x, "sy": event.y,
                              "w": hit.width, "h": hit.height,
                              "size": hit.font_size, "baseline": hit.baseline,
                              "moved": False}
            else:
                self._drag = {"mode": "move", "ov": hit,
                              "sx": event.x, "sy": event.y,
                              "x0": hit.x0, "y0": hit.y0,
                              "w": hit.width, "h": hit.height,
                              "moved": False}
            if was_selected and hit.kind == TEXT:
                # Second click on a text object = "I want to edit this".
                self._focus_text_entry(select_all=False)
            return

        # Empty space: with a placement tool this means "add a new one".
        if self.tool == "select":
            self.deselect()
            return

        if self.tool == "text":
            self.push_undo()
            ov = self.doc.add_text(self.page, px, py,
                                    text=self.text_value.get(),
                                    size=self.text_size.get(),
                                    color=self.text_color)
            self.overlays = self.doc.overlays
            self.select(ov)
            self.redraw_overlays()
            self._focus_text_entry()
            return

        if self.tool == "check":
            self.push_undo()
            ov = self.doc.add_check(self.page, px, py,
                                     size=self.mark_size.get(),
                                     color=self.mark_color)
            self.overlays = self.doc.overlays
            self.select(ov)
            self.redraw_overlays()
            return

        if self.tool == "cross":
            self.push_undo()
            ov = self.doc.add_cross(self.page, px, py,
                                     size=self.mark_size.get(),
                                     color=self.cross_color)
            self.overlays = self.doc.overlays
            self.select(ov)
            self.redraw_overlays()
            return

        if self.tool == "signature":
            if not self.sig_path:
                self.load_signature()
                if not self.sig_path:
                    return
            self.push_undo()
            w, h = self.doc.page_size(self.page)
            img_w, img_h = self._image_size(self.sig_path)
            target_w = w * 0.28
            scale = target_w / img_w if img_w else 1.0
            target_h = img_h * scale
            ov = self.doc.add_image(self.page, self.sig_path,
                                    px - target_w / 2, py - target_h / 2,
                                    target_w, target_h)
            self.overlays = self.doc.overlays
            self.select(ov)
            self.redraw_overlays()

    def on_motion(self, event) -> None:
        """Cursor feedback: show what a click would do."""
        if self._drag or not self.doc:
            return
        px, py = self.canvas_to_pdf(event.x, event.y)
        hit = self.hit_test(px, py)
        if hit is not None and self._hit_handle(hit, event):
            self.canvas.configure(cursor="size_nw_se")
        elif hit is not None:
            self.canvas.configure(cursor="fleur")
        elif self.tool in ("text", "check", "cross", "signature"):
            self.canvas.configure(cursor="crosshair")
        else:
            self.canvas.configure(cursor="arrow")

    def on_drag(self, event) -> None:
        if not self._drag:
            return
        ov = self._drag["ov"]
        z = self.zoom
        shift = bool(event.state & 0x0001)     # Shift = free / unconstrained
        if not self._drag.get("moved"):
            # Snapshot the pre-drag state once, and only if we really move.
            self.push_undo()
            self._drag["moved"] = True
        if self._drag["mode"] == "move":
            dx = (event.x - self._drag["sx"]) / z
            dy = (event.y - self._drag["sy"]) / z
            # the size is taken from the drag start - reading ov.width here
            # would already see the new x0 and collapse the object
            ov.x0 = self._drag["x0"] + dx
            ov.y0 = self._drag["y0"] + dy
            ov.x1 = ov.x0 + self._drag["w"]
            ov.y1 = ov.y0 + self._drag["h"]
        else:
            dx = (event.x - self._drag["sx"]) / z
            dy = (event.y - self._drag["sy"]) / z
            if ov.kind == IMAGE:
                new_w = max(12, self._drag["w"] + dx)
                new_h = max(12, self._drag["h"] + dy)
                if not shift:
                    # keep the signature's proportions
                    ratio = self._drag["h"] / max(self._drag["w"], 0.01)
                    new_h = new_w * ratio
                ov.x1 = ov.x0 + new_w
                ov.y1 = ov.y0 + new_h
            elif ov.kind == TEXT:
                new_h = max(4, self._drag["h"] + dy)
                ov.font_size = max(4, min(72, self._drag["size"]
                                          * new_h / max(self._drag["h"], 1)))
                ov.y0 = self._drag["baseline"] - ov.font_size * 0.75
                w, h = text_box_size(ov.text, ov.font_size)
                ov.x1 = ov.x0 + max(w + 2.0, 24.0)
                ov.y1 = ov.y0 + max(h, ov.font_size * 1.35)
            else:
                size = max(6, min(self._drag["h"] + dy, self._drag["w"] + dx))
                cx, cy = (ov.x0 + ov.x1) / 2, (ov.y0 + ov.y1) / 2
                ov.x0, ov.y0 = cx - size / 2, cy - size / 2
                ov.x1, ov.y1 = cx + size / 2, cy + size / 2
        self.redraw_overlays()
        self._update_selection_label()

    def on_release(self, _event) -> None:
        if self._drag:
            self._drag = None
            self.redraw_overlays()

    def on_double_click(self, event) -> None:
        """The second click of a double click never reaches <ButtonPress-1>.

        Tk routes it here instead, so we make sure the click is not lost:
        the object under the cursor is selected, and a text object opens
        for editing.
        """
        if not self.doc:
            return
        px, py = self.canvas_to_pdf(event.x, event.y)
        ov = self.hit_test(px, py)
        if ov is None:
            return
        self.select(ov)
        if ov.kind == TEXT:
            self.edit_text_of(ov)

    def on_right_click(self, event) -> None:
        px, py = self.canvas_to_pdf(event.x, event.y)
        ov = self.hit_test(px, py)
        if not ov:
            return
        menu = tk.Menu(self, tearoff=0, bg=theme.SURFACE,
                       activebackground=theme.ACCENT,
                       activeforeground=theme.TEXT_ON_ACCENT,
                       bd=0, relief=tk.FLAT)
        if ov.kind == TEXT:
            menu.add_command(label="Edit text…",
                             command=lambda: self.edit_text_of(ov))
        menu.add_command(label="Delete", command=lambda: self.delete_overlay(ov))
        menu.add_command(label="Bring to front",
                         command=lambda: self.bring_to_front(ov))
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()

    # ==================================================================
    # selection & editing
    # ==================================================================
    def select(self, ov: Overlay | None) -> None:
        self.selected = ov
        self._text_edit_open = False
        self.delete_btn.set_enabled(ov is not None)
        if ov:
            self._update_selection_label()
            if ov.kind == TEXT:
                self._syncing_text = True
                try:
                    self.text_value.set(ov.text)
                    self.text_size.set(ov.font_size)
                finally:
                    self._syncing_text = False
                self.text_color = ov.color
                self.text_swatch.set_color(ov.color)
                self.text_stepper.redraw()
        else:
            self.sel_label.config(text="Nothing selected")
        self.draw_selection()

    def _update_selection_label(self) -> None:
        """Live position / size readout (refreshes while dragging)."""
        ov = self.selected
        if not ov:
            return
        self.sel_label.config(
            text=f"{ov.kind.upper()}  ·  page {ov.page + 1}\n"
                 f"x {ov.x0:.0f}   y {ov.y0:.0f}\n"
                 f"w {ov.width:.0f}   h {ov.height:.0f}")

    def _focus_text_entry(self, select_all: bool = True) -> None:
        """Put the caret in the sidebar field so typing edits the object."""
        entry = self.text_entry.entry
        entry.focus_set()
        if select_all:
            entry.selection_range(0, tk.END)
        else:
            # drop the old selection, otherwise the first keystroke would
            # replace the whole text instead of editing it
            entry.icursor(tk.END)
            entry.selection_clear()

    def _on_text_changed(self, *_args) -> None:
        """Live-update the selected text field as the user types."""
        if self._syncing_text:
            return
        ov = self.selected
        if ov is None or ov.kind != TEXT:
            return
        value = self.text_value.get()
        if ov.text == value:
            return
        if not self._text_edit_open:
            self.push_undo()
            self._text_edit_open = True
        ov.text = value
        ov.fit_text()
        self.redraw_overlays()
        self._update_selection_label()

    def _on_text_size_changed(self, *_args) -> None:
        """The size stepper re-types the selected text object live."""
        if self._syncing_text:
            return
        ov = self.selected
        if ov is None or ov.kind != TEXT:
            return
        size = self.text_size.get()
        if abs(ov.font_size - size) < 0.01:
            return
        if not self._text_edit_open:
            self.push_undo()
            self._text_edit_open = True
        ov.font_size = size
        ov.fit_text()
        self.redraw_overlays()
        self._update_selection_label()

    def deselect(self) -> None:
        self.selected = None
        self.sel_label.config(text="Nothing selected")
        self.delete_btn.set_enabled(False)
        self.canvas.delete("sel")

    def edit_text_of(self, ov: Overlay) -> None:
        """Edit a text object inline: select it and put the caret in the field."""
        self.select(ov)
        self._focus_text_entry()

    def delete_selected(self) -> None:
        if self.selected:
            self.delete_overlay(self.selected)

    def delete_overlay(self, ov: Overlay) -> None:
        self.push_undo()
        if self.doc:
            self.doc.remove(ov)
        self.overlays = self.doc.overlays if self.doc else []
        self.deselect()
        self.redraw_overlays()

    def bring_to_front(self, ov: Overlay) -> None:
        self.push_undo()
        if self.doc:
            self.doc.remove(ov)
            self.doc.overlays.append(ov)
        self.overlays = self.doc.overlays if self.doc else []
        self.redraw_overlays()

    def _apply_text_entry(self) -> None:
        """Push the sidebar text into the selected text field."""
        self._on_text_changed()

    def _pick_text_color(self) -> None:
        rgb = colorchooser.askcolor(color=rgb_to_hex(self.text_color),
                                    parent=self)[0]
        if rgb:
            self.text_color = tuple(c / 255 for c in rgb)
            self.text_swatch.set_color(self.text_color)
            if self.selected and self.selected.kind == TEXT:
                self.selected.color = self.text_color
                self.redraw_overlays()

    def _pick_check_color(self) -> None:
        rgb = colorchooser.askcolor(color=rgb_to_hex(self.mark_color),
                                    parent=self)[0]
        if rgb:
            self.mark_color = tuple(c / 255 for c in rgb)
            self.check_swatch.set_color(self.mark_color)

    def _pick_cross_color(self) -> None:
        rgb = colorchooser.askcolor(color=rgb_to_hex(self.cross_color),
                                    parent=self)[0]
        if rgb:
            self.cross_color = tuple(c / 255 for c in rgb)
            self.cross_swatch.set_color(self.cross_color)

    # ==================================================================
    # undo
    # ==================================================================
    def push_undo(self) -> None:
        if not self.doc:
            return
        self.undo_stack.append({
            "overlays": copy.deepcopy(self.doc.overlays),
            "transforms": dict(self.doc.transforms),
        })
        if len(self.undo_stack) > 100:
            self.undo_stack.pop(0)
        self._set_edited(True)

    def undo(self) -> None:
        if not self.doc or not self.undo_stack:
            return
        state = self.undo_stack.pop()
        self.doc.overlays = state["overlays"]
        self.doc.transforms = state["transforms"]
        self.overlays = self.doc.overlays
        self.deselect()
        self.render_page()
        self.redraw_overlays()

    # ==================================================================
    # turning a page
    # ==================================================================
    def turn_page(self, degrees: int) -> None:
        """Turn the current page: -90 is anticlockwise, +90 is clockwise."""
        if not self.doc:
            return
        self.push_undo()
        old_size = self.doc.page_size(self.page)
        current = self.doc.get_transform(self.page)
        if degrees >= 0:
            self.doc.set_transform(self.page, current.rotate_right())
            self._carry_overlays(self.page, "right", old_size)
        else:
            self.doc.set_transform(self.page, current.rotate_left())
            self._carry_overlays(self.page, "left", old_size)
        self._after_page_turn()

    def flip_page(self, vertical: bool) -> None:
        """Mirror the page, upside down or left to right."""
        if not self.doc:
            return
        self.push_undo()
        old_size = self.doc.page_size(self.page)
        current = self.doc.get_transform(self.page)
        self.doc.set_transform(
            self.page,
            current.flipped_v() if vertical else current.flipped_h())
        self._carry_overlays(self.page, "flipv" if vertical else "fliph",
                             old_size)
        self._after_page_turn()

    def _carry_overlays(self, page: int, how: str,
                        old_size: tuple[float, float]) -> None:
        """Move the things you added along with the page when it turns.

        They stay upright and readable - it is the page underneath that
        turns, not your writing.
        """
        w, h = old_size
        if how == "right":
            def fn(x, y):
                return h - y, x
        elif how == "left":
            def fn(x, y):
                return y, w - x
        elif how == "fliph":
            def fn(x, y):
                return w - x, y
        else:
            def fn(x, y):
                return x, h - y

        for ov in self.doc.overlays_on(page):
            if ov.kind == TEXT:
                bx, by = fn(ov.x0, ov.baseline)
                tw, th = text_box_size(ov.text, ov.font_size)
                ov.x0 = bx
                ov.y0 = by - ov.font_size * 0.75
                ov.x1 = ov.x0 + max(tw + 2.0, 24.0)
                ov.y1 = ov.y0 + max(th, ov.font_size * 1.35)
            elif ov.kind in (CHECK, CROSS):
                cx, cy = fn((ov.x0 + ov.x1) / 2, (ov.y0 + ov.y1) / 2)
                half = ov.width / 2
                ov.x0, ov.y0 = cx - half, cy - half
                ov.x1, ov.y1 = cx + half, cy + half
            else:                       # IMAGE - the box turns, the picture too
                pts = [fn(ov.x0, ov.y0), fn(ov.x1, ov.y0),
                       fn(ov.x0, ov.y1), fn(ov.x1, ov.y1)]
                xs = [p[0] for p in pts]
                ys = [p[1] for p in pts]
                ov.x0, ov.y0 = min(xs), min(ys)
                ov.x1, ov.y1 = max(xs), max(ys)
                if how in ("right", "left"):
                    ov.angle = (ov.angle + 90) % 360

    def reset_page_turn(self) -> None:
        """Put the page back the way it was."""
        if not self.doc or self.doc.get_transform(self.page).identity:
            return
        self.push_undo()
        self.doc.set_transform(self.page, PageTransform())
        self._after_page_turn()

    def _after_page_turn(self) -> None:
        """Re-lay out the page after it was turned."""
        self.deselect()
        self.render_page()
        self._update_turn_label()

    def _update_turn_label(self) -> None:
        """Describe how the current page is turned."""
        if not hasattr(self, "turn_label"):
            return
        if not self.doc:
            self.turn_label.config(text="No document")
            return
        transform = self.doc.get_transform(self.page)
        bits = []
        if transform.rot:
            bits.append(f"{transform.rot}° "
                        + ("clockwise" if transform.rot == 90 else
                           "upside down" if transform.rot == 180
                           else "anticlockwise"))
        if transform.flip_h:
            bits.append("mirrored left to right")
        if transform.flip_v:
            bits.append("mirrored upside down")
        self.turn_label.config(text="Straight" if not bits
                               else " · ".join(bits))

    # ==================================================================
    # signature helpers
    # ==================================================================
    def load_signature(self) -> None:
        path = filedialog.askopenfilename(
            title="Choose signature PNG",
            filetypes=[("PNG images", "*.png"),
                       ("All images", "*.jpg;*.jpeg;*.bmp"),
                       ("All files", "*.*")])
        if path:
            self._set_signature(path)

    def paste_signature(self) -> None:
        try:
            from PIL import ImageGrab
            img = ImageGrab.grabclipboard()
        except Exception:
            img = None
        if img is None:
            messagebox.showinfo("Paste signature",
                                "The clipboard does not contain an image.")
            return
        if isinstance(img, list):
            messagebox.showinfo("Paste signature",
                                "The clipboard contains files, not an image.")
            return
        try:
            from pdfedit.engine import save_png_temp
            path = save_png_temp(img.convert("RGBA"))
        except Exception as exc:
            messagebox.showerror("Paste signature", str(exc))
            return
        self._set_signature(path)

    def _set_signature(self, path: str) -> None:
        self.sig_path = path
        self.sig_label.config(text=os.path.basename(path), fg=theme.TEXT_2)
        self.set_tool("signature")

    def _image_size(self, path: str) -> tuple[float, float]:
        try:
            with pymupdf.open(path) as im:
                page = im[0]
                return page.rect.width, page.rect.height
        except Exception:
            return (200.0, 80.0)

    def append_signature_page(self) -> None:
        if not self.doc:
            messagebox.showinfo("Append signature", "Open a PDF first.")
            return
        path = filedialog.askopenfilename(
            title="Choose signature PNG",
            filetypes=[("PNG images", "*.png"), ("All files", "*.*")])
        if not path:
            return
        out = filedialog.asksaveasfilename(
            title="Save as", defaultextension=".pdf",
            initialfile=os.path.splitext(os.path.basename(self.doc.path))[0]
            + "_signed.pdf",
            filetypes=[("PDF files", "*.pdf")])
        if not out:
            return
        try:
            self.doc.export_signature_page(out, path)
        except Exception as exc:
            messagebox.showerror("Export failed", str(exc))
            return
        messagebox.showinfo("Done", f"Signature page appended to:\n{out}")

    # ==================================================================
    # saving
    # ==================================================================
    def save(self) -> None:
        if not self.doc:
            return
        if self.saved_path:
            self._export(self.saved_path)
        else:
            self.save_as()

    def save_as(self) -> None:
        if not self.doc:
            return
        base = os.path.splitext(os.path.basename(self.doc.path))[0]
        out = filedialog.asksaveasfilename(
            title="Save as", defaultextension=".pdf",
            initialfile=f"{base}_signed.pdf",
            filetypes=[("PDF files", "*.pdf")])
        if out:
            self.saved_path = out
            self._export(out)

    def _export(self, out: str) -> None:
        try:
            self.doc.export(out)
        except Exception as exc:
            messagebox.showerror("Export failed", str(exc))
            return
        self._set_edited(False)
        messagebox.showinfo("Saved", f"Wrote:\n{out}")

    # ==================================================================
    def _bind_keys(self) -> None:
        self.bind("<Control-o>", lambda e: self._guarded(self.open_dialog))
        self.bind("<Control-s>", lambda e: self._guarded(self.save))
        self.bind("<Control-z>", lambda e: self._guarded(self.undo))
        self.bind("<Control-plus>", lambda e: self.set_zoom(self.zoom * 1.15))
        self.bind("<Control-minus>", lambda e: self.set_zoom(self.zoom / 1.15))
        self.bind("<Delete>", lambda e: self._delete_key())
        self.bind("<BackSpace>", lambda e: self._delete_key())
        self.bind("<Escape>", lambda e: self.deselect())
        self.bind("<Prior>", lambda e: self.goto_page(self.page - 1))
        self.bind("<Next>", lambda e: self.goto_page(self.page + 1))
        for key, tool in (("v", "select"), ("t", "text"), ("c", "check"),
                          ("x", "cross"), ("s", "signature")):
            self.bind(f"<{key}>", lambda e, t=tool: self._shortcut(t))

    def _typing(self) -> bool:
        """True while the user is typing inside a text field."""
        focus = self.focus_get()
        return isinstance(focus, (tk.Entry, tk.Text))

    def _guarded(self, fn) -> None:
        """Run a command unless the user is typing in a field."""
        if self._typing():
            return
        fn()

    def _shortcut(self, tool: str) -> None:
        """Switch tools - but never while the user is typing a word."""
        if self._typing():
            return
        self.set_tool(tool)

    def _delete_key(self) -> None:
        """Delete the selected object - but not while typing in a field."""
        if self._typing():
            return
        self.delete_selected()

    # ==================================================================
    # interface text size
    # ==================================================================
    def set_interface_scale(self, factor=None) -> None:
        """Change the size of the interface text.

        The choice is remembered, so the app comes up the same way next
        time.  Everything redraws itself around the new size.
        """
        if factor is None:
            try:
                factor = float(self.scale_var.get())
            except (TypeError, ValueError):
                return
        if not theme.set_scale(factor):
            return
        self._scale = theme.scale()
        self.scale_var.set(str(self._scale))
        prefs.put("interface_scale", self._scale)
        self.fonts = theme.fonts()
        self._rescale_ui()

    def _rescale_ui(self) -> None:
        """Re-lay out the interface after the text size changed."""
        frames = []
        bar = getattr(self, "titlebar", None)
        if bar is not None:
            frames.append((bar, "height", theme.titlebar_h()))
        rail = getattr(self, "rail_frame", None)
        if rail is not None:
            frames.append((rail, "width", theme.rail_w()))
        panel = getattr(self, "inspector_frame", None)
        if panel is not None:
            frames.append((panel, "width", theme.inspector_w()))
        for frame, attr, value in frames:
            try:
                frame.configure(**{attr: value})
            except Exception:
                pass

        for widget in self._descendants(self):
            rescale = getattr(widget, "rescale", None)
            if callable(rescale):
                try:
                    rescale()
                except Exception:
                    pass

        try:
            self.hint.configure(wraplength=theme.inspector_w()
                                - 2 * theme.scaled(PAD))
        except Exception:
            pass
        self.update_idletasks()
        if self.doc:
            self.render_page()

    @staticmethod
    def _descendants(widget):
        """Every widget below this one."""
        for child in widget.winfo_children():
            yield child
            yield from PdfEditorApp._descendants(child)

    def _show_text_size_menu(self) -> None:
        """The text sizes, in a small menu under the button."""
        menu = tk.Menu(self, tearoff=0)
        for name, factor in theme.SCALE_STEPS:
            menu.add_radiobutton(label=name, value=str(factor),
                                 variable=self.scale_var,
                                 command=self.set_interface_scale)
        try:
            menu.post(self.text_size_btn.winfo_rootx(),
                      self.text_size_btn.winfo_rooty()
                      + self.text_size_btn.winfo_height())
        finally:
            menu.bind("<FocusOut>", lambda e: menu.unpost())

    # ==================================================================
    # drag and drop
    # ==================================================================
    def _poll_drops(self) -> None:
        """Pick up files dropped on the window.

        The OLE callbacks cannot touch Tk, so they leave the files on a
        queue and this picks them up on the next tick.
        """
        self._collect_drops()
        self._poll_job = self.after(80, self._poll_drops)

    def _collect_drops(self) -> None:
        """Take whatever was dropped on the window and open it."""
        target = self._drop_target
        if target is None:
            return
        hovering = bool(target.hovering)
        if hovering != self._drop_hover:
            self._drop_hover = hovering
            self._set_drop_hint(hovering)
        for path in target.take():
            self._open_dropped(path)

    def _open_dropped(self, path: str) -> None:
        """Open a file that was dropped on the window."""
        if not path.lower().endswith(".pdf"):
            messagebox.showwarning(
                "Not a PDF",
                f"{os.path.basename(path)}\n\n"
                "Only PDF files can be opened here.")
            return
        self.open_file(path)

    def _set_drop_hint(self, on: bool) -> None:
        """Show that a drop would be accepted."""
        canvas = getattr(self, "canvas", None)
        if canvas is None:
            return
        canvas.delete("drophint")
        if not on:
            return
        w = max(200, canvas.winfo_width())
        h = max(140, canvas.winfo_height())
        canvas.create_rectangle(10, 10, w - 10, h - 10, outline=theme.ACCENT,
                                width=2, dash=(6, 5), tags="drophint")
        canvas.create_text(w / 2, h / 2, text="Drop to open", fill=theme.ACCENT,
                           font=self.fonts.headline, tags="drophint")

    # ==================================================================
    # default PDF app
    # ==================================================================
    def destroy(self) -> None:
        """Close the app, cancelling anything still queued for later."""
        for attr in ("_default_prompt_job", "_poll_job"):
            job = getattr(self, attr, None)
            if job:
                setattr(self, attr, None)
                try:
                    self.after_cancel(job)
                except Exception:
                    pass
        target = getattr(self, "_drop_target", None)
        if target is not None:
            self._drop_target = None
            try:
                target.unregister()
            except Exception:
                pass
        super().destroy()

    def _update_file_menu(self) -> None:
        """Keep the 'make default' entry honest about the current state."""
        menu = getattr(self, "default_menu", None)
        if menu is None:
            return
        index = getattr(self, "default_item", None)
        if index is None:
            return
        if assoc.is_default():
            menu.entryconfigure(index, label="Already the default PDF app",
                                state="disabled")
        else:
            menu.entryconfigure(index, label="Make default PDF app…",
                                state="normal")

    def make_default_app(self) -> None:
        """Register this app as a .pdf handler and hand over to Windows.

        The registry entry is only half the job: Windows 10 and 11 keep the
        real default in a protected UserChoice key, so the shell's own
        "Open with" dialog is opened for the user to confirm.
        """
        if not assoc.is_windows():
            messagebox.showinfo(
                "Not available",
                "Making a default PDF app is a Windows feature.")
            return
        if assoc.is_default():
            messagebox.showinfo(
                "Already the default",
                "PDF Sign & Fill already opens .pdf files.")
            return
        if not assoc.register():
            messagebox.showerror(
                "Could not register",
                "Windows refused the change.\n\n"
                "You can still set it by hand in\n"
                "Settings > Apps > Default apps.")
            return

        prefs.put("asked_default_app", True)
        if assoc.offer_open_with():
            DefaultAppResult(self, on_open_settings=assoc.open_default_apps)
            return
        if not assoc.is_frozen():
            # Running from source: the registry entry still works for a
            # double-click, but Windows will not list a .py in its
            # "Open with" menu, so the packaged build is the better answer.
            messagebox.showinfo(
                "Registered",
                "PDF Sign & Fill is now registered as a handler for .pdf "
                "files.\n\n"
                "Windows only lists programs in its 'Open with' menu if they "
                "are an installed .exe, so for the full experience build a "
                "copy with build_exe.bat and run that.")
            return
        # No .exe to offer (or the shell refused): send them to Settings.
        assoc.open_default_apps()

    def open_default_apps(self) -> None:
        """Open Settings > Apps > Default apps."""
        if not assoc.open_default_apps():
            messagebox.showinfo(
                "Open Settings manually",
                "Press Windows + I, then go to\n"
                "Apps > Default apps > .pdf")

    def _maybe_offer_default(self) -> None:
        """Ask once, on first run, whether to become the default PDF app."""
        if not assoc.is_windows() or assoc.is_default():
            return
        if prefs.get("never_ask_default") or prefs.get("asked_default_app"):
            return
        # Opened from Explorer already? Then the user has chosen this app.
        if len(sys.argv) > 1 and os.path.exists(sys.argv[1]):
            return
        prefs.put("asked_default_app", True)
        DefaultAppPrompt(
            self,
            on_set=self.make_default_app,
            on_dismiss=None,
            on_never=lambda: prefs.put("never_ask_default", True),
        )

    def show_help(self) -> None:
        messagebox.showinfo(
            "Keyboard shortcuts",
            "V select · T text · C check · X cross · S signature\n"
            "Ctrl+O open · Ctrl+S save · Ctrl+Z undo · Del delete\n"
            "Ctrl+ / Ctrl− zoom · PgUp / PgDn page · Esc deselect\n\n"
            "The single-letter shortcuts are ignored while you are typing\n"
            "in the text field.")

    def show_guide(self) -> None:
        """Open the built-in guide: features and how to use them."""
        show_help_window(self)

    def show_about(self) -> None:
        messagebox.showinfo(
            "About PDF Sign & Fill",
            f"{APP_TITLE}\n\n"
            "A small, portable PDF form filler.\n"
            "Type on the lines, add ticks and crosses, sign with your own PNG.\n\n"
            "Your original file is never modified - every export writes a "
            "new PDF.\n\n"
            "Free software, licensed under the GNU Affero General Public\n"
            "License v3.0 or later:\n"
            "https://www.gnu.org/licenses/agpl-3.0.html")


def _self_test(src: str, out: str) -> int:
    """Headless check used to verify a packaged build: open, edit, export.

    Usage:  app.py --selftest <source.pdf> <output.pdf>
    """
    from pdfedit.engine import PdfDocument
    with PdfDocument(src) as doc:
        doc.add_text(0, 120, 165, text="Self Test OK", size=12)
        doc.add_check(0, 64, 396, size=14)
        doc.add_cross(0, 64, 424, size=14)
        doc.export(out)

    # 1. the exported PDF must really contain the text
    import pymupdf
    chk = pymupdf.open(out)
    text = chk[0].get_text()
    chk.close()
    if "Self Test OK" not in text:
        print("SELFTEST FAILED: text missing")
        return 1

    # 2. Pillow's codec path must work - it renders the signature preview
    try:
        from PIL import Image
        import io
        img = Image.new("RGBA", (64, 32), (10, 20, 120, 255))
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        buf.seek(0)
        again = Image.open(buf).convert("RGBA").resize((32, 16))
        if again.size != (32, 16):
            print("SELFTEST FAILED: PIL round-trip")
            return 1
    except Exception as exc:
        print(f"SELFTEST FAILED: PIL unavailable ({exc})")
        return 1

    print("SELFTEST OK")
    return 0


def _doctor() -> int:
    """Report what this machine has, and what is missing."""
    from pdfedit.diagnostics import doctor_text, has_failures, run_checks
    results = run_checks()
    text = doctor_text()
    print(text)
    if getattr(sys, "frozen", False):
        # A windowed build has no console, so write the report to a file.
        out = os.path.join(prefs.home(), "doctor-report.txt")
        try:
            os.makedirs(prefs.home(), exist_ok=True)
            with open(out, "w", encoding="utf-8") as fh:
                fh.write(text + "\n")
        except OSError:
            out = ""
        try:
            messagebox.showinfo("System check",
                                f"The report was written to:\n\n{out}")
        except Exception:
            pass
    return 1 if has_failures(results) else 0


def _report_crash(exc: BaseException) -> None:
    """Write a crash log and say so, instead of vanishing."""
    import traceback
    from pdfedit.diagnostics import write_crash_report
    traceback.print_exception(type(exc), exc, exc.__traceback__)
    path = write_crash_report(exc)
    message = (f"{APP_TITLE} stopped unexpectedly.\n\n"
               f"{type(exc).__name__}: {exc}")
    if path:
        message += f"\n\nA full report was written to:\n{path}"
    try:
        messagebox.showerror("Something went wrong", message)
    except Exception:
        pass


def main() -> int:
    if "--doctor" in sys.argv:
        return _doctor()
    if "--selftest" in sys.argv:
        i = sys.argv.index("--selftest")
        if i + 2 >= len(sys.argv):
            print("usage: app.py --selftest <source.pdf> <output.pdf>")
            return 2
        return _self_test(sys.argv[i + 1], sys.argv[i + 2])
    app = PdfEditorApp()
    if len(sys.argv) > 1 and os.path.exists(sys.argv[1]):
        app.after(100, lambda: app.open_file(sys.argv[1]))
    try:
        app.mainloop()
    except Exception as exc:
        _report_crash(exc)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main() or 0)
