"""Explicit sufficient gross-biaxial FLEXURAL component, not physical ELS.

This adapter runs only at a freshly calculated, source-validated own-Ue boundary.
It creates a new response and criterion; it never recovers an old scalar index.
Reading a snapshot does not run the comparator, solver or source-file gate.
"""
import copy
import hashlib
import json
import math
from pathlib import Path

MODE = 'gross_biaxial_sufficient_component_v1'
FIELD = 'gross_biaxial_component_evidence'
SCHEMA = 'own_Ue_gross_biaxial_component_snapshot_v1'
GIRT_SCHEMA = 'own_Ue_isolated_girt_gross_biaxial_component_snapshot_v1'
SCHEMAS = (SCHEMA,GIRT_SCHEMA)
ROW = 'Flecha normal — componente flexional biaxial'
GIRT_ROW = 'Flecha horizontal — componente flexional biaxial'
ROWS = (ROW,GIRT_ROW)
LABEL = 'Flecha flexional biaxial por crivo de seção integral'
SOURCE = 'NBR 14762:2010 §9.2.2/§9.2.3 e §9.8.5; comparação suficiente MLE + viga Euler–Bernoulli tensorial'
TEXT = ('Componente flexional biaxial da seção própria: o campo simultâneo Mx/My é '
        'verificado por condição suficiente MLE em todas as paredes e em todo o vão. '
        'Quando demonstrada a seção integralmente efetiva, a resposta usa o tensor '
        'bruto Ix/Iy/Ixy do mesmo contorno e procura os extremos por trechos. O índice '
        'compara somente a flecha normal à cobertura com o limite declarado. '
        'Crivo inconclusivo não significa reprovação e não é substituído por I bruto '
        'ou por uma flecha escalar. Torção, empenamento, deformações de ligação, '
        'instabilidade física e ELS completo permanecem fora desta componente.')
TEXT_GIRT = TEXT.replace('normal à cobertura','horizontal normal ao fechamento') + ' Travessa isolada biapoiada, sem crédito de tirantes ou redistribuição 3D.'


def scope_text(data):
    return TEXT_GIRT if data.get('member_application','purlin')=='wall_girt' else TEXT


def _schema(data):
    return GIRT_SCHEMA if data.get('member_application','purlin')=='wall_girt' else SCHEMA


def is_girt_result(result):
    ev=result.get(FIELD)
    if isinstance(ev,dict) and ev.get('schema')==GIRT_SCHEMA:return True
    if isinstance(result.get('ELS'),dict) and result['ELS'].get('component_schema')==GIRT_SCHEMA:return True
    return any(isinstance(c,dict) and isinstance(c.get('evidence'),dict) and isinstance(c['evidence'].get('ELS'),dict) and c['evidence']['ELS'].get('component_schema')==GIRT_SCHEMA for c in result.get('cases',[]))


PENDING = ('Componente flexional biaxial não concluída pelo crivo suficiente nesta '
           'solicitação. Não é reprovação do elemento nem prova de seção reduzida. '
           'Não há índice de atendimento desta componente.')
PINS = {
    1.20:'f74d3f941e59af0bceb3a2fdae414e8aa479b14b16cbe284c1dff3f3e816b005',
    1.50:'9a30115583275a30ab25eb8c782398a8aa5d547b8272743da9cd2f8342f880d4',
    2.00:'fde5d287a73df9adf1b9ab3e392d7207c3423acb7a8894de5553d402cc7aef90',
    2.25:'8db5d3c4a037e01e665860c1ad8878bab01330cc07fc4165f74a40c0862ec562',
    2.65:'40aada8e49914bb1384c8ac205d8035225d5c033e1e76de8fa65f022ebdd99f1',
    3.00:'e45b3298a2a95cca875b558269046090751e3bff2fa1b9dfae3cc0c1a2a97919',
    3.35:'f1e9676c843459bcb7c14341a32ab10cc90c8ab6765e056fe9bcd47e3b58dd05'}
RUNTIME = {
    'gross_mle.py':'6c55ca5d6ee5ef7c371b93963f7101fea4cb2b1426f12acff442520eb0fd03ca',
    'tensor_beam.py':'f3080817668d9584f8c01bdc220da85d2d1a0d8a72422acc574a127598c6860f',
    'bounded_polynomial.py':'510d92dbeb0f745ad45fecf7280e74e9c3dda39d0ec47449537f31c972735a7d'}


def digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),
        ensure_ascii=False,allow_nan=False).encode()).hexdigest()



def claims_result(result):
    """A typed raw/row also demands its evidence, even if that key was lost."""
    if not isinstance(result,dict):return False
    if FIELD in result:return True
    if isinstance(result.get('ELS'),dict) and result['ELS'].get('component_schema') in SCHEMAS:return True
    for entry in result.get('cases',[]):
        if not isinstance(entry,dict):continue
        ev=entry.get('evidence',{})
        if isinstance(ev,dict) and isinstance(ev.get('ELS'),dict) and ev['ELS'].get('component_schema') in SCHEMAS:return True
        if any(isinstance(r,dict) and r.get('Verificação') in ROWS for r in entry.get('rows',[])):return True
    return any(isinstance(r,dict) and r.get('Verificação') in ROWS for r in result.get('summary',[]))


def _response_links(record,data):
    """Saved algebraic identity only; no source lookup or field recomputation."""
    from fractions import Fraction
    r=record['response'];screen=record['screen'];case=record['case']
    def real(x):return type(x) in (int,float) and math.isfinite(x)
    tensor=r.get('source_tensor_mm4');props=screen.get('computed_properties')
    if (not isinstance(tensor,dict) or set(tensor)!={'Ix','Iy','Ixy'}
        or not all(real(v) for v in tensor.values()) or not isinstance(props,dict)
        or tensor!={k:props.get(k+'_mm4') for k in ('Ix','Iy','Ixy')}
        or screen.get('geometry_source_sha256')!=record['geometry_source_sha256']
        or not real(r.get('source_E_MPa')) or r['source_E_MPa']!=data['properties']['E_MPa']
        or not real(r.get('L_mm')) or r['L_mm']!=data['L_mm']
        or r.get('q_N_mm')!=case['q_N_mm'] or r.get('P_N')!=case['P_N']
        or any(not real(v) for key in ('q_N_mm','P_N') for v in r[key])
        or r.get('point_position')!=case['point_position']):
        raise ValueError('Resposta tensorial salva não corresponde à fonte/cargas do estado.')
    position=case['point_position']
    expected_a=data['L_mm']/2 if position=='center' else case['a_mm'] if position=='finite_interior' else 0. if position=='support_limit' else None
    if r.get('a_mm')!=expected_a or (expected_a is not None and not real(r.get('a_mm'))):
        raise ValueError('Posição tensorial salva diverge do contrato físico de P.')
    exact=r.get('exact_numeric_inputs')
    if not isinstance(exact,dict) or set(exact)!={'section','loads','length_position','point_position'}:
        raise ValueError('Identidade racional da resposta tensorial incompleta.')
    if r.get('numeric_input_fingerprint')!=hashlib.sha256(json.dumps(exact,sort_keys=True,separators=(',',':')).encode()).hexdigest():
        raise ValueError('Identidade numérica tensorial inconsistente.')
    parsed={}
    for key,n in (('section',4),('loads',4),('length_position',2)):
        values=exact.get(key)
        if not isinstance(values,list) or len(values)!=n or any(not isinstance(v,str) or len(v)>4096 for v in values):
            raise ValueError('Representação racional salva inválida.')
        parsed[key]=[Fraction(v) for v in values]
    E,Ix,Iy,Ixy=parsed['section']
    if ([float(v) for v in (E,Ix,Iy,Ixy)]!=[r['source_E_MPa'],tensor['Ix'],tensor['Iy'],tensor['Ixy']]
        or parsed['loads']!=[Fraction(v) for v in case['q_N_mm']+case['P_N']]
        or parsed['length_position']!=[Fraction(data['L_mm']),Fraction(expected_a or 0.)]
        or exact['point_position']!=position or min(E,Ix,Iy)<=0 or Ix*Iy-Ixy*Ixy<=0):
        raise ValueError('Entradas exatas salvas não correspondem ao campo declarado.')
    if r.get('stiffness_matrix_Nmm2')!=[[float(E*Ix),float(-E*Ixy)],[float(-E*Ixy),float(E*Iy)]]:
        raise ValueError('Tensor EI salvo diverge da própria identidade racional.')
    extrema=r.get('extrema')
    if not isinstance(extrema,dict) or not isinstance(extrema.get('displacement'),dict) or not isinstance(extrema['displacement'].get('normal'),dict):
        raise ValueError('Estrutura dos extremos tensoriais salva inválida.')
    witness=extrema['displacement']['normal'].get('maximum_absolute')
    if not isinstance(witness,dict) or not real(witness.get('value')):
        raise ValueError('Extremo normal salvo inválido.')
    state=witness.get('state');v=state.get('displacement_mm') if isinstance(state,dict) else None
    if (not isinstance(v,list) or len(v)!=2 or not all(real(x) for x in v)
        or v[0]!=witness['value'] or not real(state.get('x_mm'))
        or not 0.<=state['x_mm']<=data['L_mm'] or state.get('side') not in ('left','right','interior')):
        raise ValueError('Testemunha da componente normal salva incoerente.')
    checks=r.get('exact_checks')
    names={'field_equation','continuity','point_shear_jump','simply_supported_bending',
           'force_balance','moment_balance','work_equals_twice_energy'}
    if not isinstance(checks,dict) or set(checks)!=names or any(v is not True for v in checks.values()):
        raise ValueError('Verificações algébricas salvas ausentes ou inconclusivas.')
    if any(screen.get(k) is not False for k in ('combined_stiffness_released','physical_ELS_approved','whole_member_approved',
        'resistance_release','torsion_or_warping_qualified','reduced_biaxial_law_qualified','published','support_transfer_and_local_bearing_qualified')):
        raise ValueError('Flags salvas do crivo excedem seu escopo matemático.')
    walls=screen.get('walls')
    names={'bottom_lip','bottom_flange','web','top_flange','top_lip'}
    if (screen.get('elastic_stress_sufficient') is not True or not isinstance(walls,list) or len(walls)!=5
        or any(not isinstance(w,dict) or not isinstance(w.get('wall'),str) or w.get('full_wall_sufficient') is not True for w in walls)
        or {w['wall'] for w in walls}!=names):
        raise ValueError('Crivo salvo não demonstra as cinco paredes e a guarda elástica.')
    # These identities bind the saved reaction/transfer trace to the same
    # actions. They are not a new evaluation of the flexural solution.
    L=parsed['length_position'][0];q=parsed['loads'][:2];P=parsed['loads'][2:]
    if position=='support_limit':
        left=[float(qi*L/2+pi) for qi,pi in zip(q,P)]
        right=[float(qi*L/2) for qi in q]
    else:
        a=parsed['length_position'][1]
        left=[float(qi*L/2+pi*(L-a)/L) for qi,pi in zip(q,P)]
        right=[float(qi*L/2+pi*a/L) for qi,pi in zip(q,P)]
    reactions=r.get('reactions_N')
    if (not isinstance(reactions,dict) or set(reactions)!={'left','right'}
        or any(not isinstance(reactions[k],list) or len(reactions[k])!=2 or not all(real(x) for x in reactions[k]) for k in reactions)
        or reactions!={'left':left,'right':right}):
        raise ValueError('Reações salvas não correspondem às ações e à posição de P.')
    if position=='support_limit':
        layer=r.get('support_transfer_limit')
        expected=dict(kind='a_to_zero_from_inside',x_mm=0.,M_before_Nmm=[0.,0.],
            V_before_N=left,V_after_N=right,original_P_N=[float(x) for x in P],
            interior_bending_P_contribution_zero=True,finite_point_on_support=False,
            local_transfer_or_resistance_qualified=False)
        flags=('interior_bending_P_contribution_zero','finite_point_on_support','local_transfer_or_resistance_qualified')
        if (not isinstance(layer,dict) or layer!=expected or not real(layer.get('x_mm'))
            or any(type(layer.get(k)) is not bool for k in flags)
            or any(not all(real(x) for x in layer[k]) for k in ('M_before_Nmm','V_before_N','V_after_N','original_P_N'))):
            raise ValueError('Camada limite salva ausente ou incompatível; P/reação não podem desaparecer.')
    elif 'support_transfer_limit' in r:
        raise ValueError('Uma força finita/ausente não pode receber a camada limite do apoio.')


def selected(data):
    return data.get('deflection_model') == MODE


def eligible_choice(data):
    """Shape/context only. The authoritative source gate is separate."""
    from .ue_member_application import FIELD as APPLICATION_FIELD,token,valid_token
    return (isinstance(data,dict) and ((data.get('member_application','purlin')=='purlin' and (APPLICATION_FIELD not in data or valid_token(data[APPLICATION_FIELD],'purlin'))) or
        (data.get('member_application')=='wall_girt' and valid_token(data.get(APPLICATION_FIELD),'wall_girt'))) 
        and ('ue_reference' in data or 'ue_family_reference' in data
             or {'ue_model','ue_source_documents'}.issubset(data)
             or {'ue_family_model','ue_family_sources'}.issubset(data))
        and not (isinstance(data.get('three_girt_model'),dict) and data['three_girt_model'].get('enabled')))


def activate(data):
    if not eligible_choice(data):
        raise ValueError('A componente biaxial integral está disponível somente nas referências próprias Ue de viga isolada, com aplicação explícita.')
    out=copy.deepcopy(data);out['deflection_model']=MODE
    return out


def _sources(data, source):
    from .ue_family_reference import claims_reference as fc, evidence as fe
    from .ue_reference import claims_reference as sc, evidence as se
    validated=fe(data) if fc(data) else se(data) if sc(data) else None
    if not eligible_choice(data) or validated != source:
        raise ValueError('Fonte própria íntegra e atual exigida para a componente biaxial.')
    t=data['properties']['t'];L=data['L_mm']
    if type(t) not in (int,float) or t not in PINS or not 3000.<=L<=6000.:
        raise ValueError('Seção/vão fora do domínio próprio de sete espessuras, 3–6 m.')
    here=Path(__file__).parent
    for name,pin in RUNTIME.items():
        if hashlib.sha256((here/'biaxial_gross'/name).read_bytes()).hexdigest()!=pin:
            raise ValueError('Módulo da componente biaxial diverge da revisão registrada: '+name)
    from .biaxial_gross.gross_mle import load_geometry
    path=here/'data/torsion_profiles'/f'ue100x50x17_t{t:.2f}.json'
    geometry=load_geometry(path,PINS[t])
    m=source['model']
    if (m['t_mm']!=float(geometry.t) or m['E_MPa']!=float(geometry.E)
        or m['nu']!=float(geometry.nu) or m['fy_MPa']!=250. or m['L_mm']!=L):
        raise ValueError('Contorno/material/vão do crivo divergem da fonte ativa.')
    return geometry


def _entries(result):
    """Original simultaneous vectors, including the support-limit force."""
    data=result['input_data']
    if result.get('schema')=='tercas_batch_results_v1':
        from .batch import case_inputs
        for entry in result['cases']:
            c=entry['combination']
            if c['limit_state']!='ELS':continue
            d=case_inputs(data,c)
            case=dict(id=c['id'],q_N_mm=[c['q_vector'][a] for a in ('normal','parallel')],
                P_N=[c['P_vector'][a] for a in ('normal','parallel')],point_position=c.get('point_position'))
            if case['point_position']=='finite_interior':case['a_mm']=c['x_mm']
            yield c['id'],case,d,entry['evidence'],entry
    elif result.get('schema')=='NBR14762_one_span_v1':
        case=dict(id='DIRECT_ELS',q_N_mm=[data['q_sls'],data.get('q_parallel_sls',0.)],
            P_N=[data['P_sls'],data.get('P_parallel_sls',0.)],
            point_position='finite_interior',a_mm=data['x_sls'])
        yield 'DIRECT_ELS',case,data,result,None
    else:raise ValueError('Esquema de resultado não admite esta componente isolada.')


def _limit(data):
    from .member_application import is_girt,normal_els_limit
    if is_girt(data):
        limit=normal_els_limit(data);value,origin=limit['value'],limit['origin']
    else:value,origin=data.get('ELS_limit_mm'),data.get('ELS_origin')
    valid=(type(value) in (int,float) and math.isfinite(value) and value>0.
           and isinstance(origin,str) and bool(origin.strip()))
    return dict(value_mm=value,origin=origin,valid=valid,
        scope='declared_limit_for_normal_component_of_biaxial_flexure_only')


def _component_raw(record):
    """Pure serialization from saved evidence, no mechanics or live source reads."""
    good=record['qualified_gross_flexural_component']
    out=dict(status='computed_bending_component' if good else 'not_evaluated',
        criterion_status='not_evaluated',diagnostic_only=not good,
        criterion_scope='normal_component_of_sufficient_gross_biaxial_flexure',
        component_schema=_schema(record),component_case_id=record['case_id'],
        qualified_gross_flexural_component=good,
        combined_ELS_approved=False,whole_member_approved=False,
        torsion_or_warping_qualified=False,
        reason=scope_text(record) if good else record['reason'],source=SOURCE)
    if good:
        extreme=record['response']['extrema']['displacement']['normal']['maximum_absolute']
        out.update(deflection_mm=extreme['value'],x_mm=extreme['state']['x_mm'],
                   simultaneous_displacement_mm=extreme['state']['displacement_mm'])
        limit=record['declared_limit']
        if limit['valid']:
            index=abs(extreme['value'])/limit['value_mm']
            if not math.isfinite(index):raise ValueError('Índice da componente não representável.')
            out.update(limit_mm=limit['value_mm'],limit_origin=limit['origin'],index=index,
                       criterion_status='meets' if index<=1. else 'fails')
        else:
            out['criterion_status']='missing_declared_limit'
            out['reason']+=' Falta limite positivo com origem para comparar esta componente.'
    return out


def _row(raw):
    idx=raw.get('index')
    situation=('Atende ao critério da componente' if idx<=1. else 'Não atende ao critério da componente') if idx is not None else 'Pendente — componente flexional biaxial'
    return {'Verificação':GIRT_ROW if raw.get('component_schema')==GIRT_SCHEMA else ROW,'Situação':situation,'Índice':idx,
        'Demanda / valor':(f"{raw['deflection_mm']:.6f} mm em x={raw['x_mm']:.3f} mm" if 'deflection_mm' in raw else '—'),
        'Resistência / limite':(f"{raw['limit_mm']:.6f} mm" if 'limit_mm' in raw else '—'),
        'Referência':SOURCE,'Observação':raw['reason']}


def attach_fresh(result,source):
    """New reference calculation only. Return a copy; caller assignment is atomic."""
    data=result['input_data']
    if not selected(data):return result
    from .application import fingerprint
    if result.get('input_fingerprint')!=fingerprint(data) or source['input_sha256']!=fingerprint(data):
        raise ValueError('Entradas, fonte e resultado não pertencem à mesma emissão.')
    if FIELD in result:raise ValueError('A componente já foi calculada; resultado salvo não é entrada de recálculo.')
    geometry=_sources(data,source)
    from .biaxial_gross.gross_mle import model_for,assess_case
    from .biaxial_gross.tensor_beam import build_beam,solve_response
    out=copy.deepcopy(result);records={}
    for cid,case,local_data,evidence,entry in _entries(out):
        record=dict(case_id=cid,case=case,declared_limit=_limit(local_data),
            previous_scalar_component=copy.deepcopy(evidence['ELS']),
            source_input_fingerprint=out['input_fingerprint'],reference_id=source['reference_id'],
            geometry_source_sha256=geometry.source_sha256,
            qualified_gross_flexural_component=False,
            physical_ELS_approved=False,whole_member_approved=False,resistance_qualified=False,
            scope_N_and_B_zero='Mathematical bending component excludes N and B; not observed physical zero demand.',
            screen=None,response=None,reason=PENDING)
        if data.get('member_application')=='wall_girt':record['member_application']='wall_girt'
        try:
            screen=assess_case(geometry,model_for(geometry,data['L_mm']),case)
            record['screen']=screen
            if screen['status']=='sufficient_comparator_pass' and screen['sufficient_full_section'] is True:
                beam=build_beam(dict(L_mm=data['L_mm'],E_MPa=geometry.E,
                    supports='simply_supported_bending',prismatic=True,scope='gross_flexural_component_only'),
                    dict(Ix_mm4=geometry.Ix,Iy_mm4=geometry.Iy,Ixy_mm4=geometry.Ixy),case)
                response=solve_response(beam);record['response']=response
                if response['status']=='finite_gross_flexural_response':
                    record['qualified_gross_flexural_component']=True;record['reason']=scope_text(record)
                else:record['reason']='Saída numérica sem resolução suficiente; componente sem índice. '+PENDING
            elif screen['status']=='outside_comparator_domain':
                record['reason']='Fora do domínio/representação do crivo: '+str(screen.get('reason',''))+'. '+PENDING
            raw=_component_raw(record)
            json.dumps(record,allow_nan=False)
        except (ValueError,TypeError,ArithmeticError,KeyError) as exc:
            record.update(qualified_gross_flexural_component=False,response=None,
                reason='Não foi possível representar/verificar a nova componente: '+str(exc)+'. '+PENDING)
            raw=_component_raw(record)
            # Never retain non-JSON partial proof after representation failure.
            try:json.dumps(record,allow_nan=False)
            except (ValueError,TypeError,OverflowError):record['screen']=None
        evidence['ELS']=raw
        inclination=evidence.get('inclination') if entry else evidence.get('inclination_evidence',{}).get('ELS')
        if inclination is not None:inclination['resistance_status']=raw['reason']
        if entry is not None:
            # The base batch filter has already retained its one normal row.
            old_names=('Flecha — flexão','Flecha horizontal — eixo forte',*ROWS)
            indices=[i for i,r in enumerate(entry['rows']) if r['Verificação'] in old_names]
            if len(indices)!=1:raise ValueError('Linha normal ELS ausente/duplicada; não reconstruída silenciosamente.')
            entry['rows'][indices[0]]=_row(raw)
        records[cid]=record
    summary=dict(schema=_schema(data),source_input_fingerprint=out['input_fingerprint'],
        reference_id=source['reference_id'],geometry_source_sha256=geometry.source_sha256,
        source_documents=copy.deepcopy(source['source_documents']),runtime_sha256=copy.deepcopy(RUNTIME),
        choice=MODE,scope=scope_text(data),records=records,
        total_cases=len(records),qualified_cases=sum(r['qualified_gross_flexural_component'] for r in records.values()),
        physical_ELS_approved=False,combined_ELS_approved=False,whole_member_approved=False,
        torque_or_warping_included=False,history_requalified=False)
    if data.get('member_application')=='wall_girt':
        from .ue_member_application import FIELD as APPLICATION_FIELD
        summary.update(member_application='wall_girt',application_contract=copy.deepcopy(data[APPLICATION_FIELD]))
    summary['snapshot_sha256']=digest(summary);out[FIELD]=summary
    out['combined_ELS_approved']=False;out['whole_member_approved']=False
    if out.get('schema')=='tercas_batch_results_v1':
        from .batch import governing
        out['summary']=governing(out['cases'])
    if _sources(data,source)!=geometry:
        raise ValueError('A fonte mudou durante a emissão da componente biaxial.')
    preserved_snapshot(out)  # Same read contract must accept every newly saved result.
    return out


def preserved_snapshot(result):
    """Integrity/consistency of a saved record, not a new mechanical certificate."""
    if FIELD not in result:
        if claims_result(result):raise ValueError('Evidência da componente biaxial ausente; índice salvo não utilizável.')
        return None
    record=result[FIELD]
    if not isinstance(record,dict):raise ValueError('Registro de componente biaxial inválido.')
    required={'schema','source_input_fingerprint','reference_id','geometry_source_sha256',
        'source_documents','runtime_sha256','choice','scope','records','total_cases','qualified_cases',
        'physical_ELS_approved','combined_ELS_approved','whole_member_approved',
        'torque_or_warping_included','history_requalified','snapshot_sha256'}
    if record.get('schema')==GIRT_SCHEMA:required|={'member_application','application_contract'}
    if (set(record)!=required or record['schema'] not in SCHEMAS or record['choice']!=MODE
        or any(not isinstance(record[k],str) or not record[k].strip() for k in
               ('reference_id','scope','source_input_fingerprint','geometry_source_sha256','snapshot_sha256'))):
        raise ValueError('Esquema da componente biaxial não reconhecido.')
    payload={k:v for k,v in record.items() if k!='snapshot_sha256'}
    if digest(payload)!=record['snapshot_sha256']:
        raise ValueError('Conteúdo salvo da componente biaxial foi alterado ou está incompleto.')
    from .application import fingerprint
    data=result['input_data']
    from .ue_member_application import FIELD as APPLICATION_FIELD,token,valid_token
    if record['schema']!=_schema(data):raise ValueError('Eixo/aplicação da componente salvo incompatível.')
    if record['schema']==GIRT_SCHEMA and (record['member_application']!='wall_girt' or record['application_contract']!=data.get(APPLICATION_FIELD) or not valid_token(record['application_contract'],'wall_girt')):
        raise ValueError('Contrato isolado da travessa salvo divergente.')
    source=result.get('ue_family_reference_evidence',result.get('ue_reference_evidence'))
    if (not selected(data) or not eligible_choice(data) or not isinstance(source,dict)
        or result.get('input_fingerprint')!=fingerprint(data)
        or record['source_input_fingerprint']!=result['input_fingerprint']
        or source.get('input_sha256')!=result['input_fingerprint']
        or record['reference_id']!=source.get('reference_id')
        or record['source_documents']!=source.get('source_documents')
        or record['geometry_source_sha256']!=PINS.get(data['properties']['t'])
        or record['runtime_sha256']!=RUNTIME
        or any(record[k] is not False for k in ('physical_ELS_approved','combined_ELS_approved',
            'whole_member_approved','torque_or_warping_included','history_requalified'))):
        raise ValueError('Vínculo/escopo da componente biaxial salvo não corresponde a esta emissão.')
    from .ue_member_application import validate_saved_context
    validate_saved_context(data,source)
    expected={cid:(case,d,ev,entry) for cid,case,d,ev,entry in _entries(result)}
    if not isinstance(record['records'],dict) or set(record['records'])!=set(expected):
        raise ValueError('Inventário de combinações da componente biaxial divergente.')
    qualified=0
    for cid,r in record['records'].items():
        case,d,ev,entry=expected[cid]
        if (not isinstance(r,dict) or r.get('case_id')!=cid or r.get('case')!=case
            or r.get('declared_limit')!=_limit(d)
            or r.get('member_application','purlin')!=data.get('member_application','purlin')
            or not isinstance(r.get('reason'),str) or not r['reason'].strip()
            or r.get('source_input_fingerprint')!=record['source_input_fingerprint']
            or r.get('reference_id')!=record['reference_id']
            or r.get('geometry_source_sha256')!=record['geometry_source_sha256']
            or type(r.get('qualified_gross_flexural_component')) is not bool
            or any(r.get(k) is not False for k in ('physical_ELS_approved','whole_member_approved','resistance_qualified'))):
            raise ValueError('Estado salvo da componente biaxial incompatível: '+cid)
        if r['qualified_gross_flexural_component']:
            screen,response=r['screen'],r['response']
            if (not isinstance(screen,dict) or not isinstance(response,dict)
                or screen.get('status')!='sufficient_comparator_pass' or screen.get('sufficient_full_section') is not True
                or response.get('status')!='finite_gross_flexural_response'
                or response.get('numeric_output_resolution_limited') is not False
                or response.get('first_order_and_shear_rigid_model') is not True
                or any(response.get(k) is not False for k in ('physical_ELS_approved','whole_member_approved',
                    'resistance_qualified','gross_stiffness_applicability_established','torque_or_warping_included'))):
                raise ValueError('Prova/resposta salva não sustenta o escopo flexional: '+cid)
            _response_links(r,data)
            qualified+=1
        if ev.get('ELS')!=_component_raw(r):
            raise ValueError('Índice/valor da componente biaxial divergente da sua evidência salva: '+cid)
        if entry is not None:
            rows=[x for x in entry['rows'] if x['Verificação'] in ROWS]
            if rows!=[_row(ev['ELS'])]:raise ValueError('Linha da componente biaxial salva diverge do estado: '+cid)
    if type(record['total_cases']) is not int or record['total_cases']!=len(expected) or type(record['qualified_cases']) is not int or record['qualified_cases']!=qualified:
        raise ValueError('Contagem da componente biaxial salva incompatível.')
    if result.get('schema')=='tercas_batch_results_v1':
        from .batch import governing
        if result.get('summary')!=governing(result['cases']):
            raise ValueError('Resumo salvo da componente biaxial diverge dos casos registrados.')
    return record


def presentation_rows(result,rows):
    """Only saved evidence can change a display row; an input token is insufficient."""
    if not claims_result(result):return rows
    try:record=preserved_snapshot(result)
    except (ValueError,TypeError,KeyError,ArithmeticError) as exc:
        out=copy.deepcopy(rows)
        for row in out:
            if row['Verificação'] in ('Flecha — flexão','Flecha horizontal — eixo forte',*ROWS):
                row.update(**{'Verificação':GIRT_ROW if is_girt_result(result) else ROW,'Índice':None,'Situação':'Registro biaxial inválido',
                    'Demanda / valor':'—','Resistência / limite':'—',
                    'Observação':str(exc)+' Recalcule explicitamente; resultado salvo não foi requalificado.'})
        return [r for r in out if not (is_girt_result(result) and r['Verificação']=='Flecha vertical — eixo fraco')]
    rows=[r for r in rows if not (is_girt_result(result) and r['Verificação']=='Flecha vertical — eixo fraco')]
    if result.get('schema')=='NBR14762_one_span_v1':
        return [_row(result['ELS']) if r['Verificação'] in ('Flecha — flexão','Flecha horizontal — eixo forte') else r for r in rows]
    return rows
