"""Compare sentence conversion: real Microsoft Bopomofo engine vs local chewing, over the P4 corpus.

Inputs : analyze/p4/ms-results.jsonl (ms_convert.py, ground truth) and chewing-results.jsonl (convert_batch).
Output : analyze/p4/conversion-comparison.json  (aggregate + every differing row, nothing sampled)
Only rows present in BOTH files are compared (the Microsoft run may still be in progress).
"""
import json
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
P4 = ROOT / 'analyze/p4'


def load(name, key):
    out = {}
    for line in open(P4 / name, encoding='utf-8'):
        if line.strip():
            d = json.loads(line)
            out[d['id']] = d
    return out


ms = load('ms-results.jsonl', 'ms')
ch = load('chewing-results.jsonl', 'chewing')
rows, diffs = [], []
by_kind = defaultdict(lambda: Counter())
for rid, m in ms.items():
    c = ch.get(rid)
    if not c:
        continue
    a, b = m['ms'], c['chewing']
    same = a == b
    kind = m['kind']
    by_kind[kind]['total'] += 1
    by_kind[kind]['same'] += same
    if not same:
        n = len(a)
        pos = [i for i in range(min(len(a), len(b))) if a[i] != b[i]]
        diffs.append(dict(id=rid, kind=kind, reading=m['reading'], microsoft=a, chewing=b,
                          len_ms=len(a), len_chewing=len(b), differing_positions=len(pos) + abs(len(a) - len(b))))
total = sum(v['total'] for v in by_kind.values())
same = sum(v['same'] for v in by_kind.values())
agg = dict(compared=total, identical=same, identical_rate=round(same / max(1, total), 4),
           by_kind={k: dict(v) for k, v in by_kind.items()}, differing=len(diffs),
           chars_differ_histogram=dict(Counter(d['differing_positions'] for d in diffs)))
(P4 / 'conversion-comparison.json').write_text(json.dumps(dict(aggregate=agg, diffs=diffs), ensure_ascii=False, indent=1), encoding='utf-8')
print(json.dumps(agg, ensure_ascii=False, indent=1))
for d in diffs[:15]:
    print(d['reading'], '| MS:', d['microsoft'], '| chewing:', d['chewing'])
