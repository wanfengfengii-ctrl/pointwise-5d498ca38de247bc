from dataclasses import dataclass


@dataclass(frozen=True)
class Origin:
    station: str
    record: str


def validate_text(value, label, *, allow_blank=False):
    if type(value) is not str or (not allow_blank and not value.strip()):
        raise ValueError(f'{label} must be text' + ('' if allow_blank else ' and nonblank'))
    try:
        value.encode('utf-8')
    except UnicodeEncodeError as error:
        raise ValueError(f'{label} must be valid Unicode') from error
    return value


def validate_origin(value):
    if isinstance(value, Origin):
        station, record = value.station, value.record
    elif isinstance(value, dict) and value.keys() == {'station', 'record'}:
        station, record = value['station'], value['record']
    else:
        raise ValueError('origin requires station and record')
    return Origin(validate_text(station, 'origin station'), validate_text(record, 'origin record'))
