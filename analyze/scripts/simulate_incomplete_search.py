"""Emulate CIncmpIdxLdr::EpxStrToWordIDList (180074524) binary search + equal-range scan
over the exported IMTCJ order, for every distinct initial-prefix query.
Static emulation of audited compare semantics (CompareInitialEpxStrWithWordID 1800765c0);
NOT a native execution."""
import csv, json
from pathlib import Path
imd=Path(__file__).resolve().parents[1]/'imd'
rows=[]
with open(imd/'IMTCJ.IMD.index.csv',encoding='utf-8',newline='') as f:
    for r in csv.DictReader(f):rows.append((int(r['word_id']),tuple(json.loads(r['initial_epx']))))
n=len(rows)
def cmp(q,key):
    for i,x in enumerate(q):
        if i>=len(key):return 1
        if x<key[i]:return -1
        if x!=key[i]:return 1
    return 0
def search(q):
    lo,hi=0,n-1;mid=None
    while lo<=hi:
        m=(lo+hi)//2;c=cmp(q,rows[m][1])
        if c<0:hi=m-1
        elif c==0:mid=m;break
        else:lo=m+1
    if mid is None:return set()
    a=mid
    while a>0 and cmp(q,rows[a-1][1])==0:a-=1
    b=mid+1
    while b<n and cmp(q,rows[b][1])==0:b+=1
    return {rows[i][0] for i in range(a,b)}
queries={}
for wid,key in rows:
    for L in range(1,len(key)+1):queries.setdefault(key[:L],[]).append((wid,len(key)))
lost={};checked=0
for q,members in queries.items():
    got=search(q)
    for wid,_ in members:
        checked+=1
        if wid not in got:lost.setdefault(wid,[]).append(len(q))
rep=dict(entries=n,distinct_prefix_queries=len(queries),entry_prefix_pairs=checked,
         unreachable_entries={str(k):v for k,v in lost.items()},
         note='Static emulation; first-match binary search then contiguous equal-range scan.')
(imd/'incomplete-search-emulation.json').write_text(json.dumps(rep,indent=2),encoding='utf-8')
print(json.dumps({k:rep[k] for k in ('entries','distinct_prefix_queries','entry_prefix_pairs','unreachable_entries')},indent=1))
