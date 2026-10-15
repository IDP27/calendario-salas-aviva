"""Read models for availability and calendar snapshots."""
from datetime import timedelta

from .bookings import filter_bookings, list_bookings, period
from .catalog import all_catalog, config_access, resources_map
from .common import Problem, serialize
from .db import get_db


def availability_snapshot(actor, q):
    first,end=period(q['start'],q['end']); conn=get_db()
    with conn.transaction():
        conn.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY')
        resources=resources_map(conn); results=[]
        occupied={(row['resource_id'],row['day']) for row in conn.execute(
            'SELECT resource_id,day FROM occupations WHERE day>=%s AND day<%s',
            (first,end))}
        allocations=list(conn.execute('''SELECT a.booking_id,a.configuration_id,a.phase,a.start_date,a.end_exclusive,a.resources,b.status
                                         FROM allocations a JOIN bookings b ON b.id=a.booking_id
                                         WHERE b.status IN ('reserved','confirmed')
                                           AND a.start_date<%s AND a.end_exclusive>%s
                                         ORDER BY a.start_date,a.end_exclusive,a.id''',(end,first)))
        request_ids={}
        for a in allocations:
            if a['status']=='reserved':
                request_ids.setdefault(a['configuration_id'],{}).setdefault(a['status'],set()).add(a['booking_id'])
        for config in all_catalog(conn):
            if not config_access(actor,config,resources) or (q['resort']!='all' and (config['resort_id'] or 'unassigned')!=q['resort']): continue
            config_resources={rid for option in config['options'] for rid in option}
            matching=[]
            for a in allocations:
                exact=a['configuration_id']==config['id']
                shared=bool(config_resources.intersection(a['resources']))
                if exact or shared:
                    matching.append({'status':a['status'],'phase':a['phase'],'start_date':a['start_date'],
                                     'end_date':a['end_exclusive']-timedelta(days=1),'related':not exact})
            periods=list(dict.fromkeys((p['status'],p['phase'],p['start_date'],p['end_date'],p['related']) for p in matching))
            periods=[{'status':status,'phase':phase,'start_date':start,'end_date':last,'related':related}
                     for status,phase,start,last,related in periods]
            periods.sort(key=lambda p:(p['status']!='confirmed',p['start_date'],p['end_date'],p['related']))
            exact_occupation=any(p['status']=='confirmed' and not p['related'] for p in periods)
            choices=[]
            for option in config['options'] if config['validated'] else []:
                wanted={(rid,first+timedelta(days=i)) for rid in option for i in range((end-first).days)}
                choices.append({'resources':option,'available':not exact_occupation and wanted.isdisjoint(occupied)})
            results.append({'id':config['id'],'name':config['name'],'resort_id':config['resort_id'],
                            'validated':config['validated'],'options':choices,'available':False if exact_occupation else any(o['available'] for o in choices) if choices else None,
                            'reserved_count':len(request_ids.get(config['id'],{}).get('reserved',set())),
                            'periods':periods})
        return serialize({'results':results,'note':'Reservado registra a demanda sem bloquear a sala. Somente Confirmado gera ocupação efetiva; a confirmação respeita a fila.'})



def calendar_snapshot(actor, q):
    first,end=period(q['start'],q['end'])
    if (end-first).days>62: raise Problem('A grade permite até 62 dias por consulta.')
    conn=get_db()
    with conn.transaction():
        conn.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY')
        resources=resources_map(conn)
        configs=[c for c in all_catalog(conn) if config_access(actor,c,resources)]
        missing=sum(c['resort_id'] is None for c in configs)
        configs=[c for c in configs if q['resort']=='all' or (c['resort_id'] or 'unassigned')==q['resort']]
        all_visible=list_bookings(actor,q['start'],q['end'])
        visible_by_id={b['id']:b for b in all_visible}
        filtered=filter_bookings(all_visible,first,end,q['resort'],q['status'],q['search'])
        occupations={(r['resource_id'],r['day']):r['booking_id'] for r in conn.execute('SELECT * FROM occupations WHERE day>=%s AND day<%s',(first,end))}
        exact_occupations={}
        for a in conn.execute('''SELECT a.configuration_id,a.start_date,a.end_exclusive,a.booking_id
                                 FROM allocations a JOIN bookings b ON b.id=a.booking_id
                                 WHERE b.status='confirmed' AND a.start_date<%s AND a.end_exclusive>%s''',(end,first)):
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
                reserved=[b['id'] for b in filtered if b['status']=='reserved' and any(
                    a['start_date']<=d<a['end_exclusive'] and
                    (a['configuration_id']==config['id'] or
                     config_resources.intersection(a['resources']))
                    for a in b['allocations'])]
                config['days'][d.isoformat()]={'state':state,'bookings':[bid for bid in sorted(matches) if bid in visible_by_id],
                                              'restricted':any(bid not in visible_by_id for bid in matches),'requests':reserved}
        return serialize({'configurations':configs,'bookings':filtered,'occupying_bookings':all_visible,'days':days,
                          'unassigned_count':missing,'server_time':conn.execute('SELECT now() AS t').fetchone()['t']})
