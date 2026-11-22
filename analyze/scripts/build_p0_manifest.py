"""P0.1/P0.4: pin every input version with SHA-256. Read-only; run with Windows Python.
Versions are kept in separate records (reference copy / installed copy / chewing); never merged."""
import ctypes as C, hashlib, json, os, re, subprocess, sys, time
from ctypes import wintypes as W
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
def sha(p):
    h=hashlib.sha256()
    with open(p,'rb') as f:
        for b in iter(lambda:f.read(1<<20),b''):h.update(b)
    return h.hexdigest().upper()
v=C.WinDLL('version',use_last_error=True)
v.GetFileVersionInfoSizeW.argtypes=(W.LPCWSTR,C.POINTER(W.DWORD))
v.GetFileVersionInfoW.argtypes=(W.LPCWSTR,W.DWORD,W.DWORD,C.c_void_p)
v.VerQueryValueW.argtypes=(C.c_void_p,W.LPCWSTR,C.POINTER(C.c_void_p),C.POINTER(W.UINT))
def fver(p):
    d=W.DWORD();n=v.GetFileVersionInfoSizeW(str(p),C.byref(d))
    if not n:return None
    buf=C.create_string_buffer(n)
    if not v.GetFileVersionInfoW(str(p),0,n,buf):return None
    ptr=C.c_void_p();ln=W.UINT()
    if not v.VerQueryValueW(buf,r'\StringFileInfo\040904b0\FileVersion',C.byref(ptr),C.byref(ln)):
        if not v.VerQueryValueW(buf,r'\VarFileInfo\Translation',C.byref(ptr),C.byref(ln)):return None
        t=(C.c_uint16*2).from_address(ptr.value);key='\\StringFileInfo\\%04x%04x\\FileVersion'%(t[0],t[1])
        if not v.VerQueryValueW(buf,key,C.byref(ptr),C.byref(ln)):return None
    return C.wstring_at(ptr.value)
def run(cmd):
    try:return subprocess.check_output(cmd,text=True,stderr=subprocess.STDOUT,timeout=60).strip().splitlines()[0]
    except Exception as e:return f'unavailable: {e}'
ref=ROOT/'IMETC.ref';sysdir=Path(r'C:\Windows\System32\IME\IMETC')
audit={a['module']:a for a in json.loads((ROOT/'analyze/symbols/identity-audit.json').read_text())}
pdbs={m['module']:m for m in json.loads((ROOT/'analyze/symbols/manifest.json').read_text())}
modules=[]
for f in sorted(ref.rglob('*')):
    if not f.is_file() or f.suffix.lower() not in ('.dll','.exe'):continue
    rel=f.relative_to(ref);inst=sysdir/rel
    rec=dict(name=f.name,reference_path=str(f),reference_version=fver(f),reference_sha256=sha(f),
             installed_path=str(inst),installed_exists=inst.exists())
    if inst.exists():
        rec.update(installed_version=fver(inst),installed_sha256=sha(inst))
        rec['installed_equals_reference']=rec['installed_sha256']==rec['reference_sha256']
    a=audit.get(f.name);p=pdbs.get(f.name)
    if a:rec['pdb']=dict(guid=a['pe_guid'],pe_age=a['pe_age'],pdb_age=a['pdb_age'],dbi_age=a['dbi_age'],
                         acceptable_match=a['acceptable_match'],file=p['path'] if p else None,
                         sha256=sha(p['path']) if p and Path(p['path']).exists() else None)
    modules.append(rec)
dicts=[];dd=Path(r'C:\Windows\IME\IMETC\DICTS')
cov={e['file']:e['sha256'].upper() for e in json.loads((ROOT/'analyze/imd/coverage.json').read_text())['inventory']}
for f in sorted(dd.glob('*')):
    s=sha(f);dicts.append(dict(name=f.name,path=str(f),bytes=f.stat().st_size,sha256=s,
                               matches_parsed_snapshot=(cov.get(f.name)==s) if f.name in cov else None))
chew=[]
for rel in ['Cargo.toml','Cargo.lock','libchewing/Cargo.toml','libchewing/Cargo.lock','analyze/rust-dependency-cache.json']:
    p=ROOT/rel
    if p.exists():chew.append(dict(path=rel,sha256=sha(p)))
for p in sorted((ROOT/'libchewing/data/dict/chewing_v4').glob('*')):
    chew.append(dict(path=p.relative_to(ROOT).as_posix(),bytes=p.stat().st_size,sha256=sha(p)))
ver=lambda t,k:(re.search(r'^%s\s*=\s*"([^"]+)"'%k,t,re.M) or [None,None])[1]
ct=(ROOT/'Cargo.toml').read_text(encoding='utf-8');lt=(ROOT/'libchewing/Cargo.toml').read_text(encoding='utf-8')
man=dict(captured_utc=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),
    os=run(['cmd','/c','ver']),
    tools=dict(python=sys.version.split()[0],rustc=run(['rustc','--version']),cargo=run(['cargo','--version']),
               ghidra='12.1.4 (analyze/modules-symbolized/IMTCCORE.DLL/metadata.txt)',llvm_pdbutil=run([r'C:/Program Files/LLVM/bin/llvm-pdbutil.exe','--version'])),
    microsoft_reference=dict(note='IMETC.ref is the analysed copy; installed copy compared byte-for-byte; versions never mixed.',modules=modules),
    microsoft_installed_dicts=dict(directory=str(dd),files=dicts),
    chewing=dict(workspace_version=ver(ct,'version'),libchewing_dependency_version=ver(lt,'version'),
                 vcs='workspace is not a git checkout (no .git); identity pinned by file hashes below',files=chew))
out=ROOT/'analyze/p0/manifest.json'
out.write_text(json.dumps(man,indent=2,ensure_ascii=False),encoding='utf-8')
bad=[m['name'] for m in modules if m.get('installed_exists') and not m.get('installed_equals_reference')]
print(json.dumps(dict(modules=len(modules),installed_mismatch=bad,dicts=len(dicts),
      dict_mismatch=[d['name'] for d in dicts if d['matches_parsed_snapshot'] is False],chewing_files=len(chew),
      tools=man['tools'],os=man['os']),indent=1))
