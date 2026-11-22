import ctypes as C, sys
sys.path.insert(0,'.')
import ife_probe as P
from ife_probe import *

def open_ife():
    ole.CoInitializeEx(None, 2)
    k = C.WinDLL('kernel32', use_last_error=True)
    k.LoadLibraryW.restype = C.c_void_p
    k.GetProcAddress.restype = C.c_void_p
    k.GetProcAddress.argtypes = (C.c_void_p, C.c_char_p)
    h = k.LoadLibraryW(str(DLL))
    getcls = C.WINFUNCTYPE(C.c_long, C.POINTER(GUID), C.POINTER(GUID), C.POINTER(C.c_void_p))(k.GetProcAddress(h, b'DllGetClassObject'))
    f = C.c_void_p()
    getcls(C.byref(guid('{F407D01A-0BCB-4591-9BD6-EA4A71DF0799}')), C.byref(guid('{00000001-0000-0000-C000-000000000046}')), C.byref(f))
    ife = C.c_void_p()
    vcall(f, 3, C.c_long, C.c_void_p, C.POINTER(GUID), C.POINTER(C.c_void_p))(f, None, C.byref(guid('{019F7152-E6DB-11D0-83C3-00C04FDDB82E}')), C.byref(ife))
    vcall(ife, 3, C.c_long)(ife)
    return ife

oa = C.WinDLL('oleaut32')
oa.SysAllocString.restype = C.c_void_p
oa.SysAllocString.argtypes = (C.c_wchar_p,)
oa.SysStringLen.argtypes = (C.c_void_p,)
def bstr(t): return oa.SysAllocString(t)
def read(b): return C.wstring_at(b, oa.SysStringLen(b)) if b else None

ife = open_ife()
text = sys.argv[1] if len(sys.argv) > 1 else 'ㄋㄧˇㄏㄠˇ'
for name, idx in (('GetConversion', 8), ('GetPhonetic', 7)):
    inp = bstr(text)
    out = C.c_void_p()
    hr = vcall(ife, idx, C.c_long, C.c_void_p, C.c_long, C.c_long, C.POINTER(C.c_void_p))(ife, inp, 0, len(text), C.byref(out))
    print(name, 'hr=0x%08x' % (hr & 0xffffffff), repr(read(out.value)))
