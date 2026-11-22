"""Batch ground truth from the real Microsoft Bopomofo engine (legacy IMETC TIP, hosted in-process).

usage: ms_convert.py INPUT.tsv OUTPUT.jsonl
INPUT.tsv rows: id <TAB> bopomofo syllables separated by spaces (e.g. "ㄋㄧˇ ㄏㄠˇ"); tone 1 has no mark.
For each row the standard (Daqian) keyboard keys are sent to the TIP, then the composition text is read
back from the in-memory text store and Esc clears the composition.  One session per process.
"""
import json
import os
import sys
import time
from pathlib import Path

# Isolation: keep the Microsoft IME's user data (learning/history files) out of the real profile.
_ROOT = Path(__file__).resolve().parents[2]
_PROFILE = _ROOT / 'tmp' / 'msprofile'
for _sub in ('AppData/Roaming', 'AppData/Local'):
    (_PROFILE / _sub).mkdir(parents=True, exist_ok=True)
os.environ['USERPROFILE'] = str(_PROFILE)
os.environ['APPDATA'] = str(_PROFILE / 'AppData' / 'Roaming')
os.environ['LOCALAPPDATA'] = str(_PROFILE / 'AppData' / 'Local')
os.environ['HOME'] = str(_PROFILE)

import ctypes as C
import tip_host4 as T
from tip_host2 import u, pump

# Standard (Daqian) layout, same as chewing's default and the Microsoft default.
KEY = {'ㄅ': '1', 'ㄆ': 'q', 'ㄇ': 'a', 'ㄈ': 'z', 'ㄉ': '2', 'ㄊ': 'w', 'ㄋ': 's', 'ㄌ': 'x',
       'ㄍ': 'e', 'ㄎ': 'd', 'ㄏ': 'c', 'ㄐ': 'r', 'ㄑ': 'f', 'ㄒ': 'v', 'ㄓ': '5', 'ㄔ': 't',
       'ㄕ': 'g', 'ㄖ': 'b', 'ㄗ': 'y', 'ㄘ': 'h', 'ㄙ': 'n', 'ㄧ': 'u', 'ㄨ': 'j', 'ㄩ': 'm',
       'ㄚ': '8', 'ㄛ': 'i', 'ㄜ': 'k', 'ㄝ': ',', 'ㄞ': '9', 'ㄟ': 'o', 'ㄠ': 'l', 'ㄡ': '.',
       'ㄢ': '0', 'ㄣ': 'p', 'ㄤ': ';', 'ㄥ': '/', 'ㄦ': '-', 'ˊ': '6', 'ˇ': '3', 'ˋ': '4', '˙': '7'}
TONES = set('ˊˇˋ˙')


def vk_of(ch):
    if ch == ' ':
        return 0x20
    r = u.VkKeyScanW(ord(ch))
    return r & 0xff


def main():
    inp, outp = sys.argv[1], sys.argv[2]
    rows = [l.rstrip('\n').split('\t') for l in open(inp, encoding='utf-8') if l.strip()]   # id, kind, reading, keys
    done = set()
    if os.path.exists(outp):
        done = {json.loads(l)['id'] for l in open(outp, encoding='utf-8') if l.strip()}     # resume support
    rows = [r for r in rows if r[0] not in done]
    host = T.start_session()
    out = open(outp, 'a', encoding='utf-8')
    t0 = time.time()
    for n, (rid, kind, reading, keys) in enumerate(rows):
        res = T.run_keys(host, [vk_of(c) for c in keys.replace('_', ' ')], settle=0.12, max_wait=0.8)
        out.write(json.dumps(dict(id=rid, kind=kind, reading=reading, ms=res['text']), ensure_ascii=False) + '\n')
        out.flush()
        T.reset(host)
        if n % 20 == 0:
            print(n, len(rows), round(time.time() - t0, 1), reading, '->', res['text'], flush=True)


if __name__ == '__main__':
    main()
