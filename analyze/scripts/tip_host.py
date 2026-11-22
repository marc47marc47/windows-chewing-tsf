"""Host the Microsoft Bopomofo TIP (IMTCTIP.DLL, legacy IMETC) inside this process and feed it keys.

Method: create a TSF thread manager (msctf!TF_CreateThreadMgr), a Win32 EDIT window (CUAS gives it a
document manager), instantiate the TIP by its CLSID {B115690A-EA02-48D5-A231-E3578D2FDF80}, call
ITfTextInputProcessor::Activate manually, then inject keys with ITfKeystrokeMgr::KeyDown and read the
composition text from the EDIT control.  Nothing outside this process is changed; the TIP's user data
is only read.  Windows x64 Python required.
"""
import ctypes as C
import json
import sys
import time
from ctypes import wintypes as W

TIP_CLSID = '{B115690A-EA02-48D5-A231-E3578D2FDF80}'
IID_TIP = '{AA80E7F7-2021-11D2-93E0-0060B067B86E}'      # ITfTextInputProcessor
IID_KSM = '{AA80E7F0-2021-11D2-93E0-0060B067B86E}'      # ITfKeystrokeMgr
IID_TM = '{AA80E801-2021-11D2-93E0-0060B067B86E}'       # ITfThreadMgr


class GUID(C.Structure):
    _fields_ = [('a', C.c_uint32), ('b', C.c_uint16), ('c', C.c_uint16), ('d', C.c_ubyte * 8)]


ole = C.WinDLL('ole32')
u = C.WinDLL('user32', use_last_error=True)
u.CreateWindowExW.restype = W.HWND
u.CreateWindowExW.argtypes = (W.DWORD, W.LPCWSTR, W.LPCWSTR, W.DWORD, C.c_int, C.c_int, C.c_int, C.c_int,
                              W.HWND, W.HMENU, W.HINSTANCE, W.LPVOID)


def guid(t):
    g = GUID()
    ole.CLSIDFromString(C.c_wchar_p(t), C.byref(g))
    return g


def vcall(obj, index, *argtypes):
    vt = C.cast(C.cast(obj, C.POINTER(C.c_void_p))[0], C.POINTER(C.c_void_p))
    return C.WINFUNCTYPE(C.c_long, C.c_void_p, *argtypes)(vt[index])


def pump(sec):
    msg = W.MSG()
    end = time.time() + sec
    while time.time() < end:
        while u.PeekMessageW(C.byref(msg), None, 0, 0, 1):
            u.TranslateMessage(C.byref(msg))
            u.DispatchMessageW(C.byref(msg))
        time.sleep(0.02)


def text_of(hwnd):
    n = u.GetWindowTextLengthW(hwnd)
    b = C.create_unicode_buffer(n + 1)
    u.GetWindowTextW(hwnd, b, n + 1)
    return b.value


def main():
    log = {}
    ole.CoInitializeEx(None, 2)
    tm = C.c_void_p()
    msctf = C.WinDLL('msctf')
    log['TF_CreateThreadMgr'] = hex(msctf.TF_CreateThreadMgr(C.byref(tm)) & 0xffffffff)
    cid = C.c_uint32()
    log['ThreadMgr.Activate'] = hex(vcall(tm, 3, C.POINTER(C.c_uint32))(tm, C.byref(cid)) & 0xffffffff)
    hwnd = u.CreateWindowExW(0, 'EDIT', '', 0x10CF0000 | 0x0004, 100, 100, 600, 200, None, None, None, None)
    u.ShowWindow(hwnd, 5)
    u.SetForegroundWindow(hwnd)
    u.SetFocus(hwnd)
    u.PostMessageW(hwnd, 0x0050, 0, 0x04040404)    # WM_INPUTLANGCHANGEREQUEST -> zh-TW layout, this window only
    pump(1.0)
    tip = C.c_void_p()
    hr = ole.CoCreateInstance(C.byref(guid(TIP_CLSID)), None, 1, C.byref(guid(IID_TIP)), C.byref(tip))
    log['CoCreateInstance(TIP)'] = hex(hr & 0xffffffff)
    if hr == 0:
        log['TIP.Activate'] = hex(vcall(tip, 3, C.c_void_p, C.c_uint32)(tip, tm, cid.value) & 0xffffffff)
    pump(1.0)
    ksm = C.c_void_p()
    log['QI KeystrokeMgr'] = hex(vcall(tm, 0, C.POINTER(GUID), C.POINTER(C.c_void_p))(tm, C.byref(guid(IID_KSM)), C.byref(ksm)) & 0xffffffff)
    # TSF only dispatches keys when a document manager has focus: create one and focus it
    mydm = C.c_void_p()
    log['CreateDocumentMgr'] = hex(vcall(tm, 5, C.POINTER(C.c_void_p))(tm, C.byref(mydm)) & 0xffffffff)
    log['ThreadMgr.SetFocus'] = hex(vcall(tm, 8, C.c_void_p)(tm, mydm) & 0xffffffff)
    pump(0.5)
    dm = C.c_void_p()
    log['ThreadMgr.GetFocus'] = hex(vcall(tm, 7, C.POINTER(C.c_void_p))(tm, C.byref(dm)) & 0xffffffff)
    log['focus_docmgr'] = hex(dm.value or 0)
    import re
    k32 = C.WinDLL('kernel32'); ps = C.WinDLL('psapi')
    k32.GetCurrentProcess.restype = W.HANDLE
    ps.EnumProcessModulesEx.argtypes = (W.HANDLE, C.POINTER(W.HMODULE), W.DWORD, C.POINTER(W.DWORD), W.DWORD)
    ps.GetModuleFileNameExW.argtypes = (W.HANDLE, W.HMODULE, W.LPWSTR, W.DWORD)
    a = (W.HMODULE * 4096)(); n = W.DWORD()
    ps.EnumProcessModulesEx(k32.GetCurrentProcess(), a, C.sizeof(a), C.byref(n), 3)
    mods = []
    for m in a[:n.value // 8]:
        b = C.create_unicode_buffer(1024); ps.GetModuleFileNameExW(k32.GetCurrentProcess(), m, b, 1024); mods.append(b.value)
    log['imetc_modules'] = [m for m in mods if re.search(r'imtc|imetc', m, re.I)]
    keys = sys.argv[1:] or ['S', 'U', '3', 'C', 'L', '3']
    eaten_log = []
    for k in keys:
        vk = ord(k.upper()) if len(k) == 1 else int(k, 0)
        scan = u.MapVirtualKeyW(vk, 0)
        lparam = 1 | (scan << 16)
        eaten = C.c_int()
        hr = vcall(ksm, 6, C.c_uint, C.c_ssize_t, C.POINTER(C.c_int))(ksm, vk, lparam, C.byref(eaten))   # KeyDown
        hr_up = vcall(ksm, 7, C.c_uint, C.c_ssize_t, C.POINTER(C.c_int))(ksm, vk, lparam | (1 << 30) | (1 << 31), C.byref(eaten))  # KeyUp
        eaten_log.append((k, hex(hr & 0xffffffff), eaten.value))
        pump(0.3)
    log['keys'] = eaten_log
    pump(1.0)
    log['edit_text'] = text_of(hwnd)
    print(json.dumps(log, ensure_ascii=False, indent=1))
    if hr == 0 and tip:
        vcall(tip, 4)(tip)
    return 0


if __name__ == '__main__':
    sys.exit(main())
