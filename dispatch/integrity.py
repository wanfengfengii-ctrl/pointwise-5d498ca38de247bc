from hashlib import sha256


def package_digest(payload):
    return sha256(payload).hexdigest()


def verify_integrity(payload, expected):
    if type(expected) is not str or package_digest(payload) != expected:
        raise ValueError('package checksum mismatch')
