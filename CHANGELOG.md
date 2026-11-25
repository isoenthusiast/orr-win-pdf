# Changelog

All notable changes to **PDF Sign & Fill** are recorded here.

The project follows [semantic versioning](https://semver.org): a *patch* fixes
something, a *minor* adds something, a *major* changes what people rely on.

## 1.1.0 — 25 November 2026

### Fixed

- **The app would not start on a PC without the Microsoft Visual C++ runtime.**
  MuPDF's engine is C++, so it imports `MSVCP140.dll` — and Windows 11 does not
  ship that runtime; it only exists where somebody installed the
  redistributable. The build machine had it, so it never showed up during
  development, and the app died instantly on a clean PC with
  *"MSVCP140.dll was not found"*. The runtime now travels with the app, and
  `tools/check_exe_deps.py` reads the finished `.exe`'s import table so a
  missing prerequisite fails the build instead of a user's afternoon.
- The application icon was written from the smallest drawing, and Pillow will
  not scale an image up — so `app.ico` held a single 16×16 frame. It now
  carries all seven sizes, 16 to 256.

### Added

- **Drag a PDF from Explorer onto the window** to open it. Done through the
  OLE interface directly, so the app keeps its one-file, no-dependencies
  promise. The window outlines itself while a file is over it.
- **The interface text can be resized.** A `T` button in the title bar, or
  `View ▸ Interface text size`, offers five sizes from *Small* to *Largest*.
  Everything scales with it — panels, buttons, the rail, the floating bar —
  and the choice is remembered between runs.
- **`app.py --doctor`** (and `PDF Sign and Fill.exe --doctor`) reports what a
  machine has and what it is missing: Python, Tk, PyMuPDF, Pillow, the fonts,
  and the Visual C++ runtime the PDF engine needs.
- **The app can become the default program for PDFs.** `File ▸ Make default
  PDF app…` registers it and walks through Windows' own *Open with* dialog.
  It is a per-user change — no administrator rights — and the app asks once,
  on first run.
- Crashes are written to `%APPDATA%\PDF Sign & Fill\error.log`, and the window
  that appears says where that file is.

### Improved

- Opening a file that is password protected, damaged, missing or simply not a
  PDF now says which of those it is, in words, instead of showing a raw error.
- `run.bat` checks its prerequisites before failing and says what to do.
- `build_exe.bat` now runs the dependency check and the full verification
  itself, so a broken build cannot quietly get through.
- 77 tests, up from 37: drag and drop, the text scaling, the system check and
  the file association all have their own coverage.

## 1.0.0 — 24 November 2026

The first public version.

- Open a PDF and edit it: place a PNG signature, drop text into form fields,
  stamp check marks or X marks.
- Turn a page — rotate left or right, flip upside down or left to right — and
  the turn is saved into the exported PDF. Anything already on the page travels
  with it and stays upright.
- A click selects, a drag moves, the corner handle resizes, and clicking empty
  space adds. Nothing mechanical about it.
- A built-in guide (`Help ▸ How to use…`), tooltips throughout, and 23 vector
  icons drawn on one optical weight.
- Packaged as a portable onefile `.exe`, and published under the AGPL-3.0.
