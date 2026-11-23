from dispatch.catalog import IssuedPackage, get_by_issue, get_by_revision, save_issued_package
from dispatch.codec import encode_package
from dispatch.envelope import build_envelope
from dispatch.integrity import package_digest, verify_integrity
from intake.day_table import validate_ordinal
from intake.origins import validate_text
from revision.history import get_revision


def _project_continuations(formal):
    """Return the parent-to-child row links recorded when the revision froze.

    Continuations come from the formal lineage, never from matching readings or
    origins. Two deliveries sharing a parent may hold identical values and origins
    yet differ in which row moved where; only the recorded lineage tells a swapped
    continuation from an in-place one, or a copy from the original it duplicates.
    """
    if formal.parent is None:
        return ()
    return tuple(sorted(formal.lineage.continuations))


def issue(connection, table_id, revision):
    validate_text(table_id, 'table_id')
    validate_ordinal(revision, 'revision')
    original = get_by_revision(connection, table_id, revision)
    if original is None:
        formal = get_revision(connection, table_id, revision)
        if formal is None:
            raise ValueError('unknown formal revision')
        envelope = build_envelope(
            table_id, revision, formal.parent, formal.rows, _project_continuations(formal),
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
