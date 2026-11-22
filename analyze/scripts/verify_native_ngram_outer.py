"""Run native outer CCompressedTboLdr::GetBigram/GetTrigram (virtual dispatch + backoff).

Loads the SHA-pinned reference DLL with DONT_RESOLVE_DLL_REFERENCES (no DllMain,
no imports). The image is not relocated, so the vftable slots and the CFG
dispatch pointer are rebased in this process's private copy only. Float32 bits
and fallback flags are compared with parse_ngram.CompressedTrigram.
"""
import array, ctypes as C, hashlib, json, os, random, struct, time
from ctypes import wintypes as W
from pathlib import Path
from parse_ngram import CompressedTrigram, ROOT
from verify_native_lexical import EXPECTED

IMG=0x180000000
VTBL=0xd00f0; GUARD_PTR=0xd2498; GUARD_STUB=0xc3f90
SEED=20261122; RANDOM_CASES=1_000_000

def main():
    if os.name!='nt' or C.sizeof(C.c_void_p)!=8:raise RuntimeError('Windows x64 required')
    path=ROOT/'IMETC.ref/IMTCCORE.DLL'
    if hashlib.sha256(path.read_bytes()).hexdigest()!=EXPECTED:raise ValueError('Reference DLL changed')
    k=C.WinDLL('kernel32',use_last_error=True)
    k.LoadLibraryExW.argtypes=(W.LPCWSTR,W.HANDLE,W.DWORD);k.LoadLibraryExW.restype=C.c_void_p
    k.VirtualProtect.argtypes=(C.c_void_p,C.c_size_t,W.DWORD,C.POINTER(W.DWORD));k.VirtualProtect.restype=W.BOOL
    k.FreeLibrary.argtypes=(C.c_void_p,);k.FreeLibrary.restype=W.BOOL
    base=k.LoadLibraryExW(str(path),None,1)
    if not base:raise C.WinError(C.get_last_error())
    old=W.DWORD()
    if not k.VirtualProtect(base+GUARD_PTR,8,0x04,C.byref(old)):raise C.WinError(C.get_last_error())
    C.c_uint64.from_address(base+GUARD_PTR).value=base+GUARD_STUB
    slots=0x80//8;vt=(C.c_uint64*slots)()
    for i in range(slots):
        v=C.c_uint64.from_address(base+VTBL+8*i).value
        vt[i]=v-IMG+base if IMG<=v<IMG+0x1000000 else v
    init=C.WINFUNCTYPE(C.c_int,C.c_void_p,C.c_void_p,C.c_uint32)(base+0xc3770)
    get_bi=C.WINFUNCTYPE(C.c_float,C.c_void_p,C.c_uint32,C.c_uint32,C.POINTER(C.c_int))(base+0xc3370)
    get_tri=C.WINFUNCTYPE(C.c_float,C.c_void_p,C.c_uint32,C.c_uint32,C.c_uint32,C.POINTER(C.c_int))(base+0xc3500)
    model=CompressedTrigram(Path('C:/Windows/IME/IMETC/DICTS/IMTCT.IMD'))
    data=C.create_string_buffer(model.data);obj=C.create_string_buffer(0x48)
    C.c_uint64.from_buffer(obj,0).value=C.addressof(vt)
    struct.pack_into('<f',obj,0x28,-500.0)
    N=model.nwords;OOR=struct.pack('<f',-500.0)
    errors=[];bad=0;counts={};started=time.monotonic();flag=C.c_int()
    pk=lambda x:struct.pack('<f',x)
    def count(name):counts[name]=counts.get(name,0)+1
    def fail(kind,key,got,want):
        nonlocal bad
        bad+=1
        if len(errors)<20:errors.append(dict(kind=kind,key=key,got=got,want=want))
    def chk_bi(kind,a,b):
        count(kind);flag.value=-1
        v=get_bi(obj,a,b,C.byref(flag))
        if a>=N or b>=N:want=(OOR,1)
        else:
            s,fb=model.bigram_score(a,b);want=(pk(s),int(fb))
        if (pk(v),flag.value)!=want:fail(kind,[a,b],[pk(v).hex(),flag.value],[want[0].hex(),want[1]])
    def chk_tri(kind,a,b,c):
        count(kind);flag.value=-1
        v=get_tri(obj,a,b,c,C.byref(flag))
        if a>=N or b>=N or c>=N:want=(OOR,1)
        else:
            s,fb=model.trigram_score(a,b,c);want=(pk(s),int(fb))
        if (pk(v),flag.value)!=want:fail(kind,[a,b,c],[pk(v).hex(),flag.value],[want[0].hex(),want[1]])
    try:
        if init(obj,data,len(model.data))!=1:raise RuntimeError('Init rejected model')
        prev=array.array('I',bytes(4*model.npairs));nxt=array.array('I',bytes(4*model.npairs))
        for pair,a,b,_,_ in model.bigram_records():
            prev[pair]=a;nxt[pair]=b;chk_bi('bigram-stored',a,b)
        for pair,c,_ in model.trigram_records():chk_tri('trigram-stored',prev[pair],nxt[pair],c)
        rnd=random.Random(SEED)
        for _ in range(RANDOM_CASES):
            a,b,c=rnd.randrange(N),rnd.randrange(N),rnd.randrange(N)
            chk_bi('bigram-random',a,b);chk_tri('trigram-random-pair',a,b,c)
            p=rnd.randrange(model.npairs);chk_tri('trigram-stored-pair-random-third',prev[p],nxt[p],c)
        for t in [(N,0,0),(0,N,0),(0,0,N),(N+7,N+7,N+7),(0xffffffff,0,0)]:
            chk_tri('trigram-out-of-range',*t);chk_bi('bigram-out-of-range',t[0],t[1])
    finally:k.FreeLibrary(base)
    report=dict(native_reference_sha256=EXPECTED,model_sha256=hashlib.sha256(model.data).hexdigest(),
        seed=SEED,calls=counts,mismatches=bad,first_mismatches=errors,seconds=round(time.monotonic()-started,3),
        scope='Native outer CCompressedTboLdr::GetBigram/GetTrigram via rebased private vftable, incl. backoff and flags.',
        limitations=['Random pairs/thirds are sampled, not exhaustive over all N^3 triples.',
                     'Python reference is parse_ngram.CompressedTrigram; no IME, decoding, ranking or learning validation.'])
    (ROOT/'analyze/imd/native-ngram-outer-verification.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps(report,indent=2),flush=True)
    if bad:raise SystemExit(1)

if __name__=='__main__':main()
