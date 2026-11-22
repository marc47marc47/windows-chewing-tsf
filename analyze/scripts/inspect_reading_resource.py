"""Export the complete native phonetic EPX alphabet and masks without executing DLLs."""
import csv
import json
import struct
from pathlib import Path
from imetc_binary import PE,Binary

root=Path(__file__).resolve().parents[2]
pe=PE(root/'IMETC.ref/IMTCCORE.DLL')
matches=[(p,d) for p,d in pe.resources() if p[:2]==(10,0x6f)]
if len(matches)!=1: raise ValueError(f'Unexpected phonetic resource variants: {len(matches)}')
path,data=matches[0]
b=Binary(data)
parts=b.u16(2)
entries=b.u16(6)
rows=[]
for index in range(entries-1):
    character,epx,part=b.unpack('<HHH',0xa4+index*6)
    rows.append(dict(character=chr(character),epx=epx,part=part))
symbols=list(csv.DictReader((root/'analyze/selection/public-symbols.csv').open(encoding='utf-8')))
matches=[s for s in symbols if s['module']=='IMTCCORE.DLL' and s['name'].endswith('g_sPHEpxFmtTable')]
if len(matches)!=1: raise ValueError('Expected unique phonetic format symbol')
format_data=Binary(pe.va(int(matches[0]['address'],16),48))
masks=list(format_data.array('I',12,parts))
report=dict(resource_path=path,resource_bytes=len(data),parts=parts,declared_entries=entries,
            masks=masks,full_sequence_shift=format_data.u16(10),alphabet=rows,
            provenance='CDicRead::fInit 180060c10, PhoneticEpx2ReadingString 18006c61c, RT_RCDATA 0x6f, g_sPHEpxFmtTable')
(root/'analyze/selection/phonetic-epx.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(report,ensure_ascii=True,indent=2))
