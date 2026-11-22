"""Tests: every one of the 96 extracted table entries is exercised through the model."""
import unittest
from candidate_key_model import *

T = load_tables()
CTX = {'default': Ctx(), 'profile_variant': Ctx(profile_id_3_or_7=True),
       'candidate_type_3': Ctx(candidate_type_3=True),
       'composition_variant': Ctx(integrated_mode=1, integrated_flag=0)}


def probe_for(e: Entry):
    """Build the key state that satisfies entry e."""
    if e.flags == 0xFFFFFFFF:
        return dict(vk=0, char=chr(e.key & 0xFFFF))
    return dict(vk=e.key, char='', shift=bool(e.flags & 1), ctrl=bool(e.flags & 4))


class Tables(unittest.TestCase):
    def test_counts(self):
        self.assertEqual({k: len(v) for k, v in T.items()},
                         {'default': 30, 'profile_variant': 19, 'candidate_type_3': 19, 'composition_variant': 28})

    def test_table_selection(self):
        for name, ctx in CTX.items():
            self.assertEqual(select_table(ctx), name)
        self.assertEqual(select_table(Ctx(candidate_type_3=True, profile_id_3_or_7=True)), 'candidate_type_3')
        self.assertEqual(select_table(Ctx(integrated_mode=1, integrated_flag=0, profile_id_3_or_7=True)),
                         'composition_variant')

    def test_every_entry_reachable_or_shadowed(self):
        shadowed = []
        for name, entries in T.items():
            ctx = CTX[name]
            for i, e in enumerate(entries):
                p = probe_for(e)
                first = next(j for j, x in enumerate(entries)
                             if entry_matches(x, p['vk'], p.get('char', ''), p.get('shift', False), p.get('ctrl', False)))
                if first != i:
                    shadowed.append((name, i, first))
                if p['vk'] in (VK['LEFT'], VK['RIGHT']) and name in ('default', 'profile_variant'):
                    continue   # arrow guards intercept before the table; tested separately
                if p['vk'] == VK['TAB']:
                    continue
                got = command_from_key(T, ctx, **p)
                want = entries[first]
                self.assertEqual(got, (want.command, want.argument), (name, i))
        # digits 1-9 appear twice in default and composition_variant: the second set is unreachable
        self.assertEqual(len(shadowed), 18)
        self.assertEqual({n for n, i, j in shadowed}, {'default', 'composition_variant'})

    def test_space_flags(self):
        d = CTX['default']
        self.assertEqual(command_from_key(T, d, VK['SPACE']), (7, 0))
        self.assertEqual(command_from_key(T, d, VK['SPACE'], shift=True)[0], NOT_HANDLED)
        self.assertEqual(command_from_key(T, d, VK['SPACE'], ctrl=True)[0], NOT_HANDLED)

    def test_type3_digits_require_shift(self):
        c = CTX['candidate_type_3']
        self.assertEqual(command_from_key(T, c, 0x31)[0], NOT_HANDLED)
        self.assertEqual(command_from_key(T, c, 0x31, shift=True), (4, 1))
        self.assertEqual(command_from_key(T, c, 0x31, shift=True, ctrl=True)[0], NOT_HANDLED)

    def test_digits_by_character(self):
        for n in range(1, 10):
            self.assertEqual(command_from_key(T, CTX['default'], 0, char=str(n)), (4, n))

    def test_tab(self):
        self.assertEqual(command_from_key(T, Ctx(), VK['TAB']), (0x14, 0))
        self.assertEqual(command_from_key(T, Ctx(), VK['TAB'], shift=True), (0, 0))
        self.assertEqual(command_from_key(T, Ctx(candidate_type_3=True), VK['TAB']), (0, 0))
        self.assertEqual(command_from_key(T, Ctx(shell_mode_1=True), VK['TAB']), (0, 0))

    def test_arrow_guards_default_profile(self):
        c = Ctx()   # vertical layout, not type 3, profile not 3/7
        self.assertEqual(command_from_key(T, c, VK['RIGHT']), (0x14, 0))
        self.assertEqual(command_from_key(T, c, VK['LEFT']), (0, 0))
        self.assertEqual(command_from_key(T, Ctx(shell_mode_1=True), VK['RIGHT']), (0, 0))
        h = Ctx(layout_is_2=True)
        self.assertEqual(command_from_key(T, h, VK['LEFT']), (0x14, 0))
        self.assertEqual(command_from_key(T, h, VK['RIGHT'])[0], 14)   # falls through to the table
        self.assertEqual(command_from_key(T, c, VK['LEFT'], shift=True)[0], 13)

    def test_arrow_profile_variant_consumed(self):
        p = CTX['profile_variant']
        self.assertEqual(command_from_key(T, p, VK['LEFT']), (0, 0))
        self.assertEqual(command_from_key(T, p, VK['RIGHT']), (0, 0))

    def test_composition_variant_arrows(self):
        c = CTX['composition_variant']
        self.assertEqual(command_from_key(T, c, VK['LEFT']), (11, 0))
        self.assertEqual(command_from_key(T, c, VK['RIGHT']), (12, 0))

    def test_unmatched(self):
        self.assertEqual(command_from_key(T, Ctx(), 0x41, char='a')[0], NOT_HANDLED)


if __name__ == '__main__':
    unittest.main()
