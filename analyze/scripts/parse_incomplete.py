"""Decode and cross-check all IMTCJ incomplete-reading word IDs against IMTCL/IMTCPH."""
import csv
import hashlib
import json
from pathlib import Path
from imetc_binary import Binary
from parse_imd import ROOT,CharacterLex,WordLex,PhoneticCodec

source=Path('C:/Windows/IME/IMETC/DICTS')
out=ROOT/'analyze/imd'
codec=PhoneticCodec(json.loads((ROOT/'analyze/selection/phonetic-epx.json').read_text(encoding='utf-8')))
chars=CharacterLex(source/'IMTCPH.IMD',codec).characters
words=dict(WordLex(source/'IMTCL.IMD').words())
data=(source/'IMTCJ.IMD').read_bytes();b=Binary(data)
if b.read(0,8)!=b'INCOMIDX' or b.u32(8)!=0 or b.u32(12)!=2:raise ValueError('Unsupported incomplete index')
offset,count=b.u32(16),b.u32(20)
ids=b.array('I',offset,count)
if offset+count*4!=len(data):raise ValueError('Unaccounted incomplete-index trailing bytes')
expected={wid for wid,cids in words.items() if all(chars[cid]['reading'] is not None for cid in cids)}
seen=set(ids)
rows=[];order_violations=0;previous=None;anomalies=[];previous_wid=None
for position,wid in enumerate(ids):
    if wid not in words:raise ValueError(f'Unknown incomplete word ID {wid}')
    cids=words[wid]
    key=tuple(chars[cid]['epx']&codec.masks[0] for cid in cids)
    if previous is not None and key<previous:
        order_violations+=1
        anomalies.append(dict(previous_position=position-1,position=position,previous_word_id=previous_wid,
                              word_id=wid,previous_key=previous,current_key=key))
    previous=key
    previous_wid=wid
    rows.append(dict(position=position,word_id=wid,initial_epx=json.dumps(key),text=''.join(chars[cid]['text'] for cid in cids)))
with (out/'IMTCJ.IMD.index.csv').open('w',encoding='utf-8',newline='') as stream:
    writer=csv.DictWriter(stream,fieldnames=['position','word_id','initial_epx','text']);writer.writeheader();writer.writerows(rows)
report=dict(file='IMTCJ.IMD',sha256=hashlib.sha256(data).hexdigest(),entries=count,unique_word_ids=len(seen),
            expected_readable_main_words=len(expected),missing_word_ids=len(expected-seen),unexpected_word_ids=len(seen-expected),
            initial_sequence_order_violations=order_violations,header_padding_bytes=offset-24,
            order_anomalies=anomalies,
            evidence=['CIncmpIdxLdr::Init 1800747dc','CompareInitialEpxStrWithWordID 1800765c0'],
            runtime_verified=False)
(out/'incomplete-coverage.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print(json.dumps(report,indent=2))
