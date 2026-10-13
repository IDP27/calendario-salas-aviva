"""Microsoft Entra ID sign-in via OIDC authorization code and PKCE."""
import hmac
import secrets
from uuid import UUID
from urllib.parse import urlsplit
from flask import Blueprint, current_app, redirect, session
from authlib.integrations.flask_client import OAuth
from authlib.common.errors import AuthlibBaseError
from joserfc.errors import JoseError
from requests.exceptions import RequestException
from .auth import csrf_token, issue_session, security_event, set_auth_cookie
from .db import write_transaction
from .common import Problem

bp = Blueprint('entra', __name__, url_prefix='/api/entra')
oauth = OAuth()


def register(app):
    if app.config['AUTH_MODE'] not in ('local', 'entra'):
        raise RuntimeError('CALENDAR_AUTH_MODE deve ser local ou entra.')
    if app.config['AUTH_MODE'] == 'entra':
        required = ('ENTRA_TENANT_ID', 'ENTRA_CLIENT_ID', 'ENTRA_CLIENT_SECRET', 'ENTRA_REDIRECT_URI')
        if any(not app.config[key] for key in required):
            raise RuntimeError('Configure tenant, client ID, client secret e redirect URI do Entra ID.')
        try:
            app.config['ENTRA_TENANT_ID'] = str(UUID(app.config['ENTRA_TENANT_ID']))
            app.config['ENTRA_CLIENT_ID'] = str(UUID(app.config['ENTRA_CLIENT_ID']))
        except ValueError as exc:
            raise RuntimeError('Tenant ID e Client ID devem ser UUIDs válidos.') from exc
        callback = urlsplit(app.config['ENTRA_REDIRECT_URI'])
        if not callback.netloc or callback.path != '/api/entra/callback' or callback.query or callback.fragment:
            raise RuntimeError('ENTRA_REDIRECT_URI deve apontar para /api/entra/callback.')
        if not app.config['TESTING'] and (callback.scheme != 'https' or not app.config['SESSION_COOKIE_SECURE']):
            raise RuntimeError('O login Entra ID exige HTTPS e cookies Secure.')
        oauth.init_app(app)
        oauth.register(
            name='entra',
            client_id=app.config['ENTRA_CLIENT_ID'],
            client_secret=app.config['ENTRA_CLIENT_SECRET'],
            server_metadata_url=f"https://login.microsoftonline.com/{app.config['ENTRA_TENANT_ID']}/v2.0/.well-known/openid-configuration",
            client_kwargs={'scope': 'openid profile email', 'code_challenge_method': 'S256'},
        )
    app.register_blueprint(bp)


@bp.get('/login')
def login():
    if current_app.config['AUTH_MODE'] != 'entra':
        raise Problem('Login corporativo não configurado.', 404)
    nonce = secrets.token_urlsafe(32)
    session['entra_nonce'] = nonce
    with write_transaction() as conn:
        security_event(conn, 'sso_start', 'started')
    return oauth.entra.authorize_redirect(current_app.config['ENTRA_REDIRECT_URI'], nonce=nonce)


@bp.get('/callback')
def callback():
    if current_app.config['AUTH_MODE'] != 'entra':
        raise Problem('Login corporativo não configurado.', 404)
    expected_nonce = session.pop('entra_nonce', None)
    if not expected_nonce:
        with write_transaction() as conn:
            security_event(conn, 'sso_callback', 'rejected', reason='missing_nonce')
        return redirect('/?login_error=1')
    try:
        token = oauth.entra.authorize_access_token()
        claims = token.get('userinfo')
        if not claims or not hmac.compare_digest(str(claims.get('nonce', '')), expected_nonce):
            raise ValueError('invalid_nonce')
        tenant = str(UUID(str(claims.get('tid', ''))))
        object_id = str(UUID(str(claims.get('oid', ''))))
        if (tenant != current_app.config['ENTRA_TENANT_ID'] or not object_id
                or claims.get('aud') != current_app.config['ENTRA_CLIENT_ID']):
            raise ValueError('invalid_identity')
        with write_transaction() as conn:
            user = conn.execute('''SELECT * FROM users WHERE entra_tenant_id=%s AND entra_object_id=%s
                                   AND active=true''', (tenant, object_id)).fetchone()
            if not user:
                security_event(conn, 'sso_callback', 'rejected', reason='unlinked_or_inactive')
            else:
                local_token = issue_session(conn, user)
                security_event(conn, 'sso_callback', 'accepted', user['id'])
        if not user:
            return redirect('/?login_error=1')
        session.clear()
        session.permanent = True
        csrf_token()
        return set_auth_cookie(redirect('/'), local_token)
    except (AuthlibBaseError, JoseError, RequestException, ValueError, KeyError) as exc:
        with write_transaction() as conn:
            security_event(conn, 'sso_callback', 'rejected', reason=type(exc).__name__)
        return redirect('/?login_error=1')
    finally:
        # The Flask OAuth client object is shared; keep provider tokens out of it.
        oauth.entra.token = None
