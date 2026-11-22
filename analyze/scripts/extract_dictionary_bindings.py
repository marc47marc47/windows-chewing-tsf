"""Extract the complete component-ID/file/role table used by IMTCCFG."""
import csv
import json
from pathlib import Path
from imetc_binary import PE

root=Path(__file__).resolve().parents[2]
pe=PE(root/'IMETC.ref/IMTCCFG.DLL')
rows=[]
for index in range(0x29):
    at=pe.offset(0x18003cfa0+index*100)
    component=pe.u32(at)
    name=pe.read(at+4,32).decode('utf-16-le').split('\0',1)[0]
    role=pe.read(at+36,64).decode('utf-16-le').split('\0',1)[0]
    rows.append(dict(component_id=component,component_hex=hex(component),file=name,role=role,
                     exists_in_dict_directory=(Path('C:/Windows/IME/IMETC/DICTS')/name).is_file()))
out=root/'analyze/imd'
out.mkdir(exist_ok=True)
(out/'component-bindings.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2),encoding='utf-8')
with (out/'component-bindings.csv').open('w',encoding='utf-8',newline='') as stream:
    writer=csv.DictWriter(stream,fieldnames=list(rows[0])); writer.writeheader();writer.writerows(rows)
print(json.dumps(rows,ensure_ascii=True,indent=2))
