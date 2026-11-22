"""Read every record of native format-2 compressed trigram backoff models.

All native quantization indices and codebooks are preserved. No log-base conversion
or model pruning is performed. Reference: CCompressedTboLdr getters at 1800c32c0..3770.
"""
import argparse
import array
import bisect
import gzip
import hashlib
import json
import math
import struct
import sys
from pathlib import Path
from imetc_binary import Binary
from parse_imd import ROOT

class CompressedTrigram(Binary):
    PAGE_SIZE=0x28004
    def __init__(self,path):
        super().__init__(Path(path).read_bytes());self.path=Path(path)
        self.h=self.array('I',0,13)
        if self.h[:4]!=(1,0x17570606,len(self.data),2):raise ValueError('Not supported compressed trigram format 2')
        self.nwords=self.h[7]
        self.page_directory,self.unigrams_at,self.pairs_at,self.pair_codes_at,self.pages_at=self.h[8:13]
        if not (0x1434<self.page_directory<=self.unigrams_at<=self.pairs_at<=self.pair_codes_at<=self.pages_at):
            raise ValueError('Invalid model section layout')
        raw=self.read(self.unigrams_at,8*(self.nwords+1))
        self.unigrams=list(struct.iter_unpack('<BBHI',raw))
        if self.unigrams_at+len(raw)>self.pairs_at:raise ValueError('Unigram section overlap')
        self.starts=[u[3] for u in self.unigrams]
        if self.starts!=sorted(self.starts):raise ValueError('Nonmonotonic bigram row offsets')
        self.npairs=self.starts[-1]
        self.pairs=array.array('H',self.read(self.pairs_at,4*(self.npairs+1)))
        if sys.byteorder!='little':self.pairs.byteswap()
        if self.pairs_at+4*(self.npairs+1)>self.pair_codes_at:raise ValueError('Bigram section overlap')
        self.pair_codes=self.read(self.pair_codes_at,self.npairs)
        if self.pair_codes_at+self.npairs>self.pages_at:raise ValueError('Bigram code section overlap')
        self.npages=self.u32(self.page_directory)
        self.page_keys=self.array('I',self.page_directory+4,self.npages+1)
        if self.page_keys!=tuple(sorted(self.page_keys)) or self.page_keys[0]!=0 or self.page_keys[-1]!=0xffffffff:
            raise ValueError('Invalid trigram page directory')
        if self.page_directory+4*len(self.page_keys)+4>self.unigrams_at:raise ValueError('Page directory overlap')
        if self.pages_at+self.npages*self.PAGE_SIZE!=len(self.data):raise ValueError('Trigram page/file size mismatch')
        self.page_counts=[self.u32(self.pages_at+i*self.PAGE_SIZE+0x28000) for i in range(self.npages)]
        if any(count>65536 for count in self.page_counts):raise ValueError('Oversized trigram page')
        self.codebooks=[self.array('f',offset,256) for offset in (0x34,0x434,0x834,0xc34,0x1034)]
        if not all(math.isfinite(value) for table in self.codebooks for value in table):raise ValueError('Nonfinite codebook')
        self.map_to_word={}
        for wid,(_,_,mapped,_) in enumerate(self.unigrams[:-1]):
            if mapped!=0xffff:
                if mapped in self.map_to_word:raise ValueError('Ambiguous word mapping')
                self.map_to_word[mapped]=wid
        self.stats={}

    def bigram_records(self):
        for previous in range(self.nwords):
            prior=-1
            for pair in range(self.starts[previous],self.starts[previous+1]):
                mapped=self.pairs[2*pair]
                if mapped<=prior:raise ValueError(f'Unsorted bigram row {previous}')
                if mapped not in self.map_to_word:raise ValueError('Unmapped bigram column')
                prior=mapped
                code=self.pair_codes[pair]
                yield pair,previous,self.map_to_word[mapped],code&15,code>>4

    def trigram_records(self):
        page=0;visited=0
        for pair in range(self.npairs):
            while page+1<self.npages and pair>=self.page_keys[page+1]:page+=1
            begin=self.pairs[2*pair+1]
            end=(self.page_counts[page] if pair+1==self.page_keys[page+1] else self.pairs[2*(pair+1)+1])
            if not 0<=begin<=end<=self.page_counts[page]:raise ValueError(f'Invalid trigram slice {pair}: {begin}:{end}')
            at=self.pages_at+page*self.PAGE_SIZE
            prior=-1
            for local in range(begin,end):
                mapped=self.u16(at+0x8000+local*2)
                if mapped<=prior:raise ValueError(f'Unsorted trigram slice {pair}')
                if mapped not in self.map_to_word:raise ValueError('Unmapped trigram column')
                prior=mapped
                byte=self.data[at+(local>>1)]
                code=(byte>>4 if local%2==0 else byte)&15
                visited+=1
                yield pair,self.map_to_word[mapped],code
        expected=sum(self.page_counts)
        if visited!=expected:raise ValueError(f'Trigram coverage mismatch: {visited}/{expected}')
        self.stats['trigrams_checked']=visited

    def bigram_index(self,previous,next_word):
        if not (0<=previous<self.nwords and 0<=next_word<self.nwords):raise ValueError('Word ID outside model')
        mapped=self.unigrams[next_word][2]
        if mapped==0xffff:return None
        left,right=self.starts[previous],self.starts[previous+1]
        while left<right:
            middle=(left+right)//2
            if self.pairs[2*middle]<mapped:left=middle+1
            else:right=middle
        if left<self.starts[previous+1] and self.pairs[2*left]==mapped:return left
        return None

    def bigram_score(self,previous,next_word):
        index=self.bigram_index(previous,next_word)
        if index is not None:return self.codebooks[2][self.pair_codes[index]&15],False
        value=self.codebooks[1][self.unigrams[previous][1]]+self.codebooks[0][self.unigrams[next_word][0]]
        return struct.unpack('<f',struct.pack('<f',value))[0],True

    def trigram_value(self,pair,next_word):
        if not (0<=pair<self.npairs and 0<=next_word<self.nwords):raise ValueError('Model index outside range')
        mapped=self.unigrams[next_word][2]
        if mapped==0xffff:return None
        page=bisect.bisect_right(self.page_keys,pair)-1
        begin=self.pairs[2*pair+1]
        end=(self.page_counts[page] if pair+1==self.page_keys[page+1] else self.pairs[2*(pair+1)+1])
        at=self.pages_at+page*self.PAGE_SIZE
        left,right=begin,end
        while left<right:
            middle=(left+right)//2
            if self.u16(at+0x8000+middle*2)<mapped:left=middle+1
            else:right=middle
        if left>=end or self.u16(at+0x8000+left*2)!=mapped:return None
        byte=self.data[at+(left>>1)]
        code=(byte>>4 if left%2==0 else byte)&15
        return self.codebooks[4][code]

    def trigram_score(self,first,second,third):
        pair=self.bigram_index(first,second)
        if pair is None:return self.bigram_score(second,third)[0],True
        value=self.trigram_value(pair,third)
        if value is not None:return value,False
        value=self.codebooks[3][self.pair_codes[pair]>>4]+self.bigram_score(second,third)[0]
        return struct.unpack('<f',struct.pack('<f',value))[0],True

    def report(self):
        return dict(file=self.path.name,sha256=hashlib.sha256(self.data).hexdigest(),bytes=len(self.data),
                    format=2,words=self.nwords,bigrams=self.npairs,pages=self.npages,trigrams=sum(self.page_counts),
                    mapped_words=len(self.map_to_word),codebook_offsets=[0x34,0x434,0x834,0xc34,0x1034],
                    codebooks=[list(t) for t in self.codebooks],raw_codebook_hex=self.read(0x34,0x1400).hex(),
                    header_u32=list(self.h),**self.stats,
                    limitations=['Float values remain in native units; log-base conversion requires separate scoring-path proof.',
                                 'This supports format 2; format 3 in PINTLGT.IMD needs its own parser.',
                                 'Runtime oracle equivalence is not yet verified.'])

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--source',type=Path,default=Path('C:/Windows/IME/IMETC/DICTS/IMTCT.IMD'))
    parser.add_argument('--output',type=Path,default=ROOT/'analyze/imd')
    parser.add_argument('--export',action='store_true')
    args=parser.parse_args();args.output.mkdir(parents=True,exist_ok=True)
    model=CompressedTrigram(args.source)
    if args.export:
        with (args.output/'IMTCT.unigrams.tsv').open('w',encoding='ascii') as stream:
            stream.write('word_id\tprobability_code\tbackoff_code\tmapped_id\tbigram_begin\n')
            for wid,record in enumerate(model.unigrams[:-1]):stream.write('\t'.join(map(str,(wid,)+record))+'\n')
    print('Validating all bigrams...',flush=True)
    count=0
    stream=gzip.open(args.output/'IMTCT.bigrams.tsv.gz','wt',encoding='ascii',compresslevel=1) if args.export else None
    try:
        if stream:stream.write('pair_index\tprevious_word_id\tnext_word_id\tprobability_code\tbackoff_code\n')
        for row in model.bigram_records():
            count+=1
            if stream:stream.write('\t'.join(map(str,row))+'\n')
    finally:
        if stream:stream.close()
    model.stats['bigrams_checked']=count
    print('Validating all trigrams...',flush=True)
    stream=gzip.open(args.output/'IMTCT.trigrams.tsv.gz','wt',encoding='ascii',compresslevel=1) if args.export else None
    try:
        if stream:stream.write('previous_pair_index\tnext_word_id\tprobability_code\n')
        for row in model.trigram_records():
            if stream:stream.write('\t'.join(map(str,row))+'\n')
    finally:
        if stream:stream.close()
    report=model.report()
    (args.output/'ngram-coverage.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps({key:value for key,value in report.items() if key not in ('codebooks','raw_codebook_hex')},indent=2))

if __name__=='__main__':main()
