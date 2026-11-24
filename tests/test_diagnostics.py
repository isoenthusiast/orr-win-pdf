"""Tests for the system check (app.py --doctor)."""
from __future__ import annotations

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pdfedit import diagnostics, theme  # noqa: E402


class ReportTest(unittest.TestCase):
    """The report itself."""

    def test_the_report_names_the_important_checks(self):
        text = diagnostics.doctor_text()
        for wanted in ("operating system", "architecture", "python", "tkinter",
                       "pymupdf", "pillow", "settings folder"):
            self.assertIn(wanted, text)

    def test_the_report_ends_with_a_verdict(self):
        text = diagnostics.doctor_text()
        self.assertTrue(text.strip().splitlines()[-1])

    def test_every_check_has_a_status(self):
        for result in diagnostics.run_checks():
            self.assertIn(result.status, (diagnostics.OK, diagnostics.WARN,
                                          diagnostics.FAIL))
            self.assertTrue(result.detail)

    def test_a_failing_check_carries_advice(self):
        result = diagnostics.Result("thing", diagnostics.FAIL, "broken",
                                    "do this about it")
        self.assertEqual(result.advice, "do this about it")

    def test_this_machine_has_everything_the_app_needs(self):
        """The build machine must pass its own check."""
        failures = [r for r in diagnostics.run_checks()
                    if r.status == diagnostics.FAIL]
        self.assertEqual([r.name for r in failures], [])


class ScaleTest(unittest.TestCase):
    """The interface text size."""

    @classmethod
    def setUpClass(cls):
        # Tk fonts need a root window, and there is none in this module.
        import tkinter
        cls.root = tkinter.Tk()
        cls.root.withdraw()
        theme.reset_fonts()

    @classmethod
    def tearDownClass(cls):
        theme.reset_fonts()
        try:
            cls.root.destroy()
        except Exception:
            pass

    def tearDown(self):
        theme.set_scale(1.0)

    def test_the_default_is_normal(self):
        theme.set_scale(1.0)
        self.assertEqual(theme.scale(), 1.0)

    def test_scaling_changes_the_measurements(self):
        theme.set_scale(1.0)
        base = theme.scaled(100)
        theme.set_scale(2.0)
        self.assertEqual(theme.scaled(100), base * 2)

    def test_the_scale_is_clamped_to_something_usable(self):
        theme.set_scale(99)
        self.assertLessEqual(theme.scale(), 2.0)
        theme.set_scale(0.01)
        self.assertGreaterEqual(theme.scale(), 0.75)

    def test_a_measurement_survives_a_round_trip(self):
        theme.set_scale(1.0)
        design = theme.design(theme.scaled(240))
        self.assertAlmostEqual(design, 240, delta=1)
        theme.set_scale(1.35)
        self.assertAlmostEqual(theme.design(theme.scaled(design)), design,
                               delta=1)

    def test_the_fonts_follow_the_scale(self):
        theme.set_scale(1.0)
        small = theme.fonts().body.actual("size")
        theme.set_scale(1.6)
        big = theme.fonts().body.actual("size")
        self.assertGreater(big, small)

    def test_there_are_five_sizes_offered(self):
        self.assertEqual(len(theme.SCALE_STEPS), 5)
        self.assertEqual(theme.SCALE_STEPS[1][1], 1.0)


class CrashLogTest(unittest.TestCase):
    """A crash leaves a report behind."""

    def test_the_crash_report_is_written(self):
        import tempfile
        tmp = tempfile.mkdtemp(prefix="pdfedit_crash_")
        saved = os.environ.get(diagnostics.prefs.ENV_HOME)
        os.environ[diagnostics.prefs.ENV_HOME] = tmp
        try:
            path = diagnostics.write_crash_report(ValueError("boom"))
            self.assertTrue(os.path.exists(path))
            with open(path, "r", encoding="utf-8") as fh:
                text = fh.read()
            self.assertIn("boom", text)
            self.assertIn("ValueError", text)
        finally:
            if saved is None:
                os.environ.pop(diagnostics.prefs.ENV_HOME, None)
            else:
                os.environ[diagnostics.prefs.ENV_HOME] = saved


if __name__ == "__main__":
    unittest.main(verbosity=2)
