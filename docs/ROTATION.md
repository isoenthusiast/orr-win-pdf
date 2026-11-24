# Rotated pages: why this editor calls `remove_rotation()`

This is the one non-obvious piece of the engine, so here is the whole story.

## The trap

A PDF page may carry a `/Rotate` entry (0, 90, 180, 270). It means *"rotate this
page clockwise by N degrees when displaying it"*. Scanned documents very often
use `/Rotate 90`.

PyMuPDF behaves like this:

| operation | coordinate space |
|---|---|
| `page.get_pixmap()` (what the user sees) | **rotated** (visible) space |
| `page.draw_line()`, `insert_text()`, `insert_image()` | **unrotated** page space |

So on a `/Rotate 90` page, a line drawn at "page" coordinates `(50, 50)` does
**not** appear where you put it in the preview — the page rotation is applied
to it on top. Any editor that draws in visible space without compensating
silently drops every signature and mark in the wrong place.

## The fix

`page.remove_rotation()` rotates the existing page content so the page *looks
exactly the same*, sets `/Rotate` to 0 and keeps the visible page box. After
that, page space == visible space and drawing is WYSIWYG.

Verified by rendering (`/Rotate 90` page, black marker rectangle):

```
reference (as the user sees it)   |  after remove_rotation() + drawing
  OLD (rotated)  █                |  OLD (rotated)  █     <- identical
                                  |  NEW upright, red line at the clicked spot
```

The engine therefore calls `remove_rotation()` on every rotated page **before**
burning in overlays (`PdfDocument.export`). Two side effects worth knowing:

* the exported page has `/Rotate 0` and the *visible* dimensions
  (a 595×842 page with `/Rotate 90` exports as 842×595 — the same on-screen
  size as before, just stored differently);
* the original file on disk is never modified; the export always starts from a
  fresh copy of the source.

## Alternative that does not work

Mapping visible coordinates back into unrotated space with
`page.rotation_matrix.inverse` puts objects in the right *position*, but the
glyphs come out rotated (sideways text, sideways signature PNG), because the
page rotation is applied to the new content too. It is only correct for
unoriented marks such as the check/cross ticks.

## Guard rail

`tests/test_engine.py::test_rotated_page_keeps_overlay_in_the_same_visible_place`
exports a `/Rotate 90` document, then renders the result and compares it with
an overlay-free export. The changed-pixel bounding box must sit where the
user clicked. If the rotation handling ever regresses, that test fails.
