from mirror.local_history import initialize_local_history
from mirror.receipts import initialize_receipts
from mirror.rows import initialize_rows
from warehouse_db import open_database, transaction


def open_mirror(path):
    connection = open_database(path)
    try:
        initialize_mirror(connection)
    except BaseException:
        connection.close()
        raise
    return connection


def initialize_mirror(connection):
    from audit.annotations import initialize_annotations

    with mirror_write(connection):
        connection.execute('''
            CREATE TABLE IF NOT EXISTS mirror_heads (
                table_id TEXT PRIMARY KEY NOT NULL,
                revision INTEGER NOT NULL
            )
        ''')
        initialize_rows(connection)
        initialize_local_history(connection)
        initialize_receipts(connection)
        initialize_annotations(connection)


def read_head(connection, table_id):
    record = connection.execute(
        'SELECT revision FROM mirror_heads WHERE table_id = ?', (table_id,)
    ).fetchone()
    return None if record is None else record[0]


def set_head(connection, table_id, revision):
    connection.execute(
        '''INSERT INTO mirror_heads (table_id, revision) VALUES (?, ?)
           ON CONFLICT (table_id) DO UPDATE SET revision = excluded.revision''',
        (table_id, revision),
    )


def mirror_write(connection):
    return transaction(connection, write=True)


def mirror_read(connection):
    return transaction(connection, write=False)
