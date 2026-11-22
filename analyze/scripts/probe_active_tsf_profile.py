"""Read-only: ask TSF which keyboard TIP profile is active for this (new) thread, and list
all registered zh-TW profiles with enable state. No activation/changes are made."""
import ctypes as C, json, sys
from ctypes import wintypes as W
class GUID(C.Structure):
    _fields_=[('a',C.c_uint32),('b',C.c_uint16),('c',C.c_uint16),('d',C.c_ubyte*8)]
    def __str__(s):return '{%08X-%04X-%04X-%02X%02X-%s}'%(s.a,s.b,s.c,s.d[0],s.d[1],''.join('%02X'%x for x in s.d[2:]))
def guid(t):
    g=GUID();o=C.WinDLL('ole32');o.CLSIDFromString(C.c_wchar_p(t),C.byref(g));return g
class PROFILE(C.Structure):
    _fields_=[('type',W.DWORD),('lang',W.WORD),('clsid',GUID),('profile',GUID),('catid',GUID),
              ('hklSub',C.c_void_p),('caps',W.DWORD),('hkl',C.c_void_p),('flags',W.DWORD)]
ole=C.WinDLL('ole32');ole.CoInitializeEx(None,2)
CLSID=guid('{33C53A50-F456-4884-B049-85FD643ECFED}');IID=guid('{71C6E74C-0F28-11D8-A82A-00065B84435C}')
pp=C.c_void_p()
hr=ole.CoCreateInstance(C.byref(CLSID),None,1,C.byref(IID),C.byref(pp))
if hr:raise SystemExit(f'CoCreateInstance failed 0x{hr&0xffffffff:08x}')
vt=C.cast(C.cast(pp,C.POINTER(C.c_void_p))[0],C.POINTER(C.c_void_p))
call=lambda i,proto:C.WINFUNCTYPE(*proto)(vt[i])
cat=guid('{34745C63-B2F0-4784-8B67-5E12C8701A31}')
prof=PROFILE()
GetActive=call(10,(C.c_long,C.c_void_p,C.POINTER(GUID),C.POINTER(PROFILE)))
hr=GetActive(pp,C.byref(cat),C.byref(prof))
rep=dict(get_active_hr=hex(hr&0xffffffff))
if hr==0:
    rep.update(type=prof.type,langid=hex(prof.lang),clsid=str(prof.clsid),profile=str(prof.profile),hkl=hex(prof.hkl or 0),flags=hex(prof.flags))
rep['note']='Reflects TSF active profile for a fresh thread of this process, not necessarily Notepad. Read-only.'
print(json.dumps(rep,indent=1))
from pathlib import Path
Path(__file__).resolve().parents[1].joinpath('selection','active-tsf-profile.json').write_text(json.dumps(rep,indent=1),encoding='utf-8')
