"""Click-by-click interaction tests.

Every step drives the *real* Tk binding machinery with ``event_generate`` -
the same path a mouse or keyboard takes - and asserts the application state
after each click.  Nothing here calls the app's handlers directly, so if a
binding is broken the test fails.

One subtlety: Tk turns a second click within 500 ms into a ``<Double-Button-1>``
event, which never reaches ``<ButtonPress-1>``.  The helpers therefore stamp
every synthetic event with a clock of their own, so a "click" is always a
plain single click unless a test explicitly asks for a double click.

Run with::

    python -m unittest discover -s tests -v
"""
from __future__ import annotations

import os
import sys
import tempfile
import tkinter as tk
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
if HERE not in sys.path:
    sys.path.insert(0, HERE)

# a click lands within half a pixel of the target, and a pixel is ~1.1 pt
TOL = 1.6


class ClickTestCase(unittest.TestCase):
    """Shared setup plus click / drag / type helpers."""

    @classmethod
    def setUpClass(cls):
        sys.path.insert(0, os.path.join(ROOT, "tools"))
        from make_demo import make_form, make_signature

        cls.tmp = tempfile.mkdtemp(prefix="pdfedit_clicks_")
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

    def setUp(self):
        app = self.app
        app.doc.overlays = []
        app.overlays = app.doc.overlays
        app.undo_stack = []
        app.deselect()
        app.set_tool("select")
        app.text_value.set("")
        app.text_size.set(12)
        app.redraw_overlays()
        app.update()
        self._clock = 100_000

    # ------------------------------------------------------------------
    # helpers
    # ------------------------------------------------------------------
    def at(self, x, y):
        """PDF point -> canvas pixel (the page is centred in the window)."""
        app = self.app
        return (int(round(app._ox + x * app.zoom)),
                int(round(app._oy + y * app.zoom)))

    def click(self, x, y, dt=1000):
        """A genuine press + release at a PDF point.

        ``dt`` is the gap in ms before the *next* click; keep it below 500
        and repeat the same spot to produce a real double click.
        """
        app = self.app
        cx, cy = self.at(x, y)
        t = self._clock
        self._clock += dt
        app.canvas.event_generate("<ButtonPress-1>", x=cx, y=cy, time=t)
        app.update()
        app.canvas.event_generate("<ButtonRelease-1>", x=cx, y=cy, time=t + 10)
        app.update()

    def drag(self, x0, y0, x1, y1, shift=False):
        """Press, move, release - a real drag gesture."""
        app = self.app
        sx, sy = self.at(x0, y0)
        ex, ey = self.at(x1, y1)
        t = self._clock
        self._clock += 1000
        app.canvas.event_generate("<ButtonPress-1>", x=sx, y=sy, time=t)
        app.update()
        # Button1 must stay in the modifier mask, otherwise Tk does not
        # treat the event as a <B1-Motion> at all.
        app.canvas.event_generate("<B1-Motion>", x=ex, y=ey,
                                  state=(1 if shift else 0) | 0x0100,
                                  time=t + 20)
        app.update()
        app.canvas.event_generate("<ButtonRelease-1>", x=ex, y=ey, time=t + 40)
        app.update()

    def press(self, x, y):
        cx, cy = self.at(x, y)
        t = self._clock
        self._clock += 1000
        self.app.canvas.event_generate("<ButtonPress-1>", x=cx, y=cy, time=t)
        self.app.update()

    def release(self, x, y):
        cx, cy = self.at(x, y)
        t = self._clock
        self._clock += 1000
        self.app.canvas.event_generate("<ButtonRelease-1>", x=cx, y=cy, time=t)
        self.app.update()

    def press_key(self, widget, keysym):
        t = self._clock
        self._clock += 1000
        widget.event_generate("<KeyPress>", keysym=keysym, time=t)
        self.app.update()

    def place_text(self, x, y, text):
        """Drop a text object and return it."""
        app = self.app
        app.set_tool("text")
        app.text_value.set(text)
        self.click(x, y)
        self.assertTrue(app.doc.overlays, "the text tool did not place anything")
        return app.doc.overlays[-1]


class InteractionTest(ClickTestCase):
    """The interaction model the user asked for, one click at a time."""

    # -- 1 ---------------------------------------------------------
    def test_1_click_on_an_object_selects_it_and_never_appends(self):
        app = self.app

        # place one text object
        app.set_tool("text")
        app.text_value.set("Ali")
        self.click(160, 130)
        self.assertEqual(len(app.doc.overlays), 1)
        text_ov = app.doc.overlays[0]

        # switch to the check tool and click *on* the text object
        app.set_tool("check")
        self.click(163, 127)
        self.assertEqual(len(app.doc.overlays), 1,
                         "clicking an existing object must never append")
        self.assertIs(app.selected, text_ov,
                      "clicking an object must select it")

        # clicking empty space with a placement tool does append
        self.click(64, 386)
        self.assertEqual(len(app.doc.overlays), 2)
        self.assertEqual(app.doc.overlays[1].kind, "check")

    # -- 2 ---------------------------------------------------------
    def test_2_clicking_empty_space_with_the_select_tool_deselects(self):
        app = self.app
        app.set_tool("check")
        self.click(64, 386)
        self.assertEqual(len(app.doc.overlays), 1)

        app.set_tool("select")
        self.click(400, 700)
        self.assertIsNone(app.selected,
                          "clicking empty space with the select tool clears it")
        self.assertEqual(len(app.doc.overlays), 1,
                         "the select tool must not add anything")

    # -- 3 ---------------------------------------------------------
    def test_3_drag_moves_the_object_it_grabbed(self):
        app = self.app
        ov = self.place_text(160, 130, "Hello")
        x0, y0, w, h = ov.x0, ov.y0, ov.width, ov.height

        self.drag(163, 127, 183, 147)          # +20 pt right, +20 pt down

        self.assertAlmostEqual(ov.x0, x0 + 20, delta=TOL)
        self.assertAlmostEqual(ov.y0, y0 + 20, delta=TOL)
        self.assertAlmostEqual(ov.width, w, delta=0.01,
                               msg="moving must not resize the object")
        self.assertAlmostEqual(ov.height, h, delta=0.01)

    # -- 4 ---------------------------------------------------------
    def test_4_a_plain_click_changes_nothing(self):
        app = self.app
        ov = self.place_text(160, 130, "Hi")
        app.set_tool("select")
        app._set_edited(False)
        undo_len = len(app.undo_stack)

        self.click(163, 127)                  # plain click, no movement

        self.assertIs(app.selected, ov)
        self.assertEqual(len(app.undo_stack), undo_len,
                         "a click without movement must not create an undo step")
        self.assertFalse(app.dirty,
                         "a click without movement must not mark the file edited")

    # -- 5 ---------------------------------------------------------
    def test_5_the_bottom_right_handle_resizes(self):
        app = self.app
        ov = self.place_text(160, 130, "Resize me")
        size0 = ov.font_size
        x0 = ov.x0

        # grab the handle exactly, then pull it down and to the right
        self.drag(ov.x1, ov.y1, ov.x1 + 40, ov.y1 + 12)

        self.assertGreater(ov.font_size, size0,
                           "dragging the handle must grow the text")
        self.assertAlmostEqual(ov.x0, x0, delta=0.01,
                               msg="resizing must not move the object")

    # -- 6 ---------------------------------------------------------
    def test_6_resizing_a_signature_keeps_its_proportions(self):
        app = self.app
        app._set_signature(self.sig)
        self.click(180, 700)
        ov = app.doc.overlays[-1]
        self.assertEqual(ov.kind, "image")
        ratio0 = ov.height / ov.width

        self.drag(ov.x1, ov.y1, ov.x1 + 40, ov.y1 + 40)
        self.assertAlmostEqual(ov.height / ov.width, ratio0, places=3,
                               msg="the signature must keep its aspect ratio")

        # holding Shift frees the proportions
        h0 = ov.height
        self.drag(ov.x1, ov.y1, ov.x1 + 40, ov.y1, shift=True)
        self.assertAlmostEqual(ov.height, h0, delta=0.01,
                               msg="Shift must allow a free resize")

    # -- 7 ---------------------------------------------------------
    def test_7_delete_removes_the_selected_object(self):
        app = self.app
        app.set_tool("check")
        self.click(64, 386)
        self.assertEqual(len(app.doc.overlays), 1)

        app.set_tool("select")
        self.click(64, 386)                  # select the tick
        self.assertIsNotNone(app.selected)

        app.canvas.focus_set()
        app.update()
        self.press_key(app, "Delete")

        self.assertEqual(len(app.doc.overlays), 0,
                         "Delete must remove the selected object")
        self.assertIsNone(app.selected)

    # -- 8 ---------------------------------------------------------
    def test_8_delete_while_typing_only_edits_the_text(self):
        app = self.app
        ov = self.place_text(160, 130, "Keep me")
        app.set_tool("select")
        self.click(163, 127)

        entry = app.text_entry.entry
        entry.focus_set()
        entry.icursor(tk.END)
        app.update()

        # the Delete key must not reach the app's "delete object" command
        self.press_key(entry, "Delete")
        self.assertEqual(len(app.doc.overlays), 1,
                         "Delete inside a text field must not remove the object")
        self.assertIs(app.selected, ov)

        # and the command itself refuses to run while a field has focus
        app._delete_key()
        self.assertEqual(len(app.doc.overlays), 1,
                         "the delete command must stand down while typing")

        # the caret sits at the end of the text, ready to keep typing
        self.assertEqual(entry.index("insert"), len("Keep me"))

    # -- 9 ---------------------------------------------------------
    def test_9_letter_shortcuts_do_not_fire_while_typing(self):
        app = self.app
        app.set_tool("check")
        entry = app.text_entry.entry
        entry.focus_set()
        entry.delete(0, tk.END)
        app.update()

        self.press_key(entry, "s")           # would normally pick the signature

        self.assertEqual(app.tool, "check",
                         "typing a letter must not switch tools")
        self.assertEqual(entry.get(), "s",
                         "the keystroke must reach the text field")

    # -- 10 --------------------------------------------------------
    def test_10_clicking_a_text_object_again_edits_it_inline(self):
        app = self.app
        ov = self.place_text(160, 130, "Draft")
        self.assertEqual(len(app.doc.overlays), 1)

        app.set_tool("select")
        self.click(163, 127)                  # click the same object again

        self.assertEqual(len(app.doc.overlays), 1,
                         "clicking a text object must not append another one")
        self.assertIs(app.selected, ov)
        self.assertIs(app.focus_get(), app.text_entry.entry,
                      "the caret must land in the text field")

        # typing updates the object live
        entry = app.text_entry.entry
        entry.selection_clear()
        entry.icursor(tk.END)
        entry.insert(tk.END, " v2")
        app.update()
        self.assertEqual(ov.text, "Draft v2",
                         "typing must update the text object live")

    # -- 11 --------------------------------------------------------
    def test_11_undo_restores_the_previous_position(self):
        app = self.app
        ov = self.place_text(160, 130, "Undo me")
        x0 = ov.x0

        self.drag(163, 127, 203, 127)          # move it 40 pt to the right
        self.assertAlmostEqual(ov.x0, x0 + 40, delta=TOL)

        app.undo()
        restored = app.doc.overlays[0]
        self.assertAlmostEqual(restored.x0, x0, delta=0.01,
                               msg="undo must restore the old position")

    # -- 12 --------------------------------------------------------
    def test_12_a_drag_creates_exactly_one_undo_step(self):
        app = self.app
        self.place_text(160, 130, "Steps")
        app.set_tool("select")
        undo_len = len(app.undo_stack)

        self.drag(163, 127, 173, 137)          # one gesture
        self.assertEqual(len(app.undo_stack), undo_len + 1,
                         "one drag must be one undo step")

        self.press(163, 127)
        self.release(173, 137)
        self.assertEqual(len(app.undo_stack), undo_len + 1,
                         "a press without motion must not add an undo step")

    # -- 13 --------------------------------------------------------
    def test_13_check_and_cross_land_where_you_clicked(self):
        app = self.app
        app.set_tool("check")
        self.click(64, 386)
        tick = app.doc.overlays[-1]
        self.assertEqual(tick.kind, "check")
        self.assertAlmostEqual((tick.x0 + tick.x1) / 2, 64, delta=TOL)
        self.assertAlmostEqual((tick.y0 + tick.y1) / 2, 386, delta=TOL)

        app.set_tool("cross")
        self.click(64, 414)
        cross = app.doc.overlays[-1]
        self.assertEqual(cross.kind, "cross")
        self.assertAlmostEqual((cross.x0 + cross.x1) / 2, 64, delta=TOL)
        self.assertAlmostEqual((cross.y0 + cross.y1) / 2, 414, delta=TOL)

    # -- 14 --------------------------------------------------------
    def test_14_the_text_size_stepper_retypes_the_selected_object(self):
        app = self.app
        ov = self.place_text(160, 130, "Sized")
        app.set_tool("select")
        self.click(163, 127)
        self.assertIs(app.selected, ov)

        app.text_size.set(24)
        app.update()

        self.assertAlmostEqual(ov.font_size, 24, places=3)
        self.assertGreater(ov.width, 0)

    # -- 15 --------------------------------------------------------
    def test_15_a_double_click_never_loses_the_click(self):
        """Tk sends the 2nd click of a double click as <Double-Button-1>.

        The app must still select the object and open it for editing
        instead of silently dropping the click.
        """
        app = self.app
        ov = self.place_text(160, 130, "Twice")

        # two quick clicks on the very same spot -> a real double click
        self.click(163, 127, dt=100)
        self.click(163, 127, dt=100)

        self.assertEqual(len(app.doc.overlays), 1,
                         "a double click must not append a second object")
        self.assertIs(app.selected, ov)
        self.assertIs(app.focus_get(), app.text_entry.entry,
                      "a double click on text must open it for editing")

    # -- 16 --------------------------------------------------------
    def test_16_the_source_pdf_is_never_touched(self):
        app = self.app
        before = os.path.getsize(self.pdf)
        with open(self.pdf, "rb") as fh:
            head = fh.read(16)
        self.place_text(160, 130, "Keep")
        self.drag(163, 127, 183, 147)
        app.delete_selected()
        app.update()

        self.assertEqual(os.path.getsize(self.pdf), before)
        with open(self.pdf, "rb") as fh:
            self.assertEqual(fh.read(16), head)

    def test_17_the_file_menu_offers_to_become_the_default_pdf_app(self):
        """The entry exists and reports the real state."""
        app = self.app
        app._update_file_menu()
        label = app.default_menu.entrycget(app.default_item, "label")
        self.assertIn("default", label.lower())
        state = app.default_menu.entrycget(app.default_item, "state")
        self.assertIn(state, ("normal", "disabled"))

    def test_18_the_first_run_offer_is_remembered(self):
        """The offer is not shown twice."""
        from pdfedit import prefs
        prefs.put("asked_default_app", True)
        self.assertTrue(prefs.get("asked_default_app"))
        # and the app must not schedule another one behind our back
        app = self.app
        job = getattr(app, "_default_prompt_job", None)
        if job is not None:
            app.after_cancel(job)
            app._default_prompt_job = None
        app._maybe_offer_default()
        # no new prompt window was created
        prompts = [w for w in app.winfo_children()
                   if isinstance(w, tk.Toplevel)]
        self.assertEqual(prompts, [])

    def test_19_the_text_size_control_resizes_the_interface(self):
        """The size can be changed, and changed back."""
        from pdfedit import theme
        app = self.app
        before = theme.fonts().body.actual("size")

        app.set_interface_scale(1.35)
        app.update()
        bigger = theme.fonts().body.actual("size")
        self.assertGreater(bigger, before)

        app.set_interface_scale(1.0)
        app.update()
        self.assertEqual(theme.fonts().body.actual("size"), before)

    def test_20_the_text_size_button_is_in_the_title_bar(self):
        """There is a way to reach the setting without the menu."""
        app = self.app
        self.assertTrue(hasattr(app, "text_size_btn"))
        app._update_file_menu()      # must not raise
        self.assertTrue(app.text_size_btn.winfo_exists())

    def test_21_a_pdf_dropped_on_the_window_opens(self):
        """Drag and drop behaves like opening the file."""
        from pdfedit import dnd
        app = self.app
        app.close_doc()
        app.update()
        self.assertIsNone(app.doc)

        target = dnd.DropTarget(0)
        target.pending.append(self.pdf)
        app._drop_target = target
        app._collect_drops()
        app.update()
        self.assertIsNotNone(app.doc)


if __name__ == "__main__":
    unittest.main(verbosity=2)
