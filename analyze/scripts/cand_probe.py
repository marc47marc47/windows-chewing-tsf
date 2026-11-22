import os, sys
from pathlib import Path
root = Path(__file__).resolve().parents[2]
prof = root / 'tmp' / 'msprofile2'
for sub in ('AppData/Roaming', 'AppData/Local'):
    (prof / sub).mkdir(parents=True, exist_ok=True)
os.environ.update(USERPROFILE=str(prof), APPDATA=str(prof / 'AppData/Roaming'), LOCALAPPDATA=str(prof / 'AppData/Local'), HOME=str(prof))
import json
import tip_host4 as T
from ms_convert import vk_of
s = T.start_session()
keys = sys.argv[1]
T.run_keys(s, [vk_of(c) for c in keys.replace('_', ' ')], settle=0.15, max_wait=1.0)
print('text:', s.store.text)
actions = sys.argv[2:]          # e.g. LEFT DOWN
VK = dict(LEFT=0x25, RIGHT=0x27, DOWN=0x28, UP=0x26, SPACE=0x20, ESC=0x1B, HOME=0x24, END=0x23)
for a in actions:
    r = T.send_key(s, VK[a]); T.settle_text(s, 0.3, 1.5); print('key', a, 'hr/eaten', r, 'text', s.store.text)
print('text after:', s.store.text, '| events:', s.host.events[-6:])
print(json.dumps(T.read_candidates(s), ensure_ascii=False))
import os as _o
if _o.environ.get('RECONV'):
    a, b = map(int, _o.environ['RECONV'].split(','))
    print(json.dumps(T.reconversion_candidates(s, a, b), ensure_ascii=False, indent=1))
