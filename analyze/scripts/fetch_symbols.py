"""Fetch exact RSDS-identified public symbols from Microsoft's symbol server."""
import json
import struct
import urllib.request
import uuid
from pathlib import Path

root = Path(__file__).resolve().parents[2]
out = root / 'analyze' / 'symbols'
out.mkdir(exist_ok=True)
opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
manifest = []
for file in sorted((root / 'IMETC.ref').rglob('*')):
    if file.suffix.lower() not in ('.dll', '.exe'):
        continue
    data = file.read_bytes()
    offset = data.find(b'RSDS')
    if offset < 0:
        manifest.append(dict(module=file.name, status='no RSDS'))
        continue
    guid = uuid.UUID(bytes_le=data[offset+4:offset+20]).hex.upper()
    age = struct.unpack_from('<I', data, offset+20)[0]
    name = data[offset+24:data.index(b'\0', offset+24)].decode().replace('\\', '/').split('/')[-1]
    key = guid + format(age, 'X')
    url = f'https://msdl.microsoft.com/download/symbols/{name}/{key}/{name}'
    entry = dict(module=file.name, pdb=name, guid=guid, age=age, url=url)
    target = out / key / name
    try:
        target.parent.mkdir(exist_ok=True)
        if not target.exists():
            with opener.open(url, timeout=30) as response:
                content = response.read()
            if not content.startswith(b'Microsoft C/C++ MSF'):
                raise ValueError('Unexpected PDB header')
            target.write_bytes(content)
        entry.update(status='downloaded', path=str(target), size=target.stat().st_size)
    except Exception as error:
        entry.update(status='failed', error=str(error))
    manifest.append(entry)
    (out / 'manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    print(file.name, entry['status'], entry.get('size', entry.get('error', '')), flush=True)
