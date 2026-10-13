from datetime import datetime, timezone, timedelta
from functools import wraps
import hashlib
import hmac
import re
import secrets
from flask import Blueprint, request, session, g, current_app, make_response, has_request_context
from werkzeug.security import generate_password_hash, check_password_hash
from .db import get_db, write_transaction
from .common import Problem, required_text, uid, json_value, audit, ensure_version

bp = Blueprint('auth', __name__, url_prefix='/api')
MIN_PASSWORD_LENGTH = 15
MAX_PASSWORD_LENGTH = 128
COMMON_PASSWORDS = frozenset({
    '123456789012345', '12345678901234567890', 'password12345678',
    'password123456789', 'qwertyuiopasdfgh', 'senha1234567890',
    'admin1234567890', 'aviva1234567890',
})


def reject_common_password(password, username):
    if password.casefold() in COMMON_PASSWORDS or password.casefold() == username.casefold():
        raise Problem('Escolha uma senha menos comum e diferente do nome de usuário.')


def public_user(user):
    return {k: v for k, v in user.items() if k not in ('password_hash', 'auth_user_version', 'auth_verifier_hash')}


def csrf_token():
    if 'csrf' not in session:
        session['csrf'] = secrets.token_urlsafe(32)
    return session['csrf']


def security_event(conn, event_type, result, user_id=None, session_id=None, reason=''):
    origin = (request.remote_addr or '') if has_request_context() else ''
    origin_hash = hmac.new(current_app.secret_key.encode(), origin.encode(), hashlib.sha256).hexdigest() if origin else None
    request_id = getattr(g, 'request_id', None) if has_request_context() else None
    conn.execute('''INSERT INTO auth_events(event_type,result,user_id,session_id,request_id,origin_hash,reason)
                    VALUES (%s,%s,%s,%s,%s,%s,%s)''',
                 (event_type, result, user_id, session_id, request_id, origin_hash, reason))


def issue_session(conn, user):
    session_id, verifier = uid(), secrets.token_urlsafe(32)
    token = f'{session_id}.{verifier}'
    conn.execute('''INSERT INTO auth_sessions(id,user_id,verifier_hash,expires_at,user_version)
                    VALUES (%s,%s,%s,now() + (%s * interval '1 hour'),%s)''',
                 (session_id, user['id'], hashlib.sha256(verifier.encode()).hexdigest(),
                  current_app.config['AUTH_SESSION_HOURS'], user['version']))
    security_event(conn, 'login', 'accepted', user['id'], session_id)
    return token


def set_auth_cookie(response, token):
    response.set_cookie(current_app.config['AUTH_COOKIE_NAME'], token,
                        max_age=current_app.config['AUTH_SESSION_HOURS'] * 3600,
                        secure=current_app.config['SESSION_COOKIE_SECURE'], httponly=True,
                        samesite='Lax', path='/')
    return response


def session_response(payload, token, status=200):
    return set_auth_cookie(make_response(payload, status), token)


def load_user():
    g.user = None
    g.auth_session_id = None
    token = request.cookies.get(current_app.config['AUTH_COOKIE_NAME'], '')
    if not token or '.' not in token:
        return
    session_id, verifier = token.split('.', 1)
    if not session_id or not verifier or len(token) > 200:
        return
    conn = get_db()
    row = conn.execute('''SELECT u.*,s.user_version AS auth_user_version,
                                 s.verifier_hash AS auth_verifier_hash
                          FROM auth_sessions s JOIN users u ON u.id=s.user_id
                          WHERE s.id=%s AND s.revoked_at IS NULL
                          AND s.expires_at>now()
                          AND s.last_seen_at>now() - (%s * interval '1 minute')''',
                       (session_id, current_app.config['AUTH_IDLE_MINUTES'])).fetchone()
    digest = hashlib.sha256(verifier.encode()).hexdigest()
    if (not row or not hmac.compare_digest(digest, row['auth_verifier_hash'])
            or not row['active'] or row['version'] != row['auth_user_version']):
        return
    conn.execute('UPDATE auth_sessions SET last_seen_at=now() WHERE id=%s', (session_id,))
    g.auth_session_id = session_id
    g.user = row


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
    if current_app.config['AUTH_MODE'] == 'entra':
        object_id = str(data.get('entra_object_id', '')).strip().lower()
        if not re.fullmatch(r'[0-9a-f]{8}-(?:[0-9a-f]{4}-){3}[0-9a-f]{12}', object_id):
            raise Problem('Informe o Object ID da pessoa no Microsoft Entra ID.')
        tenant_id = current_app.config['ENTRA_TENANT_ID']
        password_hash = generate_password_hash(secrets.token_urlsafe(48))
    else:
        object_id = tenant_id = None
        password = data.get('password', '')
        if not isinstance(password, str) or not MIN_PASSWORD_LENGTH <= len(password) <= MAX_PASSWORD_LENGTH:
            raise Problem('Use uma senha individual de 15 a 128 caracteres.')
        reject_common_password(password, username)
        password_hash = generate_password_hash(password)
    team = data.get('team_id')
    if team not in ('commercial', 'operations'):
        raise Problem('Escolha a equipe.')
    scopes = data.get('scopes', ['cs', 'rq', 'unassigned'])
    if not isinstance(scopes, list) or not scopes or any(s not in ['cs','rq','unassigned'] for s in scopes):
        raise Problem('Escopo de acesso inválido.')
    if conn.execute('SELECT id FROM users WHERE username=%s', (username,)).fetchone():
        raise Problem('Esse usuário já existe.', 409)
    if object_id and conn.execute('SELECT id FROM users WHERE entra_tenant_id=%s AND entra_object_id=%s',
                                  (tenant_id, object_id)).fetchone():
        raise Problem('Essa identidade corporativa já está vinculada.', 409)
    user_id = uid()
    conn.execute('''INSERT INTO users(id,username,name,password_hash,team_id,scopes,can_catalog,can_schedule,can_manage_users,entra_tenant_id,entra_object_id)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)''',
                 (user_id, username, required_text(data,'name',120), password_hash, team,
                  json_value(sorted(set(scopes))), first or data.get('can_catalog') is True,
                  first or data.get('can_schedule') is True, first or data.get('can_manage_users') is True,
                  tenant_id, object_id))
    user = conn.execute('SELECT * FROM users WHERE id=%s', (user_id,)).fetchone()
    audit(conn, actor or user, 'user', user_id, 'create', after=public_user(user))
    return user


@bp.get('/session')
def current_session():
    empty = get_db().execute('SELECT count(*) AS n FROM users').fetchone()['n'] == 0
    return {'user': public_user(g.user) if g.user else None, 'csrf': csrf_token(),
            'auth_mode': current_app.config['AUTH_MODE'],
            'setup_required': empty, 'qa_mode': current_app.config.get('QA_MODE', False),
            'local_setup_allowed': request.remote_addr in ('127.0.0.1','::1') and current_app.config['ALLOW_LOCAL_SETUP']}


@bp.post('/setup')
def setup():
    if current_app.config['AUTH_MODE'] != 'local':
        raise Problem('A configuração inicial local está desativada.', 403)
    if not current_app.config['ALLOW_LOCAL_SETUP'] or request.remote_addr not in ('127.0.0.1','::1'):
        raise Problem('O primeiro acesso deve ser criado localmente pelo administrador.', 403)
    with write_transaction() as conn:
        if conn.execute('SELECT count(*) AS n FROM users').fetchone()['n']:
            raise Problem('A configuração inicial já foi concluída.', 409)
        user = create_user(conn, request.get_json(), first=True)
        token = issue_session(conn, user)
    session.clear()
    session.permanent = True
    return session_response({'user': public_user(user), 'csrf': csrf_token()}, token, 201)


@bp.post('/login')
def login():
    if current_app.config['AUTH_MODE'] != 'local':
        raise Problem('Use o login corporativo para entrar.', 403)
    data = request.get_json()
    username = str(data.get('username','')).strip().lower()[:64]
    password = data.get('password','')
    if not isinstance(password,str) or len(password)>256:
        raise Problem('Usuário ou senha incorretos.',401)
    key = hashlib.sha256(f'{request.remote_addr}:{username}'.encode()).hexdigest()
    rejected = False
    rate_limited = False
    with write_transaction() as conn:
        attempt = conn.execute('SELECT * FROM login_attempts WHERE key=%s',(key,)).fetchone()
        recent = attempt and attempt['last_at'] > datetime.now(timezone.utc)-timedelta(minutes=10)
        if recent and attempt['attempts'] >= 8:
            security_event(conn, 'login', 'rate_limited', user_id=None, reason='too_many_attempts')
            rate_limited = True
        else:
            user = conn.execute('SELECT * FROM users WHERE username=%s AND active=true',(username,)).fetchone()
            valid = check_password_hash(user['password_hash'] if user else current_app.config['DUMMY_HASH'],password)
            if not user or not valid:
                count = attempt['attempts']+1 if recent else 1
                conn.execute('INSERT INTO login_attempts VALUES (%s,%s,now()) ON CONFLICT(key) DO UPDATE SET attempts=excluded.attempts,last_at=excluded.last_at',(key,count))
                security_event(conn, 'login', 'rejected', user_id=user['id'] if user else None, reason='invalid_credentials')
                rejected = True
            else:
                conn.execute('DELETE FROM login_attempts WHERE key=%s',(key,))
                token = issue_session(conn, user)
    if rate_limited:
        raise Problem('Muitas tentativas. Aguarde 10 minutos para tentar novamente.',429)
    if rejected:
        raise Problem('Usuário ou senha incorretos.',401)
    session.clear()
    session.permanent=True
    return session_response({'user':public_user(user),'csrf':csrf_token()}, token)


@bp.post('/logout')
def logout():
    if g.auth_session_id:
        with write_transaction() as conn:
            conn.execute('UPDATE auth_sessions SET revoked_at=now() WHERE id=%s', (g.auth_session_id,))
            security_event(conn, 'logout', 'accepted', g.user['id'], g.auth_session_id)
    session.clear()
    response=make_response({'csrf':csrf_token()})
    response.delete_cookie(current_app.config['AUTH_COOKIE_NAME'], path='/')
    return response


@bp.post('/password')
@login_required
def change_password():
    if current_app.config['AUTH_MODE'] != 'local':
        raise Problem('Altere sua senha no serviço corporativo.', 403)
    data=request.get_json()
    if not isinstance(data.get('current_password'),str) or not check_password_hash(g.user['password_hash'], data['current_password']):
        raise Problem('Senha atual incorreta.',403)
    password=data.get('password','')
    if not isinstance(password,str) or not MIN_PASSWORD_LENGTH<=len(password)<=MAX_PASSWORD_LENGTH:
        raise Problem('A nova senha deve ter de 15 a 128 caracteres.')
    reject_common_password(password, g.user['username'])
    with write_transaction() as conn:
        conn.execute('UPDATE users SET password_hash=%s, version=version+1 WHERE id=%s',(generate_password_hash(password),g.user['id']))
        audit(conn,g.user,'user',g.user['id'],'password_changed')
        version=conn.execute('SELECT version FROM users WHERE id=%s',(g.user['id'],)).fetchone()['version']
        conn.execute('UPDATE auth_sessions SET revoked_at=now() WHERE user_id=%s AND id<>%s AND revoked_at IS NULL',
                     (g.user['id'], g.auth_session_id))
        conn.execute('UPDATE auth_sessions SET user_version=%s WHERE id=%s', (version, g.auth_session_id))
        security_event(conn, 'password_change', 'accepted', g.user['id'], g.auth_session_id)
    return {'ok':True}
