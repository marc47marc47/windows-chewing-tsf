"""Decode format-3 compressed bigram backoff data, regardless of filename label.

Native reference: CCompressedBboLdr::Init/GetBigram/GetUnigram at 1800c38c0..3ac0.
PINTLGT.IMD is labelled PYTrigram by component metadata, but its actual header is 3.
"""
import array
import gzip
import hashlib
import json
import math
import struct
import sys
from pathlib import Path
from imetc_binary import Binary
from parse_imd import ROOT

class CompressedBigram3(Binary):
    def __init__(self,path):
        super().__init__(Path(path).read_bytes());self.path=Path(path)
        self.h=self.array('I',0,11)
        if self.h[:4]!=(1,0x17570606,len(self.data),3):raise ValueError('Unsupported compressed bigram format')
        self.nwords=self.h[7]
        self.uni_at,self.columns_at,self.codes_at=self.h[8:11]
        if not 0xc2c<self.uni_at<=self.columns_at<=self.codes_at<len(self.data):raise ValueError('Invalid section boundaries')
        self.unigrams=list(struct.iter_unpack('<BBHI',self.read(self.uni_at,8*(self.nwords+1))))
        if self.uni_at+8*(self.nwords+1)>self.columns_at:raise ValueError('Unigram overlap')
        self.starts=[row[3] for row in self.unigrams]
        if self.starts!=sorted(self.starts):raise ValueError('Nonmonotonic row offsets')
        self.npairs=self.starts[-1]
        self.columns=array.array('H',self.read(self.columns_at,2*self.npairs))
        if sys.byteorder!='little':self.columns.byteswap()
        if self.columns_at+2*self.npairs>self.codes_at:raise ValueError('Column section overlap')
        self.codes=self.read(self.codes_at,(self.npairs+1)//2)
        self.codebooks=[self.array('f',offset,256) for offset in (0x2c,0x42c,0x82c)]
        if not all(math.isfinite(v) for table in self.codebooks for v in table):raise ValueError('Nonfinite codebook')
        self.mapping={}
        for wid,(_,_,mapped,_) in enumerate(self.unigrams[:-1]):
            if mapped!=0xffff:
                if mapped in self.mapping:raise ValueError('Duplicate mapped word ID')
                self.mapping[mapped]=wid
    def probability_code(self,index):
        byte=self.codes[index>>1]
        return (byte>>4 if index%2==0 else byte)&15
    def records(self):
        for previous in range(self.nwords):
            prior=-1
            for index in range(self.starts[previous],self.starts[previous+1]):
                mapped=self.columns[index]
                if mapped<=prior:raise ValueError(f'Unsorted bigram row {previous}')
                if mapped not in self.mapping:raise ValueError('Unmapped column')
                prior=mapped
                yield index,previous,self.mapping[mapped],self.probability_code(index)
    def lookup(self,previous,next_word):
        if not(0<=previous<self.nwords and 0<=next_word<self.nwords):raise ValueError('Word ID outside model')
        mapped=self.unigrams[next_word][2]
        if mapped!=0xffff:
            left,right=self.starts[previous],self.starts[previous+1]
            while left<right:
                middle=(left+right)//2
                if self.columns[middle]<mapped:left=middle+1
                else:right=middle
            if left<self.starts[previous+1] and self.columns[left]==mapped:
                return self.codebooks[2][self.probability_code(left)],False
        value=self.codebooks[1][self.unigrams[previous][1]]+self.codebooks[0][self.unigrams[next_word][0]]
        return struct.unpack('<f',struct.pack('<f',value))[0],True

def main():
    model=CompressedBigram3(Path('C:/Windows/IME/IMETC/DICTS/PINTLGT.IMD'))
    out=ROOT/'analyze/imd';out.mkdir(exist_ok=True)
    verified=mismatches=0
    print('Exporting and verifying every format-3 bigram...',flush=True)
    with (out/'PINTLGT.unigrams.tsv').open('w',encoding='ascii') as stream:
        stream.write('word_id\tprobability_code\tbackoff_code\tmapped_id\tbigram_begin\n')
        for wid,row in enumerate(model.unigrams[:-1]):stream.write('\t'.join(map(str,(wid,)+row))+'\n')
    with gzip.open(out/'PINTLGT.bigrams.tsv.gz','wt',encoding='ascii',compresslevel=1) as stream:
        stream.write('pair_index\tprevious_word_id\tnext_word_id\tprobability_code\n')
        for row in model.records():
            index,previous,next_word,code=row
            score,fallback=model.lookup(previous,next_word)
            verified+=1
            if fallback or score!=model.codebooks[2][code]:mismatches+=1
            stream.write('\t'.join(map(str,row))+'\n')
    report=dict(file=model.path.name,format=3,sha256=hashlib.sha256(model.data).hexdigest(),
                words=model.nwords,bigrams=model.npairs,bigrams_verified=verified,mismatches=mismatches,
                header_u32=list(model.h),codebooks=model.codebooks,raw_codebook_hex=model.read(0x2c,0xc00).hex(),
                mapped_words=len(model.mapping),runtime_oracle=False,
                note='Component role says PYTrigram; native payload and getter are bigram-backoff format 3.')
    (out/'bigram3-coverage.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in report.items() if k not in ('codebooks','raw_codebook_hex')},indent=2),flush=True)
    if mismatches:raise SystemExit(1)

if __name__=='__main__':main()
