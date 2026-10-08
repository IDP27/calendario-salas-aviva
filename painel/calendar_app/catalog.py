"""Traceable source import and reviewed physical configurations. No inferred resorts."""
import hashlib
import json
from .db import get_db, write_transaction
from .common import Problem, audit, json_value, in_scope, require_capability, ensure_version, required_text, uid


def import_catalog(data, actor=None, preview=False):
    if not isinstance(data,dict) or data.get('versao') != 1 or not isinstance(data.get('itens'),list):
        raise Problem('Catálogo inválido: formato e versão não reconhecidos.')
    items=data['itens']
    codes=[r.get('codigo_fonte') for r in items if isinstance(r,dict)]
    if len(items)!=125 or set(codes)!=set(range(1,126)) or len(codes)!=len(set(codes)):
        raise Problem('Esta carga deve conter os 125 códigos únicos da lista recebida.')
    kinds={'servico','variante_utilizacao_arena','combinacao_ou_configuracao','espaco_sem_composicao_explicita'}
    for row in items:
        if not isinstance(row.get('nome_original'),str) or not row['nome_original'].strip() or len(row['nome_original'])>250 or row.get('classificacao_preliminar') not in kinds or row.get('pagina_fonte') not in (1,2):
            raise Problem('Há item com nome, tipo ou página inválidos.')
        code=row['codigo_fonte']
        if (code in (5,6)) != (row['classificacao_preliminar']=='servico') or (90<=code<=117) != (row['classificacao_preliminar']=='variante_utilizacao_arena'):
            raise Problem('A classificação de serviços ou variantes da Arena não corresponde à fonte.')
    digest=hashlib.sha256(json.dumps(items,ensure_ascii=False,sort_keys=True).encode()).hexdigest()
    with write_transaction() as conn:
        existing={r['code']:r for r in conn.execute('SELECT code,name,kind FROM source_items')}
        changed=[r['codigo_fonte'] for r in items if r['codigo_fonte'] in existing and (existing[r['codigo_fonte']]['name']!=r['nome_original'] or existing[r['codigo_fonte']]['kind']!=r['classificacao_preliminar'])]
        if changed:
            raise Problem('Códigos existentes possuem nomes/tipos diferentes. Revise a fonte; nada foi substituído.',409,changed)
        summary={'items':125,'new':125-len(existing),'services':2,'arena_variants':28,'configurations':99,'already_imported':len(existing)==125,'preview':preview}
        if preview or len(existing)==125:
            return summary
        if existing:
            raise Problem('Catálogo parcial detectado; solicite revisão administrativa.',409)
        for row in items:
            code=row['codigo_fonte']; kind=row['classificacao_preliminar']; config_id=None
            if kind!='servico':
                if kind=='variante_utilizacao_arena':
                    amount=row.get('quantidade_modulos_indicada')
                    suffix='foyer' if row.get('apenas_foyer_indicado') else str(amount)
                    if suffix not in ('1','2','3','foyer'):
                        raise Problem('Configuração da Arena inválida.')
                    config_id=f'arena_{suffix}'
                    name='Arena Sauipe · Apenas Foyer' if suffix=='foyer' else f'Arena Sauipe · {suffix} módulo(s)'
                else:
                    config_id=f'space_{code:03}'; name=row['nome_original']; amount=row.get('quantidade_modulos_indicada')
                exists=conn.execute('SELECT id,source_codes FROM configurations WHERE id=%s',(config_id,)).fetchone()
                if exists:
                    conn.execute('UPDATE configurations SET source_codes=%s WHERE id=%s',(json_value(exists['source_codes']+[code]),config_id))
                else:
                    suggestion=[]
                    if kind=='espaco_sem_composicao_explicita':
                        resource_id=f'resource_{code:03}'
                        conn.execute('INSERT INTO resources(id,name) VALUES (%s,%s)',(resource_id,name))
                        suggestion=[[resource_id]]
                    elif row.get('componentes_candidatos_codigos'):
                        suggestion=[[f'resource_{n:03}' for n in row['componentes_candidatos_codigos']]]
                    notes=row.get('observacao_original') or ''
                    if row.get('pendencias'): notes+='\n'+'\n'.join(row['pendencias'])
                    conn.execute('INSERT INTO configurations(id,name,kind,group_name,source_codes,suggested_options,technical,notes,module_count) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)',
                                 (config_id,name,kind,row.get('grupo_preliminar'),json_value([code]),json_value(suggestion),json_value(row.get('dados_tecnicos_texto_fonte',{})),notes.strip(),amount))
            conn.execute('INSERT INTO source_items(id,code,page,name,kind,payload,configuration_id) VALUES (%s,%s,%s,%s,%s,%s,%s)',
                         (f'pdf_{code:03}',code,row['pagina_fonte'],row['nome_original'],kind,json_value(row),config_id))
        conn.execute('INSERT INTO imports(digest,item_count) VALUES (%s,125)',(digest,))
        audit(conn,actor,'catalog','source_125','import',after=summary)
        return summary


def all_catalog(conn=None):
    return list((conn or get_db()).execute('SELECT * FROM configurations ORDER BY (source_codes->>0)::integer,name'))


def resources_map(conn=None):
    return {r['id']:r for r in (conn or get_db()).execute('SELECT * FROM resources ORDER BY name')}


def config_access(actor, config, resources=None):
    if not in_scope(actor,config['resort_id']): return False
    resources=resources if resources is not None else resources_map()
    return all(rid in resources and in_scope(actor,resources[rid]['resort_id']) for option in config['options'] for rid in option)


def classify(actor,data):
    require_capability(actor,'can_catalog')
    changes=data.get('changes')
    if not isinstance(changes,list) or not 1<=len(changes)<=150:
        raise Problem('Selecione de 1 a 150 espaços para classificar.')
    resort=data.get('resort_id')
    if resort not in (None,'cs','rq') or not in_scope(actor,resort):
        raise Problem('Empreendimento fora do seu escopo.',403)
    location=str(data.get('location','')).strip()
    if len(location)>150: raise Problem('Localização deve ter até 150 caracteres.')
    reason=required_text(data,'reason',500)
    ids=[item.get('id') for item in changes if isinstance(item,dict)]
    if len(ids)!=len(changes) or len(set(ids))!=len(ids): raise Problem('Seleção inválida ou duplicada.')
    with write_transaction() as conn:
        resources=resources_map(conn)
        for change in changes:
            config=conn.execute('SELECT * FROM configurations WHERE id=%s',(change['id'],)).fetchone()
            if not config: raise Problem('Espaço não encontrado.',404)
            if not config_access(actor,config,resources): raise Problem('Espaço fora do seu escopo.',403)
            ensure_version(config,change)
            conn.execute('UPDATE configurations SET resort_id=%s,location=%s,version=version+1 WHERE id=%s',(resort,location,config['id']))
            # Physical metadata follows the source's singleton, never duplicates a resource.
            if config['kind']=='espaco_sem_composicao_explicita':
                rid=f"resource_{config['source_codes'][0]:03}"
                conn.execute('UPDATE resources SET resort_id=%s,location=%s,version=version+1 WHERE id=%s',(resort,location,rid))
            after=conn.execute('SELECT * FROM configurations WHERE id=%s',(config['id'],)).fetchone()
            audit(conn,actor,'configuration',config['id'],'classify',config,after,reason)
    return {'updated':len(changes)}


def validate_topology(actor,config_id,data):
    require_capability(actor,'can_catalog')
    if data.get('attested') is not True:
        raise Problem('Confirme a verificação física e registre a referência usada.')
    reason=required_text(data,'reason',600)
    options=data.get('options')
    if not isinstance(options,list) or not 1<=len(options)<=30:
        raise Problem('Informe os conjuntos físicos permitidos.')
    with write_transaction() as conn:
        resources=resources_map(conn)
        config=conn.execute('SELECT * FROM configurations WHERE id=%s',(config_id,)).fetchone()
        if not config: raise Problem('Espaço não encontrado.',404)
        if not config_access(actor,config,resources): raise Problem('Espaço fora do seu escopo.',403)
        ensure_version(config,data)
        normalized=[]
        for option in options:
            if not isinstance(option,list) or not option or len(option)>30 or any(not isinstance(r,str) or r not in resources for r in option) or len(set(option))!=len(option):
                raise Problem('Conjunto de recursos inválido.')
            if config['module_count'] and len(option)!=config['module_count']:
                raise Problem(f"Esta configuração exige {config['module_count']} recursos físicos.")
            if any(not in_scope(actor,resources[r]['resort_id']) for r in option): raise Problem('Recurso fora do seu escopo.',403)
            normalized.append(sorted(option))
        normalized=sorted({tuple(o) for o in normalized})
        normalized=[list(o) for o in normalized]
        if config['kind']=='espaco_sem_composicao_explicita' and normalized!=[[f"resource_{config['source_codes'][0]:03}"]]:
            raise Problem('Um espaço individual deve manter sua identidade física. Fusões exigem migração revisada.')
        live=conn.execute("SELECT b.id FROM allocations a JOIN bookings b ON b.id=a.booking_id WHERE a.configuration_id=%s AND b.status IN ('waiting','option','confirmed') LIMIT 1",(config_id,)).fetchone()
        if live and normalized!=config['options']:
            raise Problem('Há solicitações na fila ou ocupações nessa configuração. A composição não pode ser trocada enquanto estiverem vigentes.',409)
        for rid in {r for o in normalized for r in o}:
            before=resources[rid]
            conn.execute('UPDATE resources SET validated=true,evidence=%s,version=version+1 WHERE id=%s',(reason,rid))
            audit(conn,actor,'resource',rid,'validate',before,{'validated':True},reason)
        conn.execute('UPDATE configurations SET options=%s,validated=true,version=version+1 WHERE id=%s',(json_value(normalized),config_id))
        after=conn.execute('SELECT * FROM configurations WHERE id=%s',(config_id,)).fetchone()
        audit(conn,actor,'configuration',config_id,'validate_topology',config,after,reason)
        return after


def add_resource(actor,data):
    require_capability(actor,'can_catalog')
    resort=data.get('resort_id')
    if resort not in (None,'cs','rq') or not in_scope(actor,resort): raise Problem('Empreendimento fora do seu escopo.',403)
    name=required_text(data,'name',200); evidence=required_text(data,'evidence',600)
    with write_transaction() as conn:
        resource_id=uid()
        conn.execute('INSERT INTO resources(id,name,resort_id,location,evidence) VALUES (%s,%s,%s,%s,%s)',(resource_id,name,resort,str(data.get('location',''))[:150],evidence))
        audit(conn,actor,'resource',resource_id,'create',after={'name':name,'resort_id':resort},note=evidence)
    return {'id':resource_id}
