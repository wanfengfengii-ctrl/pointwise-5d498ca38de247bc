def initialize_local_history(connection):
    connection.execute('''
        CREATE TABLE IF NOT EXISTS installed_positions (
            table_id TEXT NOT NULL,
            revision INTEGER NOT NULL,
            slot INTEGER NOT NULL,
            birth_revision INTEGER NOT NULL,
            birth_slot INTEGER NOT NULL,
            PRIMARY KEY (table_id, revision, slot)
        )
    ''')


def save_installed_positions(connection, table_id, revision, identities):
    """Record the stable identity of every row in one installed revision.

    ``identities`` maps the received slot to the row's birth address
    ``(birth_revision, birth_slot)``. A continuing row keeps the identity it had
    in the fixed parent; a copied or inserted row receives a fresh one.
    """
    connection.executemany(
        '''INSERT INTO installed_positions
           (table_id, revision, slot, birth_revision, birth_slot) VALUES (?, ?, ?, ?, ?)''',
        (
            (table_id, revision, slot, birth_revision, birth_slot)
            for slot, (birth_revision, birth_slot) in sorted(identities.items())
        ),
    )


def load_installed_identities(connection, table_id, revision):
    """Return ``{slot: (birth_revision, birth_slot)}`` for one installed revision."""
    records = connection.execute(
        '''SELECT slot, birth_revision, birth_slot FROM installed_positions
           WHERE table_id = ? AND revision = ?''',
        (table_id, revision),
    )
    return {slot: (birth_revision, birth_slot) for slot, birth_revision, birth_slot in records}


def lookup_seen_row(connection, table_id, revision, slot):
    """Return the stable identity behind an installed address, or ``None``."""
    record = connection.execute(
        '''SELECT birth_revision, birth_slot FROM installed_positions
           WHERE table_id = ? AND revision = ? AND slot = ?''',
        (table_id, revision, slot),
    ).fetchone()
    return None if record is None else tuple(record)


def find_live_slot(connection, table_id, revision, identity):
    """Return the slot still carrying ``identity`` in ``revision``, or ``None``."""
    record = connection.execute(
        '''SELECT slot FROM installed_positions
           WHERE table_id = ? AND revision = ? AND birth_revision = ? AND birth_slot = ?''',
        (table_id, revision, *identity),
    ).fetchone()
    return None if record is None else record[0]
