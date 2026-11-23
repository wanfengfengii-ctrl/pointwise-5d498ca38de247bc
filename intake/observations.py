from dataclasses import dataclass

from intake.origins import Origin, validate_origin


@dataclass(frozen=True)
class Observation:
    reading_mm: int
    origin: Origin


def encode_mm(value):
    if type(value) is not int:
        raise ValueError('reading_mm must be an integer')
    return format(value, 'x')


def decode_mm(value):
    if type(value) is not str:
        raise ValueError('stored millimetres must be hexadecimal text')
    try:
        number = int(value, 16)
    except ValueError as error:
        raise ValueError('invalid millimetre encoding') from error
    if encode_mm(number) != value:
        raise ValueError('noncanonical millimetre encoding')
    return number


def normalize_observation(value):
    if isinstance(value, Observation):
        reading, origin = value.reading_mm, value.origin
    elif isinstance(value, dict) and value.keys() == {'reading_mm', 'origin'}:
        reading, origin = value['reading_mm'], value['origin']
    else:
        raise ValueError('observation requires reading_mm and origin')
    encode_mm(reading)
    return Observation(reading, validate_origin(origin))
