"""Compare all lexical records with native, import-free CDicLex query methods.

Windows x64 only. Map the pinned reference DLL with DONT_RESOLVE_DLL_REFERENCES:
DllMain is not invoked. Only audited query methods are called; their only direct
call is WordIDToCharIDStrPtr -> GetWordIDLength, with no imports/global state.
The object is an isolated buffer populated from the documented fOpen layout.
This verifies getters, not native loading, filtering, ranking, or the active IME.
"""
import ctypes as C
import csv
from ctypes import wintypes as W
import hashlib
import json
import os
import struct
from pathlib import Path
from parse_imd import ROOT, WordLex

EXPECTED='e40011102ffbce5e41decb3d533da5aaf78617faca012200a65e2068e691971e'


def main():
    if os.name!='nt' or C.sizeof(C.c_void_p)!=8:raise RuntimeError('Windows x64 required')
    dll=ROOT/'IMETC.ref/IMTCCORE.DLL'
    if hashlib.sha256(dll.read_bytes()).hexdigest()!=EXPECTED:raise ValueError('Reference DLL changed')
    kernel=C.WinDLL('kernel32',use_last_error=True)
    kernel.LoadLibraryExW.argtypes=(W.LPCWSTR,W.HANDLE,W.DWORD);kernel.LoadLibraryExW.restype=C.c_void_p
    kernel.FreeLibrary.argtypes=(W.HMODULE,);kernel.FreeLibrary.restype=W.BOOL
    base=kernel.LoadLibraryExW(str(dll),None,1)
    if not base:raise C.WinError(C.get_last_error())
    get_length=C.WINFUNCTYPE(C.c_uint32,C.c_void_p,C.c_uint32)(base+0x73d50)
    pointer_type=C.WINFUNCTYPE(C.c_void_p,C.c_void_p,C.c_uint32,C.POINTER(C.c_uint32))
    get_pointer=pointer_type(base+0x73ec8)
    get_supplement_pointer=pointer_type(base+0x73f48)
    get_tail=C.WINFUNCTYPE(C.c_uint32,C.c_void_p,C.c_uint32,C.POINTER(C.c_void_p))(base+0x73d88)
    get_radical=C.WINFUNCTYPE(C.c_uint32,C.c_void_p,C.c_uint32)(base+0x7db60)
    get_stroke=C.WINFUNCTYPE(C.c_uint32,C.c_void_p,C.c_uint32)(base+0x7dbe0)
    reports=[]
    try:
        for name in ('IMTCL.IMD','IMTCLS.IMD','IMTCD.IMD','IMTCV.IMD','PINTLGD.IMD'):
            f=WordLex(Path('C:/Windows/IME/IMETC/DICTS')/name)
            data=C.create_string_buffer(f.data);start=C.addressof(data)
            obj=C.create_string_buffer(0x90)
            def u32(at,value):struct.pack_into('<I',obj,at,value)
            def ptr(at,offset):struct.pack_into('<Q',obj,at,start+offset)
            for at,value in ((0,f.h[11]),(4,f.h[12]),(8,f.h[13]),(12,f.h[14]),
                             (16,f.h[15]),(20,f.h[16]),(24,f.h[17]),(0x30,f.max_length)):
                u32(at,value)
            types={'IMEWDLEX':0,'IMEVRLEX':3,'IMETCLEX':1,'IMEDMLEX':2,'IMSUWDLX':5}
            u32(0x58,types[f.signature]);ptr(0x38,f.h[6]);ptr(0x40,f.h[6]+4*(f.max_length+1))
            ptr(0x60,f.strings);ptr(0x20,f.h[7]);ptr(0x68,f.h[7]+4*(f.h[15]-f.h[16]+1))
            ptr(0x48,0);u32(0x50,f.h[7]+4*(f.h[15]-f.h[16]+1))
            if f.supplementary:ptr(0x80,f.strings)
            checked=0;word_mismatches=[]
            for wid,ids in f.words():
                getter=get_supplement_pointer if f.supplementary else get_pointer
                item_type=C.c_uint32 if f.supplementary else C.c_uint16
                n=C.c_uint32();address=getter(obj,wid,C.byref(n))
                length=get_length(obj,wid)
                actual=tuple((item_type*n.value).from_address(address)) if address and n.value<=f.max_length else None
                if length!=len(ids) or n.value!=len(ids) or actual!=ids:
                    word_mismatches.append(wid)
                checked+=1
            offsets=f.array('I',f.h[7],f.h[15]-f.h[16]+1)
            posting_at=f.h[7]+4*len(offsets);bucket_mismatches=[];postings=0
            for i,(lo,hi) in enumerate(zip(offsets,offsets[1:])):
                address=C.c_void_p();n=get_tail(obj,f.h[16]+i,C.byref(address))
                expected=f.array('I',posting_at+4*lo,hi-lo)
                actual=tuple((C.c_uint32*n).from_address(address.value)) if n and address.value else ()
                if n!=hi-lo or actual!=expected:bucket_mismatches.append(f.h[16]+i)
                postings+=n
            report=dict(file=name,words_checked=checked,word_mismatches=word_mismatches,
                        tail_buckets_checked=len(offsets)-1,tail_postings_checked=postings,
                        bucket_mismatches=bucket_mismatches,source_sha256=hashlib.sha256(f.data).hexdigest())
            reports.append(report);print(json.dumps(report),flush=True)
        # Attribute getters contain no imports/calls. Preserve packed UTF-16
        # arguments for supplementary Unicode, as required by native API.
        raw=(Path('C:/Windows/IME/IMETC/DICTS')/'IMTCPH.IMD').read_bytes()
        h=struct.unpack_from('<32I',raw)
        data=C.create_string_buffer(raw);obj=C.create_string_buffer(0x98)
        table=h[6]+((h[11]-h[12]+7)//8*8)+8
        struct.pack_into('<Q',obj,0x68,C.addressof(data)+table)
        attributes_checked=0;attribute_mismatches=[]
        with (ROOT/'analyze/imd/IMTCPH.radical-stroke.csv').open(encoding='utf-8') as stream:
            for row in csv.DictReader(stream):
                cp=int(row['unicode_scalar'])
                if cp>0xffff:
                    v=cp-0x10000;argument=((0xd800+(v>>10))<<16)|(0xdc00+(v&1023))
                else:argument=cp
                if (get_radical(obj,argument),get_stroke(obj,argument))!=(int(row['radical']),int(row['stroke'])):
                    attribute_mismatches.append(cp)
                attributes_checked+=1
        attributes=dict(source_sha256=hashlib.sha256(raw).hexdigest(),records_checked=attributes_checked,
                        mismatches=attribute_mismatches)
        print(json.dumps(dict(attributes=attributes)),flush=True)
    finally:kernel.FreeLibrary(base)
    report=dict(native_reference_sha256=EXPECTED,reports=reports,attributes=attributes,
                scope='Native getters over synthetic object and real file buffers; DLL entry point not run.',
                limitations=['Does not validate fOpen, active input-method mode, filtering, ranking, or learning.',
                             'Supplementary words use audited WordIDToCharIDStrPtr at 180073f48.'])
    (ROOT/'analyze/imd/native-lexical-verification.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    if attribute_mismatches or any(r['word_mismatches'] or r['bucket_mismatches'] for r in reports):raise SystemExit(1)


if __name__=='__main__':main()
