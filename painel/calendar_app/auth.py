from datetime import datetime, timezone, timedelta
from functools import wraps
import hashlib
import re
import secrets
from flask import Blueprint, request, session, g, current_app
from werkzeug.security import generate_password_hash, check_password_hash
from .db import get_db, write_transaction
from .common import Problem, required_text, uid, json_value, audit, ensure_version

bp = Blueprint('auth', __name__, url_prefix='/api')


def public_user(user):
    return {k: v for k, v in user.items() if k != 'password_hash'}


def csrf_token():
    if 'csrf' not in session:
        session['csrf'] = secrets.token_urlsafe(32)
    return session['csrf']


def load_user():
    g.user = None
    if session.get('user_id'):
        user = get_db().execute('SELECT * FROM users WHERE id=%s AND active=true', (session['user_id'],)).fetchone()
        if user and user['version'] == session.get('user_version'):
            g.user = user
        else:
            session.clear()


def login_required(fn):
    @wraps(fn)
    def inner(*args, **kwargs):
        if not g.user:
            raise Problem('Entre novamente para continuar.', 401)
        return fn(*args, **kwargs)
    return inner


def create_user(conn, data, actor=None, first=False):
    username = required_text(data, 'username', 64).lower()
    if not re.fullmatch(r'[a-z0-9._@-]{3,64}', username):
        raise Problem('Usuário deve ter entre 3 e 64 letras, números ou . _ @ -')
    password = data.get('password', '')
    if not isinstance(password, str) or not 12 <= len(password) <= 256:
        raise Problem('Use uma senha individual de 12 a 256 caracteres.')
    team = data.get('team_id')
    if team not in ('commercial', 'operations'):
        raise Problem('Escolha a equipe.')
    scopes = data.get('scopes', ['cs', 'rq', 'unassigned'])
    if not isinstance(scopes, list) or not scopes or any(s not in ['cs','rq','unassigned'] for s in scopes):
        raise Problem('Escopo de acesso inválido.')
    if conn.execute('SELECT id FROM users WHERE username=%s', (username,)).fetchone():
        raise Problem('Esse usuário já existe.', 409)
    user_id = uid()
    conn.execute('INSERT INTO users(id,username,name,password_hash,team_id,scopes,can_catalog,can_schedule,can_manage_users) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)',
                 (user_id, username, required_text(data,'name',120), generate_password_hash(password), team,
                  json_value(sorted(set(scopes))), first or data.get('can_catalog') is True,
                  first or data.get('can_schedule') is True, first or data.get('can_manage_users') is True))
    user = conn.execute('SELECT * FROM users WHERE id=%s', (user_id,)).fetchone()
    audit(conn, actor or user, 'user', user_id, 'create', after=public_user(user))
    return user


@bp.get('/session')
def current_session():
    empty = get_db().execute('SELECT count(*) AS n FROM users').fetchone()['n'] == 0
    return {'user': public_user(g.user) if g.user else None, 'csrf': csrf_token(),
            'setup_required': empty, 'qa_mode': current_app.config.get('QA_MODE', False),
            'local_setup_allowed': request.remote_addr in ('127.0.0.1','::1') and current_app.config['ALLOW_LOCAL_SETUP']}


@bp.post('/setup')
def setup():
    if not current_app.config['ALLOW_LOCAL_SETUP'] or request.remote_addr not in ('127.0.0.1','::1'):
        raise Problem('O primeiro acesso deve ser criado localmente pelo administrador.', 403)
    with write_transaction() as conn:
        if conn.execute('SELECT count(*) AS n FROM users').fetchone()['n']:
            raise Problem('A configuração inicial já foi concluída.', 409)
        user = create_user(conn, request.get_json(), first=True)
    session.clear()
    session.update(user_id=user['id'], user_version=user['version'])
    session.permanent = True
    return {'user': public_user(user), 'csrf': csrf_token()}, 201


@bp.post('/login')
def login():
    data = request.get_json()
    username = str(data.get('username','')).strip().lower()[:64]
    password = data.get('password','')
    if not isinstance(password,str) or len(password)>256:
        raise Problem('Usuário ou senha incorretos.',401)
    key = hashlib.sha256(f'{request.remote_addr}:{username}'.encode()).hexdigest()
    rejected = False
    with write_transaction() as conn:
        attempt = conn.execute('SELECT * FROM login_attempts WHERE key=%s',(key,)).fetchone()
        recent = attempt and attempt['last_at'] > datetime.now(timezone.utc)-timedelta(minutes=10)
        if recent and attempt['attempts'] >= 8:
            raise Problem('Muitas tentativas. Aguarde 10 minutos para tentar novamente.',429)
        user = conn.execute('SELECT * FROM users WHERE username=%s AND active=true',(username,)).fetchone()
        valid = check_password_hash(user['password_hash'] if user else current_app.config['DUMMY_HASH'],password)
        if not user or not valid:
            count = attempt['attempts']+1 if recent else 1
            conn.execute('INSERT INTO login_attempts VALUES (%s,%s,now()) ON CONFLICT(key) DO UPDATE SET attempts=excluded.attempts,last_at=excluded.last_at',(key,count))
            rejected = True
        else:
            conn.execute('DELETE FROM login_attempts WHERE key=%s',(key,))
    if rejected:
        raise Problem('Usuário ou senha incorretos.',401)
    session.clear()
    session.update(user_id=user['id'],user_version=user['version'])
    session.permanent=True
    return {'user':public_user(user),'csrf':csrf_token()}


@bp.post('/logout')
def logout():
    session.clear()
    return {'csrf':csrf_token()}


@bp.post('/password')
@login_required
def change_password():
    data=request.get_json()
    if not isinstance(data.get('current_password'),str) or not check_password_hash(g.user['password_hash'], data['current_password']):
        raise Problem('Senha atual incorreta.',403)
    password=data.get('password','')
    if not isinstance(password,str) or not 12<=len(password)<=256:
        raise Problem('A nova senha deve ter de 12 a 256 caracteres.')
    with write_transaction() as conn:
        conn.execute('UPDATE users SET password_hash=%s, version=version+1 WHERE id=%s',(generate_password_hash(password),g.user['id']))
        audit(conn,g.user,'user',g.user['id'],'password_changed')
        version=conn.execute('SELECT version FROM users WHERE id=%s',(g.user['id'],)).fetchone()['version']
    session['user_version']=version
    return {'ok':True}
