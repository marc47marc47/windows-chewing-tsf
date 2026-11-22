"""Resolve every public PDB symbol to its PE virtual address and readable name."""
import csv
import ctypes
import json
import re
import struct
import subprocess
from pathlib import Path

root = Path(__file__).resolve().parents[2]
analysis = root / 'analyze'
undecorate = ctypes.WinDLL('dbghelp').UnDecorateSymbolName
undecorate.argtypes = [ctypes.c_char_p, ctypes.c_char_p, ctypes.c_uint, ctypes.c_uint]
undecorate.restype = ctypes.c_uint
manifest = json.loads((analysis / 'symbols/manifest.json').read_text())
rows = []
for entry in manifest:
    if entry['status'] != 'downloaded':
        continue
    source = next(p for p in (root / 'IMETC.ref').rglob('*') if p.name == entry['module'])
    data = source.read_bytes()
    pe = struct.unpack_from('<I', data, 0x3c)[0]
    count = struct.unpack_from('<H', data, pe+6)[0]
    optsize = struct.unpack_from('<H', data, pe+20)[0]
    optional = pe + 24
    magic = struct.unpack_from('<H', data, optional)[0]
    base = struct.unpack_from('<Q' if magic == 0x20b else '<I', data, optional+(24 if magic == 0x20b else 28))[0]
    sections = [struct.unpack_from('<I', data, optional+optsize+i*40+12)[0] for i in range(count)]
    dump = subprocess.check_output(['C:/Program Files/LLVM/bin/llvm-pdbutil.exe', 'dump', '-publics', entry['path']], text=True, encoding='utf-8')
    for match in re.finditer(r'S_PUB32[^\n]*`([^\n]+)`\r?\n\s+flags = ([^,\n]+), addr = (\d+):(\d+)', dump):
        mangled, flags, section, offset = match.groups()
        section = int(section)
        if not 0 < section <= len(sections):
            continue
        address = base + sections[section-1] + int(offset)
        buffer = ctypes.create_string_buffer(16384)
        name = buffer.value.decode() if undecorate(mangled.encode(), buffer, len(buffer), 0) else mangled
        rows.append(dict(module=entry['module'], address=f'{address:x}', name=name, mangled=mangled, flags=flags))
with (analysis / 'selection/public-symbols.csv').open('w', encoding='utf-8', newline='') as out:
    writer = csv.DictWriter(out, fieldnames=['module','address','name','mangled','flags'])
    writer.writeheader()
    writer.writerows(rows)
relevant = [r for r in rows if re.search(r'Cand|Phonetic|StatisLearn|Decoder|Viterbi|Ngram|Lexicon|Sorting|SortType', r['name'], re.I)]
with (analysis / 'selection/engine-symbols.csv').open('w', encoding='utf-8', newline='') as out:
    writer = csv.DictWriter(out, fieldnames=['module','address','name','mangled','flags'])
    writer.writeheader()
    writer.writerows(relevant)
print(f'{len(rows)} public symbols; {len(relevant)} engine-related symbols')
for row in rows:
    if row['module'] == 'IMTCCORE.DLL' and row['address'] in {'180059fb0','180059b00','180059cf0','180059db0','180059e10','180059e50','180059f20','18005a8b0','18005a820'}:
        print(row['address'], row['name'])
