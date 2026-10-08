"""Offline administration. Restores only into an empty, explicitly selected database."""
import json
import os
import subprocess
import tempfile
from pathlib import Path
import click
import psycopg
from psycopg.conninfo import conninfo_to_dict
from .db import migrate, get_db, write_transaction
from .catalog import import_catalog
from .auth import create_user
from .common import Problem


def pg_environment(url):
    values=conninfo_to_dict(url)
    env=os.environ.copy()
    for key,name in [('host','PGHOST'),('port','PGPORT'),('user','PGUSER'),('password','PGPASSWORD'),('dbname','PGDATABASE'),('sslmode','PGSSLMODE')]:
        if key in values: env[name]=values[key]
    return env


def backup_database(url,path,schema='public'):
    path=Path(path)
    if path.exists(): raise Problem('Escolha um novo arquivo de backup; o existente será preservado.')
    path.parent.mkdir(parents=True,exist_ok=True)
    # Create with restrictive permissions before invoking pg_dump.
    fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600); os.close(fd)
    try:
        subprocess.run(['pg_dump','--format=custom','--no-owner','--no-acl',f'--schema={schema}',f'--file={path}'],env=pg_environment(url),check=True,capture_output=True)
    except subprocess.CalledProcessError as exc:
        raise Problem('Falha ao gerar backup. Confira a conexão e a compatibilidade da versão do pg_dump.') from exc
    return path


def restore_database(url,path):
    with psycopg.connect(url,autocommit=True) as conn:
        if conn.execute("SELECT count(*) FROM pg_tables WHERE schemaname NOT IN ('pg_catalog','information_schema')").fetchone()[0]:
            raise Problem('A restauração exige um banco de destino vazio. A base atual foi preservada.')
        public_exists=conn.execute("SELECT 1 FROM pg_namespace WHERE nspname='public'").fetchone() is not None
    try:
        # PostgreSQL initializes an empty database with public already present.
        # Preserve that schema instead of dropping it or ignoring restore errors.
        listing=subprocess.run(['pg_restore','--list',str(path)],check=True,capture_output=True,text=True).stdout
        lines=[line for line in listing.splitlines() if not (
            public_exists and (' SCHEMA - public ' in line or ' COMMENT - SCHEMA public ' in line))]
        with tempfile.NamedTemporaryFile(mode='w',suffix='.toc',encoding='utf-8') as toc:
            toc.write('\n'.join(lines)+'\n'); toc.flush()
            subprocess.run(['pg_restore','--single-transaction','--exit-on-error','--no-owner','--no-acl',
                            '--use-list',toc.name,'--dbname',conninfo_to_dict(url)['dbname'],str(path)],
                           env=pg_environment(url),check=True,capture_output=True)
    except subprocess.CalledProcessError as exc:
        raise Problem('Restauração recusada ou incompleta; verifique o arquivo e a compatibilidade das ferramentas.') from exc


def register(app):
    @app.cli.command('init-db')
    def init_db():
        migrate(); click.echo('Migrações PostgreSQL aplicadas.')

    @app.cli.command('import-catalog')
    @click.argument('path',type=click.Path(exists=True,path_type=Path))
    @click.option('--preview',is_flag=True)
    def import_command(path,preview):
        migrate()
        try: click.echo(json.dumps(import_catalog(json.loads(path.read_text()),preview=preview),ensure_ascii=False))
        except (Problem,ValueError) as exc: raise click.ClickException(str(getattr(exc,'message',exc)))

    @app.cli.command('create-user')
    @click.option('--username',prompt=True)
    @click.option('--name',prompt=True)
    @click.option('--team',type=click.Choice(['commercial','operations']),prompt=True)
    @click.option('--password',prompt=True,hide_input=True,confirmation_prompt=True)
    @click.option('--admin',is_flag=True)
    def user_command(username,name,team,password,admin):
        try:
            with write_transaction() as conn:
                create_user(conn,dict(username=username,name=name,team_id=team,password=password,can_catalog=admin,can_schedule=admin,can_manage_users=admin))
            click.echo('Conta individual criada.')
        except Problem as exc: raise click.ClickException(exc.message)

    @app.cli.command('backup-db')
    @click.argument('path',type=click.Path(path_type=Path))
    def backup(path):
        try:
            backup_database(app.config['DATABASE_URL'],path,app.config['DB_SCHEMA'])
            click.echo(f'Backup PostgreSQL criado: {path}')
        except Problem as exc: raise click.ClickException(exc.message)

    @app.cli.command('restore-db')
    @click.argument('path',type=click.Path(exists=True,path_type=Path))
    @click.option('--target-url',envvar='RESTORE_DATABASE_URL',required=True,help='URL de um banco de destino vazio; prefira a variável RESTORE_DATABASE_URL para não expor credenciais no histórico.')
    def restore(path,target_url):
        try:
            restore_database(target_url,path)
            click.echo('Backup restaurado no banco vazio indicado. Valide os dados antes de trocar DATABASE_URL; a origem foi preservada.')
        except Problem as exc: raise click.ClickException(exc.message)
