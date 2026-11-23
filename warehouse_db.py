from contextlib import contextmanager
import sqlite3


def open_database(path):
    connection = sqlite3.connect(path, isolation_level=None)
    try:
        connection.execute('PRAGMA foreign_keys = ON')
    except BaseException:
        connection.close()
        raise
    return connection


@contextmanager
def transaction(connection, *, write):
    connection.execute('BEGIN IMMEDIATE' if write else 'BEGIN')
    try:
        yield connection
        connection.commit()
    except BaseException:
        if connection.in_transaction:
            connection.rollback()
        raise
