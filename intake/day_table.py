from dataclasses import dataclass

from intake.origins import Origin


@dataclass(frozen=True)
class InitialRow:
    slot: int
    reading_mm: int
    origin: Origin


def validate_ordinal(value, label):
    if type(value) is not int or not 1 <= value <= 2**63 - 1:
        raise ValueError(f'{label} must be a positive SQLite integer')
    return value


def initial_rows(batch):
    return tuple(
        InitialRow(slot, observation.reading_mm, observation.origin)
        for slot, observation in enumerate(batch.observations, start=1)
    )
