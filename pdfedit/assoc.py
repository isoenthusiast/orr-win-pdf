"""Make this app the default program for .pdf files.

Everything happens under HKEY_CURRENT_USER, so no administrator rights are
needed and nothing outside the current user's own registry is touched.

How Windows actually decides
----------------------------
On Windows 10 and 11 the *real* default lives in

    HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Explorer\\FileExts\\.pdf\\UserChoice

and that key is protected - a program cannot write it, because the ProgId
inside it is validated against a hash of the executable.  What a program
*can* do is:

1. register itself under HKCU\\Software\\Classes, which adds it to the
   "Open with" list and gives Explorer an icon for the .pdf icon; and
2. open the shell's own "How do you want to open this file?" dialog, where
   the user ticks "Always use this app".  The shell then writes a valid
   UserChoice, hash and all.

So the flow here is: register, then let the user confirm.  If the user
prefers, they can also do it by hand in Settings > Apps > Default apps.
"""
from __future__ import annotations

import os
import subprocess
import sys

try:                                    # Windows only
    import winreg
except ImportError:                     # pragma: no cover - non-Windows
    winreg = None

PROG_ID = "PDFSignAndFill.pdf"
APP_NAME = "PDF Sign & Fill"
CLASSES_ROOT = r"Software\Classes"
EXT = ".pdf"
USER_CHOICE = (r"Software\Microsoft\Windows\CurrentVersion\Explorer"
               r"\FileExts\.pdf\UserChoice")


# ------------------------------------------------------------------ basics
def is_windows() -> bool:
    """True on Windows, where file associations live in the registry."""
    return os.name == "nt" and winreg is not None


def is_frozen() -> bool:
    """True when running from the packaged .exe rather than from source."""
    return bool(getattr(sys, "frozen", False))


def app_exe() -> str:
    """The executable Windows should launch."""
    return sys.executable


def app_script() -> str | None:
    """Path of app.py when running from source, else None."""
    if is_frozen():
        return None
    here = os.path.dirname(os.path.abspath(__file__))
    return os.path.normpath(os.path.join(here, os.pardir, "app.py"))


def app_command() -> str:
    """The command line Windows runs to open a PDF with this app.

    Always ends in "%1", which Windows replaces with the file to open.
    """
    exe = app_exe()
    script = app_script()
    if script:
        return f'"{exe}" "{script}" "%1"'
    return f'"{exe}" "%1"'


# --------------------------------------------------------------- registry
def _open_key(path: str, write: bool = False):
    access = winreg.KEY_ALL_ACCESS if write else winreg.KEY_READ
    return winreg.OpenKey(winreg.HKEY_CURRENT_USER, path, 0, access)


def _read_default(path: str) -> str | None:
    """The default value of a key, or None if the key or value is missing."""
    try:
        with _open_key(path) as key:
            value, _ = winreg.QueryValueEx(key, "")
            return value
    except OSError:
        return None


def _delete_tree(path: str) -> None:
    """Remove a key and everything under it."""
    try:
        with _open_key(path, write=True) as key:
            index = 0
            while True:
                try:
                    sub = winreg.EnumKey(key, index)
                except OSError:
                    break
                _delete_tree(path + "\\" + sub)
                index += 1
        winreg.DeleteKey(winreg.HKEY_CURRENT_USER, path)
    except FileNotFoundError:
        pass
    except OSError:
        pass


def _write(path: str, values: dict) -> None:
    """Create a key and set values on it."""
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, path) as key:
        for name, (kind, value) in values.items():
            winreg.SetValueEx(key, name, 0, kind, value)


def register(root: str | None = None, command: str | None = None) -> bool:
    """Register this app as a handler for .pdf files.

    Writes three things under the given registry root (HKCU\\Software\\Classes
    by default): the .pdf extension pointing at PROG_ID, the PROG_ID entry
    itself with its icon and open command, and an Applications entry so the
    app shows up in the shell's "Open with" list.

    Returns True when the registry was written.
    """
    if not is_windows():
        return False
    base = root or CLASSES_ROOT
    cmd = command or app_command()
    exe = app_exe()

    try:
        _write(base + "\\" + EXT, {"": (winreg.REG_SZ, PROG_ID)})

        icon = f'"{exe}",0'
        _write(base + "\\" + PROG_ID, {"": (winreg.REG_SZ, APP_NAME)})
        _write(base + "\\" + PROG_ID + r"\DefaultIcon",
               {"": (winreg.REG_SZ, icon)})
        _write(base + "\\" + PROG_ID + r"\shell\open\command",
               {"": (winreg.REG_SZ, cmd)})

        # Also register under Applications\<exe> so the app appears in the
        # "Open with" list even before the user has ever picked it.
        apps = base + r"\Applications" + "\\" + os.path.basename(exe)
        _write(apps + r"\shell\open\command", {"": (winreg.REG_SZ, cmd)})
        _write(apps + r"\SupportedTypes", {EXT: (winreg.REG_SZ, "")})
    except OSError:
        return False
    return True


def unregister(root: str | None = None) -> bool:
    """Undo :func:`register`.

    The .pdf entry is only removed if it still points at this app - if the
    user has since picked something else, that choice is left alone.
    """
    if not is_windows():
        return False
    base = root or CLASSES_ROOT
    try:
        if _read_default(base + "\\" + EXT) == PROG_ID:
            _delete_tree(base + "\\" + EXT)
        _delete_tree(base + "\\" + PROG_ID)
        _delete_tree(base + r"\Applications" + "\\" + os.path.basename(app_exe()))
    except OSError:
        return False
    return True


def is_registered(root: str | None = None) -> bool:
    """True when this app is registered as a .pdf handler."""
    if not is_windows():
        return False
    base = root or CLASSES_ROOT
    return _read_default(base + "\\" + EXT) == PROG_ID


def user_choice() -> str | None:
    """The ProgId Windows currently uses for .pdf, if the user has chosen one."""
    if not is_windows():
        return None
    try:
        with _open_key(USER_CHOICE) as key:
            value, _ = winreg.QueryValueEx(key, "ProgId")
            return value
    except OSError:
        return None


def is_default() -> bool:
    """True when double-clicking a PDF would open it in this app.

    A protected UserChoice wins over the registry entry we write, so both
    are checked: if the user has made a choice, that choice must be us.
    """
    if not is_windows():
        return False
    choice = user_choice()
    if choice:
        if choice.lower() == PROG_ID.lower():
            return True
        exe = os.path.basename(app_exe()).lower()
        return exe in choice.lower()
    return is_registered()


def default_status() -> str:
    """A short, human-readable description of the current state."""
    if not is_windows():
        return "Not available on this system"
    if is_default():
        return "PDF Sign & Fill is the default for .pdf files"
    if is_registered():
        return "Registered - confirm it in the 'Open with' dialog"
    return "Not set"


# ---------------------------------------------------------- the handover
def offer_open_with() -> bool:
    """Open the shell's "How do you want to open this file?" dialog.

    The user ticks "Always use this app" there, and the shell writes the
    protected UserChoice key properly.  Only works for the packaged .exe -
    from source there is no executable to offer.
    """
    if not is_windows() or not is_frozen():
        return False
    exe = app_exe()
    try:
        subprocess.Popen(["rundll32.exe", "shell32.dll,OpenAs_RunDLL", exe])
    except OSError:
        return False
    return True


def open_default_apps() -> bool:
    """Open Settings > Apps > Default apps, where the user can do it by hand."""
    if not is_windows():
        return False
    try:
        os.startfile("ms-settings:defaultapps")   # noqa: S606 - Windows API
    except (OSError, AttributeError):
        return False
    return True
