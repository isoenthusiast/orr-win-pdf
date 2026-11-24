"""PDF edit engine: UI-independent.

Holds a source PDF plus a list of *overlays* (the edits the user makes).
Overlays live in "visible space": the coordinate system of the rendered page,
i.e. exactly what the user sees on screen, with the origin at the top-left of
the page and one unit == one PDF point (1/72 inch).

Rotation handling
-----------------
PDF pages may carry a /Rotate entry.  PyMuPDF's drawing methods always work in
*unrotated* page space, while ``get_pixmap()`` renders with the rotation
applied.  Drawing therefore does not match the preview on rotated pages.
The fix (verified by rendering, see docs/ROTATION.md): call
``page.remove_rotation()`` before drawing.  It rotates the existing content so
the page *looks* the same, sets /Rotate to 0 and keeps the visible page box,
after which page space == visible space and drawing is WYSIWYG.
"""

from __future__ import annotations

import io
import os
import tempfile
from dataclasses import dataclass, field

import pymupdf

from .transform import (
    PageTransform,
    apply,
    matrix_to_pdf_text,
    pdf_matrix,
    transformed_size,
    transform_matrix,
)

# --------------------------------------------------------------------------
# overlay model
# --------------------------------------------------------------------------

TEXT = "text"
IMAGE = "image"
CHECK = "check"
CROSS = "cross"

#: default size (PDF points) of a check/cross mark
DEFAULT_MARK_SIZE = 16.0
#: default size (PDF points) of inserted text
DEFAULT_TEXT_SIZE = 11.0
#: default colours for the marks (Apple green / red)
CHECK_COLOR = (0.20, 0.78, 0.35)
CROSS_COLOR = (1.00, 0.23, 0.19)


@dataclass
class Overlay:
    """One edit, stored in visible-page coordinates."""

    kind: str
    page: int
    x0: float
    y0: float
    x1: float
    y1: float
    text: str = ""
    font_size: float = DEFAULT_TEXT_SIZE
    color: tuple[float, float, float] = (0.0, 0.0, 0.0)
    path: str = ""          # PNG file for IMAGE overlays
    stroke: float = 1.5     # line width for CHECK/CROSS
    oid: int = 0
    angle: int = 0          # clockwise rotation of an IMAGE overlay, degrees

    @property
    def width(self) -> float:
        return self.x1 - self.x0

    @property
    def height(self) -> float:
        return self.y1 - self.y0

    @property
    def baseline(self) -> float:
        """Y of the first text baseline (text overlays only)."""
        return self.y0 + self.font_size * 0.75

    def move(self, dx: float, dy: float) -> None:
        self.x0 += dx
        self.x1 += dx
        self.y0 += dy
        self.y1 += dy

    def resize_to(self, x1: float, y1: float) -> None:
        """Resize from the fixed top-left corner."""
        self.x1 = x1
        self.y1 = y1

    def fit_text(self) -> None:
        """Resize the box so it hugs the text (no wrapping on export)."""
        if self.kind != TEXT:
            return
        w, h = text_box_size(self.text, self.font_size)
        self.x1 = self.x0 + max(w + 2.0, 24.0)
        self.y1 = self.y0 + max(h, self.font_size * 1.35)


_next_oid = 1


def _new_oid() -> int:
    global _next_oid
    oid = _next_oid
    _next_oid += 1
    return oid


# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------

def _needs_cjk(text: str) -> bool:
    """True if the string contains CJK-ish characters."""
    return any("\u2e80" <= ch <= "\u9fff" or "\uff00" <= ch <= "\uffef"
               for ch in text)


def font_for(text: str) -> str:
    """Pick a built-in font that can actually render ``text``."""
    return "china-s" if _needs_cjk(text) else "helv"


def text_width(text: str, size: float, fontname: str | None = None) -> float:
    """Width of ``text`` in PDF points, measured with the real font metrics.

    Used to size the on-screen box so the preview matches what the PDF will
    contain (no surprise line wrapping on export).
    """
    if not text:
        return 0.0
    fname = fontname or font_for(text)
    try:
        return pymupdf.Font(fname).text_length(text, fontsize=size)
    except Exception:
        # rough fallback: ~0.5 em per latin char, 1.0 em per CJK char
        return sum(size if ord(ch) > 0x2E80 else size * 0.5 for ch in text)


def text_line_height(size: float) -> float:
    """Distance between baselines for multi-line text."""
    return size * 1.2


def text_box_size(text: str, size: float) -> tuple[float, float]:
    """(width, height) needed to show ``text`` without wrapping."""
    lines = text.split("\n") or [""]
    width = max((text_width(line, size) for line in lines), default=0.0)
    return width, text_line_height(size) * len(lines)


# --------------------------------------------------------------------------
# turning a rendered page
# --------------------------------------------------------------------------
def _turn_png(pix, transform: PageTransform) -> bytes:
    """Rotate / flip a rendered page the same way the export will.

    The preview and the saved file must agree, so the preview uses the very
    same rotation the export bakes into the PDF.
    """
    from PIL import Image

    img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
    if transform.rot == 90:
        img = img.transpose(Image.ROTATE_270)      # 90 degrees clockwise
    elif transform.rot == 180:
        img = img.transpose(Image.ROTATE_180)
    elif transform.rot == 270:
        img = img.transpose(Image.ROTATE_90)
    if transform.flip_h:
        img = img.transpose(Image.FLIP_LEFT_RIGHT)
    if transform.flip_v:
        img = img.transpose(Image.FLIP_TOP_BOTTOM)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def check_segments(cx: float, cy: float, size: float):
    """Two line segments forming a check mark, centred on (cx, cy)."""
    s = size
    p1 = (cx - 0.46 * s, cy + 0.02 * s)
    p2 = (cx - 0.10 * s, cy + 0.36 * s)
    p3 = (cx + 0.50 * s, cy - 0.36 * s)
    return [(p1, p2), (p2, p3)]


def cross_segments(cx: float, cy: float, size: float):
    """Two line segments forming an X, centred on (cx, cy)."""
    s = size
    d = 0.36 * s
    return [((cx - d, cy - d), (cx + d, cy + d)),
            ((cx + d, cy - d), (cx - d, cy + d))]


# --------------------------------------------------------------------------
# document
# --------------------------------------------------------------------------

def _bake_transform(doc, page, transform: PageTransform) -> None:
    """Turn a page by rewriting its content stream and media box.

    The page keeps its vectors and its text - nothing is rasterised.  The
    content is wrapped in ``q ... cm ... Q`` so the transform can never leak
    into the page's own graphics state.
    """
    box = page.rect                      # the visible box, in PDF coordinates
    w, h = box.width, box.height
    matrix = pdf_matrix(w, h, transform, box.x0, box.y1)

    # where does the visible box end up?
    corners = [apply(matrix, box.x0, box.y0), apply(matrix, box.x1, box.y0),
               apply(matrix, box.x0, box.y1), apply(matrix, box.x1, box.y1)]
    xs = [p[0] for p in corners]
    ys = [p[1] for p in corners]
    new_w = max(xs) - min(xs)
    new_h = max(ys) - min(ys)
    # re-anchor the result so the new page starts at (0, 0)
    matrix = (matrix[0], matrix[1], matrix[2], matrix[3],
              matrix[4] - min(xs), matrix[5] - min(ys))

    xrefs = page.get_contents()
    if not xrefs:
        return
    data = b"".join(doc.xref_stream(x) for x in xrefs)
    turned = (b"q\n" + matrix_to_pdf_text(matrix) + b" cm\n"
              + data + b"\nQ\n")
    doc.update_stream(xrefs[0], turned, compress=True)
    if len(xrefs) > 1:
        # the other streams are now folded in - drop them from /Contents
        doc.xref_set_key(page.xref, "Contents", f"[{xrefs[0]} 0 R]")

    page.set_mediabox(pymupdf.Rect(0, 0, new_w, new_h))
    page.set_cropbox(pymupdf.Rect(0, 0, new_w, new_h))


class PdfDocument:
    """A source PDF plus the overlays that will be burned in on export."""

    def __init__(self, path: str):
        self.path = os.path.abspath(path)
        self.doc = pymupdf.open(self.path)
        if self.doc.needs_pass:
            raise ValueError("This PDF is password protected.")
        self.overlays: list[Overlay] = []
        self.transforms: dict[int, PageTransform] = {}
        self._temp_files: list[str] = []

    # -- page transforms ---------------------------------------------------
    def get_transform(self, page: int) -> PageTransform:
        """How the page is turned (rotation + flips)."""
        return self.transforms.get(page, PageTransform())

    def set_transform(self, page: int, transform: PageTransform) -> None:
        """Turn a page.  The working document is never modified."""
        if transform.identity:
            self.transforms.pop(page, None)
        else:
            self.transforms[page] = transform

    def transform_page(self, page: int, transform: PageTransform) -> None:
        self.set_transform(page, transform)

    def rotate_page(self, page: int, degrees: int) -> None:
        """Rotate a page by -90 (left) or +90 (right)."""
        current = self.get_transform(page)
        if degrees >= 0:
            current = current.rotate_right()
        else:
            current = current.rotate_left()
        self.set_transform(page, current)

    def flip_page(self, page: int, vertical: bool) -> None:
        current = self.get_transform(page)
        self.set_transform(page, current.flipped_v() if vertical
                           else current.flipped_h())

    # -- basic info -------------------------------------------------------
    @property
    def page_count(self) -> int:
        return self.doc.page_count

    def page_size(self, page: int) -> tuple[float, float]:
        """Visible size (width, height) of a page in PDF points."""
        r = self.doc[page].rect
        return transformed_size(r.width, r.height, self.get_transform(page))

    def page_rotation(self, page: int) -> int:
        return self.doc[page].rotation

    def page_label(self, page: int) -> str:
        return self.doc[page].get_text("text").strip().splitlines()[:1][0] \
            if self.doc[page].get_text("text").strip() else ""

    # -- rendering --------------------------------------------------------
    def render_png(self, page: int, zoom: float = 1.0) -> bytes:
        """Render a page exactly as the user sees it (rotation applied)."""
        mat = pymupdf.Matrix(zoom, zoom)
        pix = self.doc[page].get_pixmap(matrix=mat, alpha=False)
        transform = self.get_transform(page)
        if transform.identity:
            return pix.tobytes("png")
        return _turn_png(pix, transform)

    # -- overlay creation -------------------------------------------------
    def add_text(self, page: int, x: float, y: float, text: str = "",
                 size: float = DEFAULT_TEXT_SIZE,
                 color: tuple[float, float, float] = (0, 0, 0)) -> Overlay:
        """Place a text field.

        ``y`` is the **baseline** of the first line, so clicking on a ruled
        line in a form puts the text straight onto that line.
        """
        w, h = text_box_size(text, size)
        top = y - size * 0.75
        ov = Overlay(kind=TEXT, page=page, x0=x, y0=top,
                     x1=x + max(w + 2.0, 24.0),
                     y1=top + max(h, size * 1.35),
                     text=text, font_size=size, color=color, oid=_new_oid())
        self.overlays.append(ov)
        return ov

    def add_image(self, page: int, path: str, x: float, y: float,
                  w: float, h: float) -> Overlay:
        ov = Overlay(kind=IMAGE, page=page, x0=x, y0=y, x1=x + w, y1=y + h,
                     path=os.path.abspath(path), oid=_new_oid())
        self.overlays.append(ov)
        return ov

    def add_check(self, page: int, cx: float, cy: float,
                  size: float = DEFAULT_MARK_SIZE,
                  color: tuple[float, float, float] = CHECK_COLOR,
                  stroke: float = 1.6) -> Overlay:
        half = size * 0.6
        ov = Overlay(kind=CHECK, page=page, x0=cx - half, y0=cy - half,
                     x1=cx + half, y1=cy + half,
                     color=color, stroke=stroke, oid=_new_oid())
        self.overlays.append(ov)
        return ov

    def add_cross(self, page: int, cx: float, cy: float,
                  size: float = DEFAULT_MARK_SIZE,
                  color: tuple[float, float, float] = CROSS_COLOR,
                  stroke: float = 1.6) -> Overlay:
        half = size * 0.6
        ov = Overlay(kind=CROSS, page=page, x0=cx - half, y0=cy - half,
                     x1=cx + half, y1= half + cy,
                     color=color, stroke=stroke, oid=_new_oid())
        self.overlays.append(ov)
        return ov

    # -- overlay management ----------------------------------------------
    def remove(self, ov: Overlay) -> None:
        if ov in self.overlays:
            self.overlays.remove(ov)

    def overlays_on(self, page: int) -> list[Overlay]:
        return [o for o in self.overlays if o.page == page]

    def clear(self) -> None:
        self.overlays.clear()

    # -- export -----------------------------------------------------------
    def export(self, out_path: str) -> str:
        """Write a new PDF with every overlay burned in.

        The source file is never modified: we re-open it from disk, so
        exporting twice never applies the same overlay twice.
        """
        out_path = os.path.abspath(out_path)
        out = pymupdf.open(self.path)
        try:
            # 1. normalise rotation so page space == visible space
            for page in out:
                if page.rotation:
                    page.remove_rotation()

            # 2. bake the user's rotation / flips into the page content
            for pno, transform in self.transforms.items():
                if not transform.identity and pno < out.page_count:
                    _bake_transform(out, out[pno], transform)

            # 3. burn in the overlays
            for ov in self.overlays:
                page = out[ov.page]
                if ov.kind == TEXT:
                    self._burn_text(page, ov)
                elif ov.kind == IMAGE:
                    self._burn_image(page, ov)
                elif ov.kind == CHECK:
                    self._burn_check(page, ov)
                elif ov.kind == CROSS:
                    self._burn_cross(page, ov)

            parent = os.path.dirname(out_path)
            if parent:
                os.makedirs(parent, exist_ok=True)
            out.save(out_path, deflate=True, garbage=3)
        finally:
            out.close()
        return out_path

    def export_signature_page(self, out_path: str, png_path: str,
                              page_size: tuple[float, float] | None = None
                              ) -> str:
        """Append the signature PNG as a brand new page at the end."""
        out_path = os.path.abspath(out_path)
        out = pymupdf.open(self.path)
        try:
            w, h = page_size or (595.0, 842.0)
            page = out.new_page(width=w, height=h)
            if page.rotation:
                page.remove_rotation()
            pw = pymupdf.open(png_path)
            iw, ih = pw[0].rect.width, pw[0].rect.height
            pw.close()
            # fit the signature into the middle of the new page
            margin = 0.15
            scale = min(w * (1 - 2 * margin) / iw, h * (1 - 2 * margin) / ih)
            dw, dh = iw * scale, ih * scale
            rect = pymupdf.Rect((w - dw) / 2, (h - dh) / 2,
                                (w + dw) / 2, (h + dh) / 2)
            page.insert_image(rect, filename=png_path, keep_proportion=False)
            out.save(out_path, deflate=True, garbage=3)
        finally:
            out.close()
        return out_path

    # -- burn helpers -----------------------------------------------------
    @staticmethod
    def _burn_text(page, ov: Overlay) -> None:
        """Write the text line by line.

        insert_text() is used on purpose: insert_textbox() would wrap the text
        inside the box, and the preview shows unwrapped text.
        """
        if not ov.text:
            return
        fname = font_for(ov.text)
        leading = text_line_height(ov.font_size)
        baseline = ov.baseline
        for i, line in enumerate(ov.text.split("\n")):
            if line:
                page.insert_text((ov.x0, baseline + i * leading), line,
                                 fontsize=ov.font_size, fontname=fname,
                                 color=ov.color)

    @staticmethod
    def _burn_image(page, ov: Overlay) -> None:
        if not ov.path or not os.path.exists(ov.path):
            return
        path = ov.path
        if ov.angle:
            path = _rotated_png(ov.path, ov.angle)
        rect = pymupdf.Rect(ov.x0, ov.y0, ov.x1, ov.y1)
        page.insert_image(rect, filename=path, keep_proportion=False,
                          overlay=True)

    @staticmethod
    def _burn_check(page, ov: Overlay) -> None:
        cx = (ov.x0 + ov.x1) / 2
        cy = (ov.y0 + ov.y1) / 2
        size = min(ov.width, ov.height)
        for (x1, y1), (x2, y2) in check_segments(cx, cy, size):
            page.draw_line((x1, y1), (x2, y2), color=ov.color, width=ov.stroke,
                           lineCap=1, lineJoin=1)

    @staticmethod
    def _burn_cross(page, ov: Overlay) -> None:
        cx = (ov.x0 + ov.x1) / 2
        cy = (ov.y0 + ov.y1) / 2
        size = min(ov.width, ov.height)
        for (x1, y1), (x2, y2) in cross_segments(cx, cy, size):
            page.draw_line((x1, y1), (x2, y2), color=ov.color, width=ov.stroke,
                           lineCap=1)

    # -- cleanup ----------------------------------------------------------
    def close(self) -> None:
        self.doc.close()
        for f in self._temp_files:
            try:
                os.remove(f)
            except OSError:
                pass

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()
        return False


def _rotated_png(path: str, angle: int) -> str:
    """A copy of ``path`` turned clockwise by ``angle`` degrees."""
    from PIL import Image
    img = Image.open(path).convert("RGBA")
    if angle % 360:
        img = img.rotate(-(angle % 360), expand=True)
    return save_png_temp(img)


def save_png_temp(image, suffix=".png") -> str:
    """Store a PIL image in a temp file and return its path."""
    fd, path = tempfile.mkstemp(suffix=suffix, prefix="pdfedit_")
    os.close(fd)
    image.save(path)
    return path
