from dataclasses import dataclass

from revision.edits import EditBatch


@dataclass(frozen=True)
class RowLineage:
    continuations: tuple[tuple[int, int], ...]
    born: tuple[int, ...]
    retired: tuple[int, ...]


def initial_lineage(rows):
    return RowLineage((), tuple(row.slot for row in rows), ())


def derive_lineage(parent_rows, batch: EditBatch):
    moves = {edit.slot: edit.to for edit in batch.actions if edit.op == 'move'}
    withdrawals = {edit.slot for edit in batch.actions if edit.op == 'withdraw'}
    continuations = tuple(
        (row.slot, moves.get(row.slot, row.slot))
        for row in parent_rows
        if row.slot not in withdrawals
    )
    born = tuple(sorted(edit.to for edit in batch.actions if edit.op in {'copy', 'insert'}))
    return RowLineage(continuations, born, tuple(sorted(withdrawals)))
