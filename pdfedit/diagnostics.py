"""Prerequisite checks - does this machine have everything the app needs?

Run it with:

    python app.py --doctor

It prints one line per check and finishes with a verdict.  Every failure
comes with something to do about it, because "it just closed" is the worst
error message there is.
"""
from __future__ import annotations

import importlib
import os
import platform
import struct
import sys
import tempfile

from . import prefs

OK = "ok"
WARN = "warn"
FAIL = "fail"


class Result:
    """One line of the report."""

    def __init__(self, name: str, status: str, detail: str, advice: str = ""):
        self.name = name
        self.status = status
        self.detail = detail
        self.advice = advice

    @property
    def mark(self) -> str:
        return {OK: "  ok  ", WARN: " warn ", FAIL: " FAIL "}[self.status]


def _python_arch() -> str:
    return f"{struct.calcsize('P') * 8}-bit"


def _windows_version() -> str:
    try:
        import winreg
        key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,
                             r"SOFTWARE\Microsoft\Windows NT\CurrentVersion")
        name = winreg.QueryValueEx(key, "ProductName")[0]
        build = winreg.QueryValueEx(key, "CurrentBuildNumber")[0]
        return f"{name} (build {build})"
    except Exception:
        return platform.platform()


def _bundle_dir() -> str | None:
    """The folder the packaged app unpacks itself into, if packaged."""
    return getattr(sys, "_MEIPASS", None)


def check_platform() -> list[Result]:
    out = []
    if os.name != "nt":
        out.append(Result("operating system", WARN, platform.platform(),
                          "This app is built for Windows."))
    else:
        out.append(Result("operating system", OK, _windows_version()))
    arch = platform.machine().lower()
    bits = struct.calcsize("P") * 8
    if bits < 64:
        out.append(Result("architecture", FAIL, f"{arch}, {bits}-bit",
                          "A 64-bit Python is required."))
    else:
        out.append(Result("architecture", OK, f"{arch}, {bits}-bit"))
    return out


def check_python() -> list[Result]:
    version = platform.python_version()
    status = OK
    advice = ""
    if sys.version_info < (3, 11):
        status = FAIL
        advice = "Python 3.11 or newer is required."
    out = [Result("python", status, f"{version} ({platform.python_implementation()})",
                  advice)]
    if getattr(sys, "frozen", False):
        out.append(Result("build", OK, f"packaged - {sys.executable}"))
    else:
        out.append(Result("build", OK, f"running from source - {sys.executable}"))
    return out


def check_tk() -> list[Result]:
    try:
        import tkinter
        version = tkinter.TkVersion
        return [Result("tkinter", OK, f"Tk {version}")]
    except Exception as exc:
        return [Result("tkinter", FAIL, str(exc),
                       "Tk is missing. On Windows, re-run the Python "
                       "installer and tick 'tcl/tk and IDLE'.")]


def check_pymupdf() -> list[Result]:
    try:
        import pymupdf
    except Exception as exc:
        return [Result("pymupdf", FAIL, str(exc),
                       "Run: pip install -r requirements.txt")]
    version = getattr(pymupdf, "__version__", None)
    if not version:
        try:
            version = pymupdf.version[0]
        except Exception:
            version = "installed"
    out = [Result("pymupdf", OK, version)]
    try:
        doc = pymupdf.open()
        doc.new_page()
        doc.close()
        out.append(Result("pdf engine", OK, "can create a document"))
    except Exception as exc:
        out.append(Result("pdf engine", FAIL, str(exc),
                          "The PDF engine cannot run on this machine."))
    return out


def check_pillow() -> list[Result]:
    try:
        from PIL import Image
    except Exception as exc:
        return [Result("pillow", FAIL, str(exc),
                       "Run: pip install -r requirements.txt")]
    out = [Result("pillow", OK, getattr(Image, "__version__", "unknown"))]
    try:
        import io
        buf = io.BytesIO()
        Image.new("RGBA", (8, 8), (10, 20, 120, 255)).save(buf, format="PNG")
        buf.seek(0)
        Image.open(buf).convert("RGBA").load()
        out.append(Result("png support", OK, "can read and write PNG"))
    except Exception as exc:
        out.append(Result("png support", FAIL, str(exc),
                          "PNG is the only image format the app reads."))
    return out


def check_fonts() -> list[Result]:
    root = None
    made_root = False
    try:
        import tkinter
        from tkinter import font as tkfont
        root = tkinter._default_root
        if root is None:
            # No window yet - make a hidden one just to ask about fonts.
            root = tkinter.Tk()
            root.withdraw()
            made_root = True
        families = set(tkfont.families(root))
    except Exception as exc:
        return [Result("fonts", WARN, str(exc),
                       "The app will still run, with the default font.")]
    finally:
        if made_root and root is not None:
            try:
                root.destroy()
            except Exception:
                pass
    if not families:
        return [Result("fonts", WARN, "none found",
                       "The app will still run, with the default font.")]
    preferred = [f for f in ("Segoe UI Variable Text", "Segoe UI Variable",
                             "Segoe UI") if f in families]
    return [Result("fonts", OK if preferred else WARN,
                   preferred[0] if preferred else
                   f"{len(families)} fonts, none of the Segoe UI family",
                   "" if preferred else
                   "The app falls back to the default font; it still works.")]


def check_settings() -> list[Result]:
    folder = prefs.home()
    try:
        os.makedirs(folder, exist_ok=True)
        probe = os.path.join(folder, ".write-test")
        with open(probe, "w", encoding="utf-8") as fh:
            fh.write("ok")
        os.remove(probe)
        return [Result("settings folder", OK, folder)]
    except Exception as exc:
        return [Result("settings folder", FAIL, f"{folder} - {exc}",
                       "Windows needs write access to %APPDATA%.")]


def check_runtime() -> list[Result]:
    """The DLLs the app needs at run time.

    On a packaged build these are unpacked next to the app; a clean PC will
    not have the Visual C++ runtime installed, so it has to travel with the
    app.
    """
    needed = ["msvcp140.dll", "vcruntime140.dll", "vcruntime140_1.dll"]
    bundle = _bundle_dir()
    system = os.path.join(os.environ.get("SystemRoot", r"C:\Windows"),
                          "System32")
    out = []
    if bundle:
        for name in needed:
            src = os.path.join(bundle, name)
            if os.path.exists(src):
                out.append(Result(f"bundled {name}", OK, src))
            elif os.path.exists(os.path.join(system, name)):
                out.append(Result(f"bundled {name}", WARN, "taken from Windows",
                                  "Install the Microsoft Visual C++ "
                                  "redistributable, or rebuild the app."))
            else:
                out.append(Result(f"bundled {name}", FAIL, "not found",
                                  "The app cannot start without it - "
                                  "rebuild the app with build_exe.bat."))
    else:
        for name in needed:
            if os.path.exists(os.path.join(system, name)):
                out.append(Result(f"system {name}", OK, "installed"))
            else:
                out.append(Result(f"system {name}", WARN, "not installed",
                                  "Running from source needs the Visual C++ "
                                  "redistributable for the PDF engine."))
    return out


def run_checks() -> list[Result]:
    """Every check, in the order a person would work through them."""
    results: list[Result] = []
    results += check_platform()
    results += check_python()
    results += check_tk()
    results += check_pymupdf()
    results += check_pillow()
    results += check_fonts()
    results += check_settings()
    results += check_runtime()
    return results


def format_report(results: list[Result]) -> str:
    """The report as plain text."""
    lines = ["PDF Sign & Fill - system check", ""]
    width = max(len(r.name) for r in results) + 2
    for r in results:
        lines.append(f"[{r.mark}] {r.name:<{width}} {r.detail}")
        if r.advice and r.status != OK:
            lines.append(f"{'':<{width + 8}}-> {r.advice}")
    failures = [r for r in results if r.status == FAIL]
    warnings = [r for r in results if r.status == WARN]
    lines.append("")
    if failures:
        lines.append(f"{len(failures)} problem(s) found - the app will not "
                     f"work properly until they are fixed.")
    elif warnings:
        lines.append("Everything the app needs is present. "
                     f"{len(warnings)} note(s) above.")
    else:
        lines.append("Everything the app needs is present.")
    return "\n".join(lines)


def doctor_text() -> str:
    """The full report as a string."""
    return format_report(run_checks())


def has_failures(results: list[Result]) -> bool:
    return any(r.status == FAIL for r in results)


def crash_log_path() -> str:
    """Where a crash report is written."""
    return os.path.join(prefs.home(), "error.log")


def write_crash_report(exc: BaseException) -> str:
    """Record a crash on disk and return the path.

    A silent crash is the least useful thing an app can do, so every
    unhandled error is written to a log the user can point at.
    """
    import traceback
    path = crash_log_path()
    try:
        os.makedirs(prefs.home(), exist_ok=True)
        with open(path, "a", encoding="utf-8") as fh:
            fh.write("=" * 68 + "\n")
            fh.write(f"{_windows_version() if os.name == 'nt' else platform.platform()}\n")
            fh.write(f"python {platform.python_version()} at {sys.executable}\n")
            fh.write(f"frozen: {getattr(sys, 'frozen', False)}\n")
            fh.write("-" * 68 + "\n")
            traceback.print_exception(type(exc), exc, exc.__traceback__,
                                      file=fh)
            fh.write("\n")
    except OSError:
        return ""
    return path
