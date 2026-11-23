from contextlib import closing
from dataclasses import asdict
import json
from pathlib import Path
from tempfile import TemporaryDirectory

from audit.annotations import annotate
from audit.reconcile import read
from dispatch.catalog import initialize_catalog
from dispatch.issue import issue, read_issued_package
from intake.batches import register
from intake.store import initialize_intake
from mirror.install import install
from mirror.store import open_mirror
from revision.book import revise
from revision.history import initialize_revision
from warehouse_db import open_database


def details(ledger):
    return [(row.slot, row.reading_mm, row.origin.record, row.annotation) for row in ledger.rows]


def report_initial(sample, ledger):
    expected = [(1, 7, '东线-03', None), (2, 7, '西线-02', None)]
    actual = details(ledger)
    if actual != expected or ledger.total_mm != 14:
        raise AssertionError(f'初版核账不符 {actual!r}, {ledger.total_mm} mm')
    record = {
        'case_id': 'v1.equal_reading_origins',
        'input': sample['observations'],
        'expected': expected,
        'actual': actual,
        'downstream_expected': 14,
        'downstream_actual': ledger.total_mm,
        'code_paths': ['intake/batches.py', 'revision/book.py', 'dispatch/issue.py',
                       'mirror/install.py', 'audit/reconcile.py'],
        'oracle': '照输入原序逐项读原测记录号，将两条 7 mm 手工相加。',
    }
    print('POINTWISE_SCENARIO ' + json.dumps(record, ensure_ascii=False))


def main():
    sample_path = Path(__file__).resolve().parent / 'samples' / 'shift.json'
    sample = json.loads(sample_path.read_text(encoding='utf-8'))
    table_id = sample['table_id']
    with TemporaryDirectory(prefix='rail-day-') as directory:
        source_path = Path(directory) / 'formal.sqlite'
        with closing(open_database(source_path)) as source:
            initialize_intake(source)
            initialize_revision(source)
            initialize_catalog(source)
            batch = register(source, sample['batch_id'], table_id, sample['observations'])
            parent = revise(source, table_id, batch_id=batch.batch_id)
            first = issue(source, table_id, parent)
        with closing(open_mirror(Path(directory) / 'station.sqlite')) as station:
            first_receipt = install(station, first.payload)
            report_initial(sample, read(station, table_id))
            for request in sample['day_notes']:
                annotate(station, table_id, parent, request['slot'], request['text'])

            with closing(open_database(source_path)) as source:
                child = revise(source, table_id, parent=parent, edits=sample['edits'])
                fixed = issue(source, table_id, child)
                if read_issued_package(source, first.issue_id) != first:
                    raise AssertionError('复领初版材料发生变化')

            received = install(station, fixed.payload)
            after_swap = read(station, table_id)
            expected_swapped = [(1, 7, '西线-02', '已核'), (2, 7, '东线-03', '复测')]
            if details(after_swap) != expected_swapped or after_swap.total_mm != 14:
                raise AssertionError(f'换位核账不符 {after_swap!r}')
            request = sample['late_note']
            update = annotate(station, table_id, parent, request['slot'], request['text'])
            final = read(station, table_id)
            expected_final = [(1, 7, '西线-02', '已核'), (2, 7, '东线-03', '待现场复核')]
            if details(final) != expected_final or final.total_mm != 14 or update.current_slot != 2:
                raise AssertionError(f'迟交核账不符 {final!r}')
            if install(station, first.payload) != first_receipt or install(station, fixed.payload) != received:
                raise AssertionError('重投未返回原回执')
            print(json.dumps({'receipt': asdict(received), 'ledger': asdict(final)}, ensure_ascii=False))


if __name__ == '__main__':
    main()
