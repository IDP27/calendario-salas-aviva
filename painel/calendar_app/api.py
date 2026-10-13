import csv
import io
from datetime import timedelta
from flask import Blueprint, g, request, Response
from .auth import login_required, create_user, public_user, security_event
from .db import get_db, write_transaction
from .common import Problem, serialize, require_capability, audit, ensure_version, in_scope, json_value
from .catalog import all_catalog, resources_map, config_access, classify, validate_topology, add_resource, import_catalog
from .bookings import list_bookings, period, get_booking, accessible, save_booking, transition, LABELS, occupation_conflicts

bp=Blueprint('api',__name__,url_prefix='/api')


def query():
    resort=request.args.get('resort','all')
    if resort not in ('all','cs','rq','unassigned'): raise Problem('Filtro de empreendimento inválido.')
    status=request.args.get('status','')
    if status and status not in LABELS: raise Problem('Situação inválida.')
    return {'start':request.args.get('from','2026-01-01'),'end':request.args.get('to','2028-12-31'),
            'resort':resort,'status':status,'search':request.args.get('search','')[:200]}


@bp.get('/catalog')
@login_required
def catalog_get():
    conn=get_db(); resources=resources_map(conn)
    configs=[c for c in all_catalog(conn) if config_access(g.user,c,resources)]
    return serialize({'configurations':configs,'resources':[r for r in resources.values() if in_scope(g.user,r['resort_id'])],
                      'source_count':conn.execute('SELECT count(*) AS n FROM source_items').fetchone()['n'],
                      'resorts':list(conn.execute('SELECT * FROM resorts ORDER BY id'))})


@bp.post('/catalog/classify')
@login_required
def catalog_classify(): return classify(g.user,request.get_json())


@bp.post('/catalog/<config_id>/topology')
@login_required
def topology(config_id): return serialize(validate_topology(g.user,config_id,request.get_json()))


@bp.post('/resources')
@login_required
def resource_add(): return add_resource(g.user,request.get_json()),201


@bp.get('/catalog/sources')
@login_required
def sources():
    require_capability(g.user,'can_catalog')
    return serialize({'items':list(get_db().execute('SELECT * FROM source_items ORDER BY code'))})


@bp.post('/catalog/import')
@login_required
def catalog_import():
    require_capability(g.user,'can_catalog')
    data=request.get_json()
    return import_catalog(data.get('catalog'),g.user,preview=data.get('confirm') is not True)


@bp.get('/bookings')
@login_required
def booking_list(): return serialize({'bookings':list_bookings(g.user,**query())})


@bp.get('/bookings/<booking_id>')
@login_required
def booking_get(booking_id):
    booking=get_booking(get_db(),booking_id)
    if not accessible(g.user,booking): raise Problem('Solicitação fora do seu escopo.',403)
    history=list(get_db().execute("SELECT a.*,u.name AS actor_name FROM audit a LEFT JOIN users u ON u.id=a.actor_id WHERE entity_type='booking' AND entity_id=%s ORDER BY a.id DESC",(booking_id,)))
    return serialize({'booking':booking,'history':history})


@bp.post('/bookings')
@login_required
def booking_create(): return save_booking(g.user,request.get_json(),idempotency_key=request.headers.get('Idempotency-Key')),201


@bp.put('/bookings/<booking_id>')
@login_required
def booking_update(booking_id): return save_booking(g.user,request.get_json(),booking_id)


@bp.post('/bookings/<booking_id>/<action>')
@login_required
def booking_action(booking_id,action): return transition(g.user,booking_id,request.get_json(),action)


@bp.get('/availability')
@login_required
def availability():
    q=query(); first,end=period(q['start'],q['end']); conn=get_db()
    with conn.transaction():
        conn.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY')
        resources=resources_map(conn); results=[]
        allocations=list(conn.execute('''SELECT a.booking_id,a.configuration_id,a.phase,a.start_date,a.end_exclusive,a.resources,b.status
                                         FROM allocations a JOIN bookings b ON b.id=a.booking_id
                                         WHERE b.status IN ('pending','waiting','option','confirmed')
                                           AND a.start_date<%s AND a.end_exclusive>%s
                                         ORDER BY a.start_date,a.end_exclusive,a.id''',(end,first)))
        request_ids={}
        for a in allocations:
            if a['status'] in ('pending','waiting'):
                request_ids.setdefault(a['configuration_id'],{}).setdefault(a['status'],set()).add(a['booking_id'])
        for config in all_catalog(conn):
            if not config_access(g.user,config,resources) or (q['resort']!='all' and (config['resort_id'] or 'unassigned')!=q['resort']): continue
            config_resources={rid for option in config['options'] for rid in option}
            matching=[]
            for a in allocations:
                exact=a['configuration_id']==config['id']
                shared=a['status'] in ('option','confirmed') and bool(config_resources.intersection(a['resources']))
                if exact or shared:
                    matching.append({'status':a['status'],'phase':a['phase'],'start_date':a['start_date'],
                                     'end_date':a['end_exclusive']-timedelta(days=1),'related':not exact})
            periods=list(dict.fromkeys((p['status'],p['phase'],p['start_date'],p['end_date'],p['related']) for p in matching))
            periods=[{'status':status,'phase':phase,'start_date':start,'end_date':last,'related':related}
                     for status,phase,start,last,related in periods]
            exact_occupation=any(p['status'] in ('option','confirmed') and not p['related'] for p in periods)
            choices=[]
            for option in config['options'] if config['validated'] else []:
                wanted={(rid,first+timedelta(days=i)) for rid in option for i in range((end-first).days)}
                choices.append({'resources':option,'available':not exact_occupation and not occupation_conflicts(conn,wanted)})
            results.append({'id':config['id'],'name':config['name'],'resort_id':config['resort_id'],
                            'validated':config['validated'],'options':choices,'available':False if exact_occupation else any(o['available'] for o in choices) if choices else None,
                            'pending_count':len(request_ids.get(config['id'],{}).get('pending',set())),
                            'waiting_count':len(request_ids.get(config['id'],{}).get('waiting',set())),
                            'periods':periods})
        return serialize({'results':results,'note':'Solicitações pendentes e em espera não ocupam a sala. Somente opções prioritárias e confirmações geram ocupação efetiva; a promoção respeita a fila.'})


@bp.get('/calendar')
@login_required
def calendar():
    q=query(); first,end=period(q['start'],q['end'])
    if (end-first).days>62: raise Problem('A grade permite até 62 dias por consulta.')
    conn=get_db()
    with conn.transaction():
        conn.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY')
        resources=resources_map(conn)
        configs=[c for c in all_catalog(conn) if config_access(g.user,c,resources)]
        missing=sum(c['resort_id'] is None for c in configs)
        configs=[c for c in configs if q['resort']=='all' or (c['resort_id'] or 'unassigned')==q['resort']]
        all_visible=list_bookings(g.user,q['start'],q['end'])
        visible_by_id={b['id']:b for b in all_visible}
        filtered=list_bookings(g.user,**q)
        occupations={(r['resource_id'],r['day']):r['booking_id'] for r in conn.execute('SELECT * FROM occupations WHERE day>=%s AND day<%s',(first,end))}
        exact_occupations={}
        for a in conn.execute('''SELECT a.configuration_id,a.start_date,a.end_exclusive,a.booking_id
                                 FROM allocations a JOIN bookings b ON b.id=a.booking_id
                                 WHERE b.status IN ('option','confirmed') AND a.start_date<%s AND a.end_exclusive>%s''',(end,first)):
            for offset in range((min(a['end_exclusive'],end)-max(a['start_date'],first)).days):
                key=(a['configuration_id'],max(a['start_date'],first)+timedelta(days=offset))
                exact_occupations.setdefault(key,set()).add(a['booking_id'])
        days=[first+timedelta(days=i) for i in range((end-first).days)]
        for config in configs:
            config['days']={}
            config_resources = {rid for option in config['options'] for rid in option}
            for d in days:
                exact_matches=exact_occupations.get((config['id'],d),set())
                matches=exact_matches|{occupations[(rid,d)] for option in config['options'] for rid in option if (rid,d) in occupations}
                free=sum(not any((r,d) in occupations for r in option) for option in config['options'])
                state='occupied' if exact_matches else 'unvalidated' if not config['validated'] else 'available' if free==len(config['options']) else 'partial' if free else 'occupied'
                pending=[b['id'] for b in filtered if b['status'] in ('pending','waiting') and any(
                    a['start_date']<=d<a['end_exclusive'] and
                    (a['configuration_id']==config['id'] or
                     (b['status']=='waiting' and config_resources.intersection(a['resources'])))
                    for a in b['allocations'])]
                config['days'][d.isoformat()]={'state':state,'bookings':[bid for bid in sorted(matches) if bid in visible_by_id],
                                              'restricted':any(bid not in visible_by_id for bid in matches),'requests':pending}
        return serialize({'configurations':configs,'bookings':filtered,'occupying_bookings':all_visible,'days':days,
                          'unassigned_count':missing,'server_time':conn.execute('SELECT now() AS t').fetchone()['t']})


def safe_cell(value):
    text=str(value or '')
    if text.lstrip().startswith(('=','+','-','@')): text="'"+text
    return text


@bp.get('/reports.csv')
@login_required
def report_csv():
    output=io.StringIO(); writer=csv.writer(output,delimiter=';',lineterminator='\r\n',quoting=csv.QUOTE_ALL)
    writer.writerow(['Solicitação','Evento','Empreendimento','Espaço','Fase','Início','Último dia','Situação','Equipe','Responsável'])
    for b in list_bookings(g.user,**query()):
        for a in b['matched_allocations']:
            row=[b['id'],b['title'],{'cs':'Costa do Sauípe','rq':'Rio Quente',None:'Empreendimento a identificar'}[a['resort_id']],a['space_name'],{'setup':'Montagem','event':'Evento','teardown':'Desmontagem'}[a['phase']],str(a['start_date']),str(a['end_date']),LABELS[b['status']],b['team_name'],b['responsible']]
            writer.writerow([safe_cell(v) for v in row])
    return Response('\ufeff'+output.getvalue(),content_type='text/csv; charset=utf-8',headers={'Content-Disposition':'attachment; filename="calendario-salas.csv"'})


@bp.get('/users')
@login_required
def users_get():
    require_capability(g.user,'can_manage_users')
    return {'users':[public_user(u) for u in get_db().execute('SELECT * FROM users ORDER BY name')]}


@bp.post('/users')
@login_required
def users_add():
    require_capability(g.user,'can_manage_users')
    with write_transaction() as conn: user=create_user(conn,request.get_json(),g.user)
    return public_user(user),201


@bp.put('/users/<user_id>')
@login_required
def users_edit(user_id):
    require_capability(g.user,'can_manage_users'); data=request.get_json()
    with write_transaction() as conn:
        user=conn.execute('SELECT * FROM users WHERE id=%s',(user_id,)).fetchone()
        if not user: raise Problem('Usuário não encontrado.',404)
        ensure_version(user,data)
        if user_id==g.user['id']: raise Problem('Peça a outro administrador para alterar seu próprio acesso.')
        scopes=data.get('scopes',user['scopes'])
        if not isinstance(scopes,list) or not scopes or any(s not in ['cs','rq','unassigned'] for s in scopes): raise Problem('Escopo inválido.')
        conn.execute('UPDATE users SET scopes=%s,can_catalog=%s,can_schedule=%s,can_manage_users=%s,active=%s,version=version+1 WHERE id=%s',
                     (json_value(scopes),data.get('can_catalog') is True,data.get('can_schedule') is True,data.get('can_manage_users') is True,data.get('active') is True,user_id))
        conn.execute('UPDATE auth_sessions SET revoked_at=now() WHERE user_id=%s AND revoked_at IS NULL',(user_id,))
        after=conn.execute('SELECT * FROM users WHERE id=%s',(user_id,)).fetchone()
        audit(conn,g.user,'user',user_id,'access_update',public_user(user),public_user(after))
        security_event(conn,'access_change','accepted',user_id,reason='sessions_revoked')
        return public_user(after)


@bp.get('/audit/catalog')
@login_required
def catalog_audit():
    require_capability(g.user,'can_catalog')
    return serialize({'history':list(get_db().execute("SELECT a.*,u.name AS actor_name FROM audit a LEFT JOIN users u ON u.id=a.actor_id WHERE entity_type IN ('configuration','resource','catalog') ORDER BY a.id DESC LIMIT 300"))})


@bp.get('/audit/auth')
@login_required
def auth_audit():
    require_capability(g.user, 'can_manage_users')
    rows = get_db().execute('''SELECT e.id,e.occurred_at,e.event_type,e.result,e.session_id,
                                     e.request_id,e.reason,u.name AS user_name
                              FROM auth_events e LEFT JOIN users u ON u.id=e.user_id
                              ORDER BY e.id DESC LIMIT 300''')
    return serialize({'events': list(rows)})
