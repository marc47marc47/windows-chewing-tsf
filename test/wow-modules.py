"""Read-only: list input-method related modules loaded in a running Wow.exe (no input is sent)."""
import ctypes, ctypes.wintypes as w
k = ctypes.WinDLL('kernel32', use_last_error=True); p = ctypes.WinDLL('psapi', use_last_error=True)
k.OpenProcess.restype = w.HANDLE
p.EnumProcessModulesEx.argtypes = [w.HANDLE, ctypes.POINTER(w.HMODULE), w.DWORD, ctypes.POINTER(w.DWORD), w.DWORD]
p.GetModuleFileNameExW.argtypes = [w.HANDLE, w.HMODULE, w.LPWSTR, w.DWORD]


class PE(ctypes.Structure):
    _fields_ = [("dwSize", w.DWORD), ("cntUsage", w.DWORD), ("pid", w.DWORD), ("heap", ctypes.c_void_p), ("mod", w.DWORD),
                ("thr", w.DWORD), ("ppid", w.DWORD), ("pri", ctypes.c_long), ("flags", w.DWORD), ("exe", ctypes.c_wchar * 260)]


k.CreateToolhelp32Snapshot.restype = w.HANDLE
s = k.CreateToolhelp32Snapshot(2, 0); e = PE(); e.dwSize = ctypes.sizeof(e); pid = None
ok = k.Process32FirstW(w.HANDLE(s), ctypes.byref(e))
while ok:
    if e.exe.lower() == "wow.exe": pid = e.pid
    ok = k.Process32NextW(w.HANDLE(s), ctypes.byref(e))
h = k.OpenProcess(0x0410, False, pid)
arr = (w.HMODULE * 2048)(); need = w.DWORD()
p.EnumProcessModulesEx(h, arr, ctypes.sizeof(arr), ctypes.byref(need), 3)
n = need.value // ctypes.sizeof(w.HMODULE); buf = ctypes.create_unicode_buffer(520); names = []
for i in range(n):
    p.GetModuleFileNameExW(h, arr[i], buf, 520); names.append(buf.value)
print("Wow pid", pid, "modules", n)
for m in names:
    if any(x in m.lower() for x in ("ime", "ctf", "tip", "input", "imt", "chewing", "zhuyin", "bopomofo", "tsf", "msctfui")):
        print("  ", m)
print("chewing loaded:", any("chewing" in m.lower() for m in names))
