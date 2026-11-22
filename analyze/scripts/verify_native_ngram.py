"""Compare every stored format-2 record to audited native lookup primitives.

No DLL entry point/imported code is run. Outer virtual GetBigram/GetTrigram
and their backoff composition are intentionally not claimed as verified here.
"""
import ctypes as C
from ctypes import wintypes as W
import hashlib
import json
import os
import struct
import time
from pathlib import Path
from parse_ngram import CompressedTrigram, ROOT
from verify_native_lexical import EXPECTED


def main():
    if os.name!='nt' or C.sizeof(C.c_void_p)!=8:raise RuntimeError('Windows x64 required')
    path=ROOT/'IMETC.ref/IMTCCORE.DLL'
    if hashlib.sha256(path.read_bytes()).hexdigest()!=EXPECTED:raise ValueError('Reference DLL changed')
    kernel=C.WinDLL('kernel32',use_last_error=True)
    kernel.LoadLibraryExW.argtypes=(W.LPCWSTR,W.HANDLE,W.DWORD);kernel.LoadLibraryExW.restype=C.c_void_p
    kernel.FreeLibrary.argtypes=(W.HMODULE,);kernel.FreeLibrary.restype=W.BOOL
    base=kernel.LoadLibraryExW(str(path),None,1)
    if not base:raise C.WinError(C.get_last_error())
    init=C.WINFUNCTYPE(C.c_int,C.c_void_p,C.c_void_p,C.c_uint32)(base+0xc3770)
    unigram=C.WINFUNCTYPE(C.c_float,C.c_void_p,C.c_uint32)(base+0xc3730)
    pair_index=C.WINFUNCTYPE(C.c_int,C.c_void_p,C.c_uint32,C.c_uint32,C.POINTER(C.c_uint32))(base+0xc3450)
    tri_value=C.WINFUNCTYPE(C.c_int,C.c_void_p,C.c_uint32,C.c_uint32,C.POINTER(C.c_float))(base+0xc3630)
    model=CompressedTrigram(Path('C:/Windows/IME/IMETC/DICTS/IMTCT.IMD'))
    data=C.create_string_buffer(model.data);obj=C.create_string_buffer(0x48)
    struct.pack_into('<f',obj,0x28,-500.0)
    started=time.monotonic();errors=[];error_count=0
    def fail(kind,key):
        nonlocal error_count
        error_count+=1
        if len(errors)<20:errors.append(dict(kind=kind,key=key))
    pairs=triples=missing=0
    try:
        if init(obj,data,len(model.data))!=1:raise RuntimeError('Native Init rejected model')
        for wid,row in enumerate(model.unigrams[:-1]):
            if struct.pack('<f',unigram(obj,wid))!=struct.pack('<f',model.codebooks[0][row[0]]):fail('unigram',wid)
        result=C.c_uint32()
        for pair,previous,next_word,_,_ in model.bigram_records():
            if pair_index(obj,previous,next_word,C.byref(result))!=1 or result.value!=pair:fail('pair-index',pair)
            pairs+=1
        score=C.c_float()
        for pair,next_word,code in model.trigram_records():
            if tri_value(obj,pair,next_word,C.byref(score))!=1 or struct.pack('<f',score.value)!=struct.pack('<f',model.codebooks[4][code]):
                fail('trigram-value',[pair,next_word])
            triples+=1
        for previous in range(model.nwords):
            for next_word in range(model.nwords):
                if model.bigram_index(previous,next_word) is None:break
            else:raise RuntimeError('No missing pair for row')
            if pair_index(obj,previous,next_word,C.byref(result))!=0:fail('missing-pair',[previous,next_word])
            missing+=1
    finally:kernel.FreeLibrary(base)
    report=dict(native_reference_sha256=EXPECTED,model_sha256=hashlib.sha256(model.data).hexdigest(),
                native_init=True,unigrams_checked=model.nwords,bigram_indices_checked=pairs,
                trigram_values_checked=triples,missing_pair_indices_checked=missing,
                mismatches=error_count,first_mismatches=errors,seconds=round(time.monotonic()-started,3),
                scope='Native Init/GetUnigram/GetBigramIndex/GetTrigramValue (including FindPage).',
                limitations=['Outer virtual GetBigram/GetTrigram and backoff composition not executed.',
                             'Missing pairs: one per row, not all possible pairs.',
                             'No active IME, decoding, filtering, ranking or learning validation.'])
    (ROOT/'analyze/imd/native-ngram-verification.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps(report,indent=2),flush=True)
    if error_count:raise SystemExit(1)


if __name__=='__main__':main()
