from dataclasses import dataclass

from intake.origins import Origin
from revision.lineage import derive_lineage, initial_lineage


@dataclass(frozen=True)
class FormalRow:
    slot: int
    reading_mm: int
    origin: Origin


def freeze_initial_rows(initial):
    rows = tuple(FormalRow(row.slot, row.reading_mm, row.origin) for row in initial)
    return rows, initial_lineage(rows)


def apply_edits(parent_rows, batch):
    parent = {row.slot: row for row in parent_rows}
    lineage = derive_lineage(parent_rows, batch)
    values = {edit.slot: edit.reading_mm for edit in batch.actions if edit.op == 'correct'}
    rows = {}

    def add_row(slot, reading, origin):
        if slot in rows:
            raise ValueError(f'conflicting destination slot {slot}')
        rows[slot] = FormalRow(slot, reading, origin)

    for source, destination in lineage.continuations:
        row = parent[source]
        add_row(destination, values.get(source, row.reading_mm), row.origin)
    for edit in batch.actions:
        if edit.op == 'copy':
            row = parent[edit.slot]
            add_row(edit.to, row.reading_mm, row.origin)
        elif edit.op == 'insert':
            add_row(edit.to, edit.reading_mm, edit.origin)
    return tuple(rows[slot] for slot in sorted(rows)), lineage
