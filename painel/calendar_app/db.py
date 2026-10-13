"""PostgreSQL connections, versioned migrations and atomic application writes."""
from contextlib import contextmanager
from pathlib import Path
import psycopg
from psycopg import sql
from psycopg.rows import dict_row
from flask import current_app, g, has_request_context


def connect(url, schema='public'):
    conn = psycopg.connect(url, autocommit=True, row_factory=dict_row, connect_timeout=5)
    conn.execute(sql.SQL('SET search_path TO {}').format(sql.Identifier(schema)))
    conn.execute("SET statement_timeout = '20s'")
    return conn


def get_db():
    if 'db' not in g:
        g.db = connect(current_app.config['DATABASE_URL'], current_app.config['DB_SCHEMA'])
    return g.db


def close_db(error=None):
    conn = g.pop('db', None)
    if conn:
        conn.close()


@contextmanager
def write_transaction():
    conn = get_db()
    with conn.transaction():
        # Serialize the pilot's mutations, including priority checks and topology changes.
        # The database's resource/day primary key independently protects occupations.
        conn.execute('SELECT pg_advisory_xact_lock(hashtext(current_schema()), 20261007)')
        if has_request_context() and getattr(g, 'user', None):
            current = conn.execute('SELECT active, version FROM users WHERE id=%s', (g.user['id'],)).fetchone()
            active_session = conn.execute('''SELECT 1 FROM auth_sessions WHERE id=%s AND user_id=%s
                                             AND revoked_at IS NULL AND expires_at>now()
                                             AND last_seen_at>now() - (%s * interval '1 minute')''',
                                          (getattr(g, 'auth_session_id', None), g.user['id'],
                                           current_app.config['AUTH_IDLE_MINUTES'])).fetchone()
            if not current or not current['active'] or current['version'] != g.user['version'] or not active_session:
                from .common import Problem
                raise Problem('Seu acesso foi atualizado. Entre novamente para continuar.', 401)
        yield conn


def migrate():
    conn = get_db()
    with write_transaction():
        conn.execute('CREATE TABLE IF NOT EXISTS schema_migrations (version text PRIMARY KEY, applied_at timestamptz NOT NULL DEFAULT now())')
        applied = {r['version'] for r in conn.execute('SELECT version FROM schema_migrations')}
        for path in sorted((Path(__file__).parent / 'migrations').glob('*.sql')):
            if path.name not in applied:
                conn.execute(path.read_text(), prepare=False)
                conn.execute('INSERT INTO schema_migrations(version) VALUES (%s)', (path.name,))
