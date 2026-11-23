from dataclasses import dataclass

from intake.observations import Observation, decode_mm, encode_mm
from intake.origins import Origin
from warehouse_db import transaction


@dataclass(frozen=True)
class RegisteredBatch:
    batch_id: str
    table_id: str
    observations: tuple[Observation, ...]


def initialize_intake(connection):
    with transaction(connection, write=True):
        connection.execute('''
            CREATE TABLE IF NOT EXISTS source_batches (
                batch_id TEXT PRIMARY KEY NOT NULL,
                table_id TEXT NOT NULL
            )
        ''')
        connection.execute('''
            CREATE TABLE IF NOT EXISTS source_observations (
                batch_id TEXT NOT NULL REFERENCES source_batches(batch_id),
                ordinal INTEGER NOT NULL,
                reading TEXT NOT NULL,
                station TEXT NOT NULL,
                record TEXT NOT NULL,
                PRIMARY KEY (batch_id, ordinal)
            )
        ''')


def insert_batch(connection, batch):
    with transaction(connection, write=True):
        exists = connection.execute(
            'SELECT 1 FROM source_batches WHERE batch_id = ?', (batch.batch_id,)
        ).fetchone()
        if exists:
            raise ValueError('batch is already registered')
        connection.execute(
            'INSERT INTO source_batches (batch_id, table_id) VALUES (?, ?)',
            (batch.batch_id, batch.table_id),
        )
        connection.executemany(
            '''INSERT INTO source_observations
               (batch_id, ordinal, reading, station, record) VALUES (?, ?, ?, ?, ?)''',
            (
                (batch.batch_id, ordinal, encode_mm(item.reading_mm), item.origin.station, item.origin.record)
                for ordinal, item in enumerate(batch.observations, start=1)
            ),
        )
    return batch


def load_batch(connection, batch_id):
    batch = connection.execute(
        'SELECT table_id FROM source_batches WHERE batch_id = ?', (batch_id,)
    ).fetchone()
    if batch is None:
        return None
    records = connection.execute(
        '''SELECT reading, station, record FROM source_observations
           WHERE batch_id = ? ORDER BY ordinal''',
        (batch_id,),
    )
    observations = tuple(
        Observation(decode_mm(reading), Origin(station, record))
        for reading, station, record in records
    )
    return RegisteredBatch(batch_id, batch[0], observations)
