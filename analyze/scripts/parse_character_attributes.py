"""Export the PH radical/stroke subblocks using native UnicodeTo* indexing.

Evidence: CDicCharIDPH::fOpenLex 18007df30, UnicodeToRadical 18007db60,
UnicodeToStroke 18007dbe0. This does not emulate the native range-search API.
"""
import csv
from collections import Counter
import hashlib
import json
from pathlib import Path
from parse_imd import LexicalFile, ROOT, scalar


def decode(path, output):
    f=LexicalFile(path)
    if f.signature!='IMECHLEX':raise ValueError('Expected BMP PH character container')
    begin=f.h[6]+((f.h[11]-f.h[12]+7)//8*8)
    max_radical,max_stroke=f.read(begin,2)
    radical_at=begin+f.array('I',begin+4,1)[0]
    stroke_at=radical_at+f.array('I',radical_at+4,1)[0]
    ranges=((0x3400,0x4db6),(0x4e00,0x9fa6),(0x20000,0x2a6d7))
    codepoints=[cp for lo,hi in ranges for cp in range(lo,hi)]
    values=f.array('H',begin+8,len(codepoints))
    table_end=begin+8+2*len(values)
    if table_end>radical_at:raise ValueError('Attribute table crosses block boundary')
    by_scalar=dict(zip(codepoints,values))
    with (output/'IMTCPH.radical-stroke.csv').open('w',encoding='utf-8',newline='') as stream:
        writer=csv.writer(stream);writer.writerow(('unicode_scalar','text','radical','stroke','raw_u16'))
        for cp,value in by_scalar.items():writer.writerow((cp,chr(cp),value&255,value>>8,value))
    index_reports=[]
    for name,at,end in (('radical',radical_at,stroke_at),('stroke',stroke_at,f.h[7])):
        count,size=f.array('I',at,2)
        if at+size!=end or 8+count*4!=size:raise ValueError('Index block size mismatch')
        packed=f.array('I',at+8,count)
        entries=[ord(scalar(value)) for value in packed]
        if any(cp not in by_scalar for cp in entries):raise ValueError('Index Unicode outside native lookup ranges')
        keys=[((by_scalar[cp]&255,by_scalar[cp]>>8) if name=='radical' else (by_scalar[cp]>>8,)) for cp in entries]
        anomalies=[i for i in range(1,count) if keys[i]<keys[i-1]]
        with (output/('IMTCPH.'+name+'-index.csv')).open('w',encoding='utf-8',newline='') as stream:
            writer=csv.writer(stream);writer.writerow(('position','packed_utf16','unicode_scalar','radical','stroke'))
            for i,(raw,cp) in enumerate(zip(packed,entries)):
                value=by_scalar[cp];writer.writerow((i,raw,cp,value&255,value>>8))
        occurrences=Counter(entries)
        missing=[cp for cp,v in by_scalar.items() if v and cp not in occurrences]
        index_reports.append(dict(kind=name,entries=count,duplicates=count-len(occurrences),
                                  duplicate_scalars={str(cp):n for cp,n in occurrences.items() if n>1},
                                  missing_nonzero_scalars=missing,
                                  indexed_zero_attributes=sum(by_scalar[cp]==0 for cp in entries),
                                  order_anomalies=len(anomalies),first_anomaly_positions=anomalies[:20]))
    report=dict(source=f.path.name,sha256=hashlib.sha256(f.data).hexdigest(),
                records=len(values),nonzero_records=sum(v!=0 for v in values),
                max_radical=max_radical,max_stroke=max_stroke,
                radical_exceeds_max=sum((v&255)>max_radical for v in values),
                stroke_exceeds_max=sum((v>>8)>max_stroke for v in values),
                table_padding_hex=f.read(table_end,radical_at-table_end).hex(),indexes=index_reports,
                runtime_oracle=False,
                limitations=['Native range-search boundary behavior not yet validated.',
                             'Other input-method branches and supplementary attribute layout are not decoded here.'])
    (output/'character-attributes-coverage.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps(report,indent=2))


if __name__=='__main__':
    decode(Path('C:/Windows/IME/IMETC/DICTS/IMTCPH.IMD'),ROOT/'analyze/imd')
