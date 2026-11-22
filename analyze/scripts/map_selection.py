"""Inventory all exported modules; leads are deliberately not function attribution."""
import bisect
import csv
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'selection'
OUT.mkdir(exist_ok=True)

def rows(path):
    with path.open(encoding='utf-8-sig', newline='') as stream:
        yield from csv.DictReader(stream)

def save(name, entries):
    (OUT / name).write_text(json.dumps(entries, ensure_ascii=False, indent=2), encoding='utf-8')

inventory, leads, keys, edges = [], [], [], []
for directory in sorted((ROOT / 'modules').iterdir()):
    funcs = sorted(rows(directory / 'functions.csv'), key=lambda f: int(f['address'], 16))
    starts = [int(f['address'], 16) for f in funcs]
    # Function size is a byte count, not an address range; use actual exported
    # disassembly ownership from nearest entry only as an explicitly tentative lead.
    def owner(address):
        try:
            index = bisect.bisect_right(starts, int(address, 16)) - 1
            return funcs[index]['name'] if index >= 0 else None
        except ValueError:
            return None
    strings = {s['address']: s['value'] for s in rows(directory / 'strings.csv')}
    interested = {a: s for a, s in strings.items() if re.search(
        r'candidate|ranking|sort|keyhandler|key trace|dictionary|userdict|\.imd\b|\.dll\b|phonetic', s, re.I)}
    for reference in rows(directory / 'references.csv'):
        if reference['to'] in interested:
            leads.append(dict(module=directory.name, function_hint=owner(reference['from']),
                              **reference, text=interested[reference['to']]))
        if 'CALL' in reference['type']:
            edges.append(dict(module=directory.name, caller_hint=owner(reference['from']), **reference))
    for line in (directory / 'disassembly.txt').read_text(encoding='utf-8').splitlines():
        # Match immediate operands, excluding stack/member offsets containing 20/28.
        if re.search(r'\bCMP\s+[^,]+,0x(?:20|28)$', line):
            address = line.split()[0]
            keys.append(dict(module=directory.name, function_hint=owner(address), instruction=line))
    inventory.append(dict(module=directory.name, functions=len(funcs),
                          strings=len(strings), imports=list(rows(directory / 'imports.csv')),
                          exports=list(rows(directory / 'exports.csv'))))
save('inventory.json', inventory)
save('string-references.json', leads)
save('key-comparisons.json', keys)
save('direct-calls.json', edges)
save('coverage.json', dict(modules=len(inventory), functions=sum(m['functions'] for m in inventory),
                          string_reference_leads=len(leads), key_comparisons=len(keys),
                          direct_calls=len(edges), runtime_verified=False,
                          warning='Nearest-entry function hints are tentative; indirect calls and data references require Ghidra follow-up. Constants alone do not identify key handlers.'))
print((OUT / 'coverage.json').read_text(encoding='utf-8'))
