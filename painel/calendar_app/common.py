import json
from datetime import date, datetime
from uuid import uuid4
from psycopg.types.json import Jsonb


class Problem(Exception):
    def __init__(self, message, status=400, details=None):
        self.message, self.status, self.details = message, status, details


def uid():
    return str(uuid4())


def serialize(value):
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, dict):
        return {k: serialize(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [serialize(v) for v in value]
    return value


def json_value(value):
    return Jsonb(serialize(value))


def required_text(data, key, max_length=200):
    value = data.get(key)
    if not isinstance(value, str) or not value.strip() or len(value.strip()) > max_length:
        raise Problem(f'Informe {key} com até {max_length} caracteres.')
    return value.strip()


def ensure_version(current, data):
    if type(data.get('version')) is not int or data['version'] != current['version']:
        raise Problem('Este registro mudou desde a sua consulta. Recarregue antes de salvar; seu formulário foi preservado.', 409)


def audit(conn, actor, kind, entity_id, action, before=None, after=None, note=''):
    conn.execute('INSERT INTO audit(actor_id,entity_type,entity_id,action,before_data,after_data,note) VALUES (%s,%s,%s,%s,%s,%s,%s)',
                 (actor['id'] if actor else None, kind, entity_id, action, json_value(before), json_value(after), note))


def in_scope(actor, resort):
    return (resort or 'unassigned') in actor['scopes']


def require_capability(actor, capability):
    if not actor.get(capability):
        raise Problem('Seu acesso não permite essa operação.', 403)
