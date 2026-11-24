"""Engine tests:  python -m unittest discover -s tests -v

The important ones are the *placement* tests: they render the exported PDF and
check that the ink lands exactly where the user would have clicked - including
on pages that carry a /Rotate entry, where naive editors silently shift every
overlay.
"""
import os
import sys
import tempfile
import unittest

import pymupdf
from PIL import Image, ImageDraw

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pdfedit.engine import PdfDocument  # noqa: E402


def make_pdf(path, rotate=0, pages=1):
    doc = pymupdf.open()
    for i in range(pages):
        page = doc.new_page(width=595, height=842)
        page.insert_text((56, 80), f"Page {i + 1}", fontsize=20, fontname="hebo")
        page.draw_rect(pymupdf.Rect(56, 120, 300, 160), width=0.8)
        page.insert_text((60, 145), "Label:", fontsize=11)
    if rotate:
        doc[0].set_rotation(rotate)
    doc.save(path)
    doc.close()
    return path


def make_signature(path):
    img = Image.new("RGBA", (600, 200), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.line([(20, 150), (120, 30), (220, 140), (360, 40), (560, 120)],
           fill=(10, 20, 120, 255), width=10, joint="curve")
    img.save(path)
    return path


def diff_bbox(pix_a, pix_b):
    """Bounding box of the pixels that changed between two renders.

    Comparing against an overlay-free export isolates exactly the ink the
    editor added, so pre-existing page content cannot mask a placement bug.
    """
    from PIL import Image, ImageChops

    assert pix_a.width == pix_b.width and pix_a.height == pix_b.height, \
        "renders differ in size"
    a = Image.frombytes("RGB", (pix_a.width, pix_a.height), pix_a.samples)
    b = Image.frombytes("RGB", (pix_b.width, pix_b.height), pix_b.samples)
    diff = ImageChops.difference(a, b).convert("L").point(lambda v: 255 if v > 12 else 0)
    return diff.getbbox()


class EngineTestCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="pdfedit_test_")
        self.pdf = make_pdf(os.path.join(self.tmp, "src.pdf"))
        self.sig = make_signature(os.path.join(self.tmp, "sig.png"))

    def out(self, name="out.pdf"):
        return os.path.join(self.tmp, name)

    # -- basics ----------------------------------------------------------
    def test_open_and_page_size(self):
        with PdfDocument(self.pdf) as doc:
            self.assertEqual(doc.page_count, 1)
            w, h = doc.page_size(0)
            self.assertAlmostEqual(w, 595, delta=1)
            self.assertAlmostEqual(h, 842, delta=1)

    def test_render_produces_png(self):
        with PdfDocument(self.pdf) as doc:
            png = doc.render_png(0, 1.0)
            self.assertTrue(png.startswith(b"\x89PNG"))
            self.assertGreater(len(png), 1000)

    # -- text ------------------------------------------------------------
    def test_text_overlay_is_burned_in(self):
        with PdfDocument(self.pdf) as doc:
            doc.add_text(0, 120, 130, text="SAMPLE SIGNATORY", size=12)
            out = doc.export(self.out())
        chk = pymupdf.open(out)
        self.assertIn("SAMPLE SIGNATORY", chk[0].get_text())
        chk.close()

    def test_cjk_text_overlay(self):
        with PdfDocument(self.pdf) as doc:
            doc.add_text(0, 120, 130, text="签署人 Ali", size=12)
            out = doc.export(self.out())
        chk = pymupdf.open(out)
        self.assertIn("签署人", chk[0].get_text())
        chk.close()

    def test_text_lands_where_the_user_clicked(self):
        from pdfedit.engine import text_width
        # ``y`` is the baseline: clicking on a ruled form line puts the text
        # straight onto that line.
        x, y = 120.0, 130.0
        with PdfDocument(self.pdf) as doc:
            reference = doc.export(self.out("ref.pdf"))
            doc.add_text(0, x, y, text="Signature Here", size=14)
            out = doc.export(self.out())
        ref_pix = pymupdf.open(reference)[0].get_pixmap(dpi=72)
        pix = pymupdf.open(out)[0].get_pixmap(dpi=72)
        bb = diff_bbox(ref_pix, pix)
        self.assertIsNotNone(bb, "no new ink rendered")
        x0, y0, x1, y1 = bb
        # the ink sits above the baseline (ascender) and ends at it
        self.assertGreaterEqual(x0, x - 5)
        self.assertLessEqual(x1, x + 200)
        self.assertGreaterEqual(y0, y - 14)
        self.assertLessEqual(y1, y + 4)
        # the text must NOT have been wrapped: its width has to match the
        # measured width of the string
        expected = text_width("Signature Here", 14)
        self.assertLessEqual(x1 - x0, expected + 8,
                             "text was wrapped or clipped")

    # -- marks -----------------------------------------------------------
    def test_check_and_cross_are_drawn(self):
        with PdfDocument(self.pdf) as doc:
            reference = doc.export(self.out("ref.pdf"))
            doc.add_check(0, 200, 300, size=20)
            doc.add_cross(0, 260, 300, size=20)
            out = doc.export(self.out())
        ref_pix = pymupdf.open(reference)[0].get_pixmap(dpi=72)
        pix = pymupdf.open(out)[0].get_pixmap(dpi=72)
        bb = diff_bbox(ref_pix, pix)
        self.assertIsNotNone(bb)
        x0, y0, x1, y1 = bb
        self.assertGreaterEqual(x0, 200 - 14)
        self.assertLessEqual(x1, 260 + 14)
        self.assertGreaterEqual(y0, 300 - 14)
        self.assertLessEqual(y1, 300 + 14)

    # -- image ------------------------------------------------------------
    def test_signature_png_is_burned_in(self):
        with PdfDocument(self.pdf) as doc:
            reference = doc.export(self.out("ref.pdf"))
            doc.add_image(0, self.sig, 100, 400, 220, 74)
            out = doc.export(self.out())
        chk = pymupdf.open(out)
        self.assertEqual(len(chk[0].get_images()), 1)
        ref_pix = pymupdf.open(reference)[0].get_pixmap(dpi=72)
        pix = chk[0].get_pixmap(dpi=72)
        bb = diff_bbox(ref_pix, pix)
        self.assertIsNotNone(bb)
        x0, y0, x1, y1 = bb
        self.assertGreaterEqual(x0, 100 - 3)
        self.assertGreaterEqual(y0, 400 - 3)
        self.assertLessEqual(x1, 320 + 3)
        self.assertLessEqual(y1, 474 + 3)
        chk.close()

    # -- page turn --------------------------------------------------------
    def test_turning_a_page_changes_its_visible_size(self):
        with PdfDocument(self.pdf) as doc:
            self.assertEqual(doc.page_size(0), (595, 842))
            doc.rotate_page(0, 90)
            w, h = doc.page_size(0)
            self.assertAlmostEqual(w, 842, delta=1)
            self.assertAlmostEqual(h, 595, delta=1)
            doc.rotate_page(0, 90)
            doc.rotate_page(0, 90)
            self.assertEqual(doc.page_size(0), (842, 595))   # a quarter turn
            doc.rotate_page(0, 90)
            self.assertEqual(doc.page_size(0), (595, 842))   # back to square

    def test_a_turned_page_is_saved_in_the_export(self):
        """The export must really be turned, not just turned on screen."""
        from pdfedit.transform import PageTransform
        with PdfDocument(self.pdf) as doc:
            doc.set_transform(0, PageTransform(rot=90))
            out = doc.export(self.out())
        chk = pymupdf.open(out)
        page = chk[0]
        self.assertAlmostEqual(page.rect.width, 842, delta=1)
        self.assertAlmostEqual(page.rect.height, 595, delta=1)
        # the label that was in the top-left corner is now in the top-right
        blocks = page.get_text("blocks")
        self.assertTrue(blocks)
        x0, y0 = blocks[0][0], blocks[0][1]
        self.assertGreater(x0, 400, "the text did not move to the right")
        self.assertLess(y0, 120, "the text did not stay at the top")
        chk.close()

    def test_the_preview_matches_the_turned_export(self):
        """What you see must be what you get."""
        import io
        from PIL import Image, ImageChops
        from pdfedit.transform import PageTransform
        with PdfDocument(self.pdf) as doc:
            doc.set_transform(0, PageTransform(rot=90))
            preview = Image.open(io.BytesIO(doc.render_png(0, 1.0))).convert("RGB")
            out = doc.export(self.out())
        pix = pymupdf.open(out)[0].get_pixmap(dpi=72)
        exported = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
        self.assertEqual(preview.size, exported.size)
        diff = ImageChops.difference(preview, exported).convert("L")
        # only the anti-aliasing of the glyph edges may differ
        self.assertLess(sum(diff.histogram()[40:]), 400,
                        "the preview and the export disagree")

    def test_turning_a_page_never_touches_the_source(self):
        from pdfedit.transform import PageTransform
        before = os.path.getsize(self.pdf)
        with PdfDocument(self.pdf) as doc:
            doc.set_transform(0, PageTransform(rot=90))
            doc.add_text(0, 100, 200, text="x")
            doc.export(self.out())
        self.assertEqual(os.path.getsize(self.pdf), before)

    # -- rotated pages ----------------------------------------------------
    def test_rotated_page_keeps_overlay_in_the_same_visible_place(self):
        """The classic bug: on /Rotate pages overlays drift off their box."""
        pdf = make_pdf(os.path.join(self.tmp, "rot.pdf"), rotate=90)
        with PdfDocument(pdf) as doc:
            # visible size of a rotated page: width/height are swapped
            w, h = doc.page_size(0)
            self.assertAlmostEqual(w, 842, delta=1)
            self.assertAlmostEqual(h, 595, delta=1)
            reference = doc.export(self.out("rot_ref.pdf"))
            doc.add_text(0, 150, 200, text="Rotated Overlay", size=16)
            out = doc.export(self.out("rot_out.pdf"))

        # the exported page must have the same *visible* size as the preview
        chk = pymupdf.open(out)
        page = chk[0]
        self.assertEqual(page.rotation, 0)
        self.assertAlmostEqual(page.rect.width, 842, delta=1)
        self.assertAlmostEqual(page.rect.height, 595, delta=1)
        ref_pix = pymupdf.open(reference)[0].get_pixmap(dpi=72)
        pix = page.get_pixmap(dpi=72)
        bb = diff_bbox(ref_pix, pix)
        self.assertIsNotNone(bb)
        x0, y0, x1, y1 = bb
        self.assertGreaterEqual(x0, 145)
        self.assertLessEqual(x1, 400)
        # baseline at y=200: the ink sits above it, ending at the baseline
        self.assertGreaterEqual(y0, 200 - 14)
        self.assertLessEqual(y1, 200 + 4)
        chk.close()

    # -- safety -----------------------------------------------------------
    def test_source_file_is_never_modified(self):
        before = os.path.getsize(self.pdf)
        with PdfDocument(self.pdf) as doc:
            doc.add_text(0, 100, 100, text="X")
            doc.export(self.out())
        self.assertEqual(os.path.getsize(self.pdf), before)

    def test_export_twice_does_not_double_apply(self):
        with PdfDocument(self.pdf) as doc:
            doc.add_text(0, 100, 100, text="OnceOnly")
            a = doc.export(self.out("a.pdf"))
            b = doc.export(self.out("b.pdf"))
        ta = pymupdf.open(a)[0].get_text()
        tb = pymupdf.open(b)[0].get_text()
        self.assertEqual(ta.count("OnceOnly"), tb.count("OnceOnly"))

    def test_export_signature_as_new_page(self):
        with PdfDocument(self.pdf) as doc:
            out = doc.export_signature_page(self.out("appended.pdf"), self.sig)
        chk = pymupdf.open(out)
        self.assertEqual(chk.page_count, 2)
        self.assertEqual(len(chk[1].get_images()), 1)
        chk.close()

    def test_undo_restores_state(self):
        with PdfDocument(self.pdf) as doc:
            doc.add_text(0, 100, 100, text="Hello")
            doc.add_check(0, 200, 200)
            self.assertEqual(len(doc.overlays), 2)
            doc.remove(doc.overlays[0])
            self.assertEqual(len(doc.overlays), 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
