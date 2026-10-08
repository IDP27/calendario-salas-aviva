"""Disposable local UI fixture: unique schema, fictional account, no operational edits."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import json
import os
from uuid import uuid4
import psycopg
from psycopg import sql
from psycopg.conninfo import conninfo_to_dict
from waitress import serve
from calendar_app import create_app, load_environment, ROOT
from calendar_app.db import migrate, write_transaction
from calendar_app.auth import create_user
from calendar_app.catalog import import_catalog, validate_topology

load_environment()
url = os.environ['DATABASE_URL']
if conninfo_to_dict(url).get('host') not in ('127.0.0.1', 'localhost'):
    raise SystemExit('A prévia de teste aceita apenas PostgreSQL local.')
schema = 'qa_salas_' + uuid4().hex
with psycopg.connect(url, autocommit=True) as conn:
    conn.execute(sql.SQL('CREATE SCHEMA {}').format(sql.Identifier(schema)))
app = create_app({'DB_SCHEMA': schema, 'QA_MODE': True, 'SECRET_KEY': uuid4().hex,
                  'SESSION_COOKIE_NAME': 'salas_qa', 'ALLOW_LOCAL_SETUP': False})
with app.app_context():
    migrate()
    import_catalog(json.loads((ROOT / 'docs/catalogo-salas-preliminar.json').read_text()))
    with write_transaction() as conn:
        user = create_user(conn, dict(username='teste.visual', name='Teste visual — dados fictícios',
            password='Teste-isolado-2026!', team_id='commercial', can_catalog=True,
            can_schedule=True, can_manage_users=True))
        create_user(conn, dict(username='teste.operacao', name='Operação — teste fictício',
            password='Teste-isolado-2026!', team_id='operations'))
    for code in (7, 8, 10):
        with app.app_context():
            from calendar_app.db import get_db
            config = get_db().execute('SELECT * FROM configurations WHERE id=%s', (f'space_{code:03}',)).fetchone()
            validate_topology(user, config['id'], dict(version=config['version'], options=config['suggested_options'],
                attested=True, reason='Composição fictícia exclusivamente para teste da interface; sem homologação operacional.'))
print('Prévia isolada de teste: http://127.0.0.1:4175 (dados fictícios)', flush=True)
try:
    serve(app, host='127.0.0.1', port=4175, threads=6)
finally:
    with psycopg.connect(url, autocommit=True) as conn:
        conn.execute(sql.SQL('DROP SCHEMA {} CASCADE').format(sql.Identifier(schema)))
