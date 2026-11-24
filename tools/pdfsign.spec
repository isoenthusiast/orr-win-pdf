# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller build spec for PDF Sign & Fill.

Build with:
    .venv\\Scripts\\python -m PyInstaller --clean tools\\pdfsign.spec

Produces a single self-contained exe in dist\\.
Only the PyMuPDF *binaries* are collected: the package also ships ~51 MB of
ONNX layout models and C headers that this app never touches.
"""
import os

# PyInstaller 6.x renamed collect_binaries() to collect_dynamic_libs()
try:
    from PyInstaller.utils.hooks import collect_dynamic_libs as _collect_binaries
except ImportError:  # older PyInstaller
    from PyInstaller.utils.hooks import collect_binaries as _collect_binaries

ROOT = os.path.abspath(os.path.join(SPECPATH, os.pardir))

# collect_dynamic_libs() also drags in the package's *data* files, which for
# PyMuPDF means ~45 MB of ONNX layout models this app never uses.  Keep the
# real shared libraries and extension modules only.
_DLL = (".pyd", ".dll", ".so", ".dylib")
pymupdf_binaries = [(src, dest) for src, dest in _collect_binaries("pymupdf")
                     if src.lower().endswith(_DLL)]

a = Analysis(
    [os.path.join(ROOT, "app.py")],
    pathex=[ROOT],
    binaries=pymupdf_binaries,
    datas=[(os.path.join(ROOT, "app.ico"), ".")],
    hiddenimports=[
        "PIL.ImageTk",
        "PIL._tkinter_finder",
        "pymupdf.mupdf",
        "pymupdf.extra",
        "pymupdf._extra",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # not used by this app, and huge
        "pymupdf.layout",
        "pymupdf.mupdf-devel",
        # Pillow codecs we never open - PNG is the only format we touch
        "PIL._avif",
        "PIL._webp",
        "PIL._imagingcms",
        "PIL._imagingqt",
        "PIL._imagingtiff",
        "numpy",
        "scipy",
        "pandas",
        "matplotlib",
        "pytest",
        "unittest",
        "pydoc_data",
        "test",
    ],
    noarchive=False,
    optimize=0,
)

# PyMuPDF ships ~40 MB of ONNX layout models that this app never loads, but
# the analysis drags them in from the package tree.  Strip them from every
# collection the analysis produced.  The same goes for MuPDF's C headers and
# import libraries - a compiler is never involved at runtime.
def _without_layout_models(items):
    out = []
    for it in items:
        src = str(it[0]).lower()
        if src.endswith((".onnx", ".yaml", ".lib", ".h", ".hpp")):
            continue
        if "mupdf-devel" in src:
            continue
        out.append(it)
    return out


a.binaries = _without_layout_models(a.binaries)
a.datas = _without_layout_models(a.datas)
if hasattr(a, "zippeddata"):
    a.zippeddata = _without_layout_models(a.zippeddata)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="PDF Sign and Fill",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=os.path.join(ROOT, "app.ico"),
)
