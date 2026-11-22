"""Run the INSTALLED Chewing TIP (CLSID {13F2EF08-...}) in the in-process host with the user's real config
(registry read-only) and a COPY of the user's data directory; print what it really outputs for given keys."""
import os, sys, json
from pathlib import Path
root = Path(__file__).resolve().parents[2]
prof = root / 'tmp' / 'chewing_profile'
(prof / 'AppData/Roaming').mkdir(parents=True, exist_ok=True)
(prof / 'AppData/Local').mkdir(parents=True, exist_ok=True)
os.environ.update(USERPROFILE=str(prof), APPDATA=str(prof / 'AppData/Roaming'), LOCALAPPDATA=str(prof / 'AppData/Local'), HOME=str(prof))
import tip_host4 as T
from ms_convert import vk_of
keys = sys.argv[1]
s = T.start_session('{13F2EF08-575C-4D8C-88E0-F67BB8052B84}')
print('advised:', s.host.advised, 'hr', hex(s.log_hr & 0xffffffff))
res = T.run_keys(s, [vk_of(c) for c in keys.replace('_', ' ')], settle=0.3, max_wait=2.0)
for vk, eaten, text in res['trace']:
    print(chr(vk) if 32 < vk < 127 else hex(vk), 'eaten', eaten, '->', repr(text))
print('FINAL', repr(res['text']))
mods = [m for m in T.modules()]
print([m for m in mods if 'chewing' in m.lower()])
