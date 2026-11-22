"""Executable models of the Microsoft Bopomofo (IMETC reference) key-dispatch layers.

Every rule is taken from the decompilation of IMTCCORE.DLL (SHA in analyze/p0/manifest.json);
addresses are cited next to each rule.  Layers, outermost first:
  CIMController::InvokeEvent 18002f8a0 -> CImeControlProvider control stack
  -> CCandidateControl / CTypingControl / CComposeControl ::HandleKeyEvent
Linguistic conversion (what a syllable becomes) is NOT modelled here: see ranking-mapping.txt.
"""
from dataclasses import dataclass

VK = dict(BACK=0x08, TAB=0x09, ENTER=0x0D, ESC=0x1B, SPACE=0x20, PGUP=0x21, PGDN=0x22, END=0x23,
          HOME=0x24, LEFT=0x25, UP=0x26, RIGHT=0x27, DOWN=0x28, INSERT=0x2D, DELETE=0x2E)

# CImeControlProvider::SetupKeyAndCommandControlStack 1800334c4: push order of the control stack.
CONTROL_STACK = [
    ('CSearchIntegrationControl', 'always (provider+0x70)'),
    ('CBalloonControl', 'if config 0x11c and 0x11d both set (provider+0x48)'),
    ('CSoftKbdCtrl', 'if config 0x145 set (provider+0x50)'),
    ('CCandidateControl', 'if candidate editor reports an active candidate list (provider+0x58)'),
    ('CTypingControl', 'if a typing editor exists (provider+0x60)'),
    ('CComposeControl', 'if a compose editor exists (provider+0x68)'),
    ('CCommandControl', 'always, last (provider+0x38)'),
]
# CIMController::ProcessEventQueue 18002f95c: events are queued (64 slots) then offered to the
# provider one by one; a failed handler or an overflowing queue aborts the rest of the batch.
EVENT_KIND = {1: 'key -> HandleKeyEvent', 5: 'command -> HandleCommand'}   # CTypingControl::HandleEvent 1800350d0


# ---------------------------------------------------------------- CTypingControl::HandleKeyEvent 180035954
def typing_control(has_typing: bool, vk: int, *, key_up_flag: bool = False, charcode: int = 0):
    """Action of the typing layer. has_typing == CTypingEditor::GetConvertibleLength() != 0
    (vtbl+0x20).  Returns (action, handled).  Slots: +0xb0 OnSpace, +0xb8 OnBackSpace,
    +0xc0 OnDelete, +0xd8 ForceConvert, +0xe8 CancelTyping."""
    numpad = 0x60 <= vk <= 0x6F
    if not has_typing:
        if vk in (VK['END'], VK['BACK'], VK['ENTER'], VK['SPACE'], VK['PGUP'], VK['PGDN'], VK['HOME'],
                  VK['LEFT'], VK['UP'], VK['RIGHT'], VK['DOWN'], VK['DELETE']):
            return ('PASS_THROUGH', False)
        if vk == VK['ESC']:
            return ('ESC_CHECK_EDITOR_0x58_0x50', None)      # handled only if that query returns non-zero
        if numpad:
            return ('PASS_THROUGH', False)
        return ('CHAR_INPUT' if charcode else 'PASS_THROUGH', None if charcode else False)
    if vk in (VK['END'], VK['PGUP'], VK['PGDN'], VK['HOME'], VK['LEFT'], VK['UP'], VK['RIGHT'], VK['DOWN']):
        return ('FORCE_CONVERT_IF_CONFIG_0x108', True)       # LAB_180035ad5; always consumed
    if vk == VK['BACK']:
        return ('PASS_THROUGH', False) if key_up_flag else ('ON_BACKSPACE', True)
    if vk == VK['TAB'] or vk == VK['INSERT']:
        return ('CONSUME_NOTHING', True)
    if vk == VK['ENTER']:
        return ('FORCE_CONVERT', True)
    if vk == VK['ESC']:
        return ('CANCEL_TYPING', True)
    if vk == VK['SPACE']:
        return ('ON_SPACE', True)
    if vk == VK['DELETE']:
        return ('ON_DELETE', True)
    if numpad:
        return ('CANCEL_TYPING_THEN_PASS_THROUGH', False)
    return ('CHAR_INPUT' if charcode else 'PASS_THROUGH', None if charcode else False)


# ---------------------------------------------------------------- CCandidateControl 180035204 / 180037274 / 180036350
PAGE = 9


def candidate_space(cur: int, total: int):
    """CCandidateControl::OnSpace 180037274: returns the new selected index or None (no-op)."""
    if cur + PAGE < total:
        return cur + PAGE
    if total < 10:
        return None
    if cur < total - total % PAGE:
        return total - 1
    return cur % PAGE


def candidate_caret(vk: int, cur: int, total: int, layout: int = 0, busy: bool = False, swap_arrows: bool = False):
    """CCandidateControl::OnCaretKey 180036350.  layout = window layout value (vtbl+0x128, 0..3).
    swap_arrows = config 0x14f bit0 (Left/Up/Right/Down are remapped to Up/Left/Down/Right).
    Returns ('INDEX', n) | ('LAYOUT', n) | None (no-op).  busy = *(this+0x28) != 0 (Left/Right ignored)."""
    if swap_arrows and vk in (VK['LEFT'], VK['UP'], VK['RIGHT'], VK['DOWN']):
        vk = {VK['LEFT']: VK['UP'], VK['UP']: VK['LEFT'], VK['RIGHT']: VK['DOWN'], VK['DOWN']: VK['RIGHT']}[vk]

    def page_down():
        nxt = cur + PAGE
        if nxt < total:
            return ('INDEX', nxt)
        return None if total < 10 else ('INDEX', 0)

    if vk == VK['PGUP']:
        return ('INDEX', cur - PAGE) if cur - PAGE >= 0 else None
    if vk == VK['PGDN']:
        return page_down()
    if vk == VK['UP']:
        return ('INDEX', cur - 1 if cur >= 1 else total - 1)
    if vk == VK['DOWN']:
        return ('INDEX', cur + 1 if cur + 1 < total else 0)
    if vk == VK['LEFT']:
        if busy or layout not in (1, 2):
            return None
        if cur - PAGE >= 0:
            return ('INDEX', cur - PAGE)
        return ('LAYOUT', 0 if layout == 1 else 3)
    if vk == VK['RIGHT']:
        if busy:
            return None
        if layout in (1, 2):
            return page_down()
        if total < 10:
            return None
        return ('LAYOUT', 1 if layout == 0 else 2)
    return None


def candidate_control(vk: int, cur: int, total: int, **kw):
    """CCandidateControl::HandleKeyEvent 180035204 -> (action, argument)."""
    if vk == VK['ENTER']:
        return ('FINALIZE_ITEM', cur)
    if vk == VK['ESC']:
        return ('CANCEL', None)
    if vk == VK['SPACE']:
        return ('SET_INDEX', candidate_space(cur, total))
    if vk in (VK['HOME'], VK['END']):
        return ('NOT_HANDLED', None)          # OnCaretKey sets *param_2 = 0 for Home/End
    if vk in (VK['PGUP'], VK['PGDN'], VK['LEFT'], VK['UP'], VK['RIGHT'], VK['DOWN']):
        return ('CARET_KEY', candidate_caret(vk, cur, total, **kw))
    if vk == VK['TAB']:
        return ('CYCLE_LAYOUT', None)
    if vk == VK['DELETE']:
        return ('CONSUME', None)
    if 0x31 <= vk <= 0x39:
        return ('FINALIZE_ITEM_BY_DIGIT', vk - 0x31)       # via OnCharInput 180036a80
    return ('NOT_HANDLED', None)


# ---------------------------------------------------------------- CComposeControl::HandleKeyEvent 180035408 (partial)
def compose_control(vk: int, *, cursor_at_end: bool):
    """Compose layer (text already converted, no typing in progress).  Only routing is claimed:
    Space -> OnPhraseKey(0x20): PhraseInput if the phrase-suggestion state matches, otherwise
    CComposeEditor::OnSymbolInput(0x20) (a literal space symbol), NOT candidate opening.
    Up/Down -> OnCaretKey 180036614 -> OnCandSwitch/OpenCandidate 18003601c / 180037378."""
    if vk == VK['SPACE']:
        return 'PHRASE_INPUT_OR_SYMBOL_SPACE'
    if vk in (VK['UP'], VK['DOWN']):
        return 'OPEN_CANDIDATE_VIA_CARET_KEY'
    if vk in (VK['LEFT'], VK['RIGHT'], VK['HOME'], VK['END']):
        return 'MOVE_CURSOR'
    if vk == VK['ENTER']:
        return 'COMMIT'
    if vk == VK['ESC']:
        return 'CANCEL_OR_CLEAR'
    if vk == VK['BACK']:
        return 'ON_BACKSPACE'
    if vk == VK['DELETE']:
        return 'ON_DELETE'
    if vk == VK['TAB']:
        return 'PHRASE_KEY_TAB_OR_PASS'
    return 'NOT_HANDLED'
