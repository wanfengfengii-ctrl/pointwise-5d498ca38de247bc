from intake.observations import normalize_observation
from intake.origins import validate_text
from intake.store import RegisteredBatch, insert_batch, load_batch


def register(connection, batch_id, table_id, observations):
    validate_text(batch_id, 'batch_id')
    validate_text(table_id, 'table_id')
    if not isinstance(observations, (list, tuple)):
        raise ValueError('observations must be an ordered list or tuple')
    normalized = tuple(normalize_observation(item) for item in observations)
    return insert_batch(connection, RegisteredBatch(batch_id, table_id, normalized))


def get_registered_batch(connection, batch_id):
    validate_text(batch_id, 'batch_id')
    return load_batch(connection, batch_id)
