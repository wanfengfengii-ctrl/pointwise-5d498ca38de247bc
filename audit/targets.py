from mirror.local_history import find_live_slot, lookup_seen_row
from mirror.store import read_head


def resolve_annotation_target(connection, table_id, seen_revision, slot):
    """Return ``(identity, current_slot)`` for a locally seen address.

    ``identity`` is the stable ``(birth_revision, birth_slot)`` address of the
    original row, read back from the installed position the station actually
    received. ``current_slot`` is where that same row now sits in the current
    head, so an annotation follows the row across a move rather than its slot.
    """
    identity = lookup_seen_row(connection, table_id, seen_revision, slot)
    if identity is None:
        raise ValueError('unknown seen position')
    current_slot = find_live_slot(connection, table_id, read_head(connection, table_id), identity)
    if current_slot is None:
        raise ValueError('seen row has been withdrawn')
    return identity, current_slot
