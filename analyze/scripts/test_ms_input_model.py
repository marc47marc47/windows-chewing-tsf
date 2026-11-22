import unittest
from ms_input_model import *


class Typing(unittest.TestCase):
    def test_empty_state_passthrough_keys(self):
        for k in ('END', 'BACK', 'ENTER', 'SPACE', 'PGUP', 'PGDN', 'HOME', 'LEFT', 'UP', 'RIGHT', 'DOWN', 'DELETE'):
            self.assertEqual(typing_control(False, VK[k]), ('PASS_THROUGH', False), k)

    def test_empty_state_esc_char_numpad(self):
        self.assertEqual(typing_control(False, VK['ESC'])[0], 'ESC_CHECK_EDITOR_0x58_0x50')
        self.assertEqual(typing_control(False, 0x60), ('PASS_THROUGH', False))
        self.assertEqual(typing_control(False, 0x41, charcode=ord('a'))[0], 'CHAR_INPUT')

    def test_typing_state(self):
        t = lambda k, **kw: typing_control(True, VK[k], **kw)
        self.assertEqual(t('SPACE'), ('ON_SPACE', True))
        self.assertEqual(t('ENTER'), ('FORCE_CONVERT', True))
        self.assertEqual(t('ESC'), ('CANCEL_TYPING', True))
        self.assertEqual(t('DELETE'), ('ON_DELETE', True))
        self.assertEqual(t('BACK'), ('ON_BACKSPACE', True))
        self.assertEqual(t('BACK', key_up_flag=True), ('PASS_THROUGH', False))
        self.assertEqual(t('TAB'), ('CONSUME_NOTHING', True))
        for k in ('END', 'PGUP', 'PGDN', 'HOME', 'LEFT', 'UP', 'RIGHT', 'DOWN'):
            self.assertEqual(t(k), ('FORCE_CONVERT_IF_CONFIG_0x108', True))
        self.assertEqual(typing_control(True, 0x61), ('CANCEL_TYPING_THEN_PASS_THROUGH', False))


class Candidate(unittest.TestCase):
    def test_space_paging_and_wrap(self):
        self.assertEqual(candidate_space(0, 30), 9)
        self.assertEqual(candidate_space(20, 30), 29)         # last partial page: jump to last
        self.assertEqual(candidate_space(29, 30), 2)          # 30 % 9 = 3, cur >= 27 -> wrap cur % 9
        self.assertIsNone(candidate_space(3, 9))              # fewer than 10 candidates: no-op
        self.assertEqual(candidate_space(0, 10), 9)

    def test_up_down_wrap(self):
        self.assertEqual(candidate_caret(VK['UP'], 0, 5), ('INDEX', 4))
        self.assertEqual(candidate_caret(VK['UP'], 3, 5), ('INDEX', 2))
        self.assertEqual(candidate_caret(VK['DOWN'], 4, 5), ('INDEX', 0))
        self.assertEqual(candidate_caret(VK['DOWN'], 1, 5), ('INDEX', 2))

    def test_page_keys(self):
        self.assertIsNone(candidate_caret(VK['PGUP'], 3, 30))
        self.assertEqual(candidate_caret(VK['PGUP'], 12, 30), ('INDEX', 3))
        self.assertEqual(candidate_caret(VK['PGDN'], 0, 30), ('INDEX', 9))
        self.assertEqual(candidate_caret(VK['PGDN'], 25, 30), ('INDEX', 0))   # unlike Space it wraps to 0
        self.assertIsNone(candidate_caret(VK['PGDN'], 2, 9))

    def test_left_right_layouts(self):
        self.assertEqual(candidate_caret(VK['RIGHT'], 0, 30, layout=0), ('LAYOUT', 1))
        self.assertEqual(candidate_caret(VK['RIGHT'], 0, 30, layout=3), ('LAYOUT', 2))
        self.assertIsNone(candidate_caret(VK['RIGHT'], 0, 5, layout=0))
        self.assertEqual(candidate_caret(VK['RIGHT'], 0, 30, layout=1), ('INDEX', 9))
        self.assertEqual(candidate_caret(VK['LEFT'], 12, 30, layout=1), ('INDEX', 3))
        self.assertEqual(candidate_caret(VK['LEFT'], 3, 30, layout=1), ('LAYOUT', 0))
        self.assertEqual(candidate_caret(VK['LEFT'], 3, 30, layout=2), ('LAYOUT', 3))
        self.assertIsNone(candidate_caret(VK['LEFT'], 3, 30, layout=0))
        self.assertIsNone(candidate_caret(VK['RIGHT'], 0, 30, layout=0, busy=True))

    def test_swap_arrows(self):
        self.assertEqual(candidate_caret(VK['LEFT'], 3, 5, swap_arrows=True), ('INDEX', 2))   # Left acts as Up

    def test_control_routing(self):
        self.assertEqual(candidate_control(VK['ENTER'], 4, 20), ('FINALIZE_ITEM', 4))
        self.assertEqual(candidate_control(VK['ESC'], 4, 20), ('CANCEL', None))
        self.assertEqual(candidate_control(0x33, 0, 20), ('FINALIZE_ITEM_BY_DIGIT', 2))
        self.assertEqual(candidate_control(VK['DELETE'], 0, 20), ('CONSUME', None))
        self.assertEqual(candidate_control(VK['HOME'], 0, 20), ('NOT_HANDLED', None))
        self.assertEqual(candidate_control(0x41, 0, 20), ('NOT_HANDLED', None))


class Compose(unittest.TestCase):
    def test_space_is_not_open_candidate(self):
        self.assertEqual(compose_control(VK['SPACE'], cursor_at_end=True), 'PHRASE_INPUT_OR_SYMBOL_SPACE')
        self.assertEqual(compose_control(VK['DOWN'], cursor_at_end=True), 'OPEN_CANDIDATE_VIA_CARET_KEY')
        self.assertEqual(compose_control(VK['UP'], cursor_at_end=False), 'OPEN_CANDIDATE_VIA_CARET_KEY')


class Stack(unittest.TestCase):
    def test_stack_order(self):
        names = [n for n, _ in CONTROL_STACK]
        self.assertEqual(names[-1], 'CCommandControl')
        self.assertLess(names.index('CCandidateControl'), names.index('CTypingControl'))
        self.assertLess(names.index('CTypingControl'), names.index('CComposeControl'))


if __name__ == '__main__':
    unittest.main()
