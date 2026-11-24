"""Tests for the .pdf file association and the preferences file.

The registry tests write to a throw-away key under HKCU\\Software\\Classes, so
the machine's real .pdf association is never touched.
"""
from __future__ import annotations

import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pdfedit import assoc, prefs  # noqa: E402

TEST_ROOT = r"Software\Classes\PdfSignAndFillSelfTest"


def _delete_tree(path: str) -> None:
    """Remove a registry key and everything under it."""
    import winreg
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, path, 0,
                            winreg.KEY_ALL_ACCESS) as key:
            index = 0
            while True:
                try:
                    sub = winreg.EnumKey(key, index)
                except OSError:
                    break
                _delete_tree(path + "\\" + sub)
                index += 1
        winreg.DeleteKey(winreg.HKEY_CURRENT_USER, path)
    except OSError:
        pass


class CommandTest(unittest.TestCase):
    """The command Windows runs to open a PDF with this app."""

    def test_command_ends_with_the_file_argument(self):
        self.assertTrue(assoc.app_command().rstrip().endswith('"%1"'))

    def test_command_quotes_the_executable(self):
        cmd = assoc.app_command()
        self.assertIn('"', cmd)
        self.assertIn(assoc.app_exe(), cmd)

    def test_command_mentions_app_py_when_running_from_source(self):
        if assoc.is_frozen():
            self.skipTest("running from the packaged build")
        self.assertIn("app.py", assoc.app_command())

    def test_app_script_points_at_a_real_file(self):
        script = assoc.app_script()
        if script is None:
            self.skipTest("running from the packaged build")
        self.assertTrue(os.path.exists(script))


class PrefsTest(unittest.TestCase):
    """The small JSON preferences file."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="pdfedit_prefs_")
        self._saved = os.environ.get(prefs.ENV_HOME)
        os.environ[prefs.ENV_HOME] = self.tmp

    def tearDown(self):
        if self._saved is None:
            os.environ.pop(prefs.ENV_HOME, None)
        else:
            os.environ[prefs.ENV_HOME] = self._saved

    def test_missing_file_reads_as_empty(self):
        self.assertEqual(prefs.load(), {})

    def test_round_trip(self):
        self.assertTrue(prefs.put("asked_default_app", True))
        self.assertTrue(prefs.get("asked_default_app"))
        self.assertEqual(prefs.get("never_ask_default", False), False)

    def test_settings_land_in_the_override_folder(self):
        prefs.put("asked_default_app", True)
        self.assertTrue(os.path.exists(os.path.join(self.tmp, "settings.json")))

    def test_a_broken_file_does_not_raise(self):
        os.makedirs(self.tmp, exist_ok=True)
        with open(prefs.path(), "w", encoding="utf-8") as fh:
            fh.write("{not json")
        self.assertEqual(prefs.load(), {})


@unittest.skipUnless(assoc.is_windows(), "Windows registry only")
class RegistryTest(unittest.TestCase):
    """Registering, reading back and removing the association."""

    def setUp(self):
        _delete_tree(TEST_ROOT)

    def tearDown(self):
        _delete_tree(TEST_ROOT)

    def test_register_then_unregister(self):
        self.assertFalse(assoc.is_registered(TEST_ROOT))
        self.assertTrue(assoc.register(TEST_ROOT))
        self.assertTrue(assoc.is_registered(TEST_ROOT))
        self.assertTrue(assoc.unregister(TEST_ROOT))
        self.assertFalse(assoc.is_registered(TEST_ROOT))

    def test_register_writes_an_open_command(self):
        assoc.register(TEST_ROOT)
        import winreg
        path = TEST_ROOT + "\\" + assoc.PROG_ID + r"\shell\open\command"
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, path) as key:
            value, _ = winreg.QueryValueEx(key, "")
        self.assertIn("%1", value)
        self.assertIn(assoc.app_exe(), value)

    def test_register_writes_an_icon(self):
        assoc.register(TEST_ROOT)
        import winreg
        path = TEST_ROOT + "\\" + assoc.PROG_ID + r"\DefaultIcon"
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, path) as key:
            value, _ = winreg.QueryValueEx(key, "")
        self.assertIn(assoc.app_exe(), value)

    def test_unregister_leaves_another_apps_choice_alone(self):
        """If the user picked something else, we must not stomp on it."""
        import winreg
        assoc.register(TEST_ROOT)
        # pretend another program took the extension over
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER,
                              TEST_ROOT + r"\.pdf") as key:
            winreg.SetValueEx(key, "", 0, winreg.REG_SZ, "SomeOtherApp.pdf")
        assoc.unregister(TEST_ROOT)
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                            TEST_ROOT + r"\.pdf") as key:
            value, _ = winreg.QueryValueEx(key, "")
        self.assertEqual(value, "SomeOtherApp.pdf")

    def test_the_real_pdf_association_is_untouched(self):
        """The whole point of the test root: .pdf itself is never written."""
        before = assoc.is_registered()
        assoc.register(TEST_ROOT)
        self.assertEqual(assoc.is_registered(), before)


class StatusTest(unittest.TestCase):
    """The state description shown in the UI."""

    def test_status_is_a_string(self):
        self.assertIsInstance(assoc.default_status(), str)

    def test_non_windows_says_so(self):
        if assoc.is_windows():
            self.assertNotEqual(assoc.default_status(),
                                "Not available on this system")
        else:
            self.assertEqual(assoc.default_status(),
                             "Not available on this system")


if __name__ == "__main__":
    unittest.main(verbosity=2)
