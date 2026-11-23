from revision.history import get_head, get_revision
from tests.support import TABLE, WarehouseCase, observation


class RevisionTests(WarehouseCase):
    def test_conflicting_destination(self):
        parent = self.freeze([observation(7), observation(8, '002'), observation(9, '003')])
        before = get_revision(self.source, TABLE, parent)
        with self.assertRaisesRegex(ValueError, 'conflicting destination'):
            self.change(
                parent,
                {'op': 'move', 'slot': 1, 'to': 4},
                {'op': 'move', 'slot': 2, 'to': 4},
                {'op': 'correct', 'slot': 3, 'reading_mm': 15},
            )
        self.assertEqual(get_head(self.source, TABLE), parent)
        self.assertEqual(get_revision(self.source, TABLE, parent), before)
        self.assertEqual([(row.slot, row.reading_mm) for row in before.rows], [(1, 7), (2, 8), (3, 9)])
        self.assertIsNone(get_revision(self.source, TABLE, parent + 1))

    def test_stale_parent(self):
        parent = self.freeze([observation(7)])
        original = get_revision(self.source, TABLE, parent)
        child = self.change(parent, {'op': 'correct', 'slot': 1, 'reading_mm': 11})
        with self.assertRaisesRegex(ValueError, 'parent'):
            self.change(parent, {'op': 'withdraw', 'slot': 1})
        self.assertEqual(get_head(self.source, TABLE), child)
        self.assertEqual(get_revision(self.source, TABLE, parent), original)
        self.assertEqual(get_revision(self.source, TABLE, child).rows[0].reading_mm, 11)
        self.assertIsNone(get_revision(self.source, TABLE, child + 1))

    def test_move_and_correct_apply_to_original_while_copy_reads_parent(self):
        parent = self.freeze([observation(7, '001'), observation(-2, '002')])
        edits = (
            {'op': 'move', 'slot': 1, 'to': 2},
            {'op': 'copy', 'slot': 1, 'to': 3},
            {'op': 'correct', 'slot': 1, 'reading_mm': 13},
            {'op': 'move', 'slot': 2, 'to': 1},
        )
        child = self.change(parent, *edits)
        version = get_revision(self.source, TABLE, child)
        self.assertEqual(version.parent, parent)
        self.assertEqual(
            [(row.slot, row.reading_mm, row.origin.record) for row in version.rows],
            [(1, -2, '002'), (2, 13, '001'), (3, 7, '001')],
        )
        self.assertEqual([edit.op for edit in version.edits.actions], ['move', 'copy', 'correct', 'move'])
        self.assertEqual(get_revision(self.source, TABLE, parent).rows[0].reading_mm, 7)

    def test_edits_cannot_reference_rows_born_in_the_same_batch(self):
        parent = self.freeze([observation(7)])
        with self.assertRaisesRegex(ValueError, 'absent parent slot'):
            self.change(parent, {'op': 'copy', 'slot': 1, 'to': 2}, {'op': 'withdraw', 'slot': 2})
        with self.assertRaisesRegex(ValueError, 'incompatible'):
            self.change(parent, {'op': 'withdraw', 'slot': 1}, {'op': 'correct', 'slot': 1, 'reading_mm': 9})
        self.assertEqual(get_head(self.source, TABLE), parent)
        self.assertIsNone(get_revision(self.source, TABLE, parent + 1))
