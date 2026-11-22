"""Verify whole exported gzip streams and capture immutable provenance and row counts."""
import gzip
import hashlib
import json
import argparse
from pathlib import Path
from parse_ngram import ROOT

out=ROOT/'analyze/imd'
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--format',choices=('2','3'),default='2')
args=parser.parse_args()
coverage_name='bigram3-coverage.json' if args.format=='3' else 'ngram-coverage.json'
prefix='PINTLGT' if args.format=='3' else 'IMTCT'
coverage=json.loads((out/coverage_name).read_text())
specs=[(prefix+'.unigrams.tsv',coverage['words']),(prefix+'.bigrams.tsv.gz',coverage['bigrams'])]
if args.format=='2':specs.append((prefix+'.trigrams.tsv.gz',coverage['trigrams']))
report=[]
for name,expected in specs:
    path=out/name
    open_stream=gzip.open if name.endswith('.gz') else open
    with open_stream(path,'rt',encoding='ascii') as stream:
        header=next(stream).strip().split('\t')
        count=sum(1 for line in stream)
    if count!=expected:raise ValueError(f'Incomplete export {name}: {count}/{expected}')
    digest=hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda:stream.read(1024*1024),b''):digest.update(block)
    report.append(dict(file=name,sha256=digest.hexdigest(),bytes=path.stat().st_size,rows=count,columns=header))
manifest='bigram3-export-manifest.json' if args.format=='3' else 'ngram-export-manifest.json'
(out/manifest).write_text(json.dumps(report,indent=2),encoding='utf-8')
print(json.dumps(report,indent=2))
