"""Audit PE RSDS identity against downloaded public PDB metadata, preserving mismatches."""
import json
import re
import struct
import subprocess
import uuid
from pathlib import Path

root=Path(__file__).resolve().parents[2]
manifest=json.loads((root/'analyze/symbols/manifest.json').read_text())
reports=[]
for entry in manifest:
    source=next(p for p in (root/'IMETC.ref').rglob('*') if p.name==entry['module'])
    data=source.read_bytes();at=data.find(b'RSDS')
    if at<0: raise ValueError('Missing RSDS')
    pe_guid=str(uuid.UUID(bytes_le=data[at+4:at+20])).upper()
    pe_age=struct.unpack_from('<I',data,at+20)[0]
    text=subprocess.check_output(['C:/Program Files/LLVM/bin/llvm-pdbutil.exe','dump','-summary',entry['path']],text=True)
    pdb_guid=re.search(r'GUID: \{([^}]+)\}',text).group(1).upper()
    pdb_age=int(re.search(r'Age: (\d+)',text).group(1))
    yaml=subprocess.check_output(['C:/Program Files/LLVM/bin/llvm-pdbutil.exe','pdb2yaml','--dbi-stream',entry['path']],text=True)
    dbi_age=int(re.search(r'DbiStream:.*?Age:\s+(\d+)',yaml,re.S).group(1))
    reports.append(dict(module=entry['module'],pe_guid=pe_guid,pe_age=pe_age,pdb_guid=pdb_guid,pdb_age=pdb_age,
                        guid_matches=pe_guid==pdb_guid,age_matches=pe_age==pdb_age,
                        dbi_age=dbi_age,dbi_age_matches=pe_age==dbi_age,
                        acceptable_match=(pe_guid==pdb_guid and pdb_age>=pe_age and dbi_age in (0,pe_age)),
                        validation_rule_source='https://github.com/Microsoft/microsoft-pdb/blob/master/PDB/dbi/pdb.cpp',
                        stripped='Is stripped: true' in text,official_url=entry['url']))
(root/'analyze/symbols/identity-audit.json').write_text(json.dumps(reports,indent=2),encoding='utf-8')
print(json.dumps(reports,indent=2))
