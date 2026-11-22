"""Drive the Microsoft Bopomofo conversion engine through its public IFELanguage COM interface.

IMTCCORE.DLL exports DllGetClassObject with CLSID_IFEClassFactory_CHT {F407D01A-0BCB-4591-9BD6-EA4A71DF0799}
(found in the reference binary, see analyze/selection/input-state-machine.md notes).  The DLL is loaded from the
installed system directory (byte-identical to the reference copy, SHA in analyze/p0/manifest.json).
Read-only use: conversion only; no learning calls are made.  Windows x64 Python required.
"""
import ctypes as C
import hashlib
import json
import os
import sys
from ctypes import wintypes as W
from pathlib import Path

DLL = Path(r'C:\Windows\System32\IME\IMETC\IMTCCORE.DLL')
EXPECTED = 'E40011102FFBCE5E41DECB3D533DA5AAF78617FACA012200A65E2068E691971E'


class GUID(C.Structure):
    _fields_ = [('a', C.c_uint32), ('b', C.c_uint16), ('c', C.c_uint16), ('d', C.c_ubyte * 8)]


ole = C.WinDLL('ole32')


def guid(text):
    g = GUID()
    ole.CLSIDFromString(C.c_wchar_p(text), C.byref(g))
    return g


def vcall(obj, index, restype, *argtypes):
    vt = C.cast(C.cast(obj, C.POINTER(C.c_void_p))[0], C.POINTER(C.c_void_p))
    return C.WINFUNCTYPE(restype, C.c_void_p, *argtypes)(vt[index])


def main():
    if hashlib.sha256(DLL.read_bytes()).hexdigest().upper() != EXPECTED:
        raise SystemExit('IMTCCORE.DLL differs from the pinned reference')
    ole.CoInitializeEx(None, 2)
    k = C.WinDLL('kernel32', use_last_error=True)
    k.LoadLibraryW.restype = C.c_void_p
    k.GetProcAddress.restype = C.c_void_p
    k.GetProcAddress.argtypes = (C.c_void_p, C.c_char_p)
    h = k.LoadLibraryW(str(DLL))
    if not h:
        raise C.WinError(C.get_last_error())
    getcls = C.WINFUNCTYPE(C.c_long, C.POINTER(GUID), C.POINTER(GUID), C.POINTER(C.c_void_p))(
        k.GetProcAddress(h, b'DllGetClassObject'))
    factory = C.c_void_p()
    clsid = guid('{F407D01A-0BCB-4591-9BD6-EA4A71DF0799}')
    iid_cf = guid('{00000001-0000-0000-C000-000000000046}')
    hr = getcls(C.byref(clsid), C.byref(iid_cf), C.byref(factory))
    print('DllGetClassObject hr=0x%08x' % (hr & 0xffffffff))
    if hr:
        return 1
    ife = C.c_void_p()
    iid_ife = guid('{019F7152-E6DB-11D0-83C3-00C04FDDB82E}')
    hr = vcall(factory, 3, C.c_long, C.c_void_p, C.POINTER(GUID), C.POINTER(C.c_void_p))(
        factory, None, C.byref(iid_ife), C.byref(ife))
    print('CreateInstance(IFELanguage) hr=0x%08x' % (hr & 0xffffffff))
    if hr:
        return 1
    hr = vcall(ife, 3, C.c_long)(ife)
    print('Open hr=0x%08x' % (hr & 0xffffffff))
    caps = C.c_uint32()
    hr2 = vcall(ife, 6, C.c_long, C.POINTER(C.c_uint32))(ife, C.byref(caps))
    print('GetConversionModeCaps hr=0x%08x caps=0x%08x' % (hr2 & 0xffffffff, caps.value))
    out = {}
    for text, mode in ((sys.argv[1] if len(sys.argv) > 1 else 'ㄋㄧˇㄏㄠˇ', 0x40),):
        buf = C.create_unicode_buffer(text)
        info = C.c_uint32()
        res = C.c_void_p()
        hr = vcall(ife, 5, C.c_long, C.c_uint32, C.c_uint32, C.c_int, C.c_wchar_p, C.POINTER(C.c_uint32), C.POINTER(C.c_void_p))(
            ife, 0x00010000, mode, len(text), buf, C.byref(info), C.byref(res))
        print('GetJMorphResult hr=0x%08x info=0x%x result=%s' % (hr & 0xffffffff, info.value, hex(res.value or 0)))
        if res.value:
            raw = C.string_at(res.value, 128)
            print(raw.hex())
            size, = C.c_uint32.from_address(res.value),
            pw = C.c_void_p.from_address(res.value + 8).value
            cch = C.c_uint16.from_address(res.value + 16).value
            print('size', size.value, 'cchOutput', cch, 'output', C.wstring_at(pw, cch) if pw else None)
    vcall(ife, 4, C.c_long)(ife)
    return 0


if __name__ == '__main__':
    sys.exit(main())
