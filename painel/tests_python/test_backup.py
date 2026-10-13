from uuid import uuid4
import psycopg
from psycopg import sql
from psycopg.conninfo import conninfo_to_dict, make_conninfo
import pytest
from calendar_app.cli import backup_database, restore_database
from calendar_app.common import Problem
from calendar_app.db import connect, get_db
from calendar_app import create_app
from calendar_app.db import migrate


def test_backup_restore_preserves_data_and_refuses_existing_database(api, app, tmp_path):
    api.validate(7)
    booking = api.promote(api.create().json).json
    url = app.config['DATABASE_URL']
    schema = app.config['DB_SCHEMA']
    target_name = 'restore_salas_test_' + uuid4().hex
    target_url = make_conninfo(**{**conninfo_to_dict(url), 'dbname': target_name})
    tables = ['users', 'configurations', 'resources', 'source_items', 'bookings', 'allocations', 'occupations', 'audit', 'auth_sessions', 'auth_events']
    with app.app_context():
        expected = {table: get_db().execute(sql.SQL('SELECT count(*) AS n FROM {}').format(sql.Identifier(table))).fetchone()['n'] for table in tables}
    path = backup_database(url, tmp_path / 'salas.dump', schema)
    assert path.stat().st_size > 0 and path.stat().st_mode & 0o777 == 0o600
    with pytest.raises(Problem):
        backup_database(url, path, schema)
    with psycopg.connect(url, autocommit=True) as maintenance:
        maintenance.execute(sql.SQL('CREATE DATABASE {}').format(sql.Identifier(target_name)))
        try:
            restore_database(target_url, path)
            with connect(target_url, schema) as restored:
                actual = {table: restored.execute(sql.SQL('SELECT count(*) AS n FROM {}').format(sql.Identifier(table))).fetchone()['n'] for table in tables}
                assert actual == expected
                assert restored.execute('SELECT status FROM bookings WHERE id=%s', (booking['id'],)).fetchone()['status'] == 'option'
                assert restored.execute('SELECT count(*) AS n FROM occupations WHERE booking_id=%s', (booking['id'],)).fetchone()['n'] == 3
            with pytest.raises(Problem, match='destino vazio'):
                restore_database(target_url, path)
        finally:
            maintenance.execute(sql.SQL('DROP DATABASE {}').format(sql.Identifier(target_name)))


def test_restore_default_public_schema(app, tmp_path):
    url=app.config['DATABASE_URL']
    names=['backup_salas_test_'+uuid4().hex, 'restore_salas_test_'+uuid4().hex]
    urls=[make_conninfo(**{**conninfo_to_dict(url), 'dbname':name}) for name in names]
    with psycopg.connect(url, autocommit=True) as maintenance:
        for name in names: maintenance.execute(sql.SQL('CREATE DATABASE {}').format(sql.Identifier(name)))
        try:
            source=create_app({'DATABASE_URL':urls[0], 'SECRET_KEY':'test', 'TESTING':True})
            with source.app_context(): migrate()
            archive=backup_database(urls[0], tmp_path/'public.dump')
            restore_database(urls[1], archive)
            with connect(urls[1]) as restored:
                assert restored.execute('SELECT count(*) AS n FROM teams').fetchone()['n']==2
                assert restored.execute('SELECT count(*) AS n FROM schema_migrations').fetchone()['n']==2
        finally:
            for name in names: maintenance.execute(sql.SQL('DROP DATABASE {}').format(sql.Identifier(name)))
