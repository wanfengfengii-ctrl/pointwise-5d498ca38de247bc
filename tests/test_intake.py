from intake.batches import get_registered_batch, register
from intake.origins import Origin
from mirror.install import install
from revision.book import revise
from revision.history import get_head, get_revision
from tests.support import BATCH, TABLE, WarehouseCase, observation


class IntakeTests(WarehouseCase):
    def test_equal_reading_origins(self):
        initial = self.freeze([observation(7, '东线-03'), observation(7, '西线-02')])
        batch = get_registered_batch(self.source, BATCH)
        expected_origins = [Origin('石桥', '东线-03'), Origin('石桥', '西线-02')]
        self.assertEqual([row.origin for row in batch.observations], expected_origins)
        self.assertEqual([row.slot for row in get_revision(self.source, TABLE, initial).rows], [1, 2])
        delivery = self.get_issue(initial)
        self.close_source()
        receipt = install(self.mirror, delivery.payload)
        self.assertEqual((receipt.table_id, receipt.revision, receipt.parent), (TABLE, initial, None))
        self.assertEqual(self.ledger_details(), [(1, 7, '东线-03', None), (2, 7, '西线-02', None)])
        self.assertEqual([row.origin for row in self.ledger().rows], expected_origins)
        self.assertEqual(self.ledger().total_mm, 14)

    def test_invalid_registration(self):
        for bad in (
            observation(True), observation(7.0), observation('7'), observation(None),
            {'origin': {'station': '石桥', 'record': '001'}},
            {'reading_mm': 7}, {'reading_mm': 7, 'origin': None},
            observation(7, ' '), observation(7, station=''),
        ):
            with self.subTest(bad=bad):
                with self.assertRaises(ValueError):
                    register(self.source, BATCH, TABLE, [observation(7), bad])
                self.assertIsNone(get_registered_batch(self.source, BATCH))
        original = register(self.source, BATCH, TABLE, [observation(0), observation(-3, '002')])
        with self.assertRaisesRegex(ValueError, 'already registered'):
            register(self.source, BATCH, TABLE, [observation(19)])
        self.assertEqual(get_registered_batch(self.source, BATCH), original)
        self.assertEqual([item.reading_mm for item in original.observations], [0, -3])
        for batch_id, table_id in (('', TABLE), ('other', '  ')):
            with self.assertRaises(ValueError):
                register(self.source, batch_id, table_id, [observation(7)])
        self.assertIsNone(get_registered_batch(self.source, 'other'))

    def test_freeze_requires_the_registered_day_and_creates_one_first_revision(self):
        register(self.source, BATCH, TABLE, [observation(7)])
        with self.assertRaises(ValueError):
            revise(self.source, '别日', batch_id=BATCH)
        with self.assertRaises(ValueError):
            revise(self.source, TABLE, batch_id='未登记')
        self.assertIsNone(get_head(self.source, TABLE))
        initial = revise(self.source, TABLE, batch_id=BATCH)
        self.assertEqual(initial, 1)
        before = get_revision(self.source, TABLE, initial)
        with self.assertRaises(ValueError):
            revise(self.source, TABLE, batch_id=BATCH)
        self.assertEqual(get_head(self.source, TABLE), initial)
        self.assertEqual(get_revision(self.source, TABLE, initial), before)
