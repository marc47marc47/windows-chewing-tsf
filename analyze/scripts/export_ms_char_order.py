"""Export Microsoft's per-reading single-character order (the IMTCPH / IMTCPHCS "order" sections).

Source: analyze/imd/IMTCPH.IMD.order.csv + IMTCPH.IMD.characters.csv (and the CS variants) produced by
parse_imd.py from the SHA-pinned system IMD files (CDicCharIDPH order section, GetLegacyOrder 18007cd80).
Output: analyze/p3/ms-char-order.tsv   reading <TAB> source <TAB> chars joined by '|' in Microsoft order
Readings are normalised for chewing: first-tone mark U+02C9 removed, and only readings that are a
single full syllable are kept in the chewing-facing file (tone marks alone etc. go to the unmatched file).
"""
import csv
import hashlib
import json
from collections import OrderedDict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
IMD = ROOT / 'analyze/imd'
OUT = ROOT / 'analyze/p3'
OUT.mkdir(parents=True, exist_ok=True)


def load(prefix):
    chars = {r['char_id']: r for r in csv.DictReader(open(IMD / f'{prefix}.IMD.characters.csv', encoding='utf-8', newline=''))}
    groups = OrderedDict()
    for r in csv.DictReader(open(IMD / f'{prefix}.IMD.order.csv', encoding='utf-8', newline='')):
        groups.setdefault(r['epx'], []).append(r)
    out = OrderedDict()
    for epx, rows in groups.items():
        rows.sort(key=lambda r: int(r['rank']))
        reading = chars[rows[0]['char_id']]['reading']
        if any(chars[r['char_id']]['reading'] != reading for r in rows):
            raise ValueError(f'mixed readings under epx {epx}')
        out[reading] = [r['text'] for r in rows]
    return out


main = load('IMTCPH')
supp = load('IMTCPHCS')
rows = []
skipped = []
for source, table in (('IMTCPH', main), ('IMTCPHCS', supp)):
    for reading, texts in table.items():
        norm = reading.replace('ˉ', '')
        if not norm or all(c in 'ˊˇˋ˙' for c in norm):
            skipped.append((source, reading, len(texts)))      # bare tone marks (symbol entries)
            continue
        rows.append((norm, source, texts))
with open(OUT / 'ms-char-order.tsv', 'w', encoding='utf-8', newline='') as f:
    for reading, source, texts in rows:
        f.write(f"{reading}\t{source}\t{'|'.join(texts)}\n")
sha = hashlib.sha256((OUT / 'ms-char-order.tsv').read_bytes()).hexdigest().upper()
report = dict(readings=len(rows), characters=sum(len(t) for _, _, t in rows), skipped_bare_tones=skipped,
              sources={s: len(t) for s, t in (('IMTCPH', main), ('IMTCPHCS', supp))}, sha256=sha,
              provenance='analyze/imd/*.order.csv from parse_imd.py (read-only IMD parse); order = CDicCharIDPH order section')
(OUT / 'ms-char-order.json').write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding='utf-8')
print(json.dumps({k: v for k, v in report.items() if k != 'skipped_bare_tones'}, ensure_ascii=False), 'skipped', len(skipped))
