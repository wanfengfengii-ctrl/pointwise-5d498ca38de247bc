from dataclasses import asdict, dataclass
import json

from intake.day_table import validate_ordinal
from intake.observations import decode_mm, encode_mm
from intake.origins import Origin, validate_origin


@dataclass(frozen=True)
class Edit:
    op: str
    slot: int | None = None
    to: int | None = None
    reading_mm: int | None = None
    origin: Origin | None = None


@dataclass(frozen=True)
class EditBatch:
    actions: tuple[Edit, ...]


_FIELDS = {
    'move': {'op', 'slot', 'to'},
    'copy': {'op', 'slot', 'to'},
    'correct': {'op', 'slot', 'reading_mm'},
    'withdraw': {'op', 'slot'},
    'insert': {'op', 'to', 'reading_mm', 'origin'},
}


def _normalize_edit(raw, parent_slots):
    if not isinstance(raw, dict) or type(raw.get('op')) is not str:
        raise ValueError('edit requires an operation name')
    op = raw['op']
    if op not in _FIELDS or raw.keys() != _FIELDS[op]:
        raise ValueError('invalid edit operation or fields')
    slot = None
    if 'slot' in raw:
        slot = validate_ordinal(raw['slot'], 'parent slot')
        if slot not in parent_slots:
            raise ValueError('edit references an absent parent slot')
    destination = validate_ordinal(raw['to'], 'destination') if 'to' in raw else None
    reading = raw.get('reading_mm')
    if 'reading_mm' in raw:
        encode_mm(reading)
    origin = validate_origin(raw['origin']) if 'origin' in raw else None
    return Edit(op, slot, destination, reading, origin)


def validate_edits(raw_edits, parent_rows):
    if not isinstance(raw_edits, (list, tuple)):
        raise ValueError('edits must be an ordered list or tuple')
    parent_slots = {row.slot for row in parent_rows}
    actions = tuple(_normalize_edit(raw, parent_slots) for raw in raw_edits)
    mutations = {}
    for edit in actions:
        if edit.op not in {'move', 'withdraw', 'correct'}:
            continue
        previous = mutations.setdefault(edit.slot, set())
        if edit.op in previous or 'withdraw' in previous or (edit.op == 'withdraw' and previous):
            raise ValueError('incompatible edits of the same parent row')
        previous.add(edit.op)
    return EditBatch(actions)


def encode_edit_batch(batch):
    records = []
    for edit in batch.actions:
        record = {name: value for name, value in asdict(edit).items() if value is not None}
        if edit.reading_mm is not None:
            record['reading_mm'] = encode_mm(edit.reading_mm)
        records.append(record)
    return json.dumps(records, sort_keys=True, separators=(',', ':'))


def decode_edit_batch(encoded):
    records = json.loads(encoded)
    for record in records:
        if 'reading_mm' in record:
            record['reading_mm'] = decode_mm(record['reading_mm'])
        if 'origin' in record:
            record['origin'] = validate_origin(record['origin'])
    return EditBatch(tuple(Edit(**record) for record in records))
