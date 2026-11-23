from dataclasses import dataclass

from intake.day_table import validate_ordinal
from intake.observations import encode_mm
from intake.origins import Origin, validate_origin, validate_text


@dataclass(frozen=True)
class EnvelopeRow:
    slot: int
    reading_mm: int
    origin: Origin


@dataclass(frozen=True)
class RevisionEnvelope:
    table_id: str
    revision: int
    parent: int | None
    rows: tuple[EnvelopeRow, ...]
    continuations: tuple[tuple[int, int], ...]


def build_envelope(table_id, revision, parent, rows, continuations):
    envelope = RevisionEnvelope(
        table_id, revision, parent,
        tuple(EnvelopeRow(row.slot, row.reading_mm, row.origin) for row in rows),
        tuple(tuple(pair) for pair in continuations),
    )
    return validate_envelope(envelope)


def validate_envelope(envelope):
    validate_text(envelope.table_id, 'table_id')
    validate_ordinal(envelope.revision, 'revision')
    if envelope.parent is None:
        if envelope.revision != 1 or envelope.continuations:
            raise ValueError('initial package has an invalid version or continuations')
    else:
        validate_ordinal(envelope.parent, 'parent revision')
        if envelope.revision != envelope.parent + 1:
            raise ValueError('package must bind consecutive versions')

    slots = set()
    last = 0
    for ordinal, row in enumerate(envelope.rows, start=1):
        validate_ordinal(row.slot, 'row slot')
        if row.slot <= last or (envelope.parent is None and row.slot != ordinal):
            raise ValueError('package rows must be in valid slot order')
        encode_mm(row.reading_mm)
        validate_origin(row.origin)
        slots.add(row.slot)
        last = row.slot

    sources, destinations = set(), set()
    for pair in envelope.continuations:
        if not isinstance(pair, (list, tuple)) or len(pair) != 2:
            raise ValueError('invalid continuation pair')
        source, destination = pair
        validate_ordinal(source, 'continuation source')
        validate_ordinal(destination, 'continuation destination')
        if source in sources or destination in destinations or destination not in slots:
            raise ValueError('invalid continuation endpoints')
        sources.add(source)
        destinations.add(destination)
    return envelope
