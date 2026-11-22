"""Read-only IMETC lexical exporter. Unknown sections are explicitly accounted for.

Source evidence: CDicCharIDPH/PHS::fOpenLex, CDicLex/SurrogateLex::fOpen,
WordIDToCharIDStrPtr, CharIDToUnicode, CharIDToEPX and GetLegacyOrder.
This is not yet a language-model decoder or a native-runtime equivalence claim.
"""
import argparse
import collections
import csv
import hashlib
import json
from pathlib import Path
from imetc_binary import Binary

ROOT=Path(__file__).resolve().parents[2]

class PhoneticCodec:
    def __init__(self, specification):
        self.masks=specification['masks']
        self.shift=specification['full_sequence_shift']
        self.parts=[{} for _ in self.masks]
        for row in specification['alphabet']:
            self.parts[row['part']][row['epx']]=row['character']
    def decode(self, epx):
        if epx==0xffff: return None
        if epx&~sum(self.masks): raise ValueError(f'Unexpected EPX bits: {epx:#x}')
        result=[]
        for mask,part in zip(self.masks,self.parts):
            value=epx&mask
            if value:
                if value not in part: raise ValueError(f'Unknown EPX component: {value:#x}')
                result.append(part[value])
        return ''.join(result)

def scalar(value):
    if value<=0xffff:
        if 0xd800<=value<=0xdfff: raise ValueError('Unpaired surrogate')
        return chr(value)
    high,low=value>>16,value&0xffff
    if not (0xd800<=high<=0xdbff and 0xdc00<=low<=0xdfff):
        raise ValueError(f'Invalid packed surrogate: {value:#x}')
    return chr(0x10000+((high-0xd800)<<10)+(low-0xdc00))

class LexicalFile(Binary):
    def __init__(self,path):
        super().__init__(Path(path).read_bytes())
        self.path=Path(path)
        self.h=self.array('I',0,32)
        self.signature=self.read(0,8).decode('ascii',errors='replace')
        if self.h[4]!=0 or self.h[5]!=2: raise ValueError('Unsupported lexical format version')
        self.offsets=list(self.h[6:10])
        if self.signature in ('IMECHLEX','IMSUCHLX'): self.offsets.append(self.h[10])
        if self.offsets[0]!=128 or self.offsets!=sorted(self.offsets) or self.offsets[-1]>len(self.data):
            raise ValueError('Invalid section boundaries')
    def summary(self):
        return dict(file=self.path.name,sha256=hashlib.sha256(self.data).hexdigest(),bytes=len(self.data),
                    signature=self.signature,header_u32=list(self.h),
                    sections=[dict(start=a,end=b,bytes=b-a) for a,b in zip(self.offsets,self.offsets[1:])],
                    trailing_bytes=len(self.data)-self.offsets[-1])

class CharacterLex(LexicalFile):
    def __init__(self,path,codec):
        super().__init__(path)
        self.codec=codec
        self.supplementary=self.signature=='IMSUCHLX'
        if self.signature not in ('IMECHLEX','IMSUCHLX'): raise ValueError('Not a character lexicon')
        self.first,self.limit=self.h[12],self.h[11]
        count=self.limit-self.first
        if count<0: raise ValueError('Negative character count')
        codepoints=self.array('I' if self.supplementary else 'H',self.h[7],count)
        readings=self.array('H',self.h[8],count)
        self.characters={}
        for i,(unicode,epx) in enumerate(zip(codepoints,readings)):
            cid=(0x200000 if self.supplementary else 0)|(self.first+i)
            flags=None if self.supplementary else self.read(self.h[6]+i,1)[0]
            try: reading=codec.decode(epx); reading_error=None
            except ValueError as error: reading=None; reading_error=str(error)
            self.characters[cid]=dict(char_id=cid,text=scalar(unicode),epx=epx,reading=reading,
                                      reading_error=reading_error,flags=flags)
        # Native full-reading lookup uses 0x4001 uint16 offsets and then character IDs.
        self.order_offsets=self.array('H',self.h[9],0x4001)
        if self.order_offsets!=tuple(sorted(self.order_offsets)): raise ValueError('Nonmonotonic legacy index')
        item_width=4 if self.supplementary else 2
        self.order_items=self.array('I' if self.supplementary else 'H',self.h[9]+0x8002,self.order_offsets[-1])
        expected_end=self.h[9]+0x8002+item_width*len(self.order_items)
        if expected_end>self.h[10]: raise ValueError('Legacy order table exceeds section')
        self.order_trailing=self.h[10]-expected_end
    def order(self):
        for seq,(start,end) in enumerate(zip(self.order_offsets,self.order_offsets[1:])):
            for rank,index in enumerate(range(start,end)):
                cid=self.order_items[index]
                record=self.characters.get(cid)
                yield dict(sequence=seq,epx=seq<<self.codec.shift,rank=rank,char_id=cid,
                           text=record['text'] if record else None,
                           matches_reading=(record is not None and record['epx']>>self.codec.shift==seq))

class WordLex(LexicalFile):
    def __init__(self,path):
        super().__init__(path)
        if self.signature not in ('IMEWDLEX','IMSUWDLX','IMEVRLEX','IMETCLEX','IMEDMLEX'):
            raise ValueError('Unsupported word lexicon signature')
        self.supplementary=self.signature=='IMSUWDLX'
        self.max_length=self.h[10]
        if not 0<self.max_length<1024: raise ValueError('Invalid maximum word length')
        self.string_offsets=self.array('I',self.h[6],self.max_length+1)
        self.word_ids=self.array('I',self.h[6]+4*(self.max_length+1),self.max_length+1)
        if self.word_ids!=tuple(sorted(self.word_ids)): raise ValueError('Nonmonotonic word IDs')
        self.strings=self.h[6]+8*(self.max_length+1)
    def words(self):
        kind,width=('I',4) if self.supplementary else ('H',2)
        for length in range(1,self.max_length+1):
            start,end=self.word_ids[length-1:length+1]
            for wid in range(start,end):
                index=(wid-start)*length+self.string_offsets[length-1]
                offset=self.strings+index*width
                if offset+length*width>self.h[7]: raise ValueError('Word crosses string section boundary')
                yield wid,self.array(kind,offset,length)
    def reverse_index(self):
        first,limit=self.h[16],self.h[15]
        if limit<first: raise ValueError('Invalid reverse-index character range')
        offsets=self.array('I',self.h[7],limit-first+1)
        if offsets!=tuple(sorted(offsets)): raise ValueError('Nonmonotonic reverse-index offsets')
        postings_at=self.h[7]+4*len(offsets)
        postings=self.array('I',postings_at,offsets[-1])
        if postings_at+4*len(postings)>self.h[8]: raise ValueError('Reverse index crosses section')
        for i,(start,end) in enumerate(zip(offsets,offsets[1:])):
            for position in range(start,end):
                yield first+i,postings[position]

def write_csv(path, rows, fields):
    with path.open('w',encoding='utf-8',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=fields)
        writer.writeheader(); writer.writerows(rows)

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--source',type=Path,default=Path('C:/Windows/IME/IMETC/DICTS'))
    parser.add_argument('--output',type=Path,default=ROOT/'analyze/imd')
    args=parser.parse_args(); args.output.mkdir(parents=True,exist_ok=True)
    codec=PhoneticCodec(json.loads((ROOT/'analyze/selection/phonetic-epx.json').read_text(encoding='utf-8')))
    inventory=[]
    for path in sorted(args.source.glob('*.IMD')):
        data=path.read_bytes()
        try:
            f=LexicalFile(path); record=f.summary()
            record['status']='header-decoded'
        except ValueError as error:
            record=dict(file=path.name,bytes=len(data),sha256=hashlib.sha256(data).hexdigest(),
                        status='not-a-supported-lexical-container',reason=str(error),header_u32=list(Binary(data).array('I',0,32)))
        inventory.append(record)
    chars={}; stats=[]
    for name in ('IMTCPH.IMD','IMTCPHCS.IMD'):
        f=CharacterLex(args.source/name,codec)
        chars.update(f.characters)
        write_csv(args.output/(name+'.characters.csv'),f.characters.values(),
                  ['char_id','text','epx','reading','reading_error','flags'])
        order=list(f.order())
        write_csv(args.output/(name+'.order.csv'),order,['sequence','epx','rank','char_id','text','matches_reading'])
        stats.append(dict(file=name,characters=len(f.characters),order_entries=len(order),
                          order_reading_mismatches=sum(not r['matches_reading'] for r in order),
                          missing_readings=sum(r['reading'] is None for r in f.characters.values()),
                          invalid_readings=sum(r['reading_error'] is not None for r in f.characters.values()),
                          legacy_trailing_bytes=f.order_trailing))
    for name in ('IMTCL.IMD','IMTCLS.IMD','IMTCD.IMD','IMTCV.IMD'):
        f=WordLex(args.source/name)
        bound=name in ('IMTCL.IMD','IMTCLS.IMD','IMTCV.IMD')
        counts=collections.Counter()
        # CDicLex::TailCharIDToWordIDList (180073d88): buckets use the last
        # character, not the first. Validate the independent inverse index.
        expected={wid:ids[-1]&0xfffff for wid,ids in f.words()}
        seen=collections.Counter()
        for cid,wid in f.reverse_index():
            seen[wid]+=1
            counts['reverse_index_entries']+=1
            counts['reverse_index_mismatches']+=expected.get(wid)!=cid
        counts['reverse_index_missing_words']=sum(wid not in seen for wid in expected)
        counts['reverse_index_repeated_words']=sum(count>1 for count in seen.values())
        def records():
            for wid,ids in f.words():
                values=[chars.get(cid) for cid in ids]
                missing=[cid for cid,value in zip(ids,values) if value is None]
                no_reading=[cid for cid,value in zip(ids,values) if value is not None and value['reading'] is None]
                counts['words']+=1
                counts['unresolved_words']+=bool(missing)
                counts['words_without_full_reading']+=bool(no_reading or missing)
                counts['unverified_binding_words']+=not bound
                text=''.join(v['text'] if v else '\ufffd' for v in values)
                reading=' '.join(v['reading'] or '<no-reading>' if v else '<missing-id>' for v in values)
                yield dict(word_id=wid,char_ids=json.dumps(ids),text=text if bound else '',reading=reading if bound else '',
                           provisional_text='' if bound else text,provisional_reading='' if bound else reading,
                           binding_verified=bound,unresolved_char_ids=json.dumps(missing))
        write_csv(args.output/(name+'.words.csv'),records(),['word_id','char_ids','text','reading','provisional_text','provisional_reading','binding_verified','unresolved_char_ids'])
        stats.append(dict(file=name,**counts,max_word_length=f.max_length,first_word_id=f.word_ids[0],last_word_id_exclusive=f.word_ids[-1],
                          character_pairing_status=('static-confirmed: CDic::Load 180062dec + CComponentMgr::_GetComponentName 18001733c'
                                                    if bound else 'unbound legacy file: not in component filename table; text export is provisional')))
    report=dict(inventory=inventory,decoded_statistics=stats,
                limitations=['Character attribute subblocks, word reverse indexes, language models and incomplete-reading indexes are not fully decoded.',
                             'Static exports are not runtime candidate lists: filtering, ranking and learning still apply.',
                             'Files not paired to phonetic character IDs are inventoried but not assigned phonetic readings.'])
    (args.output/'coverage.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(stats,ensure_ascii=True,indent=2))

if __name__=='__main__': main()
