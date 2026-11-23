from dataclasses import asdict, dataclass
import json

from intake.day_table import validate_ordinal
from intake.observations import decode_mm, encode_mm
from intake.origins import Origin
from revision.edits import EditBatch, decode_edit_batch, encode_edit_batch
from revision.lineage import RowLineage
from revision.materialize import FormalRow
from warehouse_db import transaction


@dataclass(frozen=True)
class FormalRevision:
    table_id: str
    revision: int
    parent: int | None
    source_batch: str | None
    rows: tuple[FormalRow, ...]
    edits: EditBatch
    lineage: RowLineage


def initialize_revision(connection):
    with transaction(connection, write=True):
        connection.execute('''
            CREATE TABLE IF NOT EXISTS formal_revisions (
                table_id TEXT NOT NULL,
                revision INTEGER NOT NULL,
                parent INTEGER,
                source_batch TEXT,
                edits TEXT NOT NULL,
                lineage TEXT NOT NULL,
                PRIMARY KEY (table_id, revision),
                FOREIGN KEY (table_id, parent) REFERENCES formal_revisions(table_id, revision)
            )
        ''')
        connection.execute('''
            CREATE TABLE IF NOT EXISTS formal_rows (
                table_id TEXT NOT NULL,
                revision INTEGER NOT NULL,
                slot INTEGER NOT NULL,
                reading TEXT NOT NULL,
                station TEXT NOT NULL,
                record TEXT NOT NULL,
                PRIMARY KEY (table_id, revision, slot),
                FOREIGN KEY (table_id, revision) REFERENCES formal_revisions(table_id, revision)
            )
        ''')
        connection.execute('''
            CREATE TABLE IF NOT EXISTS formal_heads (
                table_id TEXT PRIMARY KEY NOT NULL,
                revision INTEGER NOT NULL,
                FOREIGN KEY (table_id, revision) REFERENCES formal_revisions(table_id, revision)
            )
        ''')


def get_head(connection, table_id):
    record = connection.execute(
        'SELECT revision FROM formal_heads WHERE table_id = ?', (table_id,)
    ).fetchone()
    return None if record is None else record[0]


def get_revision(connection, table_id, revision):
    validate_ordinal(revision, 'revision')
    record = connection.execute(
        '''SELECT parent, source_batch, edits, lineage FROM formal_revisions
           WHERE table_id = ? AND revision = ?''',
        (table_id, revision),
    ).fetchone()
    if record is None:
        return None
    parent, source_batch, encoded_edits, encoded_lineage = record
    facts = json.loads(encoded_lineage)
    lineage = RowLineage(
        tuple((source, destination) for source, destination in facts['continuations']),
        tuple(facts['born']),
        tuple(facts['retired']),
    )
    row_records = connection.execute(
        '''SELECT slot, reading, station, record FROM formal_rows
           WHERE table_id = ? AND revision = ? ORDER BY slot''',
        (table_id, revision),
    )
    rows = tuple(
        FormalRow(slot, decode_mm(reading), Origin(station, origin_record))
        for slot, reading, station, origin_record in row_records
    )
    return FormalRevision(table_id, revision, parent, source_batch, rows, decode_edit_batch(encoded_edits), lineage)


def save_revision(connection, formal):
    validate_ordinal(formal.revision, 'revision')
    with transaction(connection, write=True):
        head = get_head(connection, formal.table_id)
        if head != formal.parent:
            raise ValueError('formal parent is not the current head')
        if formal.revision != (1 if head is None else head + 1):
            raise ValueError('invalid formal revision number')
        connection.execute(
            '''INSERT INTO formal_revisions
               (table_id, revision, parent, source_batch, edits, lineage) VALUES (?, ?, ?, ?, ?, ?)''',
            (
                formal.table_id, formal.revision, formal.parent, formal.source_batch,
                encode_edit_batch(formal.edits), json.dumps(asdict(formal.lineage), separators=(',', ':')),
            ),
        )
        connection.executemany(
            '''INSERT INTO formal_rows
               (table_id, revision, slot, reading, station, record) VALUES (?, ?, ?, ?, ?, ?)''',
            (
                (formal.table_id, formal.revision, row.slot, encode_mm(row.reading_mm), row.origin.station, row.origin.record)
                for row in formal.rows
            ),
        )
        connection.execute(
            '''INSERT INTO formal_heads (table_id, revision) VALUES (?, ?)
               ON CONFLICT (table_id) DO UPDATE SET revision = excluded.revision''',
            (formal.table_id, formal.revision),
        )
    return formal.revision
