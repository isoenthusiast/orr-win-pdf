"""The built-in guide: what the app can do and how to use it.

Opened from Help ▸ How to use (or the ? button in the title bar).  It is a
normal window rather than a modal message box, so it can be left open and
consulted while working - which is the whole point of a help section.
"""
from __future__ import annotations

import tkinter as tk

from . import theme
from .icons import draw_icon
from .widgets import hairline, rounded_rect

# --------------------------------------------------------------------------
# the content
# --------------------------------------------------------------------------
# Each block is (kind, payload).  Keeping the copy in one list makes it easy
# to read - and to extend - without touching the drawing code.

CONTENT: list[tuple[str, object]] = [
    ("lead",
     "Fill in any PDF: type on the lines, drop a tick or a cross, and sign it "
     "with your own PNG.  Your original file is never modified."),

    ("section", "Getting started"),
    ("para",
     "Open a PDF with File ▸ Open (Ctrl+O) or the folder button in the title "
     "bar.  The page fills the middle of the window."),
    ("bullet", "The icon rail on the left picks a tool."),
    ("bullet", "The panel on the right edits whatever is selected."),
    ("bullet", "The bar floating over the page turns pages and changes zoom."),
    ("bullet", "The orange dot next to the file name means unsaved changes."),

    ("section", "Opening PDFs"),
    ("para",
     "You can also make this app the one Windows opens PDFs with."),
    ("bullet", "Drag a PDF from Explorer onto the window and it opens."),
    ("bullet", "File ▸ Make default PDF app… registers the app and walks you "
               "through Windows' own “Open with” dialog - tick "
               "“Always use this app” and you are done."),
    ("bullet", "File ▸ Windows default apps… opens the system settings, if you "
               "would rather set it by hand."),
    ("bullet", "You are asked once, the first time the app starts. "
               "“Don't ask again” in that offer turns it off for good."),

    ("section", "Interface text size"),
    ("bullet", "The T button in the title bar changes the size of the text "
               "everywhere in the app."),
    ("bullet", "View ▸ Interface text size does the same, with five sizes from "
               "Small to Largest."),
    ("bullet", "Your choice is remembered, so the app comes up the same way "
               "next time."),

    ("section", "If something goes wrong"),
    ("bullet", "If the app stops unexpectedly, the reason is written to "
               "error.log in %APPDATA%\\PDF Sign & Fill, and the window that "
               "appears tells you where that file is."),
    ("bullet", "Run the app with --doctor to get a report of anything this PC "
               "is missing - Python, Tk, the PDF engine, the fonts."),
    ("bullet", "A PDF that is password protected, damaged or simply not a PDF "
               "is reported in words, not as an error code."),

    ("section", "Adding things to the page"),
    ("tool", ("text", "Text", "T",
              "Click on the ruled line where the words should sit.  The click "
              "point is the text baseline, so the text lands on the line "
              "instead of floating above it.")),
    ("tool", ("check", "Check", "C",
              "Click where the tick should go.  Ticks are drawn in green.")),
    ("tool", ("cross", "Cross", "X",
              "Click where the X should go - a crossed-out option, or a "
              "negative answer.  Crosses are drawn in red.")),
    ("tool", ("signature", "Signature", "S",
              "Load a PNG signature once, then click to drop it on the page.  "
              "You can also paste one from the clipboard, or append it as a "
              "new page.")),

    ("section", "Turning a page"),
    ("para",
     "Sometimes a scan comes out sideways.  The page can be turned like a "
     "sheet of paper, and the turn is saved with the file."),
    ("bullet", "The four buttons under the page turn it: anticlockwise, "
               "clockwise, upside down and left to right.  View ▸ Turn page "
               "does the same."),
    ("bullet", "Reset puts the page back the way it was."),
    ("bullet", "Anything you have already added travels with the page and "
               "stays upright and readable."),
    ("bullet", "The PDF you export really is turned - the page is rewritten, "
               "not just turned on screen, so it looks the same in every "
               "reader."),

    ("section", "Selecting and adjusting"),
    ("para",
     "Anything you add on the page can be selected and moved afterwards - you "
     "never have to place it perfectly the first time."),
    ("bullet", "Click an item to select it.  Clicking never adds a second copy."),
    ("bullet", "Drag a selected item to move it."),
    ("bullet", "Drag the small blue square in the bottom-right corner to "
               "resize it."),
    ("bullet", "Hold Shift while resizing a signature to stretch it freely; "
               "without Shift its proportions are kept."),
    ("bullet", "Press Delete to remove the selected item."),
    ("bullet", "Press Ctrl+Z to undo the last change."),

    ("section", "Editing text"),
    ("bullet", "Select a text item and type in the Text field - the page "
               "updates as you type."),
    ("bullet", "Click a text item again to jump straight into the field, with "
               "the caret waiting at the end of the text."),
    ("bullet", "The size stepper and the colour chip restyle the selected "
               "text item."),
    ("bullet", "The single-letter tool shortcuts (V, T, C, X, S) are ignored "
               "while you are typing, so a word is never mistaken for a "
               "command."),

    ("section", "Saving"),
    ("bullet", "Save as PDF (Ctrl+S) always writes a new file and asks where "
               "to put it."),
    ("bullet", "The file you opened stays exactly as it was, so you can send "
               "the original on as well."),
    ("bullet", "Signatures are placed as real images, so they stay sharp at "
               "any zoom."),

    ("section", "Keyboard shortcuts"),
    ("keys", [
        ("Ctrl + O", "Open a PDF"),
        ("Ctrl + S", "Save as PDF"),
        ("Ctrl + Z", "Undo the last change"),
        ("Ctrl + / −", "Zoom in / out"),
        ("V", "Select tool"),
        ("T", "Text tool"),
        ("C", "Check mark tool"),
        ("X", "Cross tool"),
        ("S", "Signature tool"),
        ("Delete", "Delete the selected item"),
        ("Esc", "Deselect everything"),
        ("PgUp / PgDn", "Previous / next page"),
    ]),

    ("section", "Good to know"),
    ("bullet", "Rotated pages are handled properly: what you place lands "
               "exactly where you clicked and stays upright."),
    ("bullet", "Text never wraps unexpectedly - every line is written exactly "
               "as you typed it."),
    ("bullet", "Chinese, Japanese and Korean text is supported; the right "
               "font is chosen automatically."),
    ("bullet", "Ctrl + scroll wheel zooms the page."),

    ("section", "Licence"),
    ("bullet", "Free software, licensed under the GNU Affero General Public "
               "License v3.0 or later. The full text sits in the LICENSE file "
               "next to the source."),
    ("bullet", "It bundles PyMuPDF (AGPL-3.0) and Pillow. If you redistribute "
               "a built copy, ship the source and the licence with it."),
]

CANVAS_W = 660
MARGIN = 34
TEXT_W = CANVAS_W - 2 * MARGIN


class HelpWindow(tk.Toplevel):
    """A scrollable, themed guide."""

    def __init__(self, master):
        super().__init__(master)
        self.title("How to use - PDF Sign & Fill")
        self.configure(bg=theme.BG)
        self.resizable(False, False)
        self.transient(master)

        self.fonts = theme.fonts()
        self._win = self

        header = tk.Frame(self, bg=theme.BG)
        header.pack(fill=tk.X, padx=MARGIN, pady=(22, 6))
        tk.Label(header, text="How to use", bg=theme.BG, fg=theme.TEXT,
                 font=self.fonts.title, anchor="w").pack(fill=tk.X)
        tk.Label(header, text="Everything the app can do, in one place",
                 bg=theme.BG, fg=theme.TEXT_2, font=self.fonts.body,
                 anchor="w").pack(fill=tk.X, pady=(2, 0))

        body = tk.Frame(self, bg=theme.BG)
        body.pack(fill=tk.BOTH, expand=True, padx=MARGIN, pady=(0, 18))

        self.canvas = tk.Canvas(body, bg=theme.BG, highlightthickness=0, bd=0,
                                width=CANVAS_W, height=620)
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        bar = tk.Scrollbar(body, orient=tk.VERTICAL, command=self.canvas.yview,
                           troughcolor=theme.BG, bd=0, highlightthickness=0,
                           width=11, activebackground=theme.TEXT_3)
        bar.pack(side=tk.RIGHT, fill=tk.Y)
        self.canvas.configure(yscrollcommand=bar.set)

        self.canvas.bind("<MouseWheel>", self._on_wheel)
        self.canvas.bind("<Button-4>", lambda e: self.canvas.yview_scroll(-2, "units"))
        self.canvas.bind("<Button-5>", lambda e: self.canvas.yview_scroll(2, "units"))

        self._render()

        self.update_idletasks()
        self._center(master)
        self.bind("<Escape>", lambda e: self.destroy())

    # ------------------------------------------------------------------
    def _center(self, master) -> None:
        try:
            x = master.winfo_rootx() + (master.winfo_width() - self.winfo_width()) // 2
            y = master.winfo_rooty() + (master.winfo_height() - self.winfo_height()) // 3
            self.geometry(f"+{max(0, x)}+{max(0, y)}")
        except Exception:
            pass

    def _on_wheel(self, event) -> None:
        self.canvas.yview_scroll(-1 if event.delta > 0 else 1, "units")

    # ------------------------------------------------------------------
    # drawing
    # ------------------------------------------------------------------
    def _text(self, y, txt, font, fill, indent=0, gap=0):
        """Draw one wrapped line of text, return the new y.

        ``width`` on a canvas text item is the *wrap* width, so it has to be
        the space left over from the item's own x position.
        """
        item = self.canvas.create_text(
            MARGIN + indent, y, text=txt, font=font, fill=fill, anchor="nw",
            width=max(80, TEXT_W - indent), justify=tk.LEFT)
        box = self.canvas.bbox(item)
        height = (box[3] - box[1]) if box else 0
        return y + height + gap

    def _render(self) -> None:
        cv = self.canvas
        y = 8
        for kind, payload in CONTENT:
            if kind == "lead":
                y = self._text(y, payload, self.fonts.body, theme.TEXT_2,
                               gap=6)
                y += 8

            elif kind == "section":
                y += 14
                label = payload.upper()
                item = cv.create_text(MARGIN, y, text=label, anchor="nw",
                                      font=self.fonts.section, fill=theme.TEXT_3)
                tw = self.fonts.section.measure(label)
                cv.create_line(MARGIN + tw + 12, y + 9, MARGIN + TEXT_W, y + 9,
                               fill=theme.SEPARATOR_SOFT)
                box = cv.bbox(item)
                y = (box[3] if box else y + 12) + 8

            elif kind == "para":
                y = self._text(y, payload, self.fonts.body, theme.TEXT, gap=6)

            elif kind == "bullet":
                cv.create_oval(MARGIN + 4, y + 7, MARGIN + 8, y + 11,
                               fill=theme.TEXT_3, outline="")
                y = self._text(y, payload, self.fonts.body, theme.TEXT_2,
                               indent=18, gap=6)

            elif kind == "tool":
                icon, name, key, desc = payload
                icon_y = y + 2
                draw_icon(cv, icon, MARGIN + 11, icon_y + 11, 20, theme.ACCENT)
                cv.create_text(MARGIN + 30, icon_y, text=name, anchor="nw",
                               font=self.fonts.body_emphasis, fill=theme.TEXT)
                chip_w = self.fonts.caption.measure(key) + 14
                chip_x = MARGIN + 34 + self.fonts.body_emphasis.measure(name)
                rounded_rect(cv, chip_x, icon_y + 1, chip_x + chip_w, icon_y + 18,
                             8, fill=theme.FILL, outline="")
                cv.create_text(chip_x + chip_w / 2, icon_y + 10, text=key,
                               font=self.fonts.caption, fill=theme.TEXT_2)
                y = self._text(y + 26, desc, self.fonts.body, theme.TEXT_2,
                               indent=30, gap=6)

            elif kind == "keys":
                y += 2
                for combo, desc in payload:
                    w = 108
                    rounded_rect(cv, MARGIN, y - 1, MARGIN + w, y + 19, 6,
                                 fill=theme.FILL, outline="")
                    cv.create_text(MARGIN + w / 2, y + 9, text=combo,
                                   font=self.fonts.caption, fill=theme.TEXT)
                    y = self._text(y + 2, desc, self.fonts.body, theme.TEXT_2,
                                   indent=w + 14, gap=4)
                y += 6

        cv.configure(scrollregion=(0, 0, CANVAS_W, y + 10))


def show_help(master) -> None:
    """Open the guide, reusing the window if it is already open."""
    for child in master.winfo_children():
        if isinstance(child, HelpWindow):
            child.deiconify()
            child.lift()
            child.focus_set()
            return
    HelpWindow(master)
