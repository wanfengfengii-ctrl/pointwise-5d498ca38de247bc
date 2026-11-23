from dataclasses import dataclass

from warehouse_db import transaction


@dataclass(frozen=True)
class IssuedPackage:
    issue_id: str
    table_id: str
    revision: int
    parent: int | None
    payload: bytes
    digest: str


def initialize_catalog(connection):
    with transaction(connection, write=True):
        connection.execute('''
            CREATE TABLE IF NOT EXISTS issued_packages (
                issue_id TEXT PRIMARY KEY NOT NULL,
                table_id TEXT NOT NULL,
                revision INTEGER NOT NULL,
                parent INTEGER,
                payload BLOB NOT NULL,
                digest TEXT NOT NULL,
                UNIQUE (table_id, revision)
            )
        ''')


def get_by_issue(connection, issue_id):
    record = connection.execute(
        '''SELECT issue_id, table_id, revision, parent, payload, digest FROM issued_packages
           WHERE issue_id = ?''',
        (issue_id,),
    ).fetchone()
    return None if record is None else IssuedPackage(*record)


def get_by_revision(connection, table_id, revision):
    record = connection.execute(
        '''SELECT issue_id, table_id, revision, parent, payload, digest FROM issued_packages
           WHERE table_id = ? AND revision = ?''',
        (table_id, revision),
    ).fetchone()
    return None if record is None else IssuedPackage(*record)


def save_issued_package(connection, issued):
    with transaction(connection, write=True):
        original = get_by_revision(connection, issued.table_id, issued.revision)
        if original is not None:
            return original
        connection.execute(
            '''INSERT INTO issued_packages (issue_id, table_id, revision, parent, payload, digest)
               VALUES (?, ?, ?, ?, ?, ?)''',
            (issued.issue_id, issued.table_id, issued.revision, issued.parent, issued.payload, issued.digest),
        )
    return issued
