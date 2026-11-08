"""Separate, opt-in EN transverse shear and signed M–V for nominal catalogue Ue.

This is not the seven-profile EN6.1.6 component. The original catalogue binding,
qualified-normal binding and dense-field identity are captured together before
compaction. Readers replay only saved-source equilibrium and frozen capacities.
"""
import copy
import math
from fractions import Fraction as F

from . import en_signed_partial_interaction as core
from .en_ue_qualified_library import qualified_reference as normal_inventory
from .en_ue_catalog_capacity_reference import qualified_reference
from .isolated_en_application import digest, _inventory, MATERIAL

CHOICE = 'isolated_en_ue_catalog_model'
CHOICE_SCHEMA = 'isolated_EN_Ue_catalog_choice_v1'
FIELD = 'isolated_EN_Ue_catalog_component'
SCHEMA = 'isolated_EN_Ue_catalog_saved_component_v1'
SCOPE = ('Componente seccional EN dos Ue tabulados: cortantes forte/fraco §6.1.5 e '
    'M–V com N=0, §6.1.10/Equação 6.27, pisos assinados independentes e Mf=0. '
    'Torção B/Tsv/Tw não é convertida em V nem verificada por este registro; '
    'EN §6.1.6, estabilidade, forças locais e ELS permanecem separados. '
    'Teto ≤1 é suficiente apenas para a componente; teto >1 é inconclusivo, não falha física.')
FLAGS = tuple(dict.fromkeys((*core.FALSE_FLAGS, 'physical_design_approved',
    'historical_results_requalified', 'original_mechanics_changed', 'EN_6_1_6_qualified')))


def identity(data):
    return digest(dict(reference=data.get('ue_catalog_reference'), properties=data.get('properties'),
        steel_name=data.get('steel_name'), member_application=data.get('member_application','purlin')))


def choice(data, *, enabled=True, declared=False, origin=''):
    return dict(schema=CHOICE_SCHEMA, enabled=enabled, intact_section_model_declared=declared,
        model_origin=origin, section_material_identity=identity(data))


def configuration(data):
    c=data.get(CHOICE)
    if c is None:return None
    if (not isinstance(c,dict) or set(c)!=set(choice(data)) or c.get('schema')!=CHOICE_SCHEMA
        or type(c.get('enabled')) is not bool or type(c.get('intact_section_model_declared')) is not bool
        or type(c.get('model_origin')) is not str or type(c.get('section_material_identity')) is not str):
        raise ValueError('Escolha EN Ue malformada; não foi convertida automaticamente.')
    return copy.deepcopy(c)


def reset_changed_declaration(data):
    c=configuration(data)
    if c is not None and c['section_material_identity']!=identity(data):
        data[CHOICE]=choice(data, enabled=c['enabled']);return True
    return False


def _domain(data,c):
    if c['section_material_identity']!=identity(data):return 'Seção/material/aplicação mudou; declaração anterior não se transfere.'
    if not c['intact_section_model_declared'] or not c['model_origin'].strip():
        return 'Adote explicitamente seção nominal intacta, sem furos/recortes, e registre a origem do modelo.'
    net=data.get('three_girt_model',{})
    if not isinstance(net,dict) or net.get('enabled') or data.get('member_application','purlin')!='purlin':
        return 'Componente exclusiva do vão isolado de terça; rede/travessa não coberta.'
    marker=data.get('ue_catalog_reference')
    if not isinstance(marker,dict) or marker.get('schema')!='ue_catalog_reference_v1':
        return 'Ativação explícita do contorno próprio Ue de catálogo necessária.'
    if type(data['properties'].get('fy_MPa')) not in (int,float) or data['properties']['fy_MPa']!=250.:
        return 'Material fora do domínio: resistência EN exige fyb=fya=250 MPa; nenhum aço é convertido.'
    return None


def _base(result,c):
    inv=_inventory(result)
    return dict(schema=SCHEMA, configuration=copy.deepcopy(c), scope=SCOPE, material=copy.deepcopy(MATERIAL),
        source_input_fingerprint=result['input_fingerprint'], section_material_identity=identity(result['input_data']),
        source_inventory=inv, records=[], ELU_cases=sum(r['limit_state']=='ELU' for r in inv),
        ELS_cases_excluded=sum(r['limit_state']=='ELS' for r in inv), **{k:False for k in FLAGS})


def _counts(ev):
    rows=ev['records']
    return dict(shear_computed_cases=sum(r.get('check') is not None for r in rows),
        shear_sufficient_cases=sum(bool(r.get('check') and r['check']['shear']['component_sufficient']) for r in rows),
        mv_computed_cases=sum(bool(r.get('check') and r['check']['mv']['index_upper'] is not None) for r in rows),
        mv_sufficient_cases=sum(bool(r.get('check') and r['check']['mv']['component_sufficient']) for r in rows),
        pending_demand_cases=sum(r.get('check') is None for r in rows),
        mv_pending_cases=sum(not r.get('check') or r['check']['mv']['index_upper'] is None for r in rows))


def _pending(result,c,reason):
    ev=_base(result,c)
    ev['reason']=reason
    ev['records']=[dict(combination_id=r['combination_id'],limit_state='ELU',status='pending',reason=reason,
        check=None,source_analysis_sha256=None,original_source_binding=None)
        for r in ev['source_inventory'] if r['limit_state']=='ELU']
    ev.update(_counts(ev));return ev


def _finite(x):
    if type(x) not in (int,float) or not math.isfinite(x):raise ValueError('Ação/coordenada finita requerida.')
    return x


def _source_pieces(demand):
    out=[dict(kind='element',element_index=i,element_id=e['element_id'],a_mm=e['a_mm'],b_mm=e['b_mm'])
        for i,e in enumerate(demand['elements'])]
    out += [dict(kind='support_limit',element_id=s['element_id'],x_mm=s['x_mm'],position_limit=s['position_limit'])
        for s in demand.get('support_limit_states',[])]
    return out


def _load_inventory(result):
    """Arithmetic replay of source actions, never a demand/geometry solver.

    An attacker cannot substitute a different coherent q/P field, recompute
    its reactions/checks and refresh self-hashes while keeping project inputs.
    """
    data=result['input_data'];direct=result['schema']=='NBR14762_one_span_v1'
    if direct:
        from .direct_roof_separated import combinations
        expected=combinations(data);bundle=None
    else:
        from .batch import area_bundle
        bundle=area_bundle(data)
        if digest(bundle)!=digest(result.get('load_bundle')):raise ValueError('Ações de área salvas divergem da aritmética das entradas.')
        expected=bundle['combinations']
    if digest([r['source_combination'] for r in _inventory(result)])!=digest(expected):
        raise ValueError('Combinações da fonte diferem das entradas aritméticas originais.')
    rows={}
    for c in expected:
        loads=[]
        if direct:
            vectors=[('EXTERNAL',c['external_q_vector']),('PP',c['profile_PP_q_vector'])]
        else:
            vectors=[(name,{k:factor*bundle['case_vectors_N_mm'][name][k] for k in ('parallel','normal')})
                for name,factor in c['coefficients'].items() if name!='P']
        for name,v in vectors:
            vector=[v['parallel'],-v['normal']]
            if any(vector):loads.append(dict(name=name,kind='uniform',vector=vector))
        v=c['P_vector'];vector=[v['parallel'],-v['normal']]
        if any(vector):loads.append(dict(name='P',kind='point',vector=vector,s_mm=c['x_mm'],
            existing_point_position='fixed' if direct else c['point_position']))
        rows[c['id']]=loads
    return rows


def _validate_case(summary,expected,data):
    if summary['length_mm']!=data['L_mm']:raise ValueError('Comprimento da demanda difere da entrada original.')
    from .roof_top_load import configuration as roof_configuration
    roof=roof_configuration(data)
    if data.get('member_application','purlin')=='wall_girt':
        from .wall_girt_isolated import validate_case
        return validate_case(summary,expected,data)
    from .load_application_policy import active as ct_active
    ct=ct_active(data)
    if not ct and (roof is None or not roof['enabled']):raise ValueError('Linha de topo original não está ativa.')
    cg=summary['section']['properties']['centroid_xy_mm'];p=data['properties']
    if not math.isclose(cg[1],(p['h']-p['t'])/2,rel_tol=2e-12,abs_tol=1e-9):
        raise ValueError('Centróide vertical não pertence ao contorno Ue simétrico original.')
    target=[0. if (roof or {}).get('load_line')=='web_midplane' else (p['bf']-p['t'])/2,p['h']-p['t']/2]
    top=[cg[j]+(target[j]-cg[j]) for j in (0,1)]
    actual=[]
    for a in summary['loads']:
        expected_line=summary['section']['properties']['shear_center_xy_mm'] if ct else cg if a['name']=='PP' else top
        if a['application_xy_mm']!=expected_line:
            raise ValueError('PP deve permanecer no CG e ações externas na linha superior original.')
        row=dict(name=a['name'],kind=a['kind'],vector=a['q_xy_N_mm' if a['kind']=='uniform' else 'force_xy_N'])
        if a['kind']=='point':row.update(s_mm=a['s_mm'],existing_point_position=a['existing_point_position'])
        actual.append(row)
    if digest(actual)!=digest(expected):raise ValueError('Cargas/vetores/posição P diferem da combinação original das entradas.')


def _validate_source(summary,pieces,binding,material):
    if (summary.get('method')!='single_vlasov_CBCA_Annex_A_v1'
        or summary.get('schema') not in ('single_vlasov_member_demand_v1','single_vlasov_member_summary_v1')
        or summary.get('limit_state')!='ELU' or summary.get('numerics',{}).get('qualification_passed') is not True
        or type(summary.get('analysis_domain',{}).get('axial_force_in_this_model_N')) not in (int,float)
        or summary['analysis_domain']['axial_force_in_this_model_N']!=0
        or any(summary.get(k) is not False for k in ('whole_member_approved','physical_design_approved','resistance_qualified'))):
        raise ValueError('Campo Vlasov ELU numericamente qualificado e N=0 explícito requerido.')
    domain=summary['analysis_domain']
    if any(domain.get(k) is not v for k,v in dict(prismatic_single_span=True,intermediate_braces=False,sheet_contact=False,sheet_restraint=False).items()) or domain.get('order')!=1:
        raise ValueError('Equilíbrio racional exclusivo do mesmo vão biapoiado prismático de primeira ordem.')
    section=summary['section']
    if (section['nodes_sha256']!=binding['nodes_sha256'] or section['profile_id']!=binding['section_profile_id']
        or summary['E_MPa']!=material['E_MPa'] or summary['G_MPa']!=material['G_MPa']):
        raise ValueError('Demanda e geometria/material de análise não são da mesma fonte Ue.')
    L=_finite(summary['length_mm'])
    if L<=0:raise ValueError('Vão positivo requerido.')
    loads=summary['loads'];ra=summary['support_reactions']['left_force_xy_N']
    if not isinstance(ra,list) or len(ra)!=2:raise ValueError('Duas reações transversais requeridas.')
    for v in ra:_finite(v)
    points=[]
    for load in loads:
        kind=load['kind'];v=load.get('q_xy_N_mm' if kind=='uniform' else 'force_xy_N')
        if kind not in ('uniform','point') or not isinstance(v,list) or len(v)!=2:
            raise ValueError('Inventário de cargas transversais inválido.')
        for x in v:_finite(x)
        if kind=='point':
            x=_finite(load['s_mm'])
            if not 0<=x<=L:raise ValueError('P fora do vão.')
            points.append(load)
    count=len(summary['elements']) if 'elements' in summary else summary['element_count']
    states=summary.get('support_limit_states',[])
    declared=any(p.get('existing_point_position')=='support_limit' for p in points) or summary['analysis_domain'].get('point_position_scope','').startswith('Prescribed a->0+')
    if declared and (len(points)!=1 or points[0]['s_mm']!=0. or len(states)!=1):
        raise ValueError('Limite a→0+ exige estado before-P original preservado.')
    if not declared and states:raise ValueError('Estado before-P sem declaração original.')
    if type(count) is not int or count<=0 or len(pieces)!=count+len(states):
        raise ValueError('Cobertura de todos os trechos e lados de P incompleta.')
    previous=0.;seen=set()
    for i,piece in enumerate(pieces):
        if piece['element_id'] in seen:raise ValueError('Trecho duplicado.')
        seen.add(piece['element_id'])
        if i<count:
            a,b=_finite(piece['a_mm']),_finite(piece['b_mm'])
            if piece!=dict(kind='element',element_index=i,element_id=piece['element_id'],a_mm=a,b_mm=b) or a!=previous or b<=a or piece['element_id']!=summary['member_id']+':e'+str(i+1):
                raise ValueError('Partição longitudinal inválida.')
            if any(a<p['s_mm']<b for p in points):raise ValueError('Trecho cruza P sem guardar ambos os lados.')
            previous=b
        else:
            s=states[i-count]
            if (piece!=dict(kind='support_limit',element_id=s['element_id'],x_mm=s['x_mm'],position_limit=s['position_limit'])
                or s.get('element_index') is not None or 'before P' not in s['position_limit']
                or type(s.get('N_N')) not in (int,float) or s['N_N']!=0
                or any(s.get(k)!=0 for k in ('x_mm','s_mm','u')) or s.get('side')!='right'
                or s.get('combination_id')!=summary['combination_id'] or s.get('member_id')!=summary['member_id']
                or s.get('limit_state')!='ELU'):
                raise ValueError('Estado before-P incoerente.')
            # Independent equilibrium at x=0, before the point jump.
            if s['Mx_physical_Nmm']!=0 or s['My_physical_Nmm']!=0 or s['Vx_N']!=(-ra[0]-points[0]['force_xy_N'][0])+points[0]['force_xy_N'][0] or s['Vy_N']!=(-ra[1]-points[0]['force_xy_N'][1])+points[0]['force_xy_N'][1]:
                raise ValueError('Estado before-P diverge das reações originais.')
    if previous!=L:raise ValueError('Partição não cobre todo o vão.')


def _equilibrium(summary):
    """Unique bi-supported equilibrium, plus exact replay of source rounding.

    The original binary64 reactions are not changed. Their producing operations
    are replayed exactly, and the same saved loads/positions define rational
    reactions for the ideal physical moment field. No epsilon erases actions.
    """
    L=summary['length_mm'];length=F(L);loads=summary['loads']
    q=[sum((F(a['q_xy_N_mm'][j]) for a in loads if a['kind']=='uniform'),F(0)) for j in (0,1)]
    qa=[math.fsum(a['q_xy_N_mm'][j] for a in loads if a['kind']=='uniform') for j in (0,1)]
    left=[-qa[j]*L/2 for j in (0,1)];right=left.copy()
    ra=[-v*length/2 for v in q];rb=ra.copy()
    for p in loads:
        if p['kind']!='point':continue
        for j in (0,1):
            force=p['force_xy_N'][j];position=p['s_mm']
            left[j]-=force*(L-position)/L;right[j]-=force*position/L
            ra[j]-=F(force)*(length-F(position))/length;rb[j]-=F(force)*F(position)/length
    if left!=summary['support_reactions']['left_force_xy_N'] or right!=summary['support_reactions']['right_force_xy_N']:
        raise ValueError('Reações originais divergem da sequência aritmética biapoiada da fonte Vlasov.')
    def rational(x):return dict(numerator=str(x.numerator),denominator=str(x.denominator))
    proof=dict(method='Exact rational simply-supported equilibrium; source binary64 reaction operations replayed exactly, no tolerance.',
        source_left_force_xy_N=left,source_right_force_xy_N=right,
        rational_q_xy_N_mm=[rational(x) for x in q],rational_left_force_xy_N=[rational(x) for x in ra],
        rational_right_force_xy_N=[rational(x) for x in rb],original_demand_unchanged=True,
        source_loads_sha256=digest(loads),support_moments_identically_zero=True)
    return q,ra,proof


def _fields(summary,piece):
    """The original statically determinate idealization, in exact rationals."""
    q,ra,_=_equilibrium(summary)
    if piece['kind']=='support_limit':
        fields=dict(Mx=[F(0)],My=[F(0)],Vstrong=[-ra[1]],Vweak=[-ra[0]])
    else:
        a=F(piece['a_mm']);ell=F(piece['b_mm'])-a
        v=[-ra[j]-q[j]*a for j in (0,1)];mx=-ra[1]*a-q[1]*a*a/2;my=ra[0]*a+q[0]*a*a/2
        for p in summary['loads']:
            if p['kind']=='point' and p['s_mm']<=piece['a_mm']:
                force=list(map(F,p['force_xy_N']));distance=a-F(p['s_mm'])
                v=[v[j]-force[j] for j in (0,1)];mx-=force[1]*distance;my+=force[0]*distance
        fields=dict(Mx=[mx,v[1]*ell,-q[1]*ell*ell/2],My=[my,-v[0]*ell,q[0]*ell*ell/2],
            Vstrong=[v[1],-q[1]*ell],Vweak=[v[0],-q[0]*ell])
    fields['N']=[F(0)]
    fields['Mx_original']=fields['Mx'];fields['My_original']=fields['My']
    return {k:list(v)+[F(0)]*(3-len(v)) for k,v in fields.items()}


def _rational_bound(fields,original,piece,ref):
    """Reuse the audited rational Bernstein/gauge objective without conversion
    of dependent coefficients to binary64 boxes. Exact physical support zeros
    and absent signed branches therefore survive non-dyadic point reactions.
    """
    binding=_binding(original,piece);core._binding(binding,ref)
    controls={a:core._bernstein([(v,v) for v in values]) for a,values in fields.items()}
    required=set()
    for a in ('N','Mx','My','Mx_original','My_original'):
        for pair in controls[a]:required.update(core._required(a.split('_')[0],pair))
    missing=sorted(a for a in required if not ref['eligible_components'][a])
    rows=[];exact=[]
    for i in range(3):
        values={a:controls[a][i] for a in core.ACTIONS}
        row=dict(control=i,is_physical_state=False,intervals={a:[core._outward(lo,-1),core._outward(hi,1)] for a,(lo,hi) in values.items()})
        if not missing:
            metrics=core._objective(values,ref['signed_capacity_floor'],ref['shear_capacity_lower_N']);exact.append(metrics)
            row.update({k:core._outward(v,1) for k,v in metrics.items()})
        rows.append(row)
    maximum=max(r['index_upper'] for r in exact) if exact else None
    shear=max(r['shear_ratio_upper'] for r in exact) if exact else None
    sufficient=maximum is not None and maximum<=1 and shear<=1
    out=dict(schema='isolated_EN_Ue_rational_equilibrium_bound_v1',algorithm=core.SCHEMA,
        source_binding=binding,capacity_reference_sha256=digest(ref),
        exact_rational_coefficients={a:[dict(numerator=str(v.numerator),denominator=str(v.denominator)) for v in values] for a,values in fields.items()},
        source_polynomials={a:dict(lo=[core._outward(v,-1) for v in values],hi=[core._outward(v,1) for v in values]) for a,values in fields.items()},
        identically_zero_by_exact_coefficients={a:all(v==0 for v in values) for a,values in fields.items()},
        controls=rows,required_branches=sorted(required),missing_branches=missing,
        index_upper=core._outward(maximum,1) if maximum is not None else None,
        shear_ratio_upper=core._outward(shear,1) if shear is not None else None,
        component_qualified=sufficient,observed_failure=False,flange_reserve_Mf=0,
        separate_EN_6_1_6_required=True,**{k:False for k in FLAGS})
    out['content_sha256']=digest(out);return out


def _binding(original,piece):
    """Use the ORIGINAL source snapshot, not a replacement resistance object."""
    n=original['normal_source_binding'];b=original['catalog_source_binding']
    return dict(source_sha256=original['source_analysis_sha256'],catalog_index=b['catalog_index'],
        profile_id=b['section_profile_id'],nominal_identity_sha256=b['nominal_identity_sha256'],
        nodes_sha256=b['nodes_sha256'],component_sections_sha256=original['qualified_normal_sha256'],
        material=copy.deepcopy(n['material']),case_id=original['combination_id'],
        segment_id=digest(piece),action_convention=n['action_convention'])


def _authority(original):
    b=original['catalog_source_binding'];inv=normal_inventory(b['catalog_index'])
    if (original['normal_source_binding']!=inv['source_binding'] or original['qualified_normal_sha256']!=inv['qualified_content_sha256']):
        raise ValueError('Fonte normal original não coincide com inventário externo qualificado.')
    n=original['normal_source_binding']
    for a,c in [('catalog_index','catalog_index'),('catalog_id','catalog_id'),('profile_id','section_profile_id'),
                ('nominal_identity_sha256','nominal_identity_sha256'),('nodes_sha256','nodes_sha256')]:
        if n[a]!=b[c]:raise ValueError('Capacidade EN pertence a outro perfil/contorno nominal.')
    if n['material']!=MATERIAL or b['material']['fy_MPa']!=250.:raise ValueError('Material EN incompatível.')
    return qualified_reference(b['catalog_index'],original['qualified_normal_sha256'])


def _calculate(summary,pieces,original):
    ref=_authority(original);b=original['catalog_source_binding']
    _validate_source(summary,pieces,b,b['material'])
    if original['combination_id']!=summary['combination_id']:raise ValueError('Identidade do caso alterada.')
    from .en_ue_bending_applicability import assess
    applicability=assess(summary,original['normal_source_binding'])
    checks=[];ratios={'strong':F(0),'weak':F(0)}
    for piece in pieces:
        fields=_fields(summary,piece)
        bound=_rational_bound(fields,original,piece,ref)
        for axis,key in (('strong','Vstrong'),('weak','Vweak')):
            # Affine shear extrema are at the segment endpoints. Core controls
            # include both endpoints and retain the distinct before/after-P.
            v=max(abs(F(x)) for c in bound['controls'] for x in c['intervals'][key])
            ratios[axis]=max(ratios[axis],v/F(ref['shear_capacity_lower_N'][axis]))
        checks.append(dict(source_piece=copy.deepcopy(piece),fields=bound['source_polynomials'],
            field_controls=[dict(control=r['control'],intervals=r['intervals']) for r in bound['controls']],
            required_branches=bound['required_branches'],missing_branches=bound['missing_branches'],
            signed_interaction=bound if applicability['qualified'] else None))
    maximum=max(ratios.values());missing=sorted({k for p in checks for k in p['missing_branches']})
    ready=applicability['qualified'] and not missing
    index=max(p['signed_interaction']['index_upper'] for p in checks) if ready else None
    mv=dict(index_upper=index,component_sufficient=bool(ready and index<=1 and maximum<=1),
        status=('sufficient' if index<=1 and maximum<=1 else 'inconclusive_upper_bound') if ready else 'pending',
        missing_branches=missing,reason=('Teto suficiente da componente; EN6.1.6 separado.' if index<=1 and maximum<=1
            else 'Teto conservador excedido; não demonstra falha física.') if ready else
            '; '.join(([applicability['reason']] if not applicability['qualified'] else [])+
                      (['Ramos resistentes requeridos ausentes: '+', '.join(missing)] if missing else [])))
    out=dict(equilibrium_proof=_equilibrium(summary)[2],original_source_binding=copy.deepcopy(original),source_analysis_material=dict(E_MPa=summary['E_MPa'],G_MPa=summary['G_MPa']),
        member_id=summary['member_id'],capacity_reference=ref,pieces=checks,applicability=applicability,
        shear=dict(strong_ratio_upper=core._outward(ratios['strong'],1),weak_ratio_upper=core._outward(ratios['weak'],1),
            index_upper=core._outward(maximum,1),component_sufficient=maximum<=1,
            status='sufficient' if maximum<=1 else 'inconclusive_upper_bound',observed_failure=False),mv=mv,
        full_member_field_covered=True,N_identically_zero=True,original_moments_equal_current=True,
        **{k:False for k in FLAGS})
    out['content_sha256']=digest(out);return out


def attach_dense(result,section):
    if CHOICE not in result['input_data']:return result
    out=copy.deepcopy(result)
    try:c=configuration(out['input_data'])
    except ValueError as e:out[FIELD]=_pending(out,out['input_data'][CHOICE],str(e));return out
    if c is None or not c['enabled']:return out
    reason=_domain(out['input_data'],c)
    if reason:out[FIELD]=_pending(out,c,reason);return out
    from .ue_catalog_reference import preserved
    source=preserved(out)
    if source is None:out[FIELD]=_pending(out,c,'Fonte Ue original ausente.');return out
    b=source['source_binding'];inv=normal_inventory(b['catalog_index'])
    if section['nodes_sha256']!=b['nodes_sha256'] or section['profile_id']!=b['section_profile_id']:
        out[FIELD]=_pending(out,c,'Seção fornecida difere da fonte Ue.');return out
    ev=_base(out,c);ev['catalog_source_binding']=copy.deepcopy(b)
    load_inventory=_load_inventory(out)
    records=out.get('torsion_evidence',{}).get('records',[])
    if [(r['combination_id'],r['limit_state']) for r in records]!=[(r['combination_id'],r['limit_state']) for r in ev['source_inventory']]:
        out[FIELD]=_pending(out,c,'Inventário Vlasov integral divergente.');return out
    for rec in records:
        if rec['limit_state']!='ELU':continue
        row=dict(combination_id=rec['combination_id'],limit_state='ELU',status='pending',reason=None,check=None,
            source_analysis_sha256=None,original_source_binding=None)
        d=rec.get('analysis')
        if rec['status']!='elastic_demand_computed' or not isinstance(d,dict):
            row['reason']='Demanda Vlasov pendente: '+'; '.join(rec.get('missing',[]))
        else:
            try:
                if d.get('schema')!='single_vlasov_member_demand_v1' or d['section']!=section:
                    raise ValueError('Campo integral e seção corrente requeridos antes da compactação.')
                _validate_case(d,load_inventory[rec['combination_id']],out['input_data'])
                original=dict(catalog_source_binding=copy.deepcopy(b),normal_source_binding=copy.deepcopy(inv['source_binding']),
                    qualified_normal_sha256=inv['qualified_content_sha256'],source_analysis_sha256=digest(d),
                    combination_id=rec['combination_id'])
                rec['EN_ue_dense_source_sha256']=original['source_analysis_sha256']
                row.update(source_analysis_sha256=original['source_analysis_sha256'],original_source_binding=original)
                row['check']=_calculate(d,_source_pieces(d),original);row['status']='computed'
            except (ValueError,KeyError,TypeError,ArithmeticError) as e:row['reason']=str(e)
        ev['records'].append(row)
    ev.update(_counts(ev));out[FIELD]=ev;return out


def finalize(result):
    if CHOICE not in result['input_data'] or 'ue_catalog_reference' not in result['input_data']:return result
    out=copy.deepcopy(result)
    try:
        c=configuration(out['input_data'])
        if c is None or not c['enabled']:return out
        reason=_domain(out['input_data'],c)
    except ValueError as e:c=out['input_data'][CHOICE];reason=str(e)
    if FIELD not in out:out[FIELD]=_pending(out,c,reason or 'Demanda Vlasov integral indisponível; calcule explicitamente no contorno Ue ativo.')
    ev=out[FIELD];ev['source_torsion_snapshot_sha256']=digest(out.get('torsion_evidence'))
    summaries={r['combination_id']:r for r in out.get('torsion_evidence',{}).get('records',[])}
    for row in ev['records']:row['source_summary_record_sha256']=digest(summaries.get(row['combination_id']))
    ev['snapshot_sha256']=digest({k:v for k,v in ev.items() if k!='snapshot_sha256'});return out


def preserved(result):
    ev=result.get(FIELD)
    if ev is None:return None
    from .application import fingerprint
    from .ue_catalog_reference import preserved as source_preserved
    try:
        c=configuration(result['input_data']);base=_base(result,c)
        if (c is None or not c['enabled'] or fingerprint(result['input_data'])!=result['input_fingerprint']
            or any(digest(ev.get(k))!=digest(v) for k,v in base.items() if k!='records')
            or ev['source_torsion_snapshot_sha256']!=digest(result.get('torsion_evidence'))
            or ev['snapshot_sha256']!=digest({k:v for k,v in ev.items() if k!='snapshot_sha256'})):
            raise ValueError('Snapshot EN Ue incompatível com as entradas/fontes salvas.')
        expected=[r['combination_id'] for r in base['source_inventory'] if r['limit_state']=='ELU']
        if [(r['combination_id'],r['limit_state']) for r in ev['records']]!=[(i,'ELU') for i in expected]:
            raise ValueError('Inventário ELU EN incompleto/duplicado.')
        load_inventory=_load_inventory(result) if any(r['status']=='computed' for r in ev['records']) else {}
        source=source_preserved(result);summaries={r['combination_id']:r for r in result.get('torsion_evidence',{}).get('records',[])}
        for row in ev['records']:
            summary=summaries.get(row['combination_id'])
            if row['source_summary_record_sha256']!=digest(summary):raise ValueError('Fonte compacta alterada.')
            if row['status']=='computed':
                if _domain(result['input_data'],c) or source is None or summary['status']!='elastic_demand_computed':
                    raise ValueError('Componente fora do domínio original.')
                _validate_case(summary['analysis'],load_inventory[row['combination_id']],result['input_data'])
                original=row['original_source_binding']
                if (original['catalog_source_binding']!=source['source_binding'] or ev['catalog_source_binding']!=source['source_binding']
                    or original['source_analysis_sha256']!=row['source_analysis_sha256']
                    or original['source_analysis_sha256']!=summary.get('EN_ue_dense_source_sha256')
                    or original['combination_id']!=row['combination_id']):raise ValueError('Vínculo original da demanda substituído.')
                pieces=[p['source_piece'] for p in row['check']['pieces']]
                replay=_calculate(summary['analysis'],pieces,original)
                if digest(replay)!=digest(row['check']):raise ValueError('Aritmética/campos assinados EN divergem da fonte em um ou mais trechos.')
            elif row['status']!='pending' or row['check'] is not None or not row['reason']:
                raise ValueError('Pendência sem motivo ou com índice inventado.')
        if any(type(ev.get(k)) is not int or ev[k]!=v for k,v in _counts(ev).items()):raise ValueError('Contagem EN divergente.')
    except (KeyError,TypeError,AttributeError,IndexError) as e:raise ValueError('Registro EN Ue incompleto/malformado.') from e
    return copy.deepcopy(ev)


def global_context(result, *, sectional=False):
    ev=preserved(result)
    if ev is None:return None
    context=dict(reason=(f"EN Ue: dois cortantes calculados em {ev['shear_computed_cases']} casos ELU; "
        f"M–V calculada em {ev['mv_computed_cases']}, suficiente em {ev['mv_sufficient_cases']} e pendente em {ev['mv_pending_cases']}. "
        'Esta componente não verifica B/Tsv/Tw nem conclui EN6.1.6, estabilidade ou aprovação da barra.'),
        binding=dict(snapshot_sha256=ev['snapshot_sha256'],scope=SCOPE))
    if sectional:
        from .isolated_en_panorama import sectional_context
        context['sectional']=sectional_context(result,ev,catalog=True)
        if not context['sectional']['ELU_cases']:
            context['reason']='Nenhuma combinação ELU na seleção; condições seccionais EN não qualificadas por este inventário. '+context['reason']
    return context
