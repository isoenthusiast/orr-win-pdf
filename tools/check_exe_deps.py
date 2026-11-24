"""List the DLLs a packaged .exe needs, and check they are all available.

A build machine usually has the Microsoft Visual C++ runtime installed, so
a missing vcruntime140.dll never shows up while you are testing - and then
the app will not start at all on a clean PC.

This reads the PE import table straight out of the .exe, so it reports what
Windows will really ask for, and compares it against:

  * the files the onefile bundle unpacks at run time, and
  * the DLLs that ship with Windows itself.

Usage:  python tools/check_exe_deps.py [path to exe]
"""
from __future__ import annotations

import os
import re
import struct
import sys

# DLLs that ship with Windows and are therefore always available.
WINDOWS_BUILTIN = {
    "kernel32.dll", "kernelbase.dll", "user32.dll", "gdi32.dll", "advapi32.dll",
    "shell32.dll", "ole32.dll", "oleaut32.dll", "comdlg32.dll", "comctl32.dll",
    "shlwapi.dll", "msvcrt.dll", "ucrtbase.dll", "ws2_32.dll", "winmm.dll",
    "winspool.drv", "setupapi.dll", "imm32.dll", "msctf.dll", "dwmapi.dll",
    "uxtheme.dll", "wintrust.dll", "crypt32.dll", "secur32.dll", "netapi32.dll",
    "userenv.dll", "psapi.dll", "version.dll", "imagehlp.dll", "ntdll.dll",
    "bcrypt.dll", "win32u.dll", "gdi32full.dll", "msvcp_win.dll", "cfgmgr32.dll",
    "powrprof.dll", "profapi.dll", "shcore.dll", "clbcatq.dll", "combase.dll",
    "api-ms-win-crt-runtime-l1-1-0.dll", "api-ms-win-crt-heap-l1-1-0.dll",
    "api-ms-win-crt-string-l1-1-0.dll", "api-ms-win-crt-math-l1-1-0.dll",
    "api-ms-win-crt-convert-l1-1-0.dll", "api-ms-win-crt-locale-l1-1-0.dll",
    "api-ms-win-crt-multibyte-l1-1-0.dll", "api-ms-win-crt-time-l1-1-0.dll",
    "api-ms-win-crt-environment-l1-1-0.dll", "api-ms-win-crt-filesystem-l1-1-0.dll",
    "api-ms-win-crt-stdio-l1-1-0.dll", "api-ms-win-crt-process-l1-1-0.dll",
    "api-ms-win-crt-utility-l1-1-0.dll", "api-ms-win-crt-private-l1-1-0.dll",
    "api-ms-win-crt-conio-l1-1-0.dll", "api-ms-win-crt-console-l1-1-0.dll",
    "ext-ms-win-crt-convert-l1-1-0.dll", "ext-ms-win-crt-filesystem-l1-1-0.dll",
    "ext-ms-win-crt-heap-l1-1-0.dll", "ext-ms-win-crt-locale-l1-1-0.dll",
    "ext-ms-win-crt-math-l1-1-0.dll", "ext-ms-win-crt-multibyte-l1-1-0.dll",
    "ext-ms-win-crt-process-l1-1-0.dll", "ext-ms-win-crt-runtime-l1-1-0.dll",
    "ext-ms-win-crt-stdio-l1-1-0.dll", "ext-ms-win-crt-string-l1-1-0.dll",
    "ext-ms-win-crt-time-l1-1-0.dll", "ext-ms-win-crt-utility-l1-1-0.dll",
}

# The Visual C++ runtime.  These are NOT part of Windows - a clean PC only
# has them if the VC++ redistributable happens to be installed - so a build
# that needs them must ship them.
VC_RUNTIME = {"vcruntime140.dll", "vcruntime140_1.dll", "msvcp140.dll"}


# --------------------------------------------------------------- PE reader
def _u16(data: bytes, off: int) -> int:
    return struct.unpack_from("<H", data, off)[0]


def _u32(data: bytes, off: int) -> int:
    return struct.unpack_from("<I", data, off)[0]


def _u64(data: bytes, off: int) -> int:
    return struct.unpack_from("<Q", data, off)[0]


def machine_type(path: str) -> str:
    """'AMD64', 'ARM64', 'x86' or 'unknown' for a PE file."""
    with open(path, "rb") as fh:
        data = fh.read(0x400)
    if data[:2] != b"MZ":
        return "unknown"
    off = _u32(data, 0x3C)
    if data[off:off + 4] != b"PE\0\0":
        return "unknown"
    machine = _u16(data, off + 4)
    return {0x8664: "AMD64", 0xAA64: "ARM64", 0x14C: "x86"}.get(machine, "unknown")


def imported_dlls(path: str) -> list[str]:
    """Every DLL named in the PE import table."""
    with open(path, "rb") as fh:
        data = fh.read()
    off = _u32(data, 0x3C)
    coff = off + 4
    sections = _u16(data, coff + 2)
    opt_size = _u16(data, coff + 16)
    opt = coff + 20
    magic = _u16(data, opt)
    pe32plus = magic == 0x20B

    if pe32plus:
        dd_off = opt + 112
    else:
        dd_off = opt + 96
    import_rva = _u32(data, dd_off + 8)      # directory entry 1
    if not import_rva:
        return []

    section_off = opt + opt_size
    sections_table = []
    for i in range(sections):
        base = section_off + i * 40
        name = data[base:base + 8].rstrip(b"\0").decode("ascii", "replace")
        vsize = _u32(data, base + 8)
        vaddr = _u32(data, base + 12)
        raw_size = _u32(data, base + 16)
        raw_ptr = _u32(data, base + 20)
        sections_table.append((name, vaddr, vsize, raw_ptr, raw_size))

    def rva_to_offset(rva: int) -> int | None:
        for _name, vaddr, vsize, raw_ptr, raw_size in sections_table:
            if vaddr <= rva < vaddr + max(vsize, raw_size):
                return raw_ptr + (rva - vaddr)
        return None

    out: list[str] = []
    offset = rva_to_offset(import_rva)
    if offset is None:
        return out
    while True:
        entry = offset
        # OriginalFirstThunk, TimeDateStamp, ForwarderChain, Name, FirstThunk
        name_rva = _u32(data, entry + 12)
        if name_rva == 0:
            break
        name_off = rva_to_offset(name_rva)
        if name_off is None:
            break
        end = data.index(b"\0", name_off)
        out.append(data[name_off:end].decode("ascii", "replace"))
        offset = entry + 20
    return out


# ------------------------------------------------------------------ checks
def bundle_contents(exe: str) -> set[str]:
    """Every DLL recorded in the onefile archive's table of contents.

    The archive index stores each member as a length-prefixed bytes object,
    so the name is preceded by a 0x01 marker and a 'b'.  The names can be
    read without unpacking or running anything.
    """
    with open(exe, "rb") as fh:
        data = fh.read()
    names: set[str] = set()
    for match in re.finditer(
            rb"\x01b([A-Za-z0-9_./\\@+-]{2,90}\.(?:dll|pyd))", data):
        names.add(match.group(1).decode("ascii", "replace")
                   .replace("\\", "/").lower())
    return names


def report(exe: str) -> int:
    """Print what the exe needs.  Returns 0 when everything is in place."""
    print(f"checking {exe}")
    arch = machine_type(exe)
    print(f"  architecture : {arch}")
    if arch == "ARM64":
        print("  !  ARM64 build - this will NOT run on an ordinary x64 PC")
    elif arch == "x86":
        print("  !  32-bit build - Windows 11 on x64 needs a 64-bit build")
    elif arch == "AMD64":
        print("     runs on any 64-bit Windows 7 / 10 / 11 PC")

    imports = imported_dlls(exe)
    bundled = bundle_contents(exe)
    system = os.path.join(os.environ.get("SystemRoot", r"C:\Windows"), "System32")

    print(f"  exe imports  : {len(imports)} DLLs (the Windows loader)")
    print(f"  bundle       : {len(bundled)} DLLs unpacked at run time")

    print()
    print("  what the app brings with it")
    print("  -----------------------------")
    wanted = [
        ("python", "the interpreter"),
        ("tcl", "the Tk runtime"),
        ("tk8", "the Tk runtime"),
        ("pymupdf", "the PDF engine"),
        ("_imaging", "the image library"),
        ("vcruntime", "the Visual C++ runtime"),
        ("msvcp", "the Visual C++ runtime"),
    ]
    for needle, what in wanted:
        hits = sorted(d for d in bundled if needle in d)
        if hits:
            for hit in hits[:3]:
                print(f"    {hit:<44} {what}")
        else:
            print(f"    {'(none)':<44} {what}  <- MISSING")

    print()
    print("  system DLLs the loader asks for")
    missing = []
    for dll in sorted(set(imports)):
        low = dll.lower()
        if low in bundled:
            where = "bundled"
        elif low in WINDOWS_BUILTIN:
            where = "Windows"
        elif os.path.exists(os.path.join(system, dll)):
            where = "Windows (installed)"
        else:
            where = "*** MISSING ***"
            missing.append(dll)
        print(f"    {dll:<44} {where}")

    print()
    vc_bundled = [d for d in bundled
                  if os.path.basename(d) in VC_RUNTIME]
    vc_needed = [d for d in sorted(set(imports))
                 if d.lower() in VC_RUNTIME and d.lower() not in bundled]
    if vc_needed:
        print("  FAIL: the Visual C++ runtime is not bundled.")
        print("        Windows 11 does NOT ship it - it only appears if the")
        print("        VC++ redistributable happens to be installed.")
        print("        On a clean PC the app would refuse to start with")
        print("        'VCRUNTIME140.dll was not found'.")
        print(f"        Missing: {', '.join(vc_needed)}")
        return 1
    if not vc_bundled:
        print("  FAIL: no Visual C++ runtime in the bundle at all - the")
        print("        interpreter cannot start on a machine without the")
        print("        VC++ redistributable.")
        return 1
    print(f"  OK: the Visual C++ runtime travels with the app "
          f"({len(vc_bundled)} file(s)).")
    if missing:
        print(f"  FAIL: {len(missing)} system import(s) could not be located.")
        return 1
    print("  OK: every import is either bundled or part of Windows.")
    return 0


def main() -> int:
    exe = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "dist", "PDF Sign and Fill.exe")
    if not os.path.exists(exe):
        print(f"not found: {exe}")
        return 2
    return report(exe)


if __name__ == "__main__":
    sys.exit(main())
