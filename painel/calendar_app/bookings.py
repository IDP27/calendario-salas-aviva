from datetime import date, timedelta
import hashlib
import json
from .common import Problem, uid, required_text, ensure_version, audit, json_value, serialize
from .catalog import all_catalog, resources_map, config_access
from .db import get_db, write_transaction

LABELS={'pending':'Pendente de validação','waiting':'Em espera','option':'Em opção prioritária','confirmed':'Confirmado','cancelled':'Cancelado'}
ACTIVE={'option','confirmed'}


def day(value):
    try:
        if not isinstance(value,str) or len(value)!=10: raise ValueError()
        result=date.fromisoformat(value)
        if result.isoformat()!=value: raise ValueError()
        return result
    except (ValueError,TypeError):
        raise Problem('Informe uma data válida no formato AAAA-MM-DD.')


def period(start,end):
    first,last=day(start),day(end)
    if first>last or first<date(2026,1,1) or last>date(2028,12,31):
        raise Problem('O período deve estar entre 01/01/2026 e 31/12/2028, com término igual ou posterior ao início.')
    return first,last+timedelta(days=1)


def get_booking(conn, booking_id):
    booking=conn.execute('SELECT b.*, t.name AS team_name,u.name AS creator_name FROM bookings b JOIN teams t ON t.id=b.team_id JOIN users u ON u.id=b.created_by WHERE b.id=%s',(booking_id,)).fetchone()
    if not booking: raise Problem('Solicitação não encontrada.',404)
    booking['allocations']=list(conn.execute('SELECT a.*,c.name AS space_name,c.resort_id,c.location FROM allocations a JOIN configurations c ON c.id=a.configuration_id WHERE booking_id=%s ORDER BY a.id',(booking_id,)))
    for a in booking['allocations']:
        a['end_date']=a['end_exclusive']-timedelta(days=1)
    return booking


def accessible(actor,booking,configs=None,resources=None):
    configs=configs if configs is not None else {c['id']:c for c in all_catalog()}
    resources=resources if resources is not None else resources_map()
    return all(a['configuration_id'] in configs and config_access(actor,configs[a['configuration_id']],resources) for a in booking['allocations'])


def cells(allocations):
    result=set()
    for a in allocations:
        start=a['start_date'] if isinstance(a['start_date'],date) else day(a['start_date'])
        end=a['end_exclusive'] if isinstance(a['end_exclusive'],date) else day(a['end_exclusive'])
        for offset in range((end-start).days):
            result.update((rid,start+timedelta(days=offset)) for rid in a['resources'])
    return result


def normalize_allocations(conn,actor,raw,status):
    if not isinstance(raw,list) or not 1<=len(raw)<=40:
        raise Problem('Inclua de 1 a 40 períodos/espaços.')
    configs={c['id']:c for c in all_catalog(conn)}; resources=resources_map(conn)
    result=[]
    for item in raw:
        if not isinstance(item,dict): raise Problem('Período inválido.')
        conf=configs.get(item.get('configuration_id'))
        if not conf or not conf['active']: raise Problem('Selecione um espaço ativo do catálogo.')
        if not config_access(actor,conf,resources): raise Problem('Espaço fora do seu escopo.',403)
        first,end=period(item.get('start_date'),item.get('end_date'))
        phase=item.get('phase','event')
        if phase not in ('setup','event','teardown'): raise Problem('Fase inválida.')
        chosen=item.get('resources')
        if chosen is None: chosen=conf['options'][0] if len(conf['options'])==1 else []
        if not isinstance(chosen,list) or any(not isinstance(r,str) for r in chosen) or len(set(chosen))!=len(chosen): raise Problem('Seleção física inválida.')
        chosen=sorted(chosen)
        valid=conf['validated'] and chosen and chosen in conf['options'] and all(resources.get(r,{}).get('validated') and resources[r]['active'] for r in chosen)
        if status!='pending' and not valid:
            raise Problem(f"{conf['name']}: a composição física precisa ser validada. Registre como Pendente de validação.",422)
        if chosen and not valid:
            raise Problem('Não use uma composição que ainda não foi homologada. Remova a seleção para registrar a pendência.',422)
        result.append({'configuration_id':conf['id'],'phase':phase,'start_date':first,'end_exclusive':end,'resources':chosen})
    # Stable normalization lets repeated/overlapping phases produce a physical set, not duplicates.
    return sorted(result,key=lambda a:(a['configuration_id'],a['start_date'],a['end_exclusive'],a['phase'],a['resources']))


def occupation_conflicts(conn,wanted,exclude=None):
    if not wanted: return set()
    first=min(d for _,d in wanted); last=max(d for _,d in wanted)
    occupied=conn.execute('SELECT * FROM occupations WHERE day BETWEEN %s AND %s AND booking_id<>%s',(first,last,exclude or ''))
    return {(r['resource_id'],r['day']) for r in occupied}&wanted


def ensure_priority(conn, booking, wanted, old_cells=None):
    if occupation_conflicts(conn,wanted,booking['id']):
        raise Problem('Há ocupação efetiva em pelo menos um espaço/dia. Nenhuma sala foi reservada parcialmente.',409)
    added=wanted-(old_cells or set())
    for earlier in conn.execute("SELECT id FROM bookings WHERE status='waiting' AND queue_number<%s AND id<>%s ORDER BY queue_number",(booking['queue_number'],booking['id'])):
        other=get_booking(conn,earlier['id']); other_cells=cells(other['allocations'])
        if other_cells&added and not occupation_conflicts(conn,other_cells,booking['id']):
            raise Problem('Uma solicitação anterior e disponível tem prioridade sobre esse período. Consulte a fila.',409)


def allocation_signature(allocations):
    return sorted((a['configuration_id'],a['phase'],str(a['start_date']),str(a['end_exclusive']),tuple(sorted(a['resources']))) for a in allocations)


def save_booking(actor,data,booking_id=None,idempotency_key=None):
    if not isinstance(data,dict): raise Problem('Formulário inválido.')
    forbidden={'team_id','created_by','updated_by','queue_number','created_at','updated_at'}&data.keys()
    if forbidden: raise Problem('Equipe, autoria e prioridade são definidas pelo servidor.',403)
    request_hash=hashlib.sha256(json.dumps(data,sort_keys=True).encode()).hexdigest()
    with write_transaction() as conn:
        if not booking_id:
            if not isinstance(idempotency_key,str) or not 8<=len(idempotency_key)<=100:
                raise Problem('A requisição precisa de uma chave de salvamento.')
            replay=conn.execute('SELECT * FROM idempotency WHERE user_id=%s AND key=%s',(actor['id'],idempotency_key)).fetchone()
            if replay:
                if replay['request_hash']!=request_hash: raise Problem('A chave de salvamento foi reutilizada com outro conteúdo.',409)
                return replay['response']
        before=get_booking(conn,booking_id) if booking_id else None
        if before:
            if not accessible(actor,before) or before['team_id']!=actor['team_id']:
                raise Problem('Cada equipe altera apenas suas próprias solicitações.',403)
            ensure_version(before,data)
            if before['status']=='cancelled': raise Problem('Solicitação cancelada: crie uma nova para preservar o histórico.',409)
        status=data.get('status','pending')
        allowed={'pending','waiting'} if not before or before['status'] in ('pending','waiting') else {before['status'],'waiting','pending'}
        if before and before['status']=='option': allowed.add('confirmed')
        if status not in allowed:
            raise Problem('Mudança de situação não permitida. A opção prioritária depende de promoção pela fila.',409)
        allocations=normalize_allocations(conn,actor,data.get('allocations'),status)
        title=required_text(data,'title',180); responsible=required_text(data,'responsible',120)
        notes=data.get('notes','')
        if not isinstance(notes,str) or len(notes)>4000: raise Problem('Observações devem ter até 4.000 caracteres.')
        old=cells(before['allocations']) if before else set()
        if before:
            reset_queue=(status=='waiting' and (before['status']!='waiting' or allocation_signature(allocations)!=allocation_signature(before['allocations'])))
            conn.execute('UPDATE bookings SET title=%s,responsible=%s,notes=%s,status=%s,updated_by=%s,updated_at=now(),version=version+1 WHERE id=%s',(title,responsible,notes,status,actor['id'],booking_id))
            if reset_queue: conn.execute('UPDATE bookings SET queue_number=DEFAULT WHERE id=%s',(booking_id,))
            conn.execute('DELETE FROM allocations WHERE booking_id=%s',(booking_id,))
        else:
            booking_id=uid()
            conn.execute('INSERT INTO bookings(id,team_id,title,responsible,notes,status,created_by,updated_by) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)',(booking_id,actor['team_id'],title,responsible,notes,status,actor['id'],actor['id']))
        for a in allocations:
            conn.execute('INSERT INTO allocations(booking_id,configuration_id,phase,start_date,end_exclusive,resources) VALUES (%s,%s,%s,%s,%s,%s)',(booking_id,a['configuration_id'],a['phase'],a['start_date'],a['end_exclusive'],json_value(a['resources'])))
        after=get_booking(conn,booking_id)
        wanted=cells(allocations)
        if status in ACTIVE: ensure_priority(conn,after,wanted,old)
        conn.execute('DELETE FROM occupations WHERE booking_id=%s',(booking_id,))
        if status in ACTIVE:
            for resource_id,occupied_day in sorted(wanted):
                conn.execute('INSERT INTO occupations VALUES (%s,%s,%s)',(resource_id,occupied_day,booking_id))
        audit(conn,actor,'booking',booking_id,'update' if before else 'create',before,after)
        response=serialize(after)
        if not before:
            conn.execute('INSERT INTO idempotency VALUES (%s,%s,%s,%s)',(actor['id'],idempotency_key,request_hash,json_value(response)))
        return response


def transition(actor,booking_id,data,action):
    with write_transaction() as conn:
        before=get_booking(conn,booking_id)
        if not accessible(actor,before): raise Problem('Solicitação fora do seu escopo.',403)
        ensure_version(before,data)
        if action=='cancel':
            if before['team_id']!=actor['team_id']: raise Problem('Cada equipe cancela apenas suas próprias solicitações.',403)
            if before['status']=='cancelled': raise Problem('Solicitação já cancelada.',409)
            status='cancelled'; reason=required_text(data,'reason',600)
        elif action=='promote':
            if not actor['can_schedule']: raise Problem('A promoção é exclusiva do responsável da fila.',403)
            if before['status']!='waiting': raise Problem('Somente uma solicitação em espera pode receber a opção prioritária.',409)
            # Revalidate every allocation at the point of promotion.
            raw=[dict(a,end_date=str(a['end_date']),start_date=str(a['start_date'])) for a in before['allocations']]
            allocations=normalize_allocations(conn,actor,raw,'option')
            wanted=cells(allocations)
            ensure_priority(conn,before,wanted)
            for resource_id,occupied_day in sorted(wanted): conn.execute('INSERT INTO occupations VALUES (%s,%s,%s)',(resource_id,occupied_day,booking_id))
            status='option'; reason='Promoção manual por ordem de entrada, com disponibilidade integral.'
        else: raise Problem('Ação inválida.')
        conn.execute('UPDATE bookings SET status=%s,updated_by=%s,updated_at=now(),version=version+1 WHERE id=%s',(status,actor['id'],booking_id))
        if status=='cancelled': conn.execute('DELETE FROM occupations WHERE booking_id=%s',(booking_id,))
        after=get_booking(conn,booking_id)
        audit(conn,actor,'booking',booking_id,action,before,after,reason)
        return serialize(after)


def list_bookings(actor,start,end,resort='all',status='',search=''):
    first,exclusive=period(start,end)
    conn=get_db(); configs={c['id']:c for c in all_catalog(conn)}; resources=resources_map(conn)
    ids=conn.execute('SELECT DISTINCT b.id,b.queue_number FROM bookings b JOIN allocations a ON a.booking_id=b.id WHERE a.start_date<%s AND a.end_exclusive>%s ORDER BY b.queue_number',(exclusive,first))
    result=[]
    import unicodedata
    def normalize(s): return ''.join(c for c in unicodedata.normalize('NFD',s.lower()) if unicodedata.category(c)!='Mn')
    for r in ids:
        booking=get_booking(conn,r['id'])
        if not accessible(actor,booking,configs,resources): continue
        visible_allocations=[a for a in booking['allocations'] if a['start_date']<exclusive and a['end_exclusive']>first and (resort=='all' or (a['resort_id'] or 'unassigned')==resort)]
        if not visible_allocations or (status and booking['status']!=status): continue
        if search and normalize(search) not in normalize(' '.join([booking['title'],booking['responsible'],booking['team_name']]+[a['space_name'] for a in visible_allocations])): continue
        booking['matched_allocations']=visible_allocations
        result.append(booking)
    return result
