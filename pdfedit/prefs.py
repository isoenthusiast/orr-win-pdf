"""Small JSON preferences file, stored with the user's other app data.

Windows convention is %APPDATA%\\<App Name>\\settings.json.  The
PDF_SIGN_FILL_HOME environment variable overrides that, which keeps the app
portable (settings travel with it) and makes the preferences easy to test.
"""
from __future__ import annotations

import json
import os

APP_DIR_NAME = "PDF Sign & Fill"
ENV_HOME = "PDF_SIGN_FILL_HOME"
FILE_NAME = "settings.json"


def home() -> str:
    """The folder that holds this app's preferences."""
    override = os.environ.get(ENV_HOME)
    if override:
        return os.path.abspath(override)
    base = os.environ.get("APPDATA") or os.path.expanduser("~")
    return os.path.join(base, APP_DIR_NAME)


def path() -> str:
    """The full path of the settings file."""
    return os.path.join(home(), FILE_NAME)


def load() -> dict:
    """Every stored preference.  A missing or broken file reads as empty."""
    try:
        with open(path(), "r", encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def save(data: dict) -> bool:
    """Write the preferences.  Written to a temp file first, then moved, so a
    crash halfway through cannot leave a half-written file behind."""
    try:
        os.makedirs(home(), exist_ok=True)
        tmp = path() + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=2, sort_keys=True)
        os.replace(tmp, path())
        return True
    except OSError:
        return False


def get(key: str, default=None):
    """One preference, or the default."""
    return load().get(key, default)


def put(key: str, value) -> bool:
    """Change one preference and write the file."""
    data = load()
    data[key] = value
    return save(data)
