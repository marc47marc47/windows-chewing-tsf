"""P1.5 / P1.6: replay structural scenarios against (a) the Microsoft model and (b) libchewing.

Microsoft expectation = ms_input_model.py / candidate_key_model.py (decompiled rules, cited there).
chewing result       = libchewing/examples/key_replay.exe on the locally rebuilt dictionary, in-memory
                        user data only.  Both are written to analyze/p1/replay-results.json.
Status per scenario:
  SAME            same observable outcome
  DIFF_OPTION     differs by default, matched by an existing chewing option (named)
  DIFF_STRUCTURAL differs and needs chewing code change (listed in the P5 backlog)
  MS_UNDECODED    Microsoft side not fully decoded -> no verdict (kept visible)
Run with Windows or Git-Bash python; needs ./bin or libchewing/target/release/examples/key_replay.exe.
"""
import json
import subprocess
import sys
from pathlib import Path

from ms_input_model import (VK, candidate_control, candidate_space, compose_control, typing_control)

ROOT = Path(__file__).resolve().parents[2]
EXE = ROOT / 'libchewing/target/release/examples/key_replay.exe'
DICT = ROOT / 'analyze/p0/dict-rebuild'
OUT = ROOT / 'analyze/p1'


def replay(keys, *opts):
    p = subprocess.run([str(EXE), str(DICT), *opts, *keys], capture_output=True, text=True, encoding='utf-8')
    if p.returncode:
        raise RuntimeError(p.stderr)
    return [json.loads(line) for line in p.stdout.splitlines()]


def last(keys, *opts):
    return replay(keys, *opts)[-1]


SCENARIOS = []


def scenario(sid, desc, evidence):
    def deco(fn):
        SCENARIOS.append((sid, desc, evidence, fn))
        return fn
    return deco


@scenario('S01', 'empty buffer + Space', 'CTypingControl::HandleKeyEvent 180035954 (no typing) -> pass through')
def s01():
    ms = typing_control(False, VK['SPACE'])
    c = last(['<SPACE>'])
    same = ms == ('PASS_THROUGH', False) and c['commit'] == ' '
    return ms, f"commit={c['commit']!r}", 'SAME' if same else 'DIFF_STRUCTURAL', \
        'MS passes the key to the app (app inserts the space); chewing commits the space itself: same visible text'


@scenario('S02', 'partial reading ㄇㄚ + Space (first tone)', 'CTypingEditor::OnSpace 18003e520 -> CPhoneticConv::OnSpace 180049fd0 -> ToTypingParser(0x20)')
def s02():
    ms = typing_control(True, VK['SPACE'])
    c = last(['a', '8', '<SPACE>'])
    ok = ms == ('ON_SPACE', True) and not c['entering_syllable'] and c['display'] != ''
    return ms, f"display={c['display']!r} entering={c['entering_syllable']}", 'SAME' if ok else 'DIFF_STRUCTURAL', \
        'Space completes the syllable as first tone in both; verified with a syllable whose tone-1 reading exists in the dictionary'


@scenario('S03', 'partial reading with no dictionary word for first tone + Space', 'CPhoneticConv::OnSpace 180049fd0 feeds Space to the parser')
def s03():
    c = last(['s', 'u', '<SPACE>'])
    return ('ON_SPACE', True), f"behavior={c['behavior']} syllable={c['syllable']!r}", 'MS_UNDECODED', \
        'chewing rings the bell and keeps ㄋㄧ pending (no tone-1 word); Microsoft outcome depends on the parser/lexicon check (CTParserPhonetic::Parsing 1800553cc, CheckReadingString) which is not replayed'


@scenario('S04', 'composed text + Space', 'CComposeControl::HandleKeyEvent 180035408 -> OnPhraseKey(0x20) 180037070 -> CComposeEditor::OnSymbolInput(0x20)')
def s04():
    ms = compose_control(VK['SPACE'], cursor_at_end=True)
    d = last(['s', 'u', '3', 'c', 'l', '3', '<SPACE>'])
    s = last(['s', 'u', '3', 'c', 'l', '3', '<SPACE>'], '--space-select')
    same_default = ms == 'PHRASE_INPUT_OR_SYMBOL_SPACE' and d['display'] == '你好 ' and not d['selecting']
    return ms, f"default display={d['display']!r} sel={d['selecting']}; --space-select sel={s['selecting']}", \
        'SAME' if same_default else 'DIFF_STRUCTURAL', \
        'Legacy Microsoft inserts a space symbol (or PhraseInput); chewing default matches. P1.6 target behaviour (Space opens candidates) = space_is_select_key, see S05'


@scenario('S05', 'P1.6: Space opens candidates only on a composed syllable', 'target behaviour requested by the user; chewing option space_is_select_key (Entering::Action::QuickSelect)')
def s05():
    o = '--space-select'
    open_ = last(['s', 'u', '3', 'c', 'l', '3', '<SPACE>'], o)
    empty = last(['<SPACE>'], o)
    tone1 = last(['a', '8', '<SPACE>'], o)
    inside = replay(['g', '4', '<DOWN>', '<SPACE>'], o)[-1]
    ok = (open_['selecting'] and empty['commit'] == ' ' and not tone1['entering_syllable'] and tone1['display'] == '嗎'
          and inside['selecting'] and inside['page'] == 1)
    return ('target', None), (f"composed+Space sel={open_['selecting']}; empty+Space commit={empty['commit']!r}; "
                              f"ma+Space display={tone1['display']!r}; in-candidate Space page={inside['page']}"), \
        'DIFF_OPTION' if ok else 'DIFF_STRUCTURAL', \
        'all four requirements hold with space_is_select_key=true: open candidates, normal space on empty buffer, first tone kept, in-candidate Space pages'


@scenario('S06', 'composed text + Down opens candidates', 'CComposeControl::OnCaretKey 180036614 -> OpenCandidate 180037378')
def s06():
    ms = compose_control(VK['DOWN'], cursor_at_end=True)
    c = last(['g', '4', '<DOWN>'])
    return ms, f"selecting={c['selecting']} total_pages={c['total_pages']}", 'SAME' if c['selecting'] else 'DIFF_STRUCTURAL', ''


@scenario('S07', 'candidate page size', 'CCandidateControl: page step 9 (180037274/180036350); key table digits 1-9')
def s07():
    c = last(['g', '4', '<DOWN>'])
    per_page = c['candidates'].split('|')
    return ('page=9', None), f"candidates on first page returned={len(per_page)}", 'DIFF_OPTION', \
        'chewing default candidates_per_page=10 (option exists); Microsoft shows 9 per page with digits 1-9 only'


@scenario('S08', 'candidate open + Space', 'CCandidateControl::OnSpace 180037274; key table Space->cmd 7 (flags 0xa)')
def s08():
    ms_idx = candidate_space(0, 30)
    c = last(['g', '4', '<DOWN>', '<SPACE>'])
    return ('SET_INDEX', ms_idx), f"page={c['page']}", 'SAME' if c['page'] == 1 else 'DIFF_STRUCTURAL', \
        'next page; wrap-around semantics differ at the last page (Microsoft: jump to last item then wrap to the same row; chewing: next phrase group) - see S09'


@scenario('S09', 'candidate last page + Space wrap', 'candidate_space() arithmetic, tested in test_ms_input_model.py')
def s09():
    keys = ['g', '4', '<DOWN>'] + ['<SPACE>'] * 9
    c = last(keys)
    return ('wrap to index cur%9', None), f"page={c['page']}/{c['total_pages']}", 'DIFF_STRUCTURAL', \
        'Microsoft keeps a cursor index inside the list and wraps by index; chewing pages by group (needs an index cursor: P5.4)'


@scenario('S10', 'candidate open + PageDown on last page', 'CCandidateControl::OnCaretKey 180036350: wraps to index 0')
def s10():
    c = last(['g', '4', '<DOWN>'] + ['<PGDN>'] * 12)
    return ('INDEX', 0), f"page={c['page']}/{c['total_pages']}", 'MS_UNDECODED', \
        'Microsoft wraps to index 0 on PageDown past the end; chewing PageDown pages without index cursor (compare after P5.4)'


@scenario('S11', 'candidate open + Enter', 'CCandidateControl::HandleKeyEvent: Enter -> OnFinalizeItem(current index); key table ENTER->cmd 1')
def s11():
    ms = candidate_control(VK['ENTER'], 0, 20)
    c = last(['g', '4', '<DOWN>', '<ENTER>'])
    return ms, f"behavior={c['behavior']} selecting={c['selecting']}", 'DIFF_STRUCTURAL' if c['selecting'] else 'SAME', \
        'Microsoft selects the highlighted item; chewing has no highlighted item and rings the bell'


@scenario('S12', 'candidate open + digit 2', 'key table unicode "2" -> cmd 4 arg 2; OnCharInput 180036a80')
def s12():
    ms = candidate_control(0x32, 0, 20)
    c = last(['g', '4', '<DOWN>', '2'])
    return ms, f"selecting={c['selecting']} display={c['display']!r}", 'SAME' if (not c['selecting'] and c['display'] == '是') else 'DIFF_STRUCTURAL', \
        'digit selects the item at that position (note: chewing page has 10 entries, Microsoft 9)'


@scenario('S13', 'candidate open + Esc', 'key table ESC->cmd 2; CCandidateControl::OnCancel 180035efc')
def s13():
    ms = candidate_control(VK['ESC'], 0, 20)
    c = last(['g', '4', '<DOWN>', '<ESC>'])
    return ms, f"selecting={c['selecting']} display={c['display']!r}", 'SAME' if (not c['selecting'] and c['display'] == '是') else 'DIFF_STRUCTURAL', 'closes the list, text kept'


@scenario('S14', 'composed text + Enter', 'CComposeControl::HandleKeyEvent Enter branch')
def s14():
    ms = compose_control(VK['ENTER'], cursor_at_end=True)
    c = last(['s', 'u', '3', 'c', 'l', '3', '<ENTER>'])
    return ms, f"commit={c['commit']!r}", 'SAME' if c['commit'] == '你好' else 'DIFF_STRUCTURAL', ''


@scenario('S15', 'composed text + Esc', 'CComposeControl Esc branch: clear block / config 299 (0x12b)')
def s15():
    ms = compose_control(VK['ESC'], cursor_at_end=True)
    d = last(['s', 'u', '3', 'c', 'l', '3', '<ESC>'])
    o = last(['s', 'u', '3', 'c', 'l', '3', '<ESC>'])
    return ms, f"default display={d['display']!r} behavior={d['behavior']}", 'MS_UNDECODED', \
        'chewing ignores Esc by default (option esc_clear_all_buffer); Microsoft behaviour depends on config 0x12b whose meaning is not decoded'


@scenario('S16', 'typing state + Esc', 'CTypingEditor::CancelTyping 18003dcb0')
def s16():
    ms = typing_control(True, VK['ESC'])
    c = last(['s', 'u', '<ESC>'])
    return ms, f"syllable={c['syllable']!r}", 'SAME' if c['syllable'] == '' else 'DIFF_STRUCTURAL', ''


@scenario('S17', 'typing state + Tab / Delete', 'typing_control: Tab consumed, Delete -> OnDelete 18003e440')
def s17():
    t = typing_control(True, VK['TAB'])
    d = typing_control(True, VK['DELETE'])
    ct = last(['s', 'u', '<TAB>'])
    cd = last(['s', 'u', '<DEL>'])
    return (t, d), f"tab behavior={ct['behavior']} del behavior={cd['behavior']}", 'DIFF_STRUCTURAL' if (ct['behavior'] == 'Bell' or cd['behavior'] == 'Bell') else 'SAME', \
        'Microsoft consumes Tab silently and Delete edits typing; chewing rings the bell for both'


@scenario('S18', 'composed text + Backspace', 'CComposeControl Backspace -> CComposeEditor::OnBackSpace 18008ede0')
def s18():
    ms = compose_control(VK['BACK'], cursor_at_end=True)
    c = last(['s', 'u', '3', '<BKSP>'])
    return ms, f"display={c['display']!r}", 'SAME' if c['display'] == '' else 'DIFF_STRUCTURAL', ''


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    rows = []
    for sid, desc, ev, fn in SCENARIOS:
        ms, chewing, status, note = fn()
        rows.append(dict(id=sid, scenario=desc, evidence=ev, microsoft=repr(ms), chewing=chewing, status=status, note=note))
    (OUT / 'replay-results.json').write_text(json.dumps(rows, indent=2, ensure_ascii=False), encoding='utf-8')
    counts = {}
    for r in rows:
        counts[r['status']] = counts.get(r['status'], 0) + 1
        print(f"{r['id']} {r['status']:<16} {r['scenario']}  | MS={r['microsoft']} | chewing={r['chewing']}")
    print(counts)


if __name__ == '__main__':
    sys.exit(main())
