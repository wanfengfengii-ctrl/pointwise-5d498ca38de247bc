from dataclasses import dataclass

from audit.annotations import read_row_annotations
from audit.totals import total_mm
from intake.origins import Origin, validate_text
from mirror.local_history import load_installed_identities
from mirror.rows import read_current_rows
from mirror.store import mirror_read, read_head


@dataclass(frozen=True)
class LedgerRow:
    slot: int
    reading_mm: int
    origin: Origin
    annotation: str | None


@dataclass(frozen=True)
class Ledger:
    table_id: str
    revision: int
    rows: tuple[LedgerRow, ...]
    total_mm: int


def read(connection, table_id):
    validate_text(table_id, 'table_id')
    with mirror_read(connection):
        revision = read_head(connection, table_id)
        if revision is None:
            return None
        current = read_current_rows(connection, table_id)
        annotations = read_row_annotations(connection, table_id)
        identities = load_installed_identities(connection, table_id, revision)
        details = tuple(
            LedgerRow(row.slot, row.reading_mm, row.origin, annotations.get(identities.get(row.slot)))
            for row in current
        )
        return Ledger(table_id, revision, details, total_mm(details))
