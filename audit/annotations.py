from dataclasses import dataclass

from audit.targets import resolve_annotation_target
from intake.day_table import validate_ordinal
from intake.origins import validate_text
from mirror.store import mirror_write


@dataclass(frozen=True)
class AnnotationUpdate:
    update_id: int
    table_id: str
    seen_revision: int
    seen_slot: int
    current_slot: int
    text: str


def initialize_annotations(connection):
    connection.execute('''
        CREATE TABLE IF NOT EXISTS local_annotations (
            table_id TEXT NOT NULL,
            birth_revision INTEGER NOT NULL,
            birth_slot INTEGER NOT NULL,
            text TEXT NOT NULL,
            PRIMARY KEY (table_id, birth_revision, birth_slot)
        )
    ''')
    connection.execute('''
        CREATE TABLE IF NOT EXISTS annotation_updates (
            update_id INTEGER PRIMARY KEY,
            table_id TEXT NOT NULL,
            seen_revision INTEGER NOT NULL,
            seen_slot INTEGER NOT NULL,
            current_slot INTEGER NOT NULL,
            text TEXT NOT NULL
        )
    ''')


def annotate(connection, table_id, seen_revision, slot, text):
    validate_text(table_id, 'table_id')
    validate_ordinal(seen_revision, 'seen revision')
    validate_ordinal(slot, 'seen slot')
    validate_text(text, 'annotation', allow_blank=True)
    with mirror_write(connection):
        (birth_revision, birth_slot), current_slot = resolve_annotation_target(
            connection, table_id, seen_revision, slot,
        )
        connection.execute(
            '''INSERT INTO local_annotations (table_id, birth_revision, birth_slot, text)
               VALUES (?, ?, ?, ?)
               ON CONFLICT (table_id, birth_revision, birth_slot) DO UPDATE SET text = excluded.text''',
            (table_id, birth_revision, birth_slot, text),
        )
        log = connection.execute(
            '''INSERT INTO annotation_updates
               (table_id, seen_revision, seen_slot, current_slot, text)
               VALUES (?, ?, ?, ?, ?)''',
            (table_id, seen_revision, slot, current_slot, text),
        )
        return AnnotationUpdate(log.lastrowid, table_id, seen_revision, slot, current_slot, text)


def read_row_annotations(connection, table_id):
    """Return ``{(birth_revision, birth_slot): text}`` for one day table."""
    records = connection.execute(
        '''SELECT birth_revision, birth_slot, text FROM local_annotations WHERE table_id = ?''',
        (table_id,),
    )
    return {(birth_revision, birth_slot): text for birth_revision, birth_slot, text in records}
