"""Build the P4 comparison corpus from chewing's own dictionary phrases (fixed seed, reproducible).
Rows: id <TAB> kind <TAB> reading <TAB> keys    ('_' in keys = Space = first tone).
kinds: phrase (2-6 syllables from tsi_dict.csv) and concat (2-3 random phrases joined, 4-10 syllables)."""
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).parent))
KEY = {'ㄅ': '1', 'ㄆ': 'q', 'ㄇ': 'a', 'ㄈ': 'z', 'ㄉ': '2', 'ㄊ': 'w', 'ㄋ': 's', 'ㄌ': 'x', 'ㄍ': 'e', 'ㄎ': 'd', 'ㄏ': 'c',
       'ㄐ': 'r', 'ㄑ': 'f', 'ㄒ': 'v', 'ㄓ': '5', 'ㄔ': 't', 'ㄕ': 'g', 'ㄖ': 'b', 'ㄗ': 'y', 'ㄘ': 'h', 'ㄙ': 'n', 'ㄧ': 'u',
       'ㄨ': 'j', 'ㄩ': 'm', 'ㄚ': '8', 'ㄛ': 'i', 'ㄜ': 'k', 'ㄝ': ',', 'ㄞ': '9', 'ㄟ': 'o', 'ㄠ': 'l', 'ㄡ': '.', 'ㄢ': '0',
       'ㄣ': 'p', 'ㄤ': ';', 'ㄥ': '/', 'ㄦ': '-', 'ˊ': '6', 'ˇ': '3', 'ˋ': '4', '˙': '7'}
TONES = set('ˊˇˋ˙')


def keys_for(reading):
    out = []
    for syl in reading.split():
        out.extend(KEY[c] for c in syl)
        if not (set(syl) & TONES):
            out.append('_')
    return ''.join(out)


def main(n_phrase=1500, n_concat=1000, seed=20261122):
    rnd = random.Random(seed)
    words = []
    seen = set()
    for line in open(ROOT / 'libchewing/data/dict/chewing_v4/tsi_dict.csv', encoding='utf-8'):
        if line.startswith('#') or ',' not in line:
            continue
        w, r = line.rstrip('\n').split(',', 1)
        r = ' '.join(r.split())
        n = len(r.split())
        if 2 <= n <= 6 and len(w) == n and all(c in KEY for syl in r.split() for c in syl) and r not in seen:
            seen.add(r)
            words.append((w, r))
    rnd.shuffle(words)
    rows = []
    for i, (w, r) in enumerate(words[:n_phrase]):
        rows.append((f'p{i:05d}', 'phrase', r, keys_for(r)))
    pool = words[n_phrase:]
    for i in range(n_concat):
        parts = rnd.sample(pool, rnd.choice([2, 3]))
        r = ' '.join(p[1] for p in parts)
        if len(r.split()) > 10:
            continue
        rows.append((f'c{i:05d}', 'concat', r, keys_for(r)))
    out = ROOT / 'analyze/p4/corpus.tsv'
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(''.join('\t'.join(r) + '\n' for r in rows), encoding='utf-8')
    print(len(rows), 'rows ->', out)


if __name__ == '__main__':
    main()
