from types import SimpleNamespace
from uuid import uuid4

from calendar_app import create_app
from calendar_app.db import get_db
from calendar_app import entra
from conftest import API, PASSWORD


def test_logout_revokes_replayed_cookie_and_records_events(app):
    client = app.test_client()
    csrf = client.get('/api/session').json['csrf']
    login = client.post('/api/login', json={'username': 'seller', 'password': PASSWORD},
                        headers={'X-CSRF-Token': csrf})
    assert login.status_code == 200
    assert any('salas_auth=' in cookie and 'HttpOnly' in cookie and 'SameSite=Lax' in cookie
               for cookie in login.headers.getlist('Set-Cookie'))
    token = client.get_cookie('salas_auth').value
    assert client.get('/api/catalog').status_code == 200
    public = client.get('/api/session').json['user']
    assert not {'password_hash', 'auth_verifier_hash', 'auth_user_version'} & public.keys()
    assert client.post('/api/logout', json={}, headers={'X-CSRF-Token': login.json['csrf']}).status_code == 200
    replay = app.test_client()
    replay.set_cookie('salas_auth', token)
    assert replay.get('/api/catalog').status_code == 401
    with app.app_context():
        events = list(get_db().execute("SELECT event_type,result FROM auth_events ORDER BY id"))
    assert ('login', 'accepted') in [(r['event_type'], r['result']) for r in events]
    assert ('logout', 'accepted') in [(r['event_type'], r['result']) for r in events]


def test_failed_login_is_recorded_without_password_or_token(app):
    client = app.test_client()
    csrf = client.get('/api/session').json['csrf']
    assert client.post('/api/login', json={'username': 'seller', 'password': 'wrong'},
                       headers={'X-CSRF-Token': csrf}).status_code == 401
    with app.app_context():
        event = get_db().execute('SELECT * FROM auth_events ORDER BY id DESC LIMIT 1').fetchone()
    assert event['event_type'] == 'login' and event['result'] == 'rejected'
    assert 'wrong' not in str(event)
    assert API(app, 'admin').get('/audit/auth').status_code == 200
    assert API(app, 'seller').get('/audit/auth').status_code == 403


def test_access_change_revokes_server_session(app):
    admin = API(app, 'admin')
    seller = API(app, 'seller')
    user = next(u for u in admin.get('/users').json['users'] if u['username'] == 'seller')
    response = admin.send(f"/users/{user['id']}", {**user, 'active': False}, method='PUT')
    assert response.status_code == 200
    assert seller.get('/catalog').status_code == 401


def test_sql_input_is_data_not_query(app):
    client = API(app, 'seller')
    title = "Sala'); DROP TABLE users; --"
    result = client.create(code=7, status='pending', title=title)
    assert result.status_code == 201, result.json
    assert client.detail(result.json)['title'] == title
    with app.app_context():
        assert get_db().execute('SELECT count(*) AS n FROM users').fetchone()['n'] == 4


def test_entra_callback_links_only_matching_tenant_and_object(app, monkeypatch):
    tenant, client_id, object_id = (str(uuid4()) for _ in range(3))
    corporate = create_app({'TESTING': True, 'DATABASE_URL': app.config['DATABASE_URL'],
                            'DB_SCHEMA': app.config['DB_SCHEMA'], 'SECRET_KEY': 'entra-test-key',
                            'SESSION_COOKIE_SECURE': False, 'AUTH_MODE': 'entra',
                            'ENTRA_TENANT_ID': tenant, 'ENTRA_CLIENT_ID': client_id,
                            'ENTRA_CLIENT_SECRET': 'test-secret',
                            'ENTRA_REDIRECT_URI': 'http://localhost/api/entra/callback'})
    with corporate.app_context():
        assert entra.oauth.entra._get_oauth_client().code_challenge_method == 'S256'
    with corporate.app_context():
        before = get_db().execute("SELECT * FROM users WHERE username='seller'").fetchone()
    link = corporate.test_cli_runner().invoke(args=['link-entra', '--username', 'seller',
                                                   '--object-id', object_id])
    assert link.exit_code == 0, link.output
    with corporate.app_context():
        user = get_db().execute("SELECT * FROM users WHERE username='seller'").fetchone()
    assert user['id'] == before['id'] and user['password_hash'] != before['password_hash']
    local_login = corporate.test_client()
    csrf = local_login.get('/api/session').json['csrf']
    assert local_login.post('/api/login', json={'username': 'seller', 'password': PASSWORD},
                            headers={'X-CSRF-Token': csrf}).status_code == 403

    claims = {'nonce': 'expected', 'tid': tenant, 'oid': object_id, 'aud': client_id}
    monkeypatch.setattr(entra, 'oauth', SimpleNamespace(entra=SimpleNamespace(
        authorize_access_token=lambda: {'userinfo': claims})))
    browser = corporate.test_client()
    with browser.session_transaction() as session:
        session['entra_nonce'] = 'expected'
    assert browser.get('/api/entra/callback?state=example&code=example').status_code == 302
    assert browser.get('/api/session').json['user']['id'] == user['id']

    denied = corporate.test_client()
    with denied.session_transaction() as session:
        session['entra_nonce'] = 'expected'
    claims['tid'] = str(uuid4())
    assert denied.get('/api/entra/callback?state=example&code=example').location.endswith('login_error=1')
    assert denied.get('/api/session').json['user'] is None
