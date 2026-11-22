"""Read foreground window/thread keyboard layout; never inject input or attach threads."""
import ctypes
import json
from ctypes import wintypes
from pathlib import Path

user=ctypes.WinDLL('user32',use_last_error=True)
user.GetForegroundWindow.restype=wintypes.HWND
user.GetWindowThreadProcessId.argtypes=[wintypes.HWND,ctypes.POINTER(wintypes.DWORD)]
user.GetWindowThreadProcessId.restype=wintypes.DWORD
user.GetKeyboardLayout.argtypes=[wintypes.DWORD]
user.GetKeyboardLayout.restype=ctypes.c_void_p
user.GetWindowTextW.argtypes=[wintypes.HWND,wintypes.LPWSTR,ctypes.c_int]
pid=wintypes.DWORD()
window=user.GetForegroundWindow()
thread=user.GetWindowThreadProcessId(window,ctypes.byref(pid))
layout=user.GetKeyboardLayout(thread)
title=ctypes.create_unicode_buffer(2048)
user.GetWindowTextW(window,title,len(title))
report=dict(hwnd=hex(window or 0),pid=pid.value,thread=thread,hkl=hex(layout or 0),
            language_id=hex((layout or 0)&0xffff),title=title.value,
            warning='HKL alone does not identify the active TSF profile or compatibility mode.')
print(json.dumps(report,ensure_ascii=False,indent=2))
