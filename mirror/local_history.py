def initialize_local_history(connection):
    connection.execute('''
        CREATE TABLE IF NOT EXISTS installed_positions (
            table_id TEXT NOT NULL,
            revision INTEGER NOT NULL,
            slot INTEGER NOT NULL,
            PRIMARY KEY (table_id, revision, slot)
        )
    ''')


def save_installed_positions(connection, table_id, revision, rows):
    connection.executemany(
        'INSERT INTO installed_positions (table_id, revision, slot) VALUES (?, ?, ?)',
        ((table_id, revision, row.slot) for row in rows),
    )


def lookup_seen_row(connection, table_id, revision, slot):
    record = connection.execute(
        '''SELECT revision, slot FROM installed_positions
           WHERE table_id = ? AND revision = ? AND slot = ?''',
        (table_id, revision, slot),
    ).fetchone()
    return None if record is None else tuple(record)
