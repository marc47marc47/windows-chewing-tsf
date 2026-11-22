"""P4-lite: compare Microsoft's per-reading single-character order with chewing's raw and ranked order.

Inputs : analyze/p3/ms-char-order.tsv (export_ms_char_order.py) and the output of
         libchewing/examples/raw_order.rs on the same readings (tmp/chewing_raw_vs_ranked.tsv).
Output : analyze/p3/char-order-comparison.json  (per-reading rows + aggregate), full, nothing sampled.
"""
import json
import sys
from collections import OrderedDict, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ms = OrderedDict()
for line in open(ROOT / 'analyze/p3/ms-char-order.tsv', encoding='utf-8'):
    reading, source, chars = line.rstrip('\n').split('\t')
    ms.setdefault(reading, []).extend(c for c in chars.split('|') if c)
chew = defaultdict(dict)
src = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / 'tmp/chewing_raw_vs_ranked.tsv'
for line in open(src, encoding='utf-8'):
    p = line.rstrip('\n').split('\t')
    if len(p) == 3 and p[1] in ('0', '1'):
        chew[p[0]][p[1]] = [c for c in p[2].split('|') if c]


def kendall(a, b):
    """Normalised Kendall tau between two orders of the same item set (1.0 identical, -1.0 reversed)."""
    pos = {x: i for i, x in enumerate(b)}
    seq = [pos[x] for x in a]
    n = len(seq)
    if n < 2:
        return 1.0
    inv = 0
    # O(n^2) is fine: the largest reading has a few hundred characters
    for i in range(n):
        for j in range(i + 1, n):
            if seq[i] > seq[j]:
                inv += 1
    return 1 - 2 * inv / (n * (n - 1) / 2)


rows = []
for reading, mchars in ms.items():
    c = chew.get(reading)
    if not c or '0' not in c:
        rows.append(dict(reading=reading, status='chewing_no_candidates', ms_count=len(mchars)))
        continue
    row = dict(reading=reading, ms_count=len(mchars), chewing_count=len(c['0']))
    # single characters only (chewing lookup of one syllable also returns words)
    cs = {k: [x for x in v if len(x) == 1 or (len(x) == 2 and ord(x[0]) > 0xffff)] for k, v in c.items()}
    for key, name in (('0', 'raw'), ('1', 'ranked')):
        cl = cs[key]
        common_ms = [x for x in mchars if x in set(cl)]
        common_ch = [x for x in cl if x in set(mchars)]
        row[f'{name}_common'] = len(common_ms)
        row[f'{name}_tau'] = round(kendall(common_ms, common_ch), 4) if len(common_ms) > 1 else 1.0
        row[f'{name}_top1_same'] = bool(common_ms) and common_ms[0] == common_ch[0]
        row[f'{name}_identical_order'] = common_ms == common_ch
    row['ms_only'] = len([x for x in mchars if x not in set(cs['0'])])
    row['chewing_only_chars'] = len([x for x in cs['0'] if x not in set(mchars)])
    row['status'] = 'compared'
    rows.append(row)

cmp_rows = [r for r in rows if r['status'] == 'compared']
agg = dict(
    ms_readings=len(ms), compared=len(cmp_rows),
    chewing_missing_reading=len(rows) - len(cmp_rows),
    raw_identical_order=sum(r['raw_identical_order'] for r in cmp_rows),
    raw_top1_same=sum(r['raw_top1_same'] for r in cmp_rows),
    ranked_identical_order=sum(r['ranked_identical_order'] for r in cmp_rows),
    ranked_top1_same=sum(r['ranked_top1_same'] for r in cmp_rows),
    raw_mean_tau=round(sum(r['raw_tau'] for r in cmp_rows) / max(1, len(cmp_rows)), 4),
    ranked_mean_tau=round(sum(r['ranked_tau'] for r in cmp_rows) / max(1, len(cmp_rows)), 4),
    ms_chars_missing_in_chewing=sum(r['ms_only'] for r in cmp_rows),
    chewing_chars_not_in_ms=sum(r['chewing_only_chars'] for r in cmp_rows),
)
(ROOT / 'analyze/p3/char-order-comparison.json').write_text(
    json.dumps(dict(aggregate=agg, rows=rows), indent=1, ensure_ascii=False), encoding='utf-8')
print(json.dumps(agg, indent=1))
worst = sorted(cmp_rows, key=lambda r: r['raw_tau'])[:8]
print('lowest raw tau:', [(r['reading'], r['raw_tau'], r['raw_common']) for r in worst])
