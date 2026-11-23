from dispatch.catalog import IssuedPackage, get_by_issue, get_by_revision, save_issued_package
from dispatch.codec import encode_package
from dispatch.envelope import build_envelope
from dispatch.integrity import package_digest, verify_integrity
from intake.day_table import validate_ordinal
from intake.origins import validate_text
from revision.history import get_revision


def _project_continuations(connection, formal):
    if formal.parent is None:
        return ()
    parent = get_revision(connection, formal.table_id, formal.parent)
    child_by_slot = {row.slot: row for row in formal.rows}
    continuations = {
        old.slot: old.slot for old in parent.rows
        if old.slot in child_by_slot and old.origin == child_by_slot[old.slot].origin
    }
    free_sources = {}
    for row in parent.rows:
        if row.slot not in continuations:
            free_sources.setdefault(row.origin, []).append(row.slot)
    used = set(continuations.values())
    free_destinations = {}
    for row in formal.rows:
        if row.slot not in used:
            free_destinations.setdefault(row.origin, []).append(row.slot)
    for origin, slots in free_sources.items():
        destinations = free_destinations.get(origin, ())
        if len(slots) == len(destinations) == 1:
            continuations[slots[0]] = destinations[0]
    return tuple(sorted(continuations.items()))


def issue(connection, table_id, revision):
    validate_text(table_id, 'table_id')
    validate_ordinal(revision, 'revision')
    original = get_by_revision(connection, table_id, revision)
    if original is None:
        formal = get_revision(connection, table_id, revision)
        if formal is None:
            raise ValueError('unknown formal revision')
        envelope = build_envelope(
            table_id, revision, formal.parent, formal.rows, _project_continuations(connection, formal),
        )
        payload = encode_package(envelope)
        digest = package_digest(payload)
        original = save_issued_package(
            connection, IssuedPackage(f'issue-{digest}', table_id, revision, formal.parent, payload, digest),
        )
    verify_integrity(original.payload, original.digest)
    return original


def read_issued_package(connection, issue_id):
    validate_text(issue_id, 'issue_id')
    issued = get_by_issue(connection, issue_id)
    if issued is None:
        raise ValueError('unknown issue')
    verify_integrity(issued.payload, issued.digest)
    return issued
