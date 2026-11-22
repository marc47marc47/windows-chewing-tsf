"""Read-only: list processes (all sessions visible to this user) that have IME TC modules loaded.
Uses EnumProcessModulesEx + GetModuleFileNameExW; no injection, no writes. Windows Python required."""
import ctypes as C, hashlib, json, os, sys, time
from ctypes import wintypes as W
from pathlib import Path
if os.name!='nt':raise SystemExit('Windows Python required')
k=C.WinDLL('kernel32',use_last_error=True);p=C.WinDLL('psapi',use_last_error=True)
k.OpenProcess.restype=W.HANDLE;k.OpenProcess.argtypes=(W.DWORD,W.BOOL,W.DWORD)
p.EnumProcesses.argtypes=(C.POINTER(W.DWORD),W.DWORD,C.POINTER(W.DWORD))
p.EnumProcessModulesEx.argtypes=(W.HANDLE,C.POINTER(W.HMODULE),W.DWORD,C.POINTER(W.DWORD),W.DWORD)
p.GetModuleFileNameExW.argtypes=(W.HANDLE,W.HMODULE,W.LPWSTR,W.DWORD)
p.GetModuleFileNameExW.restype=W.DWORD
def scan():
    pids=(W.DWORD*8192)();n=W.DWORD()
    p.EnumProcesses(pids,C.sizeof(pids),C.byref(n))
    WANT=('imtc','chtime','msctf','input')
    hits=[];denied=0;total=0
    for pid in pids[:n.value//4]:
        if pid==0:continue
        total+=1
        h=k.OpenProcess(0x0410,False,pid)  # QUERY_INFORMATION|VM_READ
        if not h:denied+=1;continue
        try:
            mods=(W.HMODULE*4096)();need=W.DWORD()
            if not p.EnumProcessModulesEx(h,mods,C.sizeof(mods),C.byref(need),3):continue
            exe=C.create_unicode_buffer(1024);p.GetModuleFileNameExW(h,None,exe,1024)
            found=[]
            for m in mods[:need.value//C.sizeof(W.HMODULE)]:
                b=C.create_unicode_buffer(1024)
                if p.GetModuleFileNameExW(h,m,b,1024) and 'imetc' in b.value.lower() or 'chtime' in b.value.lower():
                    found.append(b.value)
            if found:hits.append(dict(pid=pid,exe=exe.value,modules=sorted(set(found))))
        finally:k.CloseHandle(h)
    return hits,denied,total

wait=int(sys.argv[1]) if len(sys.argv)>1 else 0
deadline=time.time()+wait
while True:
    hits,denied,total=scan()
    if hits or time.time()>=deadline:break
    time.sleep(2)
sha={}
for h in hits:
    for m in h['modules']:
        if m not in sha:
            try:sha[m]=hashlib.sha256(Path(m).read_bytes()).hexdigest().upper()
            except Exception as e:sha[m]=f'ERR {e}'
rep=dict(captured_utc=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),processes_seen=total,access_denied=denied,processes_with_imetc=hits,module_sha256=sha)
out=Path(__file__).resolve().parents[1]/'selection'/'loaded-modules-probe.json'
out.write_text(json.dumps(rep,indent=2,ensure_ascii=False),encoding='utf-8')
print(json.dumps(dict(processes_seen=total,access_denied=denied,hit_count=len(hits),exes=[h['exe'] for h in hits][:20],sha=sha),indent=1,ensure_ascii=False))
