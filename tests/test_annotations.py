from contextlib import closing
import json

from audit.annotations import annotate
from audit.reconcile import read
from mirror.install import install
from mirror.store import open_mirror
from tests.support import TABLE, WarehouseCase, observation, swap


class AnnotationTests(WarehouseCase):
    def test_equal_swap_same_origin(self):
        first = self.freeze([observation(7)])
        parent = self.change(first, {'op': 'copy', 'slot': 1, 'to': 2})
        child = self.change(parent, *swap())
        deliveries = [self.get_issue(number) for number in (first, parent, child)]
        self.close_source()
        for delivery in deliveries[:2]:
            install(self.mirror, delivery.payload)
        annotate(self.mirror, TABLE, parent, 1, '复测')
        annotate(self.mirror, TABLE, parent, 2, '已核')
        before = self.ledger()
        self.assertEqual(before.total_mm, 14)
        install(self.mirror, deliveries[-1].payload)
        after = self.ledger()
        self.assertEqual(after.total_mm, 14)
        self.assertEqual([(row.slot, row.reading_mm, row.origin) for row in before.rows],
                         [(row.slot, row.reading_mm, row.origin) for row in after.rows])
        self.assertEqual(self.ledger_details(), [(1, 7, '晨测-001', '已核'), (2, 7, '晨测-001', '复测')])
        update = annotate(self.mirror, TABLE, parent, 1, '待现场复核')
        self.assertEqual(update.current_slot, 2)
        self.assertEqual(self.ledger_details(), [(1, 7, '晨测-001', '已核'), (2, 7, '晨测-001', '待现场复核')])
        self.assertEqual(self.ledger().total_mm, 14)

    def test_correct_reading(self):
        parent = self.freeze([observation(7, '东线'), observation(7, '西线')])
        child = self.change(parent, {'op': 'correct', 'slot': 1, 'reading_mm': -2})
        initial, successor = self.get_issue(parent), self.get_issue(child)
        self.close_source()
        install(self.mirror, initial.payload)
        annotate(self.mirror, TABLE, parent, 1, '仪器重测')
        install(self.mirror, successor.payload)
        self.assertEqual(self.ledger_details(), [(1, -2, '东线', '仪器重测'), (2, 7, '西线', None)])
        self.assertEqual(self.ledger().total_mm, 5)

    def test_late_write_order(self):
        parent = self.freeze([observation(7, '东线'), observation(7, '西线')])
        child = self.change(parent, *swap())
        initial, successor = self.get_issue(parent), self.get_issue(child)
        self.close_source()
        observed = []
        expected = [(1, 7, '西线', '已核'), (2, 7, '东线', '待现场复核')]
        for early in (True, False):
            with self.subTest(early=early), closing(open_mirror(self.root / f'order-{early}.sqlite')) as station:
                install(station, initial.payload)
                annotate(station, TABLE, parent, 1, '复测')
                annotate(station, TABLE, parent, 2, '已核')
                if early:
                    annotate(station, TABLE, parent, 1, '待现场复核')
                install(station, successor.payload)
                if not early:
                    annotate(station, TABLE, parent, 1, '待现场复核')
                ledger = read(station, TABLE)
                details = [(row.slot, row.reading_mm, row.origin.record, row.annotation) for row in ledger.rows]
                self.assertEqual(details, expected)
                self.assertEqual(ledger.total_mm, 14)
                observed.append({'details': details, 'total_mm': ledger.total_mm})
        self.assertEqual(observed[0], observed[1])
        print('POINTWISE_SCENARIO ' + json.dumps({
            'case_id': 'v7.late_write_order',
            'input': {'readings_mm': [7, 7], 'parent': parent, 'successor': child, 'swap': [[1, 2], [2, 1]],
                      'seen_slot': 1, 'text': '待现场复核'},
            'expected': expected,
            'actual': [result['details'] for result in observed],
            'downstream_expected': [14, 14],
            'downstream_actual': [result['total_mm'] for result in observed],
            'code_paths': ['revision/materialize.py', 'dispatch/issue.py', 'mirror/install.py',
                           'audit/annotations.py', 'audit/reconcile.py'],
            'oracle': '手工交换东西线位置，以原出处辨认旧位 1 的观测，两条 7 mm 相加为 14 mm。',
        }, ensure_ascii=False))

    def test_unknown_seen_address(self):
        parent = self.freeze([observation(7)])
        delivery = self.get_issue(parent)
        self.close_source()
        install(self.mirror, delivery.payload)
        annotate(self.mirror, TABLE, parent, 1, '原批注')
        before = self.ledger()
        for revision, slot in ((parent + 10, 1), (parent, 9)):
            with self.subTest(revision=revision, slot=slot):
                with self.assertRaisesRegex(ValueError, 'unknown seen position'):
                    annotate(self.mirror, TABLE, revision, slot, '不得写入')
                self.assertEqual(self.ledger(), before)
        self.assertEqual(self.mirror.execute('SELECT COUNT(*) FROM annotation_updates').fetchone()[0], 1)

    def test_unreceived_table(self):
        self.assertIsNone(read(self.mirror, TABLE))
        with self.assertRaises(ValueError):
            annotate(self.mirror, TABLE, 1, 1, '未实收')
        self.assertIsNone(read(self.mirror, TABLE))

    def test_exact_total(self):
        large = 2**63
        parent = self.freeze([observation(large, '正值'), observation(-(large - 1), '负值')])
        delivery = self.get_issue(parent)
        self.close_source()
        install(self.mirror, delivery.payload)
        self.reopen_mirror()
        self.assertEqual(self.ledger_details(), [(1, large, '正值', None), (2, -(large - 1), '负值', None)])
        self.assertEqual(self.ledger().total_mm, 1)

    def test_copy_withdraw_replace(self):
        original = observation(7)
        parent = self.freeze([original])
        child = self.change(
            parent,
            {'op': 'copy', 'slot': 1, 'to': 3},
            {'op': 'withdraw', 'slot': 1},
            {'op': 'insert', 'to': 1, **original},
        )
        initial, successor = self.get_issue(parent), self.get_issue(child)
        self.close_source()
        install(self.mirror, initial.payload)
        annotate(self.mirror, TABLE, parent, 1, '原行复测')
        install(self.mirror, successor.payload)
        self.assertEqual(self.ledger_details(), [(1, 7, '晨测-001', None), (3, 7, '晨测-001', None)])
        with self.assertRaisesRegex(ValueError, 'withdrawn'):
            annotate(self.mirror, TABLE, parent, 1, '迟到复核')
        self.assertEqual(self.ledger_details(), [(1, 7, '晨测-001', None), (3, 7, '晨测-001', None)])
        self.assertEqual(self.mirror.execute('SELECT COUNT(*) FROM annotation_updates').fetchone()[0], 1)
        annotate(self.mirror, TABLE, child, 1, '补入行')
        annotate(self.mirror, TABLE, child, 3, '副本')
        self.assertEqual(self.ledger_details(), [(1, 7, '晨测-001', '补入行'), (3, 7, '晨测-001', '副本')])
        self.assertEqual(self.ledger().total_mm, 14)

    def test_empty_total(self):
        parent = self.freeze([observation(7)])
        child = self.change(parent, {'op': 'withdraw', 'slot': 1})
        initial, successor = self.get_issue(parent), self.get_issue(child)
        self.close_source()
        install(self.mirror, initial.payload)
        annotate(self.mirror, TABLE, parent, 1, '复测')
        received = install(self.mirror, successor.payload)
        self.assertEqual(received.revision, child)
        self.assertEqual((self.ledger().revision, self.ledger().rows, self.ledger().total_mm), (child, (), 0))
        self.assertIsNone(read(self.mirror, '从未实收'))
        with self.assertRaisesRegex(ValueError, 'withdrawn'):
            annotate(self.mirror, TABLE, parent, 1, '晚到')
        self.assertEqual(install(self.mirror, successor.payload), received)
