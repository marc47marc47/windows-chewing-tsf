"""P0.3 evidence: in THIS process only, create a classic Win32 EDIT window, create a TSF thread
manager (msctf!TF_CreateThreadMgr), activate the Microsoft Bopomofo profile for this thread
(no FORPROCESS/FORSESSION, so other apps and the user's session setting are untouched), then
record every DLL newly loaded into the process (path, SHA-256). No keys sent, no user data touched.
Windows Python required."""
import ctypes as C, hashlib, json, sys, time
from ctypes import wintypes as W
from pathlib import Path
class GUID(C.Structure):
    _fields_=[('a',C.c_uint32),('b',C.c_uint16),('c',C.c_uint16),('d',C.c_ubyte*8)]
ole=C.WinDLL('ole32');u=C.WinDLL('user32',use_last_error=True);k=C.WinDLL('kernel32');ps=C.WinDLL('psapi')
def guid(t):
    g=GUID();ole.CLSIDFromString(C.c_wchar_p(t),C.byref(g));return g
u.CreateWindowExW.restype=W.HWND
u.CreateWindowExW.argtypes=(W.DWORD,W.LPCWSTR,W.LPCWSTR,W.DWORD,C.c_int,C.c_int,C.c_int,C.c_int,W.HWND,W.HMENU,W.HINSTANCE,W.LPVOID)
u.GetKeyboardLayout.restype=C.c_void_p
k.GetCurrentProcess.restype=W.HANDLE
ps.EnumProcessModulesEx.argtypes=(W.HANDLE,C.POINTER(W.HMODULE),W.DWORD,C.POINTER(W.DWORD),W.DWORD)
ps.GetModuleFileNameExW.argtypes=(W.HANDLE,W.HMODULE,W.LPWSTR,W.DWORD)
def mods():
    h=k.GetCurrentProcess();a=(W.HMODULE*4096)();n=W.DWORD()
    ps.EnumProcessModulesEx(h,a,C.sizeof(a),C.byref(n),3);out=set()
    for m in a[:n.value//C.sizeof(W.HMODULE)]:
        b=C.create_unicode_buffer(1024);ps.GetModuleFileNameExW(h,m,b,1024);out.add(b.value)
    return out
def method(p,i,*at):
    vt=C.cast(C.cast(p,C.POINTER(C.c_void_p))[0],C.POINTER(C.c_void_p))
    return C.WINFUNCTYPE(C.c_long,C.c_void_p,*at)(vt[i])
def pump(sec):
    msg=W.MSG();end=time.time()+sec
    while time.time()<end:
        while u.PeekMessageW(C.byref(msg),None,0,0,1):
            u.TranslateMessage(C.byref(msg));u.DispatchMessageW(C.byref(msg))
        time.sleep(0.05)
ole.CoInitializeEx(None,2)
base=mods()
hwnd=u.CreateWindowExW(0,'EDIT','',0x10CF0000|0x0004,100,100,500,200,None,None,None,None)
u.ShowWindow(hwnd,5);u.SetForegroundWindow(hwnd);u.SetFocus(hwnd);pump(1)
rep=dict(hwnd=hex(hwnd or 0))
tm=C.c_void_p();msctf=C.WinDLL('msctf')
rep['TF_CreateThreadMgr_hr']=hex(msctf.TF_CreateThreadMgr(C.byref(tm))&0xffffffff)
if tm:
    cid=C.c_uint32();rep['ThreadMgr_Activate_hr']=hex(method(tm,3,C.POINTER(C.c_uint32))(tm,C.byref(cid))&0xffffffff)
pm=C.c_void_p()
hr=ole.CoCreateInstance(C.byref(guid('{33C53A50-F456-4884-B049-85FD643ECFED}')),None,1,C.byref(guid('{71C6E74C-0F28-11D8-A82A-00065B84435C}')),C.byref(pm))
rep['ProfileMgr_hr']=hex(hr&0xffffffff)
TARGETS={'msbopomofo':('{B115690A-EA02-48D5-A231-E3578D2FDF80}','{B2F9C502-1742-11D4-9790-0080C882687E}'),
         'chewing':('{13F2EF08-575C-4D8C-88E0-F67BB8052B84}','{CE45F71D-CE79-41D1-967D-640B65A380E3}')}
which=sys.argv[1] if len(sys.argv)>1 else 'msbopomofo'
rep['target']=which
CL=guid(TARGETS[which][0]);PF=guid(TARGETS[which][1])
if not hr:
    rep['ActivateProfile_hr']=hex(method(pm,3,W.DWORD,W.WORD,C.POINTER(GUID),C.POINTER(GUID),C.c_void_p,W.DWORD)(pm,1,0x0404,C.byref(CL),C.byref(PF),None,0x1)&0xffffffff)
dm=C.c_void_p()
if tm:
    rep['CreateDocumentMgr_hr']=hex(method(tm,5,C.POINTER(C.c_void_p))(tm,C.byref(dm))&0xffffffff)
    if dm:rep['ThreadMgr_SetFocus_hr']=hex(method(tm,8,C.c_void_p)(tm,dm)&0xffffffff)
pump(10);u.SetFocus(hwnd);pump(4)
class PROFILE(C.Structure):
    _fields_=[('type',W.DWORD),('lang',W.WORD),('clsid',GUID),('profile',GUID),('catid',GUID),('hklSub',C.c_void_p),('caps',W.DWORD),('hkl',C.c_void_p),('flags',W.DWORD)]
def gs(g):return '{%08X-%04X-%04X-%02X%02X-%s}'%(g.a,g.b,g.c,g.d[0],g.d[1],''.join('%02X'%x for x in g.d[2:]))
if not hr:
    pr=PROFILE();cat=guid('{34745C63-B2F0-4784-8B67-5E12C8701A31}')
    h2=method(pm,10,C.POINTER(GUID),C.POINTER(PROFILE))(pm,C.byref(cat),C.byref(pr))
    rep['GetActiveProfile_after']=dict(hr=hex(h2&0xffffffff),clsid=gs(pr.clsid),profile=gs(pr.profile),flags=hex(pr.flags),hkl=hex(pr.hkl or 0))
now=mods();new=sorted(now-base)
rep['thread_hkl']=hex(u.GetKeyboardLayout(0) or 0)
rep['new_modules']=new
rep['new_module_sha256']={m:hashlib.sha256(Path(m).read_bytes()).hexdigest().upper() for m in new if Path(m).exists()}
rep['imetc_or_chewing_loaded']=[m for m in new if any(x in m.lower() for x in ('imtc','imetc','chtime','chewing'))]
try:
    if not hr:method(pm,4,W.DWORD,W.WORD,C.POINTER(GUID),C.POINTER(GUID),C.c_void_p,W.DWORD)(pm,1,0x0404,C.byref(CL),C.byref(PF),None,0)
    if tm:method(tm,4)(tm)
except Exception as e:rep['cleanup_error']=str(e)
u.DestroyWindow(hwnd)
Path(__file__).resolve().parents[1].joinpath('selection',f'win32-edit-tip-probe.{which}.json').write_text(json.dumps(rep,indent=2),encoding='utf-8')
print(json.dumps({k:v for k,v in rep.items() if k!='new_module_sha256'},indent=1))
