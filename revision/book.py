from intake.batches import get_registered_batch
from intake.day_table import initial_rows, validate_ordinal
from intake.origins import validate_text
from revision.edits import EditBatch, validate_edits
from revision.history import FormalRevision, get_head, get_revision, save_revision
from revision.materialize import apply_edits, freeze_initial_rows


def revise(connection, table_id, *, batch_id=None, parent=None, edits=None):
    validate_text(table_id, 'table_id')
    if batch_id is not None:
        if parent is not None or edits is not None:
            raise ValueError('a freeze request accepts only a registered batch')
        batch = get_registered_batch(connection, batch_id)
        if batch is None or batch.table_id != table_id:
            raise ValueError('batch is not registered for this day table')
        rows, lineage = freeze_initial_rows(initial_rows(batch))
        candidate = FormalRevision(table_id, 1, None, batch_id, rows, EditBatch(()), lineage)
    else:
        if parent is None or edits is None:
            raise ValueError('a successor requires parent and edits')
        validate_ordinal(parent, 'parent revision')
        if get_head(connection, table_id) != parent:
            raise ValueError('formal parent is not the current head')
        revision = validate_ordinal(parent + 1, 'revision')
        previous = get_revision(connection, table_id, parent)
        batch = validate_edits(edits, previous.rows)
        rows, lineage = apply_edits(previous.rows, batch)
        candidate = FormalRevision(table_id, revision, parent, None, rows, batch, lineage)
    return save_revision(connection, candidate)
