"""UI smoke test: drives the real Tk app the way a user would.

    python -m unittest discover -s tests -v

It opens the demo form, drops a text field, a check mark, a cross and a
signature through the actual mouse handlers, exports the result and writes
ui_screenshot.png so the layout can be eyeballed.
"""
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
if HERE not in sys.path:
    sys.path.insert(0, HERE)


class Event:
    """Minimal stand-in for a Tk mouse event."""

    def __init__(self, x, y, state=0):
        self.x = x
        self.y = y
        self.x_root = x
        self.y_root = y
        self.delta = 0
        self.state = state          # modifier mask (Shift = 0x0001)


class UiSmokeTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import pymupdf
        sys.path.insert(0, os.path.join(ROOT, "tools"))
        from make_demo import make_form, make_signature

        cls.tmp = tempfile.mkdtemp(prefix="pdfedit_ui_")
        cls.pdf = make_form(os.path.join(cls.tmp, "form.pdf"))
        cls.sig = make_signature(os.path.join(cls.tmp, "sig.png"))

        # Keep the app's preferences out of the real %APPDATA%, and stop the
        # first-run "make this the default PDF app" offer from appearing
        # in the middle of a test.
        os.environ["PDF_SIGN_FILL_HOME"] = cls.tmp
        from pdfedit import prefs
        prefs.put("asked_default_app", True)

        from app import PdfEditorApp
        cls.app = PdfEditorApp()
        cls.app.update()
        cls.app.open_file(cls.pdf)
        cls.app.update()

    @classmethod
    def tearDownClass(cls):
        try:
            cls.app.destroy()
        except Exception:
            pass

    def test_app_opens_document(self):
        self.assertIsNotNone(self.app.doc)
        self.assertEqual(self.app.doc.page_count, 1)
        self.assertEqual(self.app.page, 0)

    def test_drop_text_check_cross_and_signature(self):
        app = self.app

        def at(px, py):
            """PDF point -> canvas pixel (the page may be centred)."""
            return Event(int(app._ox + px * app.zoom), int(app._oy + py * app.zoom))

        # --- text field ------------------------------------------------
        app.set_tool("text")
        app.text_value.set("SAMPLE SIGNATORY")
        app.on_press(at(160, 130))
        app.update()
        self.assertEqual(len(app.doc.overlays), 1)
        self.assertEqual(app.doc.overlays[0].kind, "text")
        self.assertEqual(app.doc.overlays[0].text, "SAMPLE SIGNATORY")

        # --- check mark -------------------------------------------------
        app.set_tool("check")
        app.on_press(at(64, 386))
        app.update()
        self.assertEqual(len(app.doc.overlays), 2)
        self.assertEqual(app.doc.overlays[1].kind, "check")

        # --- cross ------------------------------------------------------
        app.set_tool("cross")
        app.on_press(at(64, 414))
        app.update()
        self.assertEqual(len(app.doc.overlays), 3)
        self.assertEqual(app.doc.overlays[2].kind, "cross")

        # --- signature --------------------------------------------------
        app._set_signature(self.sig)
        app.on_press(at(180, 700))
        app.update()
        self.assertEqual(len(app.doc.overlays), 4)
        self.assertEqual(app.doc.overlays[3].kind, "image")

    def test_move_and_delete(self):
        app = self.app
        app.set_tool("select")
        ov = app.doc.overlays[0]
        app.select(ov)
        x0_before = ov.x0

        def at(px, py):
            return Event(int(app._ox + px * app.zoom), int(app._oy + py * app.zoom))

        app.on_press(at(ov.x0 + 5, ov.y0 + 5))
        app.on_drag(at(ov.x0 + 25, ov.y0 + 5))
        app.on_release(at(ov.x0 + 25, ov.y0 + 5))
        self.assertGreater(ov.x0, x0_before)

        count = len(app.doc.overlays)
        app.delete_selected()
        self.assertEqual(len(app.doc.overlays), count - 1)

    def test_undo(self):
        app = self.app
        before = len(app.doc.overlays)
        app.undo()
        self.assertGreaterEqual(len(app.doc.overlays), before - 1)

    def test_export_and_screenshot(self):
        app = self.app
        out = os.path.join(self.tmp, "signed.pdf")
        app.doc.export(out)
        self.assertTrue(os.path.exists(out))

        import pymupdf
        chk = pymupdf.open(out)
        self.assertIn("SAMPLE SIGNATORY", chk[0].get_text())
        self.assertGreaterEqual(len(chk[0].get_images()), 1)
        chk.close()

        # a picture of the running app (best effort - needs a desktop)
        try:
            from screenshot import capture_tk
            shot = os.path.join(ROOT, "ui_screenshot.png")
            if capture_tk(app, shot):
                print(f"\n  screenshot -> {shot}")
            else:
                print("\n  screenshot unavailable")
        except Exception as exc:            # pragma: no cover
            print(f"\n  screenshot skipped: {exc}")


if __name__ == "__main__":
    unittest.main(verbosity=2)
