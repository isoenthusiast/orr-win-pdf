"""Page transforms: rotate left/right, flip vertically/horizontally.

A page can be turned like a sheet of paper.  The transform is stored per page
as data, never baked into the working document, so it can be changed or undone
freely.  It is applied in two places:

* **preview** - the rendered page image is turned with Pillow, and the page
  reports its turned size, so the canvas lays out exactly what will be saved.
* **export** - the transform is baked into the page content (a ``cm`` matrix
  plus a new media box) so the saved PDF really is turned.

Coordinates
-----------
Everything here works in *visible space*: the origin is the top-left of the
page, x grows to the right and y grows **downwards** - the same space the
overlays use and the same one PyMuPDF's drawing helpers use.

A transform maps the original page space to the turned page space.  Rotation
is clockwise, and the flips are applied in the turned frame (so "flip
horizontal" always mirrors what you see on screen).
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PageTransform:
    """How a page is turned.  ``rot`` is clockwise, in degrees."""

    rot: int = 0
    flip_h: bool = False
    flip_v: bool = False

    def __post_init__(self) -> None:
        if self.rot not in (0, 90, 180, 270):
            raise ValueError(f"rotation must be 0/90/180/270, not {self.rot}")

    @property
    def identity(self) -> bool:
        return self.rot == 0 and not self.flip_h and not self.flip_v

    def rotate_left(self) -> "PageTransform":
        """Turn the page 90 degrees anticlockwise."""
        return PageTransform((self.rot + 270) % 360, self.flip_h, self.flip_v)

    def rotate_right(self) -> "PageTransform":
        """Turn the page 90 degrees clockwise."""
        return PageTransform((self.rot + 90) % 360, self.flip_h, self.flip_v)

    def flipped_h(self) -> "PageTransform":
        return PageTransform(self.rot, not self.flip_h, self.flip_v)

    def flipped_v(self) -> "PageTransform":
        return PageTransform(self.rot, self.flip_h, not self.flip_v)


# --------------------------------------------------------------------------
# matrices  (x' = a*x + c*y + e ,  y' = b*x + d*y + f)
# --------------------------------------------------------------------------
Matrix = tuple[float, float, float, float, float, float]

IDENTITY: Matrix = (1.0, 0.0, 0.0, 1.0, 0.0, 0.0)


def apply(m: Matrix, x: float, y: float) -> tuple[float, float]:
    """Map a point through a matrix."""
    a, b, c, d, e, f = m
    return a * x + c * y + e, b * x + d * y + f


def compose(outer: Matrix, inner: Matrix) -> Matrix:
    """Return ``outer(inner(p))`` - i.e. ``inner`` is applied first."""
    a1, b1, c1, d1, e1, f1 = outer
    a2, b2, c2, d2, e2, f2 = inner
    return (
        a1 * a2 + c1 * b2,
        b1 * a2 + d1 * b2,
        a1 * c2 + c1 * d2,
        b1 * c2 + d1 * d2,
        a1 * e2 + c1 * f2 + e1,
        b1 * e2 + d1 * f2 + f1,
    )


def invert(m: Matrix) -> Matrix:
    """The inverse of an affine matrix."""
    a, b, c, d, e, f = m
    det = a * d - b * c
    if abs(det) < 1e-12:
        raise ValueError("matrix is not invertible")
    ia, ib, ic, id_ = d / det, -b / det, -c / det, a / det
    return (ia, ib, ic, id_, -(ia * e + ic * f), -(ib * e + id_ * f))


def transformed_size(w: float, h: float, t: PageTransform) -> tuple[float, float]:
    """The size of the page after the transform."""
    if t.rot in (90, 270):
        return h, w
    return w, h


def transform_matrix(w: float, h: float, t: PageTransform) -> Matrix:
    """Matrix mapping the original page space to the turned page space."""
    if t.identity:
        return IDENTITY

    # rotation, clockwise, in visible space (y grows downwards)
    if t.rot == 90:
        rot: Matrix = (0.0, 1.0, -1.0, 0.0, h, 0.0)
    elif t.rot == 180:
        rot = (-1.0, 0.0, 0.0, -1.0, w, h)
    elif t.rot == 270:
        rot = (0.0, -1.0, 1.0, 0.0, 0.0, w)
    else:
        rot = IDENTITY

    # the flips happen in the turned frame
    tw, th = transformed_size(w, h, t)
    flip: Matrix = IDENTITY
    if t.flip_h:
        flip = (-1.0, 0.0, 0.0, 1.0, tw, 0.0)
    if t.flip_v:
        flip = compose(flip, (1.0, 0.0, 0.0, -1.0, 0.0, th))

    return compose(flip, rot)


def transform_rect(t: PageTransform, w: float, h: float,
                   x0: float, y0: float, x1: float, y1: float
                   ) -> tuple[float, float, float, float]:
    """Map a rectangle into the turned page space (as an axis-aligned box)."""
    if t.identity:
        return x0, y0, x1, y1
    m = transform_matrix(w, h, t)
    pts = [apply(m, x0, y0), apply(m, x1, y0),
           apply(m, x0, y1), apply(m, x1, y1)]
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    return min(xs), min(ys), max(xs), max(ys)


# --------------------------------------------------------------------------
# the PDF side: baking a transform into a page
# --------------------------------------------------------------------------
def pdf_matrix(w: float, h: float, t: PageTransform,
              x0: float = 0.0, y1: float | None = None) -> Matrix:
    """Matrix that turns the page content, in PDF space (y grows upwards).

    PDF's content streams use a bottom-left origin, so the visible-space
    matrix has to be flipped.  ``x0``/``y1`` are the top-left corner of the
    page's visible box in PDF coordinates.
    """
    if t.identity:
        return IDENTITY

    a, b, c, d, e, f = transform_matrix(w, h, t)
    if y1 is None:
        y1 = h
    th = transformed_size(w, h, t)[1]
    # visible (x, y) -> PDF (x0 + x, y1 - y); turned visible -> turned PDF
    return (a, -b, -c, d,
            e - a * x0 + c * y1,
            th - f + b * x0 - d * y1)


def matrix_to_pdf_text(m: Matrix) -> bytes:
    """The matrix as a PDF ``cm`` operand."""
    a, b, c, d, e, f = m
    return (" ".join(f"{v:.6f}" for v in (a, b, c, d, e, f))).encode("ascii")
