"""Static reconstruction of all reachable ShortTermWeight ring distances.

Reference: 1800793f8; sqrtf -> double divide/add -> float store, as verified
in disassembly. No execution of Microsoft code or access to personal history.
"""
import csv
import hashlib
import json
import math
import struct
from imetc_binary import PE
from parse_imd import ROOT


def f32(value):return struct.unpack('<f',struct.pack('<f',value))[0]


def main():
    pe=PE(ROOT/'IMETC.ref/IMTCCORE.DLL')
    one=struct.unpack('<d',pe.va(0x1800e8f90,8))[0]
    if one!=1:raise ValueError('Native constant changed')
    table=[f32(one/float(f32(math.sqrt(i)))+one) for i in range(1,206)]
    if any(a<b for a,b in zip(table,table[1:])):raise ValueError('Nonmonotonic recency weights')
    out=ROOT/'analyze/selection'
    with (out/'shortterm-weights.csv').open('w',encoding='ascii',newline='') as stream:
        writer=csv.writer(stream);writer.writerow(('ring_distance','bucket','weight','float32_hex'))
        for distance in range(2048):
            value=table[distance//10]
            writer.writerow((distance,distance//10,value,struct.pack('<f',value).hex()))
    constants={hex(va):dict(raw=pe.va(va,4).hex(),value=struct.unpack('<f',pe.va(va,4))[0])
               for va in (0x1800e8f40,0x1800e8f4c,0x1800e8f54,0x1800e8f64)}
    report=dict(source_sha256=hashlib.sha256(pe.data).hexdigest(),
                function='ShortTermWeight 1800793f8',buckets=205,reachable_distances=2048,
                initialization_end='18011e3a4',table_base='18011e070',
                formula='f32(1.0 / float(f32(sqrt(bucket + 1))) + 1.0)',
                bucket='C integer division of distance by 10; valid buckets 0..204, otherwise 0.0',
                ring_distance='(ring_head - occurrence_position + 2048) % 2048 for valid positions',
                get_weight='logf(f32(f32(min(length,4) * length) * f32(sum of matching occurrence weights)))',
                persistence_constants=constants,runtime_oracle=False,
                limitations=['Host sqrt/log routines have not been compared to native Microsoft CRT.',
                             'Occurrence matching, insertion, pruning and persistence activation are not fully specified.'])
    (out/'shortterm-weight-spec.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps(report,indent=2))


if __name__=='__main__':main()
