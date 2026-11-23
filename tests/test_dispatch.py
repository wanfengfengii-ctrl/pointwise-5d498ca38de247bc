from contextlib import closing

from audit.annotations import annotate
from audit.reconcile import read
from dispatch.catalog import get_by_revision
from dispatch.issue import issue, read_issued_package
from mirror.install import install
from mirror.store import open_mirror
from revision.book import revise
from tests.support import TABLE, WarehouseCase, observation, swap
from warehouse_db import open_database


class DispatchTests(WarehouseCase):
    def test_pinned_issue(self):
        parent = self.freeze([observation(7)])
        initial = self.get_issue(parent)
        child = self.change(parent, {'op': 'correct', 'slot': 1, 'reading_mm': 11})
        later = self.get_issue(child)
        self.assertNotEqual(initial.issue_id, later.issue_id)
        self.assertNotEqual(initial.payload, later.payload)
        self.reopen_source()
        reread = read_issued_package(self.source, initial.issue_id)
        self.assertEqual(reread, initial)
        self.assertEqual(self.get_issue(parent), initial)
        self.assertEqual((reread.revision, reread.parent), (parent, None))
        self.close_source()
        self.assertEqual(install(self.mirror, reread.payload).revision, parent)
        self.assertEqual(self.ledger().total_mm, 7)
        self.assertEqual(install(self.mirror, later.payload).revision, child)
        self.assertEqual(self.ledger().total_mm, 11)

    def test_unknown_issue(self):
        parent = self.freeze([observation(7)])
        with self.assertRaisesRegex(ValueError, 'unknown formal revision'):
            self.get_issue(parent + 1)
        with self.assertRaisesRegex(ValueError, 'unknown issue'):
            read_issued_package(self.source, 'unknown')
        self.assertIsNone(get_by_revision(self.source, TABLE, parent + 1))
        self.assertEqual(self.source.execute('SELECT COUNT(*) FROM issued_packages').fetchone()[0], 0)
        self.assertEqual(self.get_issue(parent).revision, parent)

    def test_same_parent_equal_snapshots_can_have_different_annotation_attribution(self):
        first = self.freeze([observation(7)])
        parent = self.change(first, {'op': 'copy', 'slot': 1, 'to': 2})
        initial, base = self.get_issue(first), self.get_issue(parent)
        with closing(open_database(self.root / 'unchanged-source.sqlite')) as alternative:
            self.source.backup(alternative)
            unchanged = revise(alternative, TABLE, parent=parent, edits=[])
            unchanged_delivery = issue(alternative, TABLE, unchanged)
        swapped = self.change(parent, *swap())
        swapped_delivery = self.get_issue(swapped)
        self.close_source()
        self.assertEqual(unchanged, swapped)
        self.assertNotEqual(unchanged_delivery.payload, swapped_delivery.payload)
        for name, delivery, expected in (
            ('unchanged', unchanged_delivery, ['复测', '已核']),
            ('swapped', swapped_delivery, ['已核', '复测']),
        ):
            with self.subTest(name=name), closing(open_mirror(self.root / f'{name}.sqlite')) as station:
                install(station, initial.payload)
                install(station, base.payload)
                annotate(station, TABLE, parent, 1, '复测')
                annotate(station, TABLE, parent, 2, '已核')
                install(station, delivery.payload)
                ledger = read(station, TABLE)
                self.assertEqual([(row.slot, row.reading_mm, row.origin.record) for row in ledger.rows],
                                 [(1, 7, '晨测-001'), (2, 7, '晨测-001')])
                self.assertEqual([row.annotation for row in ledger.rows], expected)
                self.assertEqual(ledger.total_mm, 14)
