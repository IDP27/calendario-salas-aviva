import hmac
import json
import logging
import os
import secrets
from pathlib import Path
from datetime import timedelta
from flask import Flask, request, session, jsonify, send_from_directory, g, has_request_context
from werkzeug.security import generate_password_hash
from werkzeug.exceptions import HTTPException
import psycopg
from . import db
from .common import Problem

ROOT=Path(__file__).resolve().parent.parent


class JsonLogFormatter(logging.Formatter):
    def format(self, record):
        from datetime import datetime, timezone
        data = {'time': datetime.now(timezone.utc).isoformat(), 'level': record.levelname,
                'message': record.getMessage()}
        if has_request_context():
            data['request_id'] = getattr(g, 'request_id', None)
            data['path'] = request.path
        return json.dumps(data, ensure_ascii=False)


def load_environment():
    path=ROOT/'.env'
    if path.exists():
        for line in path.read_text().splitlines():
            if line.strip() and not line.startswith('#') and '=' in line:
                key,value=line.split('=',1)
                if key in ('DATABASE_URL','CALENDAR_SECRET_KEY','CALENDAR_PORT','CALENDAR_SECURE_COOKIES','CALENDAR_ALLOW_LOCAL_SETUP','CALENDAR_AUTH_MODE','CALENDAR_AUTH_SESSION_HOURS','CALENDAR_AUTH_IDLE_MINUTES','ENTRA_TENANT_ID','ENTRA_CLIENT_ID','ENTRA_CLIENT_SECRET','ENTRA_REDIRECT_URI'):
                    os.environ.setdefault(key,value.strip())


def create_app(config=None):
    load_environment()
    app=Flask(__name__,static_folder=str(ROOT/'dist'),static_url_path='/static',instance_path=str(ROOT/'instance'))
    app.config.update(DATABASE_URL=os.environ.get('DATABASE_URL',''),DB_SCHEMA='public',
                      SECRET_KEY=os.environ.get('CALENDAR_SECRET_KEY'),SESSION_COOKIE_NAME='salas_session',
                      SESSION_COOKIE_HTTPONLY=True,SESSION_COOKIE_SAMESITE='Lax',
                      SESSION_COOKIE_SECURE=os.environ.get('CALENDAR_SECURE_COOKIES')=='1',
                      AUTH_COOKIE_NAME='salas_auth',AUTH_MODE=os.environ.get('CALENDAR_AUTH_MODE','local'),
                      AUTH_SESSION_HOURS=int(os.environ.get('CALENDAR_AUTH_SESSION_HOURS','8')),
                      AUTH_IDLE_MINUTES=int(os.environ.get('CALENDAR_AUTH_IDLE_MINUTES','60')),
                      ENTRA_TENANT_ID=os.environ.get('ENTRA_TENANT_ID',''),
                      ENTRA_CLIENT_ID=os.environ.get('ENTRA_CLIENT_ID',''),
                      ENTRA_CLIENT_SECRET=os.environ.get('ENTRA_CLIENT_SECRET',''),
                      ENTRA_REDIRECT_URI=os.environ.get('ENTRA_REDIRECT_URI',''),
                      PERMANENT_SESSION_LIFETIME=timedelta(hours=8),MAX_CONTENT_LENGTH=3*1024*1024,
                      ALLOW_LOCAL_SETUP=os.environ.get('CALENDAR_ALLOW_LOCAL_SETUP','1')=='1')
    if config: app.config.update(config)
    if not 1 <= app.config['AUTH_SESSION_HOURS'] <= 24 or not 5 <= app.config['AUTH_IDLE_MINUTES'] <= 240:
        raise RuntimeError('Configure duração absoluta entre 1 e 24 horas e inatividade entre 5 e 240 minutos.')
    app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=app.config['AUTH_SESSION_HOURS'])
    if not app.config['DATABASE_URL']: raise RuntimeError('Configure DATABASE_URL para o PostgreSQL. Consulte o README.')
    if not app.config['SECRET_KEY']:
        path=ROOT/'instance'/'secret-key'; path.parent.mkdir(exist_ok=True)
        try:
            with path.open('x') as stream: stream.write(secrets.token_hex(32))
            path.chmod(0o600)
        except FileExistsError: pass
        app.config['SECRET_KEY']=path.read_text().strip()
    app.config['DUMMY_HASH']=generate_password_hash(secrets.token_urlsafe(24))
    for handler in app.logger.handlers:
        handler.setFormatter(JsonLogFormatter())
    app.teardown_appcontext(db.close_db)
    from . import auth, api, cli, entra
    app.register_blueprint(auth.bp); app.register_blueprint(api.bp); entra.register(app); cli.register(app)

    @app.before_request
    def guard():
        g.request_id = secrets.token_hex(12)
        if request.path.startswith('/api/'):
            auth.load_user()
            if request.method not in ('GET','HEAD','OPTIONS'):
                token=request.headers.get('X-CSRF-Token','')
                if not token or not hmac.compare_digest(token,session.get('csrf','')):
                    raise Problem('Sessão de formulário inválida. Recarregue a página.',403)
                if not request.is_json or not isinstance(request.get_json(silent=True),dict):
                    raise Problem('Envie um objeto JSON válido.')

    @app.after_request
    def headers(response):
        response.headers['X-Request-ID'] = getattr(g, 'request_id', '')
        response.headers['X-Content-Type-Options']='nosniff'
        response.headers['X-Frame-Options']='DENY'
        response.headers['Referrer-Policy']='same-origin'
        response.headers['Content-Security-Policy']="default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'"
        response.headers['Cache-Control']='no-store'
        return response

    @app.errorhandler(Problem)
    def problem(error):
        if error.status == 403 and getattr(g, 'user', None):
            from .auth import security_event
            security_event(db.get_db(), 'access_denied', 'rejected', g.user['id'],
                           getattr(g, 'auth_session_id', None), 'forbidden')
        return jsonify(error=error.message,details=error.details),error.status

    @app.errorhandler(HTTPException)
    def http_error(error): return jsonify(error='Requisição inválida ou endereço não encontrado.'),error.code

    @app.errorhandler(psycopg.IntegrityError)
    def integrity(error):
        app.logger.warning('Database integrity constraint rejected an operation: %s',error.sqlstate)
        return jsonify(error='A alteração conflita com os dados atuais. Nada foi salvo parcialmente.'),409

    @app.errorhandler(psycopg.OperationalError)
    def unavailable(error):
        app.logger.error('PostgreSQL unavailable (%s)',type(error).__name__)
        return jsonify(error='O banco está indisponível. Seus dados não foram confirmados; tente novamente.'),503

    @app.get('/')
    def index(): return send_from_directory(ROOT/'dist','index.html')

    @app.get('/legacy/')
    def legacy_index(): return send_from_directory(ROOT/'legacy'/'dist','index.html')

    @app.get('/legacy/<path:name>')
    def legacy_file(name): return send_from_directory(ROOT/'legacy'/'dist',name)

    @app.get('/health')
    def health():
        db.get_db().execute('SELECT 1')
        return {'status':'ok','database':'postgresql'}

    return app
