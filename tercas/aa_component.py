"""Explicit AA-web component ceilings, never actual deflections or global ELS.

The three portable methods remain separate choices. Fresh calculations verify
source files. Historical presentation validates stored identities only and does
not run a comparator, source gate, section solver, Green solver or selector.
"""
import copy
from fractions import Fraction as F
import hashlib
import json
import math
from pathlib import Path
import types
import uuid

from .biaxial_component import eligible_choice, _entries, _limit, _sources, PINS
from .aa_component_contract import CONTRACT

MODE = 'aa_web_family_bound_component_v1'
LOCAL_MODE = 'aa_web_local_partition_bound_component_v1'
POSITIVE_MODE = 'aa_web_positive_ratio_bound_component_v1'
METHODS = {MODE:'family', LOCAL_MODE:'local_partition', POSITIVE_MODE:'positive_ratio'}
MODES = tuple(METHODS)
LABEL = 'Teto flexional biaxial — somente alma AA reduzível'
METHOD_LABELS = {MODE:'Família AA, domínio único', LOCAL_MODE:'Família AA com partição local',
                 POSITIVE_MODE:'Família AA com razão positiva'}
FIELD = 'aa_web_component_evidence'
SCHEMA = 'own_Ue_aa_web_component_snapshot_v1'
GIRT_SCHEMA = 'own_Ue_isolated_girt_aa_web_component_snapshot_v1'
SCHEMAS = (SCHEMA,GIRT_SCHEMA)
ROW = 'Teto normal — componente flexional biaxial AA'
GIRT_ROW = 'Teto horizontal — componente flexional biaxial AA'
ROWS = (ROW,GIRT_ROW)
BUNDLE_MANIFEST = 'efa22491705213d7e5d1b51f75e945f8677b8a99a1ffca494d3914167ed8a812'
LOADER_SHA = '5724db13d47d130e95d508cff7f39f01ce244e5ee71f4f84c5e8f8082af1327c'
REFINEMENT_BUDGET = 64
SOURCE = 'NBR 14762:2010 §9.2.2, Tabela 5, §9.2.3 e §9.8.5; teto derivado AA/PSD/Green da componente flexional'
TEXT = ('Teto conservador do máximo absoluto da componente normal da flexão biaxial, '
        'com ações simultâneas e somente a alma admitida reduzível pela lei AA. Mesas, '
        'lábios e dobras permanecem integrais e exigem suas guardas. Não é flecha exata, '
        'estimativa de flecha, inércia escalar nem prova de alma realmente reduzida. '
        'Teto menor ou igual ao limite declarado demonstra suficiência apenas desta '
        'componente no modelo; teto maior ou crivo inconclusivo permanece pendente, '
        'não demonstra falha física. Torção, empenamento, cisalhamento, ligações, '
        'instabilidade e ELS físico completo não são aprovados.')
PENDING = 'Sem teto utilizável nesta rota; não há índice recuperado da flecha escalar ou de outro método.'
AXIS = ('Vetores locais [normal, paralelo] mantidos em [Mx, My] do contrato '
        'b=[1,y-yc,-x], R=[0,Mx,My], -d\'\'=[kappa_x,kappa_y]. '
        'Sem rotação adicional, projeção ou duplicação do peso próprio.')


def digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),
        ensure_ascii=True,allow_nan=False).encode()).hexdigest()


def selected(data):
    return isinstance(data,dict) and data.get('deflection_model') in MODES


def scope_text(data):
    return TEXT.replace('componente normal','componente horizontal normal ao fechamento') if data.get('member_application')=='wall_girt' else TEXT


def _schema(data):
    return GIRT_SCHEMA if data.get('member_application')=='wall_girt' else SCHEMA


def activate(data, mode=MODE):
    if mode not in MODES or not eligible_choice(data):
        raise ValueError('Teto AA exclusivo das sete referências próprias Ue de viga isolada, com aplicação explícita.')
    out=copy.deepcopy(data);out['deflection_model']=mode
    return out


def _bundle():
    path=Path(__file__).parent/'aa_bundle/aa_portable.py'
    source=path.read_bytes()
    if hashlib.sha256(source).hexdigest()!=LOADER_SHA:
        raise ValueError('Loader portátil AA diverge do pin externo; cálculo não emitido.')
    module=types.ModuleType('_aa_loader_'+uuid.uuid4().hex);module.__file__=str(path)
    exec(compile(source,str(path),'exec'),module.__dict__)
    return module.Bundle(BUNDLE_MANIFEST)


def _request(data,case,geometry_sha,mode):
    """Contract mapping only. No action, position or source is repaired."""
    position=case['point_position']
    if position=='support_limit':
        raise ValueError('P no limite a→0+ está fora da API AA; força e camada do apoio permanecem preservadas, sem teto desta rota.')
    if position=='center':a=data['L_mm']/2
    elif position=='finite_interior':a=case['a_mm']
    elif position is None:a=None
    else:raise ValueError('Posição de P não reconhecida pela API AA.')
    return dict(schema_version=('aa_web_positive_ratio_qp_component_v1' if mode==POSITIVE_MODE else 'aa_web_family_qp_component_v1'),
        geometry_sha256=geometry_sha,material=dict(E_MPa=data['properties']['E_MPa'],nu=.3,fy_MPa=data['properties']['fy_MPa']),
        L_mm=data['L_mm'],q_N_mm=copy.deepcopy(case['q_N_mm']),P_N=copy.deepcopy(case['P_N']),a_mm=a,
        N_N=0,bimoment_Nmm2=0,supports='simply_supported_bending',stress_scope='bending_component_only')


def _finite(x):return type(x) in (int,float) and math.isfinite(x)


def _upper_ratio(upper,limit):
    exact=F(upper)/F(limit)
    try:value=float(exact)
    except OverflowError:return None
    if not math.isfinite(value):return None
    if F(value)<exact:value=math.nextafter(value,math.inf)
    return value if math.isfinite(value) else None

def _pair(value):
    if (not isinstance(value,list) or len(value)!=2 or any(not isinstance(x,str) or len(x)>4096 for x in value)):
        raise ValueError('Representação racional AA inválida.')
    n,d=map(int,value)
    if d<=0:raise ValueError('Denominador racional AA inválido.')
    f=F(n,d)
    if value!=[str(f.numerator),str(f.denominator)]:raise ValueError('Racional AA não canônico.')
    return f


def _field_links(response,request):
    """Stored equilibrium identity, not a new section or beam evaluation."""
    field=response['field']
    L=F(request['L_mm']);q=list(map(F,request['q_N_mm']));p=list(map(F,request['P_N']))
    a=F(request['a_mm']) if any(p) and request['a_mm'] is not None else None
    if (_pair(field['L_fraction'])!=L or list(map(_pair,field['q_fractions']))!=q
        or list(map(_pair,field['P_fractions']))!=p
        or (None if field['effective_position_fraction'] is None else _pair(field['effective_position_fraction']))!=a
        or response['field_digest']!=digest(field)):
        raise ValueError('Campo AA salvo não corresponde às ações e ao vão.')
    left=[qi*L/2+(pi*(L-a)/L if a is not None else 0) for qi,pi in zip(q,p)]
    right=[qi*L+pi-ri for qi,pi,ri in zip(q,p,left)]
    if list(map(_pair,field['reaction_left_fractions']))!=left or list(map(_pair,field['reaction_right_fractions']))!=right:
        raise ValueError('Reações AA salvas não correspondem às ações originais.')
    pieces=field['pieces']
    if not isinstance(pieces,list) or not pieces:raise ValueError('Cobertura longitudinal AA ausente.')
    end=F(0)
    for piece in pieces:
        u,v=_pair(piece['left_fraction']),_pair(piece['right_fraction'])
        if not end==u<v<=L or (a is not None and u<a<v):raise ValueError('Partição do campo AA incompatível.')
        controls=[[ _pair(x) for x in row] for row in piece['controls_N_Nmm']]
        def moment(z):return [r*z-qi*z*z/2-pi*(max(F(0),z-a) if a is not None else 0) for r,qi,pi in zip(left,q,p)]
        m0,m2=moment(u),moment(v)
        slope=[r-qi*u-(pi if a is not None and u>=a else 0) for r,qi,pi in zip(left,q,p)]
        m1=[m+(v-u)*s/2 for m,s in zip(m0,slope)]
        if controls!=[[F(0),*m0],[F(0),*m1],[F(0),*m2]]:raise ValueError('Controles simultâneos AA salvos divergentes.')
        end=v
    if end!=L:raise ValueError('Campo AA salvo não cobre todo o vão.')


def _response_links(record):
    """Validate saved request/proof/result links without accessing live sources."""
    response=record['response'];request=record['request'];method=METHODS[record['choice']]
    if not isinstance(response,dict) or record['response_sha256']!=digest(response):
        raise ValueError('Resposta AA salva alterada/incompleta.')
    if (response.get('schema')!=request['schema_version'] or response.get('request')!=request
        or response.get('request_digest')!=digest(request) or response.get('result_kind')!='component_upper_bound'
        or type(response.get('sufficient')) is not bool
        or any(response.get(k) is not False for k in ('physical_ELS_approved','whole_member_approved','published'))):
        raise ValueError('Resposta AA não corresponde ao pedido ou ao escopo salvo.')
    sufficient=response['sufficient']
    if record['qualified_bound_component'] is not sufficient:raise ValueError('Qualificação AA salva diverge da prova.')
    if not sufficient:
        if 'displacement_component_bounds' in response:raise ValueError('Resposta inconclusiva não pode conter teto utilizável.')
        return
    if (not response.get('status','').startswith('sufficient_')
        or any(response.get(k) is not True for k in ('existence_sufficient','domain_sufficient','material_sufficient'))
        or response.get('uniqueness_proved') is not False):
        raise ValueError('Guardas AA salvas incompletas.')
    base='positive_ratio' if method=='positive_ratio' else 'family'
    expected=CONTRACT[base]
    if (response.get('source_manifest_sha256')!=expected['manifest_sha256']
        or response.get('source_pins')!=expected['source_pins']
        or response.get('implementation_sha256') not in (None,expected['implementation_sha256'])):
        raise ValueError('Identidade da API AA salva divergente.')
    _field_links(response,request)
    route=response['route']
    binding=dict(request=response['request_digest'],field=response['field_digest'],manifest=expected['manifest_sha256'],route=route)
    if route=='finite_local_partition':
        if method!='local_partition':raise ValueError('Partição não pertence à escolha AA salva.')
        part=response['partition'];contract=CONTRACT['local_partition']
        if not isinstance(part,dict):raise ValueError('Partição AA salva malformada.')
        if (part.get('schema')!='aa_web_local_partition_v1' or part.get('source_manifest_sha256')!=contract['manifest_sha256']
            or part.get('source_pins')!=contract['source_pins'] or part.get('budget_requested')!=REFINEMENT_BUDGET
            or part.get('coverage_complete') is not True or part.get('frontier_covers_original_span') is not True
            or part.get('global_Green_C1_verified') is not True or part.get('pending_leaf_ids')!=[]
            or part.get('original_field_digest')!=response['field_digest'] or response['partition_digest']!=digest(part)):
            raise ValueError('Partição AA salva incompleta ou incompatível.')
        leaves=part['certified_leaf_ids'];nodes=part['nodes']
        if not isinstance(leaves,list) or not isinstance(nodes,list) or not isinstance(part.get('interfaces'),list) or any(not isinstance(x,dict) for x in part['interfaces']):raise ValueError('Inventário da partição AA salvo malformado.')
        if not leaves or part['frontier_ids']!=leaves or len(set(leaves))!=len(leaves):raise ValueError('Folhas AA salvas incompletas.')
        end=F(0)
        for i in leaves:
            n=nodes[i];u,v=_pair(n['left_fraction']),_pair(n['right_fraction'])
            if n['id']!=i or n['status']!='certified' or not end==u<v<=F(request['L_mm']):raise ValueError('Cobertura das folhas AA inválida.')
            h=n['hull_evidence']
            if not isinstance(h,dict):raise ValueError('Hull da folha AA salvo ausente.')
            if any(h.get(k) is not True for k in ('sufficient','existence_sufficient','nonweb_and_material_sufficient')):raise ValueError('Guarda de folha AA inválida.')
            end=v
        if end!=F(request['L_mm']) or any(x.get('additional_support') is not False or x.get('original_field_continuous') is not True for x in part['interfaces']):raise ValueError('Vão/continuidade da partição AA inválidos.')
        binding.update(manifest=contract['manifest_sha256'],partition=response['partition_digest'])
    elif route=='gross_full_section':
        gross=response.get('gross_evidence',{})
        if not isinstance(gross,dict):raise ValueError('Crivo integral AA salvo ausente.')
        if gross.get('sufficient_full_section') is not True or gross.get('elastic_stress_sufficient') is not True:raise ValueError('Ramo integral AA sem guarda salva.')
    elif route=='web_control_hull':
        hull=response.get('hull_evidence',{})
        if not isinstance(hull,dict):raise ValueError('Hull AA salvo ausente.')
        if (hull.get('geometry_sha256')!=request['geometry_sha256'] or hull.get('material')!=request['material']
            or any(hull.get(k) is not True for k in ('sufficient','existence_sufficient','nonweb_and_material_sufficient'))):
            raise ValueError('Guardas de não-alma/material AA ausentes.')
    elif route=='zero_identity':
        if any(request['q_N_mm']+request['P_N']):raise ValueError('Identidade nula AA incompatível com as ações.')
    else:raise ValueError('Ramo AA salvo não reconhecido.')
    if base=='positive_ratio':binding['implementation_sha256']=expected['implementation_sha256']
    if response.get('binding_digest')!=digest(binding):raise ValueError('Vínculo final AA salvo divergente.')
    bounds=response.get('displacement_component_bounds')
    if not isinstance(bounds,list) or len(bounds)!=2:raise ValueError('Os dois tetos de componente AA devem permanecer explícitos.')
    for i,bound in enumerate(bounds):
        if not isinstance(bound,dict):raise ValueError('Teto de componente AA salvo malformado.')
        upper=bound.get('absolute_max_upper_mm');exact=_pair(bound.get('absolute_max_upper_fraction'))
        if (type(bound.get('component')) is not int or bound.get('component')!=i or not _finite(upper) or upper<0 or exact<0 or F(upper)<exact
            or (upper>0 and F(math.nextafter(upper,-math.inf))>=exact)):
            raise ValueError('Teto racional AA ou arredondamento para cima incompatível.')
    from .aa_saved_certificate import check_saved
    check_saved(response,request,base,CONTRACT[base],_pair)


def _raw(record):
    good=record['qualified_bound_component'];limit=record['declared_limit']
    out=dict(status='computed_bending_component' if good else 'not_evaluated',
        criterion_status='not_evaluated',diagnostic_only=True,result_kind='component_upper_bound',
        criterion_scope='sufficient_normal_component_bound_AA_web_only',component_schema=record['schema'],
        component_case_id=record['case_id'],qualified_bound_component=good,
        combined_ELS_approved=False,whole_member_approved=False,torsion_or_warping_qualified=False,
        exact_deflection_computed=False,reason=record['reason'],source=SOURCE)
    if good:
        upper=record['response']['displacement_component_bounds'][0]['absolute_max_upper_mm']
        out['upper_bound_mm']=upper
        if limit['valid']:
            value=limit['value_mm'];meets=F(upper)<=F(value)
            ratio=_upper_ratio(upper,value)
            out.update(limit_mm=value,limit_origin=limit['origin'],
                criterion_status='meets' if meets else 'inconclusive_bound_above_limit',
                bound_comparison='sufficient_component_only' if meets else 'inconclusive',
                upper_bound_ratio=ratio)
            # Only a sufficient ceiling produces an active ratio, never a failure.
            if meets:out.update(index=ratio,index_kind='conservative_upper_bound_over_declared_limit',diagnostic_only=False)
        else:out['criterion_status']='missing_declared_limit'
    return out


def _row(raw):
    meets=raw.get('criterion_status')=='meets'
    observation=raw['reason']
    if 'upper_bound_ratio' in raw:
        observation+=' Razão teto/limite conservadora, não utilização por flecha exata.'
    if raw.get('criterion_status')=='inconclusive_bound_above_limit':observation+=' O teto excede o limite; isso não prova descumprimento físico.'
    return {'Verificação':GIRT_ROW if raw.get('component_schema')==GIRT_SCHEMA else ROW,
        'Situação':'Atende por teto suficiente — somente componente' if meets else 'Pendente — teto AA inconclusivo',
        'Índice':raw.get('index'),
        'Demanda / valor':f"Teto: {raw['upper_bound_mm']:.9g} mm (arred.)" if 'upper_bound_mm' in raw else '—',
        'Resistência / limite':f"{raw['limit_mm']:.9g} mm" if 'limit_mm' in raw else '—',
        'Referência':SOURCE,'Observação':observation}


def attach_fresh(result,source):
    data=result['input_data']
    if not selected(data):return result
    from .application import fingerprint
    if (result.get('input_fingerprint')!=fingerprint(data) or source['input_sha256']!=fingerprint(data)
        or FIELD in result or 'gross_biaxial_component_evidence' in result):
        raise ValueError('Teto AA exige novo cálculo e emissão única das mesmas entradas/fontes.')
    geometry=_sources(data,source);bundle=_bundle();mode=data['deflection_model'];method=METHODS[mode]
    out=copy.deepcopy(result);records={}
    for cid,case,local,evidence,entry in _entries(out):
        r=dict(schema=_schema(data),case_id=cid,case=case,choice=mode,method=method,
            declared_limit=_limit(local),previous_scalar_component=copy.deepcopy(evidence['ELS']),
            source_input_fingerprint=out['input_fingerprint'],reference_id=source['reference_id'],
            geometry_source_sha256=geometry.source_sha256,request=None,response=None,response_sha256=None,
            qualified_bound_component=False,physical_ELS_approved=False,whole_member_approved=False,
            resistance_qualified=False,exact_deflection_computed=False,
            reason=scope_text(data)+' '+PENDING)
        try:
            request=_request(data,case,geometry.source_sha256,mode);r['request']=request
            response=(bundle.local_partition_assess(request,refinement_budget=REFINEMENT_BUDGET) if mode==LOCAL_MODE
                else bundle.positive_ratio_assess(request) if mode==POSITIVE_MODE else bundle.family_assess(request))
            r.update(response=response,response_sha256=digest(response),qualified_bound_component=response.get('sufficient') is True)
            _response_links(r)
            r['reason']=scope_text(data) if r['qualified_bound_component'] else scope_text(data)+' '+str(response.get('reason',response.get('status')))+'. '+PENDING
        except (ValueError,TypeError,ArithmeticError,KeyError,IndexError) as exc:
            r.update(response=None,response_sha256=None,qualified_bound_component=False,reason=str(exc)+' '+PENDING+' '+scope_text(data))
        raw=_raw(r);evidence['ELS']=raw
        inclination=evidence.get('inclination') if entry else evidence.get('inclination_evidence',{}).get('ELS')
        if inclination is not None:inclination['resistance_status']=raw['reason']
        if entry is not None:
            names=('Flecha — flexão','Flecha horizontal — eixo forte',*ROWS)
            indices=[i for i,row in enumerate(entry['rows']) if row['Verificação'] in names]
            if len(indices)!=1:raise ValueError('Linha normal ELS ausente/duplicada; não reconstruída silenciosamente.')
            entry['rows'][indices[0]]=_row(raw)
        records[cid]=r
    summary=dict(schema=_schema(data),source_input_fingerprint=out['input_fingerprint'],
        reference_id=source['reference_id'],geometry_source_sha256=geometry.source_sha256,
        source_documents=copy.deepcopy(source['source_documents']),source_evidence_sha256=digest(source),choice=mode,method=method,
        bundle_manifest_sha256=BUNDLE_MANIFEST,loader_sha256=LOADER_SHA,
        refinement_budget=REFINEMENT_BUDGET if mode==LOCAL_MODE else None,
        scope=scope_text(data),coordinate_contract=AXIS,records=records,total_cases=len(records),
        bounded_cases=sum(r['qualified_bound_component'] for r in records.values()),
        sufficient_cases=sum(_raw(r)['criterion_status']=='meets' for r in records.values()),
        physical_ELS_approved=False,combined_ELS_approved=False,whole_member_approved=False,
        torsion_or_warping_included=False,exact_deflection_computed=False,history_requalified=False,published=False)
    if data.get('member_application')=='wall_girt':
        from .ue_member_application import FIELD as APPLICATION_FIELD
        summary.update(member_application='wall_girt',application_contract=copy.deepcopy(data[APPLICATION_FIELD]))
    summary['snapshot_sha256']=digest(summary);out[FIELD]=summary
    out['combined_ELS_approved']=False;out['whole_member_approved']=False
    if out.get('schema')=='tercas_batch_results_v1':
        from .batch import governing
        out['summary']=governing(out['cases'])
    bundle.verify()
    if _sources(data,source)!=geometry:raise ValueError('Fonte própria mudou durante emissão AA.')
    preserved_snapshot(out)
    return out


def claims_result(result):
    if not isinstance(result,dict):return False
    if FIELD in result:return True
    if isinstance(result.get('ELS'),dict) and result['ELS'].get('component_schema') in SCHEMAS:return True
    for case in result.get('cases',[]):
        if not isinstance(case,dict):continue
        ev=case.get('evidence',{})
        if isinstance(ev,dict) and isinstance(ev.get('ELS'),dict) and ev['ELS'].get('component_schema') in SCHEMAS:return True
        if any(isinstance(r,dict) and r.get('Verificação') in ROWS for r in case.get('rows',[])):return True
    return any(isinstance(r,dict) and r.get('Verificação') in ROWS for r in result.get('summary',[]))


def is_girt_result(result):
    ev=result.get(FIELD)
    if isinstance(ev,dict) and ev.get('schema')==GIRT_SCHEMA:return True
    if isinstance(result.get('ELS'),dict) and result['ELS'].get('component_schema')==GIRT_SCHEMA:return True
    return any(isinstance(c,dict) and isinstance(c.get('evidence'),dict) and isinstance(c['evidence'].get('ELS'),dict) and c['evidence']['ELS'].get('component_schema')==GIRT_SCHEMA for c in result.get('cases',[]))


def preserved_snapshot(result):
    if FIELD not in result:
        if claims_result(result):raise ValueError('Evidência do teto AA ausente; índice salvo não utilizável.')
        return None
    s=result[FIELD]
    if not isinstance(s,dict):raise ValueError('Registro AA inválido.')
    required={'schema','source_input_fingerprint','reference_id','geometry_source_sha256','source_documents',
        'source_evidence_sha256','choice','method','bundle_manifest_sha256','loader_sha256','refinement_budget','scope','coordinate_contract',
        'records','total_cases','bounded_cases','sufficient_cases','physical_ELS_approved','combined_ELS_approved',
        'whole_member_approved','torsion_or_warping_included','exact_deflection_computed','history_requalified','published','snapshot_sha256'}
    if s.get('schema')==GIRT_SCHEMA:required|={'member_application','application_contract'}
    if set(s)!=required or s.get('schema') not in SCHEMAS or s.get('choice') not in MODES:
        raise ValueError('Esquema do teto AA não reconhecido.')
    if s['snapshot_sha256']!=digest({k:v for k,v in s.items() if k!='snapshot_sha256'}):raise ValueError('Registro AA alterado ou incompleto.')
    data=result['input_data'];mode=data.get('deflection_model')
    from .application import fingerprint
    from .ue_member_application import validate_saved_context,FIELD as APPLICATION_FIELD,valid_token
    source=result.get('ue_family_reference_evidence',result.get('ue_reference_evidence'))
    if (not selected(data) or not eligible_choice(data) or not isinstance(source,dict)
        or s['schema']!=_schema(data) or s['choice']!=mode or s['method']!=METHODS[mode]
        or s['source_input_fingerprint']!=fingerprint(data) or result.get('input_fingerprint')!=s['source_input_fingerprint']
        or source.get('input_sha256')!=s['source_input_fingerprint'] or source.get('reference_id')!=s['reference_id']
        or result.get('whole_member_approved') is not False or result.get('combined_ELS_approved') is not False
        or digest(source)!=s['source_evidence_sha256']
        or source.get('source_documents')!=s['source_documents'] or s['geometry_source_sha256']!=PINS.get(data['properties']['t'])
        or s['bundle_manifest_sha256']!=BUNDLE_MANIFEST or s['loader_sha256']!=LOADER_SHA
        or s['refinement_budget']!=(REFINEMENT_BUDGET if mode==LOCAL_MODE else None)
        or s['scope']!=scope_text(data) or s['coordinate_contract']!=AXIS
        or any(s[k] is not False for k in ('physical_ELS_approved','combined_ELS_approved','whole_member_approved',
            'torsion_or_warping_included','exact_deflection_computed','history_requalified','published'))):
        raise ValueError('Vínculo/escopo AA salvo não corresponde à emissão.')
    if s['schema']==GIRT_SCHEMA and (s['member_application']!='wall_girt' or s['application_contract']!=data.get(APPLICATION_FIELD) or not valid_token(s['application_contract'],'wall_girt')):
        raise ValueError('Contrato de aplicação AA salvo divergente.')
    validate_saved_context(data,source)
    expected={cid:(case,d,ev,entry) for cid,case,d,ev,entry in _entries(result)}
    if not isinstance(s['records'],dict) or set(s['records'])!=set(expected):raise ValueError('Inventário AA salvo divergente.')
    bounded=met=0
    for cid,r in s['records'].items():
        case,d,ev,entry=expected[cid]
        if (not isinstance(r,dict) or r.get('schema')!=s['schema'] or r.get('choice')!=mode or r.get('method')!=METHODS[mode]
            or r.get('case_id')!=cid or r.get('case')!=case or r.get('declared_limit')!=_limit(d)
            or r.get('source_input_fingerprint')!=s['source_input_fingerprint'] or r.get('reference_id')!=s['reference_id']
            or r.get('geometry_source_sha256')!=s['geometry_source_sha256'] or type(r.get('qualified_bound_component')) is not bool
            or not isinstance(r.get('reason'),str) or not r['reason'].strip()
            or any(r.get(k) is not False for k in ('physical_ELS_approved','whole_member_approved','resistance_qualified','exact_deflection_computed'))):
            raise ValueError('Estado salvo AA incompatível: '+cid)
        try:req=_request(data,case,s['geometry_source_sha256'],mode)
        except ValueError:req=None
        if r.get('request')!=req:raise ValueError('Pedido AA salvo não corresponde às ações/posição originais.')
        if r.get('response') is not None:_response_links(r)
        elif r['qualified_bound_component'] or r.get('response_sha256') is not None:raise ValueError('Teto AA sem resposta/prova salva.')
        raw=_raw(r)
        if ev.get('ELS')!=raw:raise ValueError('Valor/critério AA diverge da evidência salva: '+cid)
        if entry is not None and [x for x in entry['rows'] if x['Verificação'] in ROWS]!=[_row(raw)]:raise ValueError('Linha AA salva divergente.')
        bounded+=r['qualified_bound_component'];met+=raw['criterion_status']=='meets'
    if any(type(s[k]) is not int or s[k]!=v for k,v in (('total_cases',len(expected)),('bounded_cases',bounded),('sufficient_cases',met))):raise ValueError('Contagem AA salva divergente.')
    if result.get('schema')=='tercas_batch_results_v1':
        from .batch import governing
        if result.get('summary')!=governing(result['cases']):raise ValueError('Resumo AA salvo divergente.')
    return s


def presentation_rows(result,rows):
    if not claims_result(result):return rows
    try:preserved_snapshot(result)
    except (ValueError,TypeError,KeyError,ArithmeticError,IndexError) as exc:
        out=copy.deepcopy(rows)
        for row in out:
            if row['Verificação'] in ('Flecha — flexão','Flecha horizontal — eixo forte',*ROWS):
                row.update(**{'Verificação':GIRT_ROW if is_girt_result(result) else ROW,'Índice':None,
                    'Situação':'Registro AA inválido','Demanda / valor':'—','Resistência / limite':'—',
                    'Observação':str(exc)+' Recalcule explicitamente; nenhum resultado salvo foi requalificado.'})
        return [r for r in out if not (is_girt_result(result) and r['Verificação']=='Flecha vertical — eixo fraco')]
    rows=[r for r in rows if not (is_girt_result(result) and r['Verificação']=='Flecha vertical — eixo fraco')]
    if result.get('schema')=='NBR14762_one_span_v1':
        return [_row(result['ELS']) if r['Verificação'] in ('Flecha — flexão','Flecha horizontal — eixo forte') else r for r in rows]
    return rows
