"""Bounds-checked, read-only PE helpers for IMETC format investigation."""
import struct
from pathlib import Path

class Binary:
    def __init__(self, data): self.data=data
    def read(self, offset, size):
        if offset<0 or size<0 or offset+size>len(self.data):
            raise ValueError(f'Out of bounds: {offset:#x}+{size:#x}, size={len(self.data):#x}')
        return self.data[offset:offset+size]
    def unpack(self, fmt, offset): return struct.unpack(fmt,self.read(offset,struct.calcsize(fmt)))
    def u16(self, offset): return self.unpack('<H',offset)[0]
    def u32(self, offset): return self.unpack('<I',offset)[0]
    def array(self, kind, offset, count):
        if count<0: raise ValueError('Negative count')
        return self.unpack('<'+str(count)+kind,offset)

class PE(Binary):
    def __init__(self, path):
        super().__init__(Path(path).read_bytes())
        pe=self.u32(0x3c)
        if self.read(pe,4)!=b'PE\0\0': raise ValueError('Not a PE')
        optional=pe+24
        magic=self.u16(optional)
        self.base=self.unpack('<Q' if magic==0x20b else '<I',optional+(24 if magic==0x20b else 28))[0]
        self.resource_rva=self.u32(optional+(112 if magic==0x20b else 96)+16)
        self.sections=[]
        for index in range(self.u16(pe+6)):
            at=optional+self.u16(pe+20)+40*index
            virtual_size,rva,size,raw=self.unpack('<IIII',at+8)
            self.sections.append((rva,size,raw))
    def offset(self, va):
        rva=va-self.base
        for start,size,raw in self.sections:
            if start<=rva<start+size: return raw+rva-start
        raise ValueError(f'Unmapped VA {va:#x}')
    def va(self, va, size): return self.read(self.offset(va),size)
    def resources(self):
        base=self.offset(self.base+self.resource_rva)
        def walk(relative, path):
            if len(path)>3: raise ValueError('Unexpected resource depth')
            at=base+relative
            named,ids=self.unpack('<HH',at+12)
            for i in range(named+ids):
                name,target=self.unpack('<II',at+16+8*i)
                if name&0x80000000:
                    p=base+(name&0x7fffffff)
                    key=self.read(p+2,2*self.u16(p)).decode('utf-16-le')
                else: key=name
                branch=path+(key,)
                if target&0x80000000: yield from walk(target&0x7fffffff,branch)
                else:
                    rva,size,codepage,reserved=self.unpack('<IIII',base+target)
                    yield branch,self.va(self.base+rva,size)
        yield from walk(0,())
