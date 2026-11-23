from dispatch.codec import decode_package
from dispatch.integrity import package_digest
from mirror.local_history import load_installed_identities, save_installed_positions
from mirror.receipts import find_receipt_for_package, save_receipt
from mirror.rows import replace_current_rows
from mirror.store import mirror_write, read_head, set_head


def row_identities(connection, envelope):
    """Map each row in ``envelope`` to the stable identity it carries locally."""
    parent_identities = (
        load_installed_identities(connection, envelope.table_id, envelope.parent)
        if envelope.parent is not None else {}
    )
    identities = {row.slot: (envelope.revision, row.slot) for row in envelope.rows}
    for source, destination in envelope.continuations:
        identity = parent_identities.get(source)
        if identity is None:
            raise ValueError('continuation references an absent parent row')
        identities[destination] = identity
    return identities


def install(connection, payload):
    envelope = decode_package(payload)
    digest = package_digest(payload)
    with mirror_write(connection):
        existing = find_receipt_for_package(connection, digest)
        if existing is not None:
            return existing
        if read_head(connection, envelope.table_id) != envelope.parent:
            raise ValueError('package parent is not the current received revision')
        rows = replace_current_rows(connection, envelope)
        identities = row_identities(connection, envelope)
        save_installed_positions(connection, envelope.table_id, envelope.revision, identities)
        set_head(connection, envelope.table_id, envelope.revision)
        return save_receipt(connection, envelope.table_id, envelope.revision, envelope.parent, digest)
