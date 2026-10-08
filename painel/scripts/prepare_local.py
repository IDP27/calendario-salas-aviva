"""Prepare only the dedicated local PostgreSQL pilot, without exposing credentials."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import json
import os
import psycopg
from psycopg import sql
from psycopg.conninfo import conninfo_to_dict,make_conninfo
from calendar_app import create_app,load_environment,ROOT
from calendar_app.db import migrate
from calendar_app.catalog import import_catalog

load_environment()
parts=conninfo_to_dict(os.environ['DATABASE_URL'])
if parts.get('host') not in ('127.0.0.1','localhost') or parts.get('dbname')!='calendario':
    raise SystemExit('Este auxiliar é exclusivo do banco local calendario. Use as migrações documentadas para outro ambiente.')
maintenance={**parts,'dbname':'postgres'}
with psycopg.connect(make_conninfo(**maintenance),autocommit=True) as conn:
    if not conn.execute('SELECT 1 FROM pg_database WHERE datname=%s',(parts['dbname'],)).fetchone():
        conn.execute(sql.SQL('CREATE DATABASE {}').format(sql.Identifier(parts['dbname'])))
app=create_app()
with app.app_context():
    migrate()
    result=import_catalog(json.loads((ROOT/'docs/catalogo-salas-preliminar.json').read_text()))
print('Banco PostgreSQL preparado; catálogo rastreável importado sem ocupações ou contas fictícias.')
print(f"Itens de origem: {result['items']}; espaços/configurações: {result['configurations']}.")
