from dataclasses import dataclass

from dispatch.envelope import RevisionEnvelope
from intake.observations import decode_mm, encode_mm
from intake.origins import Origin


@dataclass(frozen=True)
class CurrentRow:
    slot: int
    reading_mm: int
    origin: Origin


def initialize_rows(connection):
    connection.execute('''
        CREATE TABLE IF NOT EXISTS current_rows (
            table_id TEXT NOT NULL,
            slot INTEGER NOT NULL,
            reading TEXT NOT NULL,
            station TEXT NOT NULL,
            record TEXT NOT NULL,
            PRIMARY KEY (table_id, slot)
        )
    ''')


def read_current_rows(connection, table_id):
    records = connection.execute(
        '''SELECT slot, reading, station, record FROM current_rows
           WHERE table_id = ? ORDER BY slot''',
        (table_id,),
    )
    return tuple(
        CurrentRow(slot, decode_mm(reading), Origin(station, record))
        for slot, reading, station, record in records
    )


def replace_current_rows(connection, envelope: RevisionEnvelope):
    parent_rows = {row.slot: row for row in read_current_rows(connection, envelope.table_id)}
    child_rows = {row.slot: row for row in envelope.rows}
    for source, destination in envelope.continuations:
        if source not in parent_rows:
            raise ValueError('continuation references an absent parent row')
        if parent_rows[source].origin != child_rows[destination].origin:
            raise ValueError('a continuing row changed its origin')

    rows = tuple(CurrentRow(row.slot, row.reading_mm, row.origin) for row in envelope.rows)
    connection.execute('DELETE FROM current_rows WHERE table_id = ?', (envelope.table_id,))
    connection.executemany(
        '''INSERT INTO current_rows (table_id, slot, reading, station, record)
           VALUES (?, ?, ?, ?, ?)''',
        (
            (envelope.table_id, row.slot, encode_mm(row.reading_mm), row.origin.station, row.origin.record)
            for row in rows
        ),
    )
    return rows
