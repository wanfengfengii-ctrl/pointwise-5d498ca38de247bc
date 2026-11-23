from dataclasses import asdict
import json

from dispatch.envelope import EnvelopeRow, RevisionEnvelope, validate_envelope
from dispatch.integrity import package_digest, verify_integrity
from intake.observations import decode_mm, encode_mm
from intake.origins import validate_origin


_BODY_FIELDS = {'version', 'table_id', 'revision', 'parent', 'rows', 'continuations'}
_ROW_FIELDS = {'slot', 'reading_mm', 'origin'}


def _encode_json(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode('ascii')


def encode_package(envelope):
    validate_envelope(envelope)
    body = {
        'version': 1,
        'table_id': envelope.table_id,
        'revision': envelope.revision,
        'parent': envelope.parent,
        'rows': [
            {'slot': row.slot, 'reading_mm': encode_mm(row.reading_mm), 'origin': asdict(row.origin)}
            for row in envelope.rows
        ],
        'continuations': envelope.continuations,
    }
    return _encode_json({'body': body, 'sha256': package_digest(_encode_json(body))})


def _decode_row(value):
    if not isinstance(value, dict) or value.keys() != _ROW_FIELDS:
        raise ValueError('invalid package row')
    return EnvelopeRow(value['slot'], decode_mm(value['reading_mm']), validate_origin(value['origin']))


def decode_package(payload):
    if type(payload) is not bytes:
        raise ValueError('package must be bytes')
    try:
        document = json.loads(payload.decode('ascii'))
        if _encode_json(document) != payload:
            raise ValueError('noncanonical package encoding')
    except (ValueError, RecursionError) as error:
        raise ValueError('invalid package encoding') from error
    if not isinstance(document, dict) or document.keys() != {'body', 'sha256'}:
        raise ValueError('invalid package wrapper')
    body = document['body']
    verify_integrity(_encode_json(body), document['sha256'])
    if not isinstance(body, dict) or body.keys() != _BODY_FIELDS:
        raise ValueError('invalid package body')
    if type(body['version']) is not int or body['version'] != 1:
        raise ValueError('unsupported package version')
    if not isinstance(body['rows'], list) or not isinstance(body['continuations'], list):
        raise ValueError('invalid package row material')
    envelope = RevisionEnvelope(
        body['table_id'], body['revision'], body['parent'],
        tuple(_decode_row(row) for row in body['rows']),
        tuple(pair for pair in body['continuations']),
    )
    validate_envelope(envelope)
    return RevisionEnvelope(
        envelope.table_id, envelope.revision, envelope.parent, envelope.rows,
        tuple((source, destination) for source, destination in envelope.continuations),
    )
