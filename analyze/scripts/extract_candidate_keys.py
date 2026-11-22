"""Extract all four candidate-command tables used by CFnCandUIKeyHandler."""
import csv
import json
import struct
from pathlib import Path

root = Path(__file__).resolve().parents[2]
data = (root / 'IMETC.ref/IMTCTIP.dll').read_bytes()
pe = struct.unpack_from('<I', data, 0x3c)[0]
optional = pe + 24
base = struct.unpack_from('<Q', data, optional+24)[0]
sections = []
count, optsize = struct.unpack_from('<H', data, pe+6)[0], struct.unpack_from('<H', data, pe+20)[0]
for i in range(count):
    at = optional+optsize+i*40
    virtual_size, rva, size, raw = struct.unpack_from('<IIII', data, at+8)
    sections.append((rva, size, raw))

def read(va, fmt):
    rva = va-base
    for start, size, raw in sections:
        if start <= rva and rva+struct.calcsize(fmt) <= start+size:
            return struct.unpack_from(fmt, data, raw+rva-start)
    raise ValueError(hex(va))

keys={0x20:'SPACE',0x28:'DOWN',0x26:'UP',0x25:'LEFT',0x27:'RIGHT',0x0d:'ENTER',0x1b:'ESC',0x09:'TAB',0x21:'PAGEUP',0x22:'PAGEDOWN',0x24:'HOME',0x23:'END'}
rows=[]
for name, pointer, count_address in [
    ('default',0x1800788a8,0x18007d420),
    ('profile_variant',0x1800788b0,0x18007d424),
    ('candidate_type_3',0x1800788b8,0x18007d428),
    ('composition_variant',0x1800788c0,0x18007d42c),
]:
    table=read(pointer,'<Q')[0]
    count=read(count_address,'<I')[0]
    if count>1024: raise ValueError(f'Unexpected count {count}')
    for index in range(count):
        flags,key,command,argument=read(table+index*16,'<IIII')
        unicode=flags==0xffffffff
        rows.append(dict(table=name,index=index,address=hex(table+index*16),flags=hex(flags),
                         key=hex(key),key_name=(chr(key&0xffff) if unicode else keys.get(key,'')),
                         match='unicode' if unicode else 'virtual-key',command=command,argument=argument))
out=root/'analyze/selection'
with (out/'candidate-keys.csv').open('w',encoding='utf-8',newline='') as stream:
    writer=csv.DictWriter(stream,fieldnames=list(rows[0]))
    writer.writeheader(); writer.writerows(rows)
print(json.dumps(rows,ensure_ascii=False,indent=2))
