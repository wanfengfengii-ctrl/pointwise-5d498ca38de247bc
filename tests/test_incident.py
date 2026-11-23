"""Regression: equal-origin observations must follow the row, not the slot."""
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

import incident
from mirror.store import open_mirror
from warehouse_db import open_database


class IncidentTests(unittest.TestCase):
    def test_swap_and_in_place_deliveries_stay_distinct_and_annotations_follow_rows(self):
        with TemporaryDirectory(prefix='rail-incident-test-') as directory:
            root = Path(directory)
            actual, expected = incident.run(
                lambda name: open_database(root / f'{name}.sqlite'),
                lambda name: open_mirror(root / f'{name}.sqlite'),
            )
        self.assertEqual(actual, expected)
        self.assertTrue(actual['distinct_deliveries'])
        # The late note on the seen parent row 1 lands on the row it named, never
        # on the other equal observation that happens to share that slot.
        self.assertEqual(actual['swapped']['late_slot'], 2)
        self.assertEqual(actual['swapped']['after_late_note']['rows'][0][3], '已核')
        self.assertEqual(actual['swapped']['after_late_note']['rows'][1][3], '待现场复核')
        self.assertEqual(actual['swapped']['after_late_note']['total_mm'], 14)


if __name__ == '__main__':
    unittest.main()
