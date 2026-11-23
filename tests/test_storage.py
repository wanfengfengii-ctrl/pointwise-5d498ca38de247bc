from audit.annotations import annotate
from audit.reconcile import read
from dispatch.issue import issue, read_issued_package
from intake.batches import get_registered_batch, register
from mirror.install import install
from mirror.receipts import get_receipt
from revision.book import revise
from revision.history import get_head, get_revision
from tests.support import BATCH, TABLE, WarehouseCase, observation


class StorageTests(WarehouseCase):
    def test_reinitializing_source_retains_batch_history_and_fixed_issues(self):
        first = self.freeze([observation(7), observation(7, '002')])
        original = get_revision(self.source, TABLE, first)
        second = self.change(first, {'op': 'move', 'slot': 2, 'to': 4})
        later = get_revision(self.source, TABLE, second)
        deliveries = [self.get_issue(version) for version in (first, second)]
        self.reopen_source()
        self.assertEqual([row.origin.record for row in get_registered_batch(self.source, BATCH).observations],
                         ['晨测-001', '002'])
        self.assertEqual(get_head(self.source, TABLE), second)
        self.assertEqual(get_revision(self.source, TABLE, first), original)
        self.assertEqual(get_revision(self.source, TABLE, second), later)
        for delivery in deliveries:
            self.assertEqual(read_issued_package(self.source, delivery.issue_id), delivery)

    def test_tables_with_matching_slots_and_revision_numbers_stay_separate(self):
        first = self.freeze([observation(7)])
        other = '岚北-0413'
        register(self.source, '晨班-0413', other, [observation(11, '另日原测')])
        other_first = revise(self.source, other, batch_id='晨班-0413')
        self.assertEqual(first, other_first)
        initial = self.get_issue(first)
        other_delivery = issue(self.source, other, other_first)
        child = self.change(first, {'op': 'move', 'slot': 1, 'to': 2})
        successor = self.get_issue(child)
        self.close_source()
        install(self.mirror, initial.payload)
        other_receipt = install(self.mirror, other_delivery.payload)
        annotate(self.mirror, TABLE, first, 1, '当日')
        annotate(self.mirror, other, other_first, 1, '另日')
        other_before = read(self.mirror, other)
        install(self.mirror, successor.payload)
        self.assertEqual(self.ledger_details(), [(2, 7, '晨测-001', '当日')])
        self.assertEqual(read(self.mirror, other), other_before)
        self.assertEqual((other_before.total_mm, other_before.rows[0].annotation), (11, '另日'))
        self.assertEqual(get_receipt(self.mirror, other_receipt.receipt_id), other_receipt)

    def test_readings_larger_than_decimal_conversion_limit_remain_exact(self):
        large = 1 << 15000
        first = self.freeze([observation(large, '上界外'), observation(1 - large, '下界外')])
        package = self.get_issue(first)
        self.close_source()
        install(self.mirror, package.payload)
        self.reopen_mirror()
        ledger = self.ledger()
        self.assertTrue(ledger.rows[0].reading_mm == large)
        self.assertTrue(ledger.rows[1].reading_mm == 1 - large)
        self.assertEqual(ledger.total_mm, 1)
