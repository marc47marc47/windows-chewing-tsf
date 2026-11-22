"""Corpus-wide structural checks plus malformed-input tests for the IMD reader."""
import collections
import json
import struct
import unittest
from pathlib import Path
from imetc_binary import Binary
from parse_imd import CharacterLex,WordLex,LexicalFile,PhoneticCodec,scalar,ROOT

SOURCE=Path('C:/Windows/IME/IMETC/DICTS')

class ImdCorpusTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        spec=json.loads((ROOT/'analyze/selection/phonetic-epx.json').read_text(encoding='utf-8'))
        cls.codec=PhoneticCodec(spec)
        cls.alphabet={r['character']:r['epx'] for r in spec['alphabet']}
        cls.chars={}
        cls.lex=[]
        for name in ('IMTCPH.IMD','IMTCPHCS.IMD'):
            f=CharacterLex(SOURCE/name,cls.codec)
            cls.lex.append(f);cls.chars.update(f.characters)

    def test_every_character_reading_round_trips(self):
        self.assertEqual(71931,len(self.chars))
        for cid,record in self.chars.items():
            self.assertIsNone(record['reading_error'],cid)
            if record['reading'] is None:
                self.assertEqual(0xffff,record['epx'],cid)
            else:
                encoded=0
                for char in record['reading']:encoded|=self.alphabet[char]
                self.assertEqual(record['epx'],encoded,cid)

    def test_every_legacy_order_entry_matches_its_reading(self):
        entries=0
        for f in self.lex:
            seen=[]
            for row in f.order():
                self.assertTrue(row['matches_reading'],row)
                seen.append(row['char_id']);entries+=1
            self.assertEqual(len(seen),len(set(seen)))
            self.assertEqual({cid for cid,r in f.characters.items() if r['reading'] is not None},set(seen))
            self.assertEqual(b'\0\0',f.read(f.h[10]-f.order_trailing,f.order_trailing))
        self.assertEqual(63875,entries)

    def test_every_word_has_exactly_one_matching_tail_index(self):
        expected_counts={'IMTCL.IMD':133633,'IMTCLS.IMD':33729,'IMTCD.IMD':123958,'IMTCV.IMD':19117}
        for name,count in expected_counts.items():
            f=WordLex(SOURCE/name); words=dict(f.words())
            self.assertEqual(count,len(words),name)
            seen=collections.Counter()
            for tail,wid in f.reverse_index():
                self.assertIn(wid,words,name)
                self.assertEqual(tail,words[wid][-1]&0xfffff,(name,wid))
                seen[wid]+=1
            self.assertEqual(set(words),set(seen),name)
            self.assertTrue(all(n==1 for n in seen.values()),name)

    def test_bound_words_resolve_every_character_id(self):
        for name in ('IMTCL.IMD','IMTCLS.IMD','IMTCV.IMD'):
            for wid,ids in WordLex(SOURCE/name).words():
                for cid in ids:self.assertIn(cid,self.chars,(name,wid,cid))

class MalformedTests(unittest.TestCase):
    def test_binary_bounds(self):
        b=Binary(b'\0'*8)
        for offset,size in ((-1,1),(0,-1),(8,1),(7,2)):
            with self.assertRaises(ValueError):b.read(offset,size)
        with self.assertRaises(ValueError):b.array('I',0,0x7fffffff)

    def test_invalid_unicode(self):
        self.assertEqual('\U00020000',scalar(0xd840dc00))
        for value in (0xd800,0xdc00,0x20000,0xffff0000):
            with self.assertRaises(ValueError):scalar(value)

    def test_corrupt_header_rejected(self):
        source=bytearray((SOURCE/'IMTCPH.IMD').read_bytes())
        mutations=((0x14,3),(0x10,1),(0x18,0x7fffffff),(0x1c,4))
        directory=(ROOT/'.cache/imetc-parser-tests').resolve()
        self.assertTrue(directory.is_relative_to(ROOT.resolve()))
        directory.mkdir(parents=True,exist_ok=True)
        path=directory/'corrupt.imd'
        for offset,value in mutations:
            changed=source.copy();struct.pack_into('<I',changed,offset,value);path.write_bytes(changed)
            with self.assertRaises(ValueError):LexicalFile(path)

if __name__=='__main__':unittest.main(verbosity=2)
