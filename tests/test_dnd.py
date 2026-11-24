"""Tests for dropping a PDF from Explorer onto the app window.

The OLE plumbing cannot be driven from a test, but the part that matters -
reading the file names out of a CF_HDROP - can be, with a handle built by
hand.
"""
from __future__ import annotations

import ctypes
import os
import struct
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pdfedit import dnd  # noqa: E402

kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
kernel32.GlobalAlloc.argtypes = [ctypes.c_uint, ctypes.c_size_t]
kernel32.GlobalAlloc.restype = ctypes.c_void_p
kernel32.GlobalLock.argtypes = [ctypes.c_void_p]
kernel32.GlobalLock.restype = ctypes.c_void_p
kernel32.GlobalUnlock.argtypes = [ctypes.c_void_p]
kernel32.GlobalFree.argtypes = [ctypes.c_void_p]
kernel32.GlobalFree.restype = ctypes.c_void_p

GMEM_MOVEABLE = 0x0002


def make_hdrop(paths: list[str]) -> int:
    """Build a CF_HDROP handle holding these file names."""
    payload = "".join(p + "\0" for p in paths).encode("utf-16-le") + b"\0\0"
    # DROPFILES: pFiles, POINT (2 x LONG), fNC, fWide
    header = struct.pack("<I", 20) + struct.pack("<ii", 0, 0) + \
        struct.pack("<I", 0) + struct.pack("<I", 1)
    data = header + payload
    handle = kernel32.GlobalAlloc(GMEM_MOVEABLE, len(data))
    ptr = kernel32.GlobalLock(handle)
    ctypes.memmove(ptr, data, len(data))
    kernel32.GlobalUnlock(handle)
    return int(handle)


class HdropTest(unittest.TestCase):
    """Reading the file names out of a drop."""

    @unittest.skipUnless(os.name == "nt", "Windows only")
    def test_one_file_comes_back(self):
        handle = make_hdrop([r"C:\Users\test\Documents\form.pdf"])
        try:
            self.assertEqual(dnd.files_from_hdrop(handle),
                             [r"C:\Users\test\Documents\form.pdf"])
        finally:
            kernel32.GlobalFree(handle)

    @unittest.skipUnless(os.name == "nt", "Windows only")
    def test_several_files_come_back_in_order(self):
        wanted = [r"C:\a.pdf", r"C:\b.pdf", r"C:\c.pdf"]
        handle = make_hdrop(wanted)
        try:
            self.assertEqual(dnd.files_from_hdrop(handle), wanted)
        finally:
            kernel32.GlobalFree(handle)

    @unittest.skipUnless(os.name == "nt", "Windows only")
    def test_a_path_with_spaces_survives(self):
        wanted = [r"C:\My Documents\Annual Report 2026.pdf"]
        handle = make_hdrop(wanted)
        try:
            self.assertEqual(dnd.files_from_hdrop(handle), wanted)
        finally:
            kernel32.GlobalFree(handle)


class TargetTest(unittest.TestCase):
    """The drop target itself."""

    def test_install_returns_none_off_windows(self):
        if os.name == "nt":
            self.skipTest("Windows can register a drop target")
        self.assertIsNone(dnd.install(None))

    @unittest.skipUnless(os.name == "nt", "Windows only")
    def test_a_target_starts_empty(self):
        target = dnd.DropTarget(0)
        self.assertEqual(target.take(), [])
        self.assertFalse(target.hovering)

    @unittest.skipUnless(os.name == "nt", "Windows only")
    def test_the_queue_holds_what_was_dropped(self):
        target = dnd.DropTarget(0)
        target.pending.append(r"C:\x.pdf")
        self.assertEqual(target.take(), [r"C:\x.pdf"])
        self.assertEqual(target.take(), [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
