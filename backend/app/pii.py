"""Session-stable PII tokens. Only the gateway restores tool arguments."""
import json
import re
from threading import RLock
from backend.app import db

LOCK = RLock()
PATTERN = re.compile(r'(?P<EMAIL>[\w.+-]+@[\w.-]+\.[A-Za-z]{2,})|(?P<UPI>[\w.+-]+@[A-Za-z][\w.-]*)|(?P<ACCT>(?<!\d)\d{12,16}(?!\d))|(?P<PHONE>(?<!\d)[6-9]\d{9}(?!\d))')


def mask(text, session_id):
    with LOCK:
        row = db.fetch_one('SELECT pii_map_json FROM sessions WHERE id=?', (session_id,))
        if row is None:
            raise ValueError('session not found')
        mapping = json.loads(row['pii_map_json'])
        def replace(match):
            value = match.group()
            if value not in mapping:
                kind = match.lastgroup
                mapping[value] = f'<{kind}_{1 + sum(token.startswith("<" + kind + "_") for token in mapping.values())}>'
            return mapping[value]
        result = PATTERN.sub(replace, text)
        db.execute('UPDATE sessions SET pii_map_json=? WHERE id=?', (json.dumps(mapping), session_id))
        return result


def unmask(obj, session_id):
    row = db.fetch_one('SELECT pii_map_json FROM sessions WHERE id=?', (session_id,))
    if row is None:
        raise ValueError('session not found')
    mapping = {token: value for value, token in json.loads(row['pii_map_json']).items()}
    def restore(value):
        if isinstance(value, str):
            return re.sub(r'<(?:PHONE|EMAIL|UPI|ACCT)_\d+>', lambda m: mapping.get(m.group(), m.group()), value)
        if isinstance(value, dict):
            return {key: restore(item) for key, item in value.items()}
        if isinstance(value, list):
            return [restore(item) for item in value]
        return value
    return restore(obj)


def mask_obj(obj, session_id):
    if isinstance(obj, str):
        return mask(obj, session_id)
    if isinstance(obj, dict):
        return {key: mask_obj(value, session_id) for key, value in obj.items()}
    if isinstance(obj, list):
        return [mask_obj(value, session_id) for value in obj]
    return obj
