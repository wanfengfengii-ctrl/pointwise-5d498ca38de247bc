from dataclasses import dataclass


@dataclass(frozen=True)
class Receipt:
    receipt_id: str
    table_id: str
    revision: int
    parent: int | None
    digest: str


def initialize_receipts(connection):
    connection.execute('''
        CREATE TABLE IF NOT EXISTS receipts (
            receipt_id TEXT PRIMARY KEY NOT NULL,
            table_id TEXT NOT NULL,
            revision INTEGER NOT NULL,
            parent INTEGER,
            digest TEXT NOT NULL UNIQUE,
            UNIQUE (table_id, revision)
        )
    ''')


def find_receipt_for_package(connection, digest):
    record = connection.execute(
        'SELECT receipt_id, table_id, revision, parent, digest FROM receipts WHERE digest = ?',
        (digest,),
    ).fetchone()
    return None if record is None else Receipt(*record)


def get_receipt(connection, receipt_id):
    record = connection.execute(
        'SELECT receipt_id, table_id, revision, parent, digest FROM receipts WHERE receipt_id = ?',
        (receipt_id,),
    ).fetchone()
    return None if record is None else Receipt(*record)


def save_receipt(connection, table_id, revision, parent, digest):
    receipt = Receipt(f'receipt-{digest}', table_id, revision, parent, digest)
    connection.execute(
        'INSERT INTO receipts (receipt_id, table_id, revision, parent, digest) VALUES (?, ?, ?, ?, ?)',
        (receipt.receipt_id, receipt.table_id, receipt.revision, receipt.parent, receipt.digest),
    )
    return receipt
