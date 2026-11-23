"""Reproduce the two equal-row deliveries using isolated station databases."""
from contextlib import closing
import json
from pathlib import Path
from tempfile import TemporaryDirectory

from audit.annotations import annotate
from audit.reconcile import read
from dispatch.catalog import initialize_catalog
from dispatch.issue import issue
from intake.batches import register
from intake.store import initialize_intake
from mirror.install import install
from mirror.store import open_mirror
from revision.book import revise
from revision.history import initialize_revision
from warehouse_db import open_database


TABLE = '石桥-夜间复核'
ORIGINAL = {'reading_mm': 7, 'origin': {'station': '石桥', 'record': '晨测-17'}}
SWAP = [{'op': 'move', 'slot': 1, 'to': 2}, {'op': 'move', 'slot': 2, 'to': 1}]


def build_deliveries(open_source):
    with closing(open_source('formal')) as source:
        initialize_intake(source)
        initialize_revision(source)
        initialize_catalog(source)
        register(source, '晨班', TABLE, [ORIGINAL])
        initial = revise(source, TABLE, batch_id='晨班')
        parent = revise(source, TABLE, parent=initial, edits=[{'op': 'copy', 'slot': 1, 'to': 2}])
        prefix = [issue(source, TABLE, version).payload for version in (initial, parent)]
        with closing(open_source('unchanged')) as unchanged:
            source.backup(unchanged)
            control_version = revise(unchanged, TABLE, parent=parent, edits=[])
            control = issue(unchanged, TABLE, control_version).payload
        swapped_version = revise(source, TABLE, parent=parent, edits=SWAP)
        swapped = issue(source, TABLE, swapped_version).payload
    return prefix, parent, control, swapped


def summarize(ledger):
    return {
        'rows': [[row.slot, row.reading_mm, row.origin.record, row.annotation] for row in ledger.rows],
        'total_mm': ledger.total_mm,
    }


def receive(open_station, name, prefix, parent, payload):
    with closing(open_station(name)) as station:
        for earlier in prefix:
            install(station, earlier)
        annotate(station, TABLE, parent, 1, '复测')
        annotate(station, TABLE, parent, 2, '已核')
        install(station, payload)
        before = summarize(read(station, TABLE))
        update = annotate(station, TABLE, parent, 1, '待现场复核')
        return {'after_install': before, 'late_slot': update.current_slot,
                'after_late_note': summarize(read(station, TABLE))}


def expected_state(first, second):
    return {'rows': [[1, 7, '晨测-17', first], [2, 7, '晨测-17', second]], 'total_mm': 14}


def run(open_source, open_station):
    prefix, parent, control, swapped = build_deliveries(open_source)
    actual = {
        'distinct_deliveries': control != swapped,
        'unchanged': receive(open_station, 'station-unchanged', prefix, parent, control),
        'swapped': receive(open_station, 'station-swapped', prefix, parent, swapped),
    }
    expected = {
        'distinct_deliveries': True,
        'unchanged': {'after_install': expected_state('复测', '已核'), 'late_slot': 1,
                      'after_late_note': expected_state('待现场复核', '已核')},
        'swapped': {'after_install': expected_state('已核', '复测'), 'late_slot': 2,
                    'after_late_note': expected_state('已核', '待现场复核')},
    }
    return actual, expected


def main():
    with TemporaryDirectory(prefix='rail-incident-') as directory:
        root = Path(directory)
        actual, expected = run(
            lambda name: open_database(root / f'{name}.sqlite'),
            lambda name: open_mirror(root / f'{name}.sqlite'),
        )
    print(json.dumps({'actual': actual, 'expected': expected}, ensure_ascii=False))
    if actual != expected:
        print('ANNOTATION_FOLLOWS_SLOT')
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
