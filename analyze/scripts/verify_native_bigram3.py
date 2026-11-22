"""Full stored format-3 model comparison with native Init/GetUnigram/GetBigram.

Pinned DLL is mapped without entry-point execution. These three audited methods
contain no imported calls. Only copied model bytes and an isolated object are used.
"""
import ctypes as C
from ctypes import wintypes as W
import hashlib
import json
import os
import struct
import time
from pathlib import Path
from parse_bigram3 import CompressedBigram3
from parse_imd import ROOT
from verify_native_lexical import EXPECTED


def bits(value):return struct.pack('<f',value)


def main():
    if os.name!='nt' or C.sizeof(C.c_void_p)!=8:raise RuntimeError('Windows x64 required')
    path=ROOT/'IMETC.ref/IMTCCORE.DLL'
    if hashlib.sha256(path.read_bytes()).hexdigest()!=EXPECTED:raise ValueError('Reference DLL changed')
    kernel=C.WinDLL('kernel32',use_last_error=True)
    kernel.LoadLibraryExW.argtypes=(W.LPCWSTR,W.HANDLE,W.DWORD);kernel.LoadLibraryExW.restype=C.c_void_p
    kernel.FreeLibrary.argtypes=(W.HMODULE,);kernel.FreeLibrary.restype=W.BOOL
    base=kernel.LoadLibraryExW(str(path),None,1)
    if not base:raise C.WinError(C.get_last_error())
    init=C.WINFUNCTYPE(C.c_int,C.c_void_p,C.c_void_p,C.c_uint32)(base+0xc3a40)
    unigram=C.WINFUNCTYPE(C.c_float,C.c_void_p,C.c_uint32)(base+0xc3a00)
    bigram=C.WINFUNCTYPE(C.c_float,C.c_void_p,C.c_uint32,C.c_uint32,C.POINTER(C.c_int))(base+0xc38c0)
    model=CompressedBigram3(Path('C:/Windows/IME/IMETC/DICTS/PINTLGT.IMD'))
    data=C.create_string_buffer(model.data);obj=C.create_string_buffer(0x38)
    struct.pack_into('<f',obj,0x30,-500.0)
    started=time.monotonic();errors=[];error_count=0
    def check(kind,key,actual,expected,flag=None,wanted=None):
        nonlocal error_count
        if bits(actual)!=bits(expected) or flag!=wanted:
            error_count+=1
            if len(errors)<20:errors.append(dict(kind=kind,key=key,actual=actual,expected=expected,flag=flag,wanted=wanted))
    try:
        if init(obj,data,len(model.data))!=1:raise RuntimeError('Native model Init rejected source')
        for wid,(prob,_,_,_) in enumerate(model.unigrams[:-1]):
            check('unigram',wid,unigram(obj,wid),model.codebooks[0][prob])
        checked=0;flag=C.c_int()
        for _,previous,next_word,code in model.records():
            actual=bigram(obj,previous,next_word,C.byref(flag))
            check('stored-bigram',[previous,next_word],actual,model.codebooks[2][code],flag.value,0)
            checked+=1
        fallback_checked=0
        for previous in range(model.nwords):
            for next_word in range(model.nwords):
                expected,fallback=model.lookup(previous,next_word)
                if fallback:break
            else:raise ValueError('No missing pair available for row')
            actual=bigram(obj,previous,next_word,C.byref(flag))
            check('fallback',[previous,next_word],actual,expected,flag.value,1)
            fallback_checked+=1
        # Explicit out-of-range and disabled-object behavior use constructor's
        # fallback field, not data beyond the copied model.
        check('out-of-range-unigram',model.nwords,unigram(obj,model.nwords),-500.0)
        check('out-of-range-bigram',model.nwords,bigram(obj,model.nwords,0,C.byref(flag)),-500.0,flag.value,1)
        struct.pack_into('<I',obj,8,0)
        check('disabled-unigram',0,unigram(obj,0),-500.0)
        check('disabled-bigram',0,bigram(obj,0,0,C.byref(flag)),-500.0,flag.value,1)
    finally:kernel.FreeLibrary(base)
    report=dict(model_sha256=hashlib.sha256(model.data).hexdigest(),native_reference_sha256=EXPECTED,
                native_init=True,unigrams_checked=model.nwords,stored_bigrams_checked=checked,
                missing_pair_checks=fallback_checked,boundary_checks=4,mismatches=error_count,
                first_mismatches=errors,seconds=round(time.monotonic()-started,3),
                comparison='float32 bit patterns and native fallback flags',
                scope='Native format-3 Init/GetUnigram/GetBigram; DLL entry point not run; isolated buffers.',
                limitations=['One missing pair per previous-word row; not all nwords squared pairs.',
                             'Not the format-2 model, active IME, decoder, ranking or learning.'])
    (ROOT/'analyze/imd/native-bigram3-verification.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps(report,indent=2),flush=True)
    if error_count:raise SystemExit(1)


if __name__=='__main__':main()
