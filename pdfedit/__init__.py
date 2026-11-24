"""pdfedit — a tiny PDF signing / filling engine built on PyMuPDF."""

from .engine import (  # noqa: F401
    CHECK,
    CROSS,
    IMAGE,
    TEXT,
    Overlay,
    PdfDocument,
    check_segments,
    cross_segments,
    font_for,
)

__all__ = [
    "CHECK", "CROSS", "IMAGE", "TEXT",
    "Overlay", "PdfDocument", "check_segments", "cross_segments", "font_for",
]
