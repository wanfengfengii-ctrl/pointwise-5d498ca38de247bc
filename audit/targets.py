from mirror.local_history import lookup_seen_row
from mirror.rows import find_live_row


def resolve_annotation_target(connection, table_id, seen_revision, slot):
    if lookup_seen_row(connection, table_id, seen_revision, slot) is None:
        raise ValueError('unknown seen position')
    current_slot = find_live_row(connection, table_id, slot)
    if current_slot is None:
        raise ValueError('seen row has been withdrawn')
    return current_slot
