"""Export PY character/word containers without assigning phonetic EPX semantics.

Component IDs 0x37/0x38 bind PINTLGC/PINTLGD; this preserves raw reading codes.
Native lexical string/tail-index layout is shared with the verified PH containers.
"""
import csv
import hashlib
import json
from collections import Counter
from pathlib import Path
from parse_imd import LexicalFile, WordLex, ROOT, scalar


def main():
    source=Path('C:/Windows/IME/IMETC/DICTS');out=ROOT/'analyze/imd'
    chars=LexicalFile(source/'PINTLGC.IMD')
    first,limit=chars.h[12],chars.h[11];count=limit-first
    if chars.signature!='IMECHLEX':raise ValueError('Unsupported PY character container')
    if chars.h[7]+2*count!=chars.h[8] or chars.h[8]+2*count!=chars.h[9]:
        raise ValueError('Character/reading section size mismatch')
    texts={first+i:scalar(v) for i,v in enumerate(chars.array('H',chars.h[7],count))}
    readings=chars.array('H',chars.h[8],count)
    with (out/'PINTLGC.characters.csv').open('w',encoding='utf-8',newline='') as stream:
        writer=csv.writer(stream);writer.writerow(('char_id','text','raw_reading_u16'))
        for i,(cid,text) in enumerate(texts.items()):writer.writerow((cid,text,readings[i]))
    words=WordLex(source/'PINTLGD.IMD')
    expected={wid:ids[-1]&0xfffff for wid,ids in words.words()}
    seen=Counter();mismatch_rows=[]
    for cid,wid in words.reverse_index():
        seen[wid]+=1
        if expected.get(wid)!=cid:mismatch_rows.append(dict(bucket=cid,word_id=wid,raw_tail=expected.get(wid)))
    missing_ids=Counter();total=0
    with (out/'PINTLGD.words.csv').open('w',encoding='utf-8',newline='') as stream:
        writer=csv.writer(stream);writer.writerow(('word_id','char_ids','text','raw_reading_u16','unresolved_ids'))
        for wid,ids in words.words():
            missing=[cid for cid in ids if cid not in texts];missing_ids.update(missing)
            writer.writerow((wid,json.dumps(ids),''.join(texts.get(cid,'\ufffd') for cid in ids),
                             json.dumps([readings[cid-first] if cid in texts else None for cid in ids]),json.dumps(missing)))
            total+=1
    report=dict(characters=count,words=total,reverse_index_entries=sum(seen.values()),
                reverse_index_mismatches=len(mismatch_rows),reverse_index_missing=sum(w not in seen for w in expected),
                reverse_index_duplicates=sum(n>1 for n in seen.values()),
                unresolved_character_occurrences=sum(missing_ids.values()),unresolved_ids=dict(missing_ids),
                raw_reading_distinct=len(set(readings)),raw_reading_ffff=readings.count(0xffff),
                source_sha256={f.path.name:hashlib.sha256(f.data).hexdigest() for f in (chars,words)},
                validation_status='pending-PY-specific-ID-semantics',
                runtime_oracle=False,limitations=['Raw reading u16 semantics are not decoded as phonetic EPX.',
                    'PY first/last character sections, filtering and model word-ID binding remain unverified.'])
    (out/'pinyin-lexical-coverage.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    anomalies=dict(mismatched_postings=mismatch_rows,missing_word_ids=[w for w in expected if w not in seen],
                   duplicate_word_ids={str(w):n for w,n in seen.items() if n>1})
    (out/'pinyin-index-differences.json').write_text(json.dumps(anomalies,indent=2),encoding='utf-8')
    print(json.dumps(report,indent=2))
    if mismatch_rows or missing_ids or report['reverse_index_missing'] or report['reverse_index_duplicates']:
        raise SystemExit(1)


if __name__=='__main__':main()
