from dataclasses import replace
import sqlite3

from audit.annotations import annotate
from dispatch.codec import decode_package, encode_package
from dispatch.integrity import package_digest
from mirror.install import install
from mirror.local_history import lookup_seen_row
from mirror.receipts import find_receipt_for_package, get_receipt
from mirror.store import initialize_mirror, read_head
from tests.support import TABLE, WarehouseCase, observation


class InstallTests(WarehouseCase):
    def test_reopen_preserves_annotations(self):
        parent = self.freeze([observation(7), observation(7, '002')])
        delivery = self.get_issue(parent)
        self.close_source()
        receipt = install(self.mirror, delivery.payload)
        first = annotate(self.mirror, TABLE, parent, 1, '初核')
        edited = annotate(self.mirror, TABLE, parent, 1, '  人工修订\n复测  ')
        before = self.ledger()
        self.reopen_mirror()
        initialize_mirror(self.mirror)
        self.assertEqual(self.ledger(), before)
        self.assertEqual(self.ledger_details(), [(1, 7, '晨测-001', '  人工修订\n复测  '), (2, 7, '002', None)])
        self.assertEqual(get_receipt(self.mirror, receipt.receipt_id), receipt)
        self.assertEqual(install(self.mirror, delivery.payload), receipt)
        updates = self.mirror.execute('SELECT update_id, text FROM annotation_updates ORDER BY update_id').fetchall()
        self.assertEqual(updates, [(first.update_id, '初核'), (edited.update_id, '  人工修订\n复测  ')])

    def test_missing_parent_then_install_in_order(self):
        parent = self.freeze([observation(7)])
        child = self.change(parent, {'op': 'correct', 'slot': 1, 'reading_mm': 11})
        grandchild = self.change(child, {'op': 'correct', 'slot': 1, 'reading_mm': 13})
        first, second, third = [self.get_issue(version) for version in (parent, child, grandchild)]
        self.close_source()
        with self.assertRaisesRegex(ValueError, 'parent'):
            install(self.mirror, second.payload)
        self.assertIsNone(self.ledger())
        self.assertIsNone(find_receipt_for_package(self.mirror, second.digest))
        original = install(self.mirror, first.payload)
        annotate(self.mirror, TABLE, parent, 1, '复测')
        before = self.ledger()
        with self.assertRaisesRegex(ValueError, 'parent'):
            install(self.mirror, third.payload)
        self.assertEqual(self.ledger(), before)
        self.assertEqual(get_receipt(self.mirror, original.receipt_id), original)
        self.assertIsNone(find_receipt_for_package(self.mirror, third.digest))
        receipt = install(self.mirror, second.payload)
        self.assertEqual(install(self.mirror, second.payload), receipt)
        self.assertEqual((receipt.parent, receipt.revision), (parent, child))
        self.assertEqual(self.ledger_details(), [(1, 11, '晨测-001', '复测')])
        self.assertEqual(install(self.mirror, third.payload).revision, grandchild)

    def test_invalid_package_leaves_current_state(self):
        parent = self.freeze([observation(7)])
        child = self.change(parent, {'op': 'correct', 'slot': 1, 'reading_mm': 11})
        initial, successor = self.get_issue(parent), self.get_issue(child)
        self.close_source()
        receipt = install(self.mirror, initial.payload)
        annotate(self.mirror, TABLE, parent, 1, '复测')
        before = self.ledger()
        damaged = successor.payload.replace(b'"reading_mm":"b"', b'"reading_mm":"c"')
        self.assertNotEqual(damaged, successor.payload)
        with self.assertRaisesRegex(ValueError, 'checksum'):
            install(self.mirror, damaged)
        self.assertEqual(self.ledger(), before)
        self.assertEqual(get_receipt(self.mirror, receipt.receipt_id), receipt)
        self.assertIsNone(find_receipt_for_package(self.mirror, successor.digest))
        self.assertIsNone(find_receipt_for_package(self.mirror, package_digest(damaged)))
        self.assertEqual(install(self.mirror, successor.payload).revision, child)

    def test_intact_checksum_does_not_make_a_missing_parent_row_valid(self):
        parent = self.freeze([observation(7)])
        child = self.change(parent, {'op': 'move', 'slot': 1, 'to': 2})
        initial, successor = self.get_issue(parent), self.get_issue(child)
        self.close_source()
        install(self.mirror, initial.payload)
        before = self.ledger()
        envelope = replace(decode_package(successor.payload), continuations=((98, 2),))
        unsuitable = encode_package(envelope)
        with self.assertRaisesRegex(ValueError, 'absent parent row'):
            install(self.mirror, unsuitable)
        self.assertEqual(self.ledger(), before)
        self.assertIsNone(find_receipt_for_package(self.mirror, package_digest(unsuitable)))
        self.assertEqual(install(self.mirror, successor.payload).revision, child)

    def test_replay_after_advance(self):
        parent = self.freeze([observation(7)])
        child = self.change(parent, {'op': 'correct', 'slot': 1, 'reading_mm': 11})
        initial, successor = self.get_issue(parent), self.get_issue(child)
        self.close_source()
        original = install(self.mirror, initial.payload)
        current = install(self.mirror, successor.payload)
        self.assertEqual(install(self.mirror, initial.payload), original)
        self.assertEqual(install(self.mirror, successor.payload), current)
        self.assertEqual(read_head(self.mirror, TABLE), child)
        self.assertEqual(self.ledger().total_mm, 11)
        self.assertEqual(self.mirror.execute('SELECT COUNT(*) FROM receipts').fetchone()[0], 2)

    def test_rollback_history(self):
        parent = self.freeze([observation(7)])
        child = self.change(parent, {'op': 'move', 'slot': 1, 'to': 2})
        initial, successor = self.get_issue(parent), self.get_issue(child)
        self.close_source()
        receipt = install(self.mirror, initial.payload)
        annotate(self.mirror, TABLE, parent, 1, '复测')
        before = self.ledger()
        seen = lookup_seen_row(self.mirror, TABLE, parent, 1)
        self.assertIsNotNone(seen)
        # The receipt insert succeeds. The deferred constraint fails at COMMIT.
        self.mirror.executescript('''
            CREATE TEMP TABLE permitted_commits (id INTEGER PRIMARY KEY);
            CREATE TEMP TABLE pending_commits (
                id INTEGER REFERENCES permitted_commits(id) DEFERRABLE INITIALLY DEFERRED
            );
            CREATE TEMP TRIGGER fail_receipt_commit AFTER INSERT ON main.receipts
            BEGIN
                INSERT INTO pending_commits VALUES (1);
            END;
        ''')
        with self.assertRaisesRegex(sqlite3.IntegrityError, 'FOREIGN KEY'):
            install(self.mirror, successor.payload)
        self.assertFalse(self.mirror.in_transaction)
        self.reopen_mirror()
        self.assertEqual(self.ledger(), before)
        self.assertEqual(read_head(self.mirror, TABLE), parent)
        self.assertEqual(lookup_seen_row(self.mirror, TABLE, parent, 1), seen)
        self.assertIsNone(lookup_seen_row(self.mirror, TABLE, child, 2))
        self.assertEqual(get_receipt(self.mirror, receipt.receipt_id), receipt)
        self.assertIsNone(find_receipt_for_package(self.mirror, successor.digest))
        self.assertEqual(self.mirror.execute('SELECT COUNT(*) FROM receipts').fetchone()[0], 1)
        installed = install(self.mirror, successor.payload)
        self.assertEqual(install(self.mirror, successor.payload), installed)
        self.assertEqual(read_head(self.mirror, TABLE), child)
        self.assertEqual(self.ledger_details(), [(2, 7, '晨测-001', '复测')])
        self.assertEqual(lookup_seen_row(self.mirror, TABLE, child, 2), seen)
        self.assertEqual(self.mirror.execute('SELECT COUNT(*) FROM receipts').fetchone()[0], 2)
