"""Cross-check every stored ngram with random-access lookup and retained codebooks.

This validates the static reader's indexing/rounding, not a live Microsoft oracle.
"""
import bisect
import json
import time
from pathlib import Path
from parse_ngram import CompressedTrigram,ROOT

start=time.monotonic()
model=CompressedTrigram(Path('C:/Windows/IME/IMETC/DICTS/IMTCT.IMD'))
report=dict(bigrams_verified=0,trigrams_verified=0,bigram_mismatches=0,trigram_mismatches=0,
            runtime_oracle=False)
print('Checking every bigram lookup...',flush=True)
for pair,previous,next_word,probability,alpha in model.bigram_records():
    score,fallback=model.bigram_score(previous,next_word)
    report['bigrams_verified']+=1
    if fallback or score!=model.codebooks[2][probability] or model.bigram_index(previous,next_word)!=pair:
        report['bigram_mismatches']+=1
print('Checking every trigram lookup...',flush=True)
for pair,next_word,probability in model.trigram_records():
    first=bisect.bisect_right(model.starts,pair)-1
    second=model.map_to_word[model.pairs[2*pair]]
    score,fallback=model.trigram_score(first,second,next_word)
    report['trigrams_verified']+=1
    if fallback or score!=model.codebooks[4][probability]:report['trigram_mismatches']+=1
for previous,next_word in ((-1,0),(0,-1),(model.nwords,0),(0,model.nwords)):
    try:model.bigram_index(previous,next_word)
    except ValueError:pass
    else:raise AssertionError('Invalid word ID accepted')
report['elapsed_seconds']=time.monotonic()-start
(ROOT/'analyze/imd/ngram-lookup-verification.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print(json.dumps(report,indent=2),flush=True)
if report['bigram_mismatches'] or report['trigram_mismatches']:raise SystemExit(1)
