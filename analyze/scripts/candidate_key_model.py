"""Executable model of IMTCTIP!CFnCandUIKeyHandler::CandUICommandFromKey (180028070).

Evidence: decompilation of IMTCTIP.dll (reference SHA in analyze/p0/manifest.json) and the four
key tables extracted from the DLL data section into analyze/selection/candidate-keys.csv.
Command NAMES are inferred from the key bindings (the consumer of these numbers lives in the OS
candidate UI, outside the reference set); the NUMBERS and the matching rules are from the binary.
"""
import csv
from dataclasses import dataclass
from pathlib import Path

NOT_HANDLED = 0xFFFFFFFF
CMD_NAMES = {0: 'NONE_CONSUME', 1: 'SELECT_CURRENT', 2: 'CANCEL_CLOSE', 4: 'SELECT_BY_NUMBER',
             7: 'PAGE_NEXT', 8: 'PAGE_PREV', 9: 'FIRST_PAGE', 10: 'LAST_PAGE', 11: 'MOVE_11',
             12: 'MOVE_12', 13: 'MOVE_LEFT', 14: 'MOVE_RIGHT', 20: 'TAB_0x14'}
VK = dict(TAB=0x09, ENTER=0x0D, ESC=0x1B, SPACE=0x20, PGUP=0x21, PGDN=0x22, END=0x23, HOME=0x24,
          LEFT=0x25, UP=0x26, RIGHT=0x27, DOWN=0x28, DELETE=0x2E)
CSV = Path(__file__).resolve().parents[1] / 'selection' / 'candidate-keys.csv'


@dataclass(frozen=True)
class Entry:
    flags: int
    key: int
    command: int
    argument: int


def load_tables(path=CSV):
    tables = {}
    for r in csv.DictReader(open(path, encoding='utf-8', newline='')):
        tables.setdefault(r['table'], []).append(
            Entry(int(r['flags'], 16), int(r['key'], 16), int(r['command']), int(r['argument'])))
    return tables


@dataclass
class Ctx:
    """Inputs that CandUICommandFromKey reads."""
    profile_id_3_or_7: bool = False   # MapProfileGUIDToProfileID in {3,7} (and !=9) -> iVar14
    candidate_type_3: bool = False    # IImeCandidateListProperty type == 3 -> local_f4
    integrated_mode: int = 0          # Canduiutil::GetIsIntegratedMode -> local_b4
    integrated_flag: int = 1          # window query result local_a0[0]
    layout_is_2: bool = False         # candidate window layout enum == 2 (bVar15 == False)
    shell_mode_1: bool = False        # TextInputProcessor::GetShellMode == 1


def is_composition(ctx: Ctx) -> bool:
    # bVar16 is set when the integrated-mode guard fails (local_b4 != 0 and local_a0 == 0)
    return ctx.integrated_mode != 0 and ctx.integrated_flag == 0


def select_table(ctx: Ctx) -> str:
    if ctx.candidate_type_3:
        return 'candidate_type_3'
    if is_composition(ctx):
        return 'composition_variant'
    return 'profile_variant' if ctx.profile_id_3_or_7 else 'default'


def entry_matches(e: Entry, vk, char, shift, ctrl):
    if e.flags == 0xFFFFFFFF:                      # unicode entry: compare typed character
        return bool(char) and (e.key & 0xFFFF) == ord(char)
    if e.key != vk:
        return False
    if e.flags & 1:
        shift_ok = shift                            # bit0: Shift required
    else:
        shift_ok = (not shift) if e.flags & 2 else True   # bit1: Shift must be up
    if e.flags & 4:                                 # bit2: Ctrl required
        return shift_ok and ctrl
    if e.flags & 8:                                 # bit3: Ctrl must be up
        return shift_ok and not ctrl
    return shift_ok


def command_from_key(tables, ctx: Ctx, vk, char='', shift=False, ctrl=False, alt=False):
    """Return (command, argument) exactly as the binary does; NOT_HANDLED if no entry matches."""
    if not is_composition(ctx):
        if not ctx.profile_id_3_or_7:
            if vk in (VK['LEFT'], VK['RIGHT']) and not alt and not shift and not ctrl:
                horizontal = ctx.layout_is_2
                if ((not ctx.candidate_type_3 and not horizontal and vk == VK['RIGHT']) or
                        (ctx.integrated_mode < 9 and horizontal and vk == VK['LEFT'])):
                    return (0, 0) if (ctx.shell_mode_1 or ctx.integrated_mode != 0) else (0x14, 0)
                if not ctx.candidate_type_3 and not horizontal and vk == VK['LEFT']:
                    return (0, 0)
        elif vk in (VK['LEFT'], VK['RIGHT']):
            return (0, 0)
    if vk == VK['TAB']:
        if (not ctx.candidate_type_3 and not alt and not shift and not ctrl and
                ctx.integrated_mode == 0 and not ctx.shell_mode_1):
            return (0x14, 0)
        return (0, 0)
    for e in tables[select_table(ctx)]:
        if entry_matches(e, vk, char, shift, ctrl):
            return (e.command, e.argument)
    return (NOT_HANDLED, 0)
