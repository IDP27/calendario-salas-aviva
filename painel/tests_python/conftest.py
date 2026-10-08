import json
import os
from uuid import uuid4
import pytest
import psycopg
from psycopg import sql
from calendar_app import create_app, load_environment, ROOT
from calendar_app.db import migrate, get_db, write_transaction
from calendar_app.catalog import import_catalog
from calendar_app.auth import create_user

PASSWORD='Teste-isolado-2026!'


@pytest.fixture
def app():
    load_environment()
    url=os.environ.get('TEST_DATABASE_URL') or os.environ['DATABASE_URL']
    schema='test_salas_'+uuid4().hex
    with psycopg.connect(url,autocommit=True) as conn:
        conn.execute(sql.SQL('CREATE SCHEMA {}').format(sql.Identifier(schema)))
    app=create_app({'TESTING':True,'DATABASE_URL':url,'DB_SCHEMA':schema,'SECRET_KEY':'isolated-test-secret','SESSION_COOKIE_SECURE':False})
    with app.app_context():
        migrate()
        import_catalog(json.loads((ROOT/'docs/catalogo-salas-preliminar.json').read_text()))
        with write_transaction() as conn:
            for username,team,catalog,schedule,admin in [('admin','commercial',True,True,True),('seller','commercial',False,False,False),('ops','operations',False,False,False),('reviewer','operations',True,False,False)]:
                create_user(conn,dict(username=username,name=username,password=PASSWORD,team_id=team,can_catalog=catalog,can_schedule=schedule,can_manage_users=admin))
    yield app
    with psycopg.connect(url,autocommit=True) as conn:
        conn.execute(sql.SQL('DROP SCHEMA {} CASCADE').format(sql.Identifier(schema)))


class API:
    def __init__(self,app,user='admin'):
        self.client=app.test_client()
        csrf=self.client.get('/api/session').json['csrf']
        login=self.client.post('/api/login',json={'username':user,'password':PASSWORD},headers={'X-CSRF-Token':csrf})
        assert login.status_code==200,login.json
        self.csrf=login.json['csrf'];self.user=login.json['user']
    def get(self,path): return self.client.get('/api'+path)
    def send(self,path,body,method='POST',key=None):
        return self.client.open('/api'+path,method=method,json=body,headers={'X-CSRF-Token':self.csrf,'Idempotency-Key':key or str(uuid4())})
    def config(self,code):
        return next(c for c in self.get('/catalog').json['configurations'] if c['id']==f'space_{code:03}')
    def validate(self,code,options=None):
        c=self.config(code)
        result=self.send(f"/catalog/{c['id']}/topology",{'version':c['version'],'options':options or c['suggested_options'],'reason':'Dados fictícios de homologação usados exclusivamente em teste','attested':True})
        assert result.status_code==200,result.json
        return result.json
    def create(self,code=7,status='waiting',start='2027-01-10',end='2027-01-12',allocations=None,**extra):
        body={'title':'Evento de teste','responsible':'Responsável de teste','status':status,'allocations':allocations or [allocation(code,start,end)],**extra}
        return self.send('/bookings',body)
    def promote(self,booking): return self.send(f"/bookings/{booking['id']}/promote",{'version':booking['version']})
    def detail(self,booking): return self.get(f"/bookings/{booking['id']}").json['booking']


def allocation(code,start='2027-01-10',end='2027-01-12',phase='event',resources=None):
    result={'configuration_id':f'space_{code:03}' if isinstance(code,int) else code,'start_date':start,'end_date':end,'phase':phase}
    if resources is not None: result['resources']=resources
    return result


def edit_body(booking,**changes):
    return {'version':booking['version'],'title':booking['title'],'responsible':booking['responsible'],'notes':booking['notes'],'status':booking['status'],
            'allocations':[{k:a[k] for k in ('configuration_id','phase','start_date','end_date','resources')} for a in booking['allocations']],**changes}


@pytest.fixture
def api(app): return API(app)
