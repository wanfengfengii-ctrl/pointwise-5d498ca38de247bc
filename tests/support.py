from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from audit.reconcile import read
from dispatch.catalog import initialize_catalog
from dispatch.issue import issue
from intake.batches import register
from intake.store import initialize_intake
from mirror.store import open_mirror
from revision.book import revise
from revision.history import initialize_revision
from warehouse_db import open_database


TABLE = '岚北-0412'
BATCH = '晨班-0412'


def observation(reading, record='晨测-001', station='石桥'):
    return {'reading_mm': reading, 'origin': {'station': station, 'record': record}}


class WarehouseCase(unittest.TestCase):
    def setUp(self):
        directory = TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        self.source_path = self.root / 'source.sqlite'
        self.mirror_path = self.root / 'mirror.sqlite'
        self.source = None
        self.mirror = None
        self.addCleanup(self.close_source)
        self.addCleanup(self.close_mirror)
        self.reopen_source()
        self.reopen_mirror()

    def close_source(self):
        if self.source is not None:
            self.source.close()
            self.source = None

    def close_mirror(self):
        if self.mirror is not None:
            self.mirror.close()
            self.mirror = None

    def reopen_source(self):
        self.close_source()
        self.source = open_database(self.source_path)
        initialize_intake(self.source)
        initialize_revision(self.source)
        initialize_catalog(self.source)

    def reopen_mirror(self):
        self.close_mirror()
        self.mirror = open_mirror(self.mirror_path)

    def freeze(self, observations):
        register(self.source, BATCH, TABLE, observations)
        return revise(self.source, TABLE, batch_id=BATCH)

    def change(self, parent, *edits):
        return revise(self.source, TABLE, parent=parent, edits=edits)

    def get_issue(self, revision):
        return issue(self.source, TABLE, revision)

    def ledger(self):
        return read(self.mirror, TABLE)

    def ledger_details(self):
        return [(row.slot, row.reading_mm, row.origin.record, row.annotation) for row in self.ledger().rows]


def swap():
    return ({'op': 'move', 'slot': 1, 'to': 2}, {'op': 'move', 'slot': 2, 'to': 1})
