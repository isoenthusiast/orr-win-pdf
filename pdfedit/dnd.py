"""Drop a PDF from Explorer straight onto the app window.

Windows delivers Explorer drops through the OLE IDropTarget interface, which
Tk does not implement.  Rather than take on a dependency for it, this module
talks to ole32 directly through ctypes - the app keeps its promise of being
one file with nothing to install.

How it works
------------
The COM callbacks are invoked on the app's own thread, but inside a nested
message loop that Tk does not know about.  So they never touch Tk: they put
the file names on a queue and the Tk side collects them on its next tick.

The drop target is registered on the window's client HWND.  Explorer finds
the deepest registered target under the cursor, so the drop lands on the
page area of the app.
"""
from __future__ import annotations

import ctypes
import os
import threading
from ctypes import wintypes

# --------------------------------------------------------------- constants
CF_HDROP = 15
DVASPECT_CONTENT = 1
TYMED_HGLOBAL = 1
DROPEFFECT_COPY = 1
DRAGDROP_S_DROP = 1
DRAGDROP_S_CANCEL = 2
COINIT_APARTMENTTHREADED = 0x2
REGDB_E_CLASSNOTREG = 0x80040154

S_OK = 0
E_NOTIMPL = 0x80004001
E_NOINTERFACE = 0x80004002

# IID_IDropTarget {00000122-0000-0000-C000-000000000046}
IID_IDROP_TARGET = bytes([
    0x22, 0x01, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
    0xC0, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x46,
])
# IID_IUnknown {00000000-0000-0000-C000-000000000046}
IID_IUNKNOWN = bytes([
    0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
    0xC0, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x46,
])

HRESULT = ctypes.c_long
ULONG = ctypes.c_ulong
LPV = ctypes.c_void_p

kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
shell32 = ctypes.WinDLL("shell32", use_last_error=True)
ole32 = ctypes.OleDLL("ole32")

kernel32.GlobalFree.argtypes = [wintypes.HGLOBAL]
kernel32.GlobalFree.restype = wintypes.HGLOBAL
shell32.DragQueryFileW.argtypes = [wintypes.HANDLE, wintypes.UINT,
                                    wintypes.LPWSTR, wintypes.UINT]
shell32.DragQueryFileW.restype = wintypes.UINT


# ------------------------------------------------------------- COM plumbing
class _FORMATETC(ctypes.Structure):
    _fields_ = [
        ("cfFormat", wintypes.WORD),
        ("dwAspect", wintypes.DWORD),
        ("lindex", ctypes.c_long),
        ("tymed", wintypes.DWORD),
        ("pUnkForRelease", LPV),
    ]


QueryInterface_t = ctypes.WINFUNCTYPE(HRESULT, LPV, ctypes.c_void_p,
                                       ctypes.POINTER(LPV))
AddRef_t = ctypes.WINFUNCTYPE(ULONG, LPV)
Release_t = ctypes.WINFUNCTYPE(ULONG, LPV)
DragEnter_t = ctypes.WINFUNCTYPE(HRESULT, LPV, LPV, wintypes.DWORD,
                                  ctypes.POINTER(wintypes.DWORD))
DragOver_t = ctypes.WINFUNCTYPE(HRESULT, LPV, wintypes.DWORD,
                                ctypes.POINTER(wintypes.DWORD))
DragLeave_t = ctypes.WINFUNCTYPE(HRESULT, LPV)
Drop_t = ctypes.WINFUNCTYPE(HRESULT, LPV, LPV, wintypes.DWORD,
                            ctypes.POINTER(wintypes.DWORD))
GetData_t = ctypes.WINFUNCTYPE(HRESULT, LPV, ctypes.POINTER(_FORMATETC),
                               ctypes.POINTER(LPV))


class _IDropTargetVtbl(ctypes.Structure):
    _fields_ = [
        ("QueryInterface", QueryInterface_t),
        ("AddRef", AddRef_t),
        ("Release", Release_t),
        ("DragEnter", DragEnter_t),
        ("DragOver", DragOver_t),
        ("DragLeave", DragLeave_t),
        ("Drop", Drop_t),
    ]


class _IDataObjectVtbl(ctypes.Structure):
    """Only the first few slots are needed; GetData is the fourth."""
    _fields_ = [
        ("QueryInterface", QueryInterface_t),
        ("AddRef", AddRef_t),
        ("Release", Release_t),
        ("GetData", GetData_t),
        ("GetDataHere", GetData_t),
        ("QueryGetData", GetData_t),
        ("GetCanonicalFormatEtc", GetData_t),
        ("SetData", GetData_t),
        ("EnumFormatEtc", GetData_t),
        ("DAdvise", GetData_t),
        ("DUnadvise", GetData_t),
        ("EnumDAdvise", GetData_t),
    ]


class _Target(ctypes.Structure):
    _fields_ = [("lpVtbl", ctypes.POINTER(_IDropTargetVtbl))]


# ----------------------------------------------------------------- helpers
def files_from_hdrop(hglobal: int) -> list[str]:
    """The file names inside a CF_HDROP handle.

    Kept separate from the COM plumbing so it can be tested without a
    drag operation.
    """
    count = shell32.DragQueryFileW(hglobal, 0xFFFFFFFF, None, 0)
    if not count:
        return []
    paths: list[str] = []
    for index in range(count):
        length = shell32.DragQueryFileW(hglobal, index, None, 0)
        if not length:
            continue
        buffer = ctypes.create_unicode_buffer(length + 1)
        if shell32.DragQueryFileW(hglobal, index, buffer, length + 1):
            paths.append(buffer.value)
    return paths


def _extract_files(data_object: int) -> list[str]:
    """Ask an IDataObject for its CF_HDROP and read the file names."""
    fmt = _FORMATETC()
    fmt.cfFormat = CF_HDROP
    fmt.dwAspect = DVASPECT_CONTENT
    fmt.lindex = -1
    fmt.tymed = TYMED_HGLOBAL
    fmt.pUnkForRelease = None

    hglobal = LPV()
    vtbl = ctypes.cast(data_object,
                       ctypes.POINTER(ctypes.POINTER(_IDataObjectVtbl))).contents
    get_data = vtbl.contents.GetData
    try:
        result = get_data(data_object, ctypes.byref(fmt),
                          ctypes.byref(hglobal))
    except Exception:
        return []
    if result != S_OK or not hglobal:
        return []
    try:
        return files_from_hdrop(int(hglobal.value or 0))
    finally:
        try:
            kernel32.GlobalFree(hglobal)
        except Exception:
            pass


# ------------------------------------------------------------------ target
class DropTarget:
    """An OLE drop target registered on a window.

    Files dropped on the window are collected in :attr:`pending`; the owner
    drains that list from the Tk side.
    """

    def __init__(self, hwnd: int):
        self.hwnd = hwnd
        self.pending: list[str] = []
        self.hovering = False
        self._lock = threading.Lock()
        self._registered = False
        self._com_initialised = False
        self._object = _Target()
        self._vtbl = _IDropTargetVtbl()

        # The callbacks have to stay alive for as long as the vtable does.
        self._c_query = QueryInterface_t(self._query_interface)
        self._c_addref = AddRef_t(self._add_ref)
        self._c_release = Release_t(self._release)
        self._c_enter = DragEnter_t(self._drag_enter)
        self._c_over = DragOver_t(self._drag_over)
        self._c_leave = DragLeave_t(self._drag_leave)
        self._c_drop = Drop_t(self._drop)

        self._vtbl.QueryInterface = self._c_query
        self._vtbl.AddRef = self._c_addref
        self._vtbl.Release = self._c_release
        self._vtbl.DragEnter = self._c_enter
        self._vtbl.DragOver = self._c_over
        self._vtbl.DragLeave = self._c_leave
        self._vtbl.Drop = self._c_drop

        self._object.lpVtbl = ctypes.pointer(self._vtbl)

    # -- COM boilerplate ---------------------------------------------
    def _query_interface(self, this, iid, out):
        """Hand out this object for IDropTarget (and IUnknown).

        RegisterDragDrop calls this first, so it has to work - a failure
        here is reported as a puzzling "not enough memory".
        """
        try:
            wanted = ctypes.string_at(iid, 16)
        except Exception:
            wanted = b""
        if wanted not in (IID_IDROP_TARGET, IID_IUNKNOWN):
            out[0] = None
            return E_NOINTERFACE
        out[0] = this
        return S_OK

    def _add_ref(self, _this):
        return 1

    def _release(self, _this):
        return 1

    # -- the interesting ones ----------------------------------------
    def _drag_enter(self, _this, _data_object, _key_state, effect):
        if effect:
            effect[0] = DROPEFFECT_COPY
        self.hovering = True
        return S_OK

    def _drag_over(self, _this, _key_state, effect):
        if effect:
            effect[0] = DROPEFFECT_COPY
        return S_OK

    def _drag_leave(self, _this):
        self.hovering = False
        return S_OK

    def _drop(self, _this, data_object, _key_state, effect):
        self.hovering = False
        if effect:
            effect[0] = DROPEFFECT_COPY
        try:
            paths = _extract_files(int(data_object or 0))
        except Exception:
            paths = []
        if paths:
            with self._lock:
                self.pending.extend(paths)
        return S_OK

    # -- public ------------------------------------------------------
    def register(self) -> bool:
        """Start accepting drops on the window."""
        if os.name != "nt":
            return False
        try:
            # OLE drag and drop needs OleInitialize, not just CoInitializeEx:
            # it also installs the OLE message filter that the drop
            # machinery talks through.  Without it RegisterDragDrop fails
            # with a misleading "not enough memory".
            result = ole32.OleInitialize(None)
            if result in (0, 1):           # S_OK, S_FALSE
                self._com_initialised = True
            elif result == REGDB_E_CLASSNOTREG:
                # The message filter could not be created, but the drop
                # target itself may still work.
                pass
            ole32.RegisterDragDrop(wintypes.HWND(self.hwnd),
                                   ctypes.cast(ctypes.byref(self._object), LPV),
                                   0)
            self._registered = True
            return True
        except Exception:
            return False

    def unregister(self) -> None:
        """Stop accepting drops."""
        if not self._registered:
            return
        self._registered = False
        try:
            ole32.RevokeDragDrop(wintypes.HWND(self.hwnd))
        except Exception:
            pass
        if self._com_initialised:
            self._com_initialised = False
            try:
                ole32.OleUninitialize()
            except Exception:
                pass

    def take(self) -> list[str]:
        """The files dropped since the last call."""
        with self._lock:
            files = self.pending
            self.pending = []
        return files


def install(widget) -> DropTarget | None:
    """Register a drop target on a Tk window.

    Returns None when the platform cannot do it, so the caller can simply
    carry on without the feature.
    """
    if os.name != "nt":
        return None
    try:
        hwnd = int(widget.winfo_id())
        target = DropTarget(hwnd)
        if not target.register():
            return None
        return target
    except Exception:
        return None
