"""Print complete Ghidra function blocks matching an address/name regex (read-only)."""
import argparse
import re
from pathlib import Path

parser=argparse.ArgumentParser()
parser.add_argument('pattern')
parser.add_argument('--module',default='IMTCCORE.DLL')
args=parser.parse_args()
path=Path(__file__).resolve().parents[1]/'modules-symbolized'/args.module/'decompiled.c'
text=path.read_text(encoding='utf-8')
markers=list(re.finditer(r'^/\* ([0-9a-fA-F]+) ([^\n]+) \*/\s*$',text,re.M))
pattern=re.compile(args.pattern,re.I)
for i,marker in enumerate(markers):
    block=text[marker.start():markers[i+1].start() if i+1<len(markers) else len(text)]
    header=block[:block.find('{') if '{' in block else len(block)]
    if pattern.search(header):
        print(block)
