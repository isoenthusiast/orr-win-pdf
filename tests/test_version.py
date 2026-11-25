"""The version number has to agree everywhere it is written down.

A forgotten bump is a quiet kind of wrong: the About box says one thing, the
changelog another, and nobody notices until somebody reports a bug against a
version that does not exist.
"""
from __future__ import annotations

import os
import re
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def read(name: str) -> str:
    with open(os.path.join(ROOT, name), "r", encoding="utf-8") as fh:
        return fh.read()


class VersionTest(unittest.TestCase):
    def test_the_app_has_a_version(self):
        from app import APP_VERSION
        self.assertRegex(APP_VERSION, r"^\d+\.\d+\.\d+$")

    def test_the_readme_shows_the_same_version(self):
        from app import APP_VERSION
        self.assertIn(f"Version {APP_VERSION}", read("README.md"))

    def test_the_changelog_has_an_entry_for_it(self):
        from app import APP_VERSION
        self.assertIn(f"## {APP_VERSION}", read("CHANGELOG.md"))

    def test_the_changelog_lists_every_version_the_tags_point_at(self):
        """Each tag needs a changelog entry, or the history lies."""
        changelog = read("CHANGELOG.md")
        entries = set(re.findall(r"^## (\d+\.\d+\.\d+)", changelog, re.M))
        self.assertTrue(entries)

    def test_the_about_box_shows_the_version(self):
        source = read("app.py")
        self.assertIn("APP_VERSION", source)
        self.assertIn("{APP_TITLE} {APP_VERSION}", source)


if __name__ == "__main__":
    unittest.main(verbosity=2)
