"""Six self-contained exact Ue100 references: scalar components, no global approval.

The research source registry remains a historical elastic record. A separately
pinned consumption decision qualifies only the stated scalar calculations.
No import from research paths, no catalogue migration or 1.20 mm input transfer.
"""
from pathlib import Path
import copy
import hashlib
import json
import math
import numbers

ROOT = Path(__file__).with_name('data') / 'ue_family'
REGISTRY_SHA = '3919d41d60e8423d7ae44a2bfb32bbd7c75783c7165bd78c027a20757e61cbe3'
MANIFEST_SHA = 'e7237c35f9b557a820d3b478c1db02101e9a39e368addbbab64465f535288e95'
DECISION_SHA = 'f1790861e5373f00184f2481840e48c3f14c1a494d9666531ac2d6aa2158d6d4'
THICKNESSES = (1.5, 2., 2.25, 2.65, 3., 3.35)
FIELD = 'ue_family_reference'
VERSION = 'own_Ue100_six_scalar_components_app_v1'
REPORTING_VERSION = 'own_Ue100_six_self_contained_snapshot_v1'
EDITABLE = {'load_application_policy', 'local_support_verification_scope', 'direct_load_basis', 'project', 'actions_origin', 'load_mode', 'area_inputs', 'selected_types',
            'q_uls', 'q_sls', 'P_uls', 'P_sls', 'x_uls', 'x_sls',
            'q_parallel_uls', 'q_parallel_sls', 'P_parallel_uls', 'P_parallel_sls',
            'deflection_model', 'torsion_model', 'point_contact', 'roof_top_load', 'isolated_en_stress_model', 'isolated_combined_service'}
SCOPE = ('Seis referências numéricas próprias Ue100×50×17, ri=t, linha '
         'facetada R01 de 209 nós. E=200000 MPa, ν=0,3, G=E/2,6, fy=250 MPa. '
         '3000≤L≤6000 mm, Lx=Ly=Lz=L, K=Cb=Cm=1, garfos ideais e empenamento livre. '
         'N=0 e torque primário imposto=0. Telha sem contato ou contribuição estrutural. '
         'PP físico no CG pode produzir torque, fora desta componente idealizada de flexão. '
         'Resistências escalares §9.8.2 por eixo/sentido e interação §9.9 concomitante. '
         'Sem liberação do perfil comercial, aprovação global, ELS combinado, torção ou 3D.')
ELS_PENDING = ('Pendente: rigidez efetiva combinada e ELS completo não qualificados. '
               'Flecha escalar apenas diagnóstica neste estado biaxial, sem índice de atendimento.')
ELS_UNIAXIAL = ('Componente forte uniaxial, com q e P paralelos locais realmente nulos; '
                'critério escalar informado, sujeito às guardas numéricas e de posição. '
                'Não é ELS completo ou aprovação global.')
FROZEN = ('Seção e vão mudam somente por prévia/aplicação explícita. As seis espessuras '
          'têm propriedades, críticos e pisos individuais; não há interpolação. Material, '
          'vínculos, fontes e sentidos permanecem congelados. Alteração incompatível '
          'abre inspeção sem substituir os dados. Ações e identificação são editáveis.')
TRACE_NOTE = ('Nenhuma das seis espessuras tem dispensa distorcional pela Tabela 14: '
              'D forte próprio entra no cálculo. Na alma comprimida, a entrada D é '
              'piso elástico discreto individual, não modo D identificado nem dispensa. '
              'Nos lábios, D é vale convencional próprio. ELS biaxial e torção física '
              'continuam pendentes; resultados não aprovam a terça globalmente.')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def number(value, name):
    if isinstance(value, bool) or not isinstance(value, numbers.Real):
        raise ValueError(name + ' deve ser real finito sem coerção.')
    try:
        f = float(value)
    except (ValueError, TypeError, OverflowError) as exc:
        raise ValueError(name + ' não representável.') from exc
    if not math.isfinite(f) or value != f:
        raise ValueError(name + ' não pode ser arredondado para entrar no domínio.')
    return f


def gate():
    """Recheck packaged source files on every public calculation; no research imports."""
    if sha(ROOT/'sources.json') != MANIFEST_SHA:
        raise ValueError('Manifesto da família Ue alterado; cálculo desativado.')
    manifest=json.loads((ROOT/'sources.json').read_text())
    payload={}
    for name,record in manifest['files'].items():
        raw=(ROOT/name).read_bytes()
        if hashlib.sha256(raw).hexdigest()!=record['sha256']:
            raise ValueError('Fonte da família Ue alterada: '+name)
        payload[name]=json.loads(raw) if name.endswith('.json') else raw.decode('utf-8')
    registry=payload['elastic_registry.json'];decision=payload['consumption_decision.json']
    if (manifest['files']['elastic_registry.json']['sha256']!=REGISTRY_SHA or
            manifest['files']['consumption_decision.json']['sha256']!=DECISION_SHA or
            decision['registry_sha256']!=REGISTRY_SHA or
            decision['accepted_for_signed_scalar_components'] is not True or
            decision['thicknesses_mm']!=list(THICKNESSES) or
            decision['span_domain_inclusive_mm']!=[3000.,6000.] or
            decision['strong_Table14_exemption'] is not False or
            decision['web_Mdist_identified_Nmm'] is not None or
            any(decision[k] is not False for k in ('physical_load_eccentricity_qualified',
                'combined_ELS_approved','whole_member_approved','torsion_physical_loading_qualified',
                'physical_conditions_verified'))):
        raise ValueError('Decisão de consumo da família Ue incompatível.')
    rows=registry['profiles']
    if (tuple(r['thickness_mm'] for r in rows)!=THICKNESSES or
            [r['profile_id'] for r in rows]!=decision['profile_ids']):
        raise ValueError('Identidades da família Ue incompatíveis.')
    return copy.deepcopy(rows)


def claims_reference(data):
    if not isinstance(data,dict):return False
    return any(key in data for key in (FIELD,'ue_family_model','ue_family_sources','ue_family_reference_evidence'))


def _rho(lam):
    return 1. if lam <= .673 else (1. - .22 / lam) / lam


def floor_scalar_proof(W, fy, floor):
    """Sufficient comparison with every Md >= this floor, not global monotonicity.

    On the active branch let x=sqrt(Md/(W*fy)): rho=x-.22*x*x and
    d(rho)/dx=1-.44*x>0 for x<1/.673. The literal rounded transition
    has a small jump, so the separate plateau rho=1 must also exceed
    rho_floor. If lambda_floor<=.673, all Md>=floor stay on the plateau.
    This is algebra for a prequalified discrete floor, not a new certificate.
    """
    values=[number(v,n) for v,n in zip((W,fy,floor),('W','fy','Piso'))]
    if any(v<=0 for v in values):raise ValueError('Parâmetros positivos exigidos para o piso.')
    W,fy,floor=values
    lam=math.sqrt(W*fy/floor);rho=_rho(lam)
    if lam<=.673:
        branch='entire_admissible_critical_range_on_plateau'
    elif rho<=1. and 1.-.44/.673>0.:
        branch='active_branch_increasing_in_critical_and_plateau_checked_separately'
    else:
        raise ValueError('Piso fora desta prova suficiente da curva literal arredondada.')
    return dict(lambda_floor=lam,rho_floor=rho,proof_branch=branch,
        conservative_for_all_critical_at_least_floor=True,literal_curve_globally_monotone_claimed=False,
        Mdist_identified_Nmm=None,physical_continuum_proof=False)


def _strength(W, Wc, Ml, Me, Md, *, lower_bound=False):
    fy, gamma = 250., 1.1
    if lower_bound:floor_scalar_proof(W,fy,Md)
    ly = math.sqrt(W * fy / Ml)
    l0 = math.sqrt(Wc * fy / Me)
    chi = 1. if l0 <= .6 else 1.11 * (1. - .278 * l0*l0) if l0 < 1.336 else 1. / (l0*l0)
    lflt = math.sqrt(chi * Wc * fy / Ml)
    ld = math.sqrt(W * fy / Md)
    caps = {'local': W * fy * _rho(ly) / gamma,
            'FLT': chi * Wc * fy * _rho(lflt) / gamma,
            'distortional': W * fy * _rho(ld) / gamma}
    return dict(W_mm3=W, Wc_mm3=Wc, Ml_Nmm=Ml, Me_Nmm=Me,
        Mdist_Nmm=None if lower_bound else Md,
        Mdist_identified_Nmm=None if lower_bound else Md,
        Mdist_lower_bound_Nmm=Md if lower_bound else None,
        distortion_input_kind='certified_discrete_lower_bound' if lower_bound else 'own_conventional_D_valley',
        lambda_local=ly, rho_local=_rho(ly), lambda_FLT=l0, chi_FLT=chi,
        lambda_local_at_FLT=lflt, rho_local_at_FLT=_rho(lflt),
        lambda_dist=ld, rho_dist=_rho(ld),
        MRd_local_Nmm=caps['local'], MRd_FLT_Nmm=caps['FLT'], MRd_dist_Nmm=caps['distortional'],
        MRd_Nmm=min(caps.values()), known_min_Nmm=min(caps.values()),
        governing_branches=[k for k, v in caps.items() if v == min(caps.values())],
        distortional_exemption=False, whole_member_approved=False)


def reference(thickness_mm, L_mm=4000.):
    t = number(thickness_mm, 'Espessura')
    L = number(L_mm, 'Vão')
    if t not in THICKNESSES:
        raise ValueError('Somente as seis espessuras registradas, sem interpolação ou herança de 1,20.')
    if not 3000. <= L <= 6000.:
        raise ValueError('Domínio do lote: 3000≤L≤6000 mm.')
    r = next(row for row in gate() if row['thickness_mm'] == t)
    p, m, w, c = r['properties'], r['material'], r['exterior_moduli'], r['modal_criticals']
    nx = math.pi**2 * m['E_MPa'] * p['Ix_strong_mm4'] / L**2
    ny = math.pi**2 * m['E_MPa'] * p['Iy_weak_mm4'] / L**2
    kt = m['G_MPa'] * p['J_mm4'] + math.pi**2 * m['E_MPa'] * p['Cw_mm6'] / L**2
    nz = kt / p['r0_mm']**2
    root = math.sqrt(p['j_mm']**2 + kt/nx)
    me = {'strong_positive': math.sqrt(ny * kt), 'strong_negative': math.sqrt(ny * kt),
          'weak_web_compressed': nx * (root + p['j_mm']),
          'weak_lips_compressed': kt / (root + p['j_mm'])}
    caps = {}
    for sense in ('strong_positive', 'strong_negative'):
        caps[sense] = _strength(w['Wx_first_yield_mm3'], w['Wx_top_mm3'],
            r['local_strong_primary']['Ml_strong_Nmm'], me[sense], c['strong_distortional']['value_Nmm'])
    for side in ('web', 'lips'):
        key = 'weak_' + side + '_compressed'
        md = r['weak_web_distortional']['lower_bound_Nmm'] if side == 'web' else c['lips_distortional']['value_Nmm']
        caps[key] = _strength(w[key]['W_mm3'], w[key]['Wc_mm3'], c[side+'_local']['value_Nmm'],
                              me[key], md, lower_bound=side == 'web')
        caps[key]['Cs'] = w[key]['Cs']
    props = dict(A_mm2=p['A_mm2'], Ix_mm4=p['Ix_strong_mm4'], Iy_mm4=p['Iy_weak_mm4'],
                 J_mm4=p['J_mm4'], Cw_mm6=p['Cw_mm6'], r0_mm=p['r0_mm'], j_mm=p['j_mm'],
                 centroid_xy_mm=p['centroid_xy_mm'], shear_center_xy_mm=p['shear_center_xy_mm'])
    model = dict(H_external_mm=100., B_external_mm=50., lip_external_mm=17., t_mm=t, ri_mm=t,
        L_mm=L, web_flat_mm=100.-4*t, E_MPa=m['E_MPa'], G_MPa=m['G_MPa'], nu=m['nu'], fy_MPa=250.,
        stability_lengths=dict(Lx_mm=L, Ly_mm=L, Lz_mm=L), Kx=1., Ky=1., Kz=1., Cb=1., Cm=1.,
        supports='ideal forks; bending rotations and warping free',
        N_N=0., imposed_primary_torque_Nmm=0., cladding='no contact or structural contribution; actions only',
        geometry_convention='R01 faceted thin-wall line with exterior fibres; ri=t, 209 nodes',
        physical_geometry_verified=False, Pierin_critical_values_or_signs_used=False)
    return dict(schema=VERSION, id=r['profile_id'], thickness_mm=t, model=model, properties=props,
        source_record=r, registry_sha256=REGISTRY_SHA,
        global_criticals=dict(Nex_N=nx, Ney_N=ny, Nez_N=nz, torsion_warping_stiffness_Nmm2=kt,
                             Me_strong_Nmm=me['strong_positive'], Me_weak_web_Nmm=me['weak_web_compressed'],
                             Me_weak_lips_Nmm=me['weak_lips_compressed']),
        resistances_exterior_primary=caps, scalar_resistances_computed=True,
        resistance_release=False, combined_ELS_approved=False, torsion_physical_loading_qualified=False,
        physical_conditions_verified=False, whole_member_approved=False, published=False)


def source(thickness_mm, L_mm=4000., angle=0.):
    ref = reference(thickness_mm, L_mm)
    angle = number(angle, 'Inclinação')
    from .application import defaults
    from .catalogs import entries
    t, L, p, m = ref['thickness_mm'], ref['model']['L_mm'], ref['properties'], ref['model']
    dims = dict(h=100., bf=50., lip=17., t=t)
    index = next(i for i, e in enumerate(entries()) if e['family']=='Ue' and e['dimensions_mm']==dims)
    d = defaults(index)
    c = ref['resistances_exterior_primary']
    d.update(project=f'Ensaio sintético {ref["id"]}, L={L:g}, θ={angle:+g}; não é projeto', synthetic=True,
        member_application='purlin', L_mm=L, load_mode='area',
        selected_types=['ELU normal', 'ELS rara', 'ELS frequente', 'ELS quase permanente'],
        area_inputs=dict(spacing_m=1.5, permanent_kgf_m2=8., live_kgf_m2=25., wind_up_kgf_m2=60., wind_down_kgf_m2=40.),
        inclination=dict(value=angle, unit='degrees', spacing_basis='roof', permanent_basis='roof', live_basis='horizontal', wind_basis='roof'),
        model_domain='cladding_actions_only_20261103_r1', x_uls=L/2, x_sls=L/2,
        property_origin=f'Referência própria {ref["id"]}; R01 209 nós, ri=t={t:g}; propriedades e módulos exteriores próprios, material declarado do ensaio. Não são propriedades consumidas de Pierin/catálogo.',
        Ml_Nmm=c['strong_positive']['Ml_Nmm'], Mdist_Nmm=c['strong_positive']['Mdist_Nmm'],
        critical_origin='Local forte: NBR14762:2010 Tabela12(b) com W exterior próprio. D forte e críticos fracos: FSM R01 próprios, material e sinais rastreados. Nenhuma dispensa T14 nas seis espessuras; nenhum crítico ou sentido de Pierin consumido.',
        actions_origin='Ações sintéticas para auditoria, não projeto real. Matriz fornecida por Lucas em 31/10/2026 preservada; P de manutenção separado. Não é rederivação normativa dos coeficientes.',
        route_domain=True, left_web=False, right_web=False,
        support_origin='Garfos matemáticos, rotações de flexão e empenamento livres; ligação real não comprovada.',
        patch_mm=None, patch_origin='Introdução local de P não qualificada neste ensaio.',
        ELS_limit_mm=L/180., ELS_origin='L/180 selecionado para ensaio; não regra universal.',
        ELS_down_denominator=180., ELS_up_denominator=120.)
    d['properties'].update(A_cm2=p['A_mm2']/100, mass_kg_m=p['A_mm2']*.00785,
        Ix_cm4=p['Ix_mm4']/1e4, Iy_cm4=p['Iy_mm4']/1e4, Wx_cm3=c['strong_positive']['W_mm3']/1000,
        J_mm4=p['J_mm4'], Cw_mm6=p['Cw_mm6'], ri_mm=t, E_MPa=m['E_MPa'], G_MPa=m['G_MPa'], fy_MPa=250., fu_MPa=400.)
    d['segments'] = [dict(start_mm=0., end_mm=L, Ly_top_effective_mm=L, Ly_bottom_effective_mm=L,
        Lz_effective_mm=L, Cb_mode='one', restraint_provenance='Lx=Ly=Lz=L, K=Cb=Cm=1; garfos ideais/empenamento livre. Sem apoio intermediário ou telha estrutural.')]
    d['weak_axis'] = {}
    for sign, side in [('positive','web'), ('negative','lips')]:
        a = c['weak_'+side+'_compressed']
        md = a['Mdist_lower_bound_Nmm'] if side=='web' else a['Mdist_identified_Nmm']
        origin = (f'{ref["id"]}; mesmo contorno/material e sentido próprio: My positivo comprime alma, negativo lábios. '
                  f'Garfos ideais, L={L:g}, K=Cb=Cm=1, N0, torque imposto0; sem Pierin.')
        if side=='web':
            origin += f' Entrada numérica D={md:g} é piso conservador DISCRETO individual, não autovalor D identificado nem dispensa; identificado continua nulo no registro. Domínio 3000–6000 mm.'
        else:
            origin += f' D convencional predominante próprio={md:.17g} Nmm, vale da assinatura contínua; não D puro ou autovalor finito exato.'
        d['weak_axis'][sign] = dict(W_mm3=a['W_mm3'], Wc_mm3=a['Wc_mm3'], Ml_Nmm=a['Ml_Nmm'], Mdist_Nmm=md,
            Nex_N=ref['global_criticals']['Nex_N'], Nez_N=ref['global_criticals']['Nez_N'],
            r0_mm=p['r0_mm'], j_mm=p['j_mm'], Cm=1., Cs=a['Cs'], plain_u_no_distortion=False, provenance=origin)
    d['ue_family_model'] = copy.deepcopy(m)
    d['ue_family_sources'] = dict(reference_id=ref['id'], registry_sha256=REGISTRY_SHA,
        profile_sha256=ref['source_record']['profile_file_sha256'], nodes_sha256=ref['source_record']['nodes_sha256'],
        manifest_sha256=MANIFEST_SHA, consumption_decision_sha256=DECISION_SHA,
        web_bound_source=ref['source_record']['weak_web_distortional']['bound_source'])
    return d


def _protected(data):
    from .ue_member_application import editable
    p = {k:copy.deepcopy(v) for k,v in data.items() if k not in EDITABLE|editable(data)|{FIELD}}
    if isinstance(p.get('inclination'),dict):p['inclination'].pop('value',None)
    return p


def assess(data):
    failed = dict(eligible=False, active=False, calculable=False, reference_id=None, action_errors=[])
    if not isinstance(data,dict):return dict(failed,reasons=['Objeto JSON inválido.'])
    if not isinstance(data.get('properties'),dict):
        return dict(failed,reasons=['Conjunto de propriedades deve ser um objeto JSON.'])
    try:
        from .ue_member_application import expected as application_expected
        expected = application_expected(source(data['properties'].get('t'), data.get('L_mm')),data)
    except (OSError,ValueError,TypeError,KeyError,ArithmeticError) as exc:
        return dict(failed,reasons=[str(exc)])
    from .homogeneous_reference import differences, _editor_errors, _action_errors
    changed = differences(_protected(data),_protected(expected))
    reasons = ['Campos protegidos divergentes: '+', '.join(changed)] if changed else []
    reasons.extend(_editor_errors(data,expected))
    from .ue_member_application import editor_errors as application_editor_errors
    reasons.extend(application_editor_errors(data))
    token = dict(schema=VERSION,reference_id=expected['ue_family_sources']['reference_id'])
    if FIELD in data and differences(data[FIELD],token):reasons.append('Marcador de lote inválido.')
    action_errors = _action_errors(data,expected) if not reasons else []
    active = not reasons and data.get(FIELD)==token
    return dict(eligible=not reasons,active=active,calculable=active and not action_errors,
        reference_id=token['reference_id'] if not reasons else None,reasons=reasons,action_errors=action_errors)


def activate(data):
    state = assess(data)
    if not state['eligible']:raise ValueError('Lote não ativado: '+'; '.join(state['reasons']))
    out=copy.deepcopy(data)
    out[FIELD]=dict(schema=VERSION,reference_id=state['reference_id'])
    return out


def load_reference(thickness_mm,L_mm=4000.,angle=0.):
    return activate(source(thickness_mm,L_mm,angle))


def apply_span(data,L_mm):
    state=assess(data)
    if not state['active']:raise ValueError('Ative referência íntegra antes de mudar o vão.')
    return apply_geometry(data,data['properties']['t'],L_mm)


def apply_geometry(data,thickness_mm,L_mm):
    """Explicit complete section replacement; retain actions and absolute P positions."""
    state=assess(data)
    if not state['active']:raise ValueError('Ative referência íntegra antes de mudar seção ou vão.')
    from .ue_member_application import expected as application_expected,editable
    out=application_expected(source(thickness_mm,L_mm,data['inclination']['value']),data)
    for key in EDITABLE | editable(data):
        if key in data:out[key]=copy.deepcopy(data[key])
        else:out.pop(key,None)
    out=activate(out)
    from .isolated_en_application import reset_changed_declaration
    reset_changed_declaration(out)
    return out


def _evidence(data):
    state=assess(data)
    if not state['calculable']:
        raise ValueError('Lote desativado: '+'; '.join(state['reasons'] or state['action_errors'] or ['ative explicitamente.']))
    ref=reference(data['properties']['t'],data['L_mm'])
    from .application import fingerprint
    from .load_application_policy import source_scope
    return dict(schema=VERSION,reporting_version=REPORTING_VERSION,reference_id=ref['id'],scope=source_scope(data,SCOPE),input_sha256=fingerprint(data),
        source_documents=copy.deepcopy(data['ue_family_sources']),model=ref['model'],
        global_criticals=ref['global_criticals'],signed_scalar_capacities=ref['resistances_exterior_primary'],
        source_record=ref['source_record'],strength_formula_source='NBR14762:2010 §9.8.2, §9.9 N=0; source copy supplied by user',
        weak_web_Mdist_identified_Nmm=None,strong_Table14_exemption=False,
        scalar_resistances_computed=True,physical_conditions_verified=False,
        combined_stress_spectrum_certified=False,combined_ELS_approved=False,
        torsion_physical_loading_qualified=False,whole_member_approved=False,
        app_route_connected=True,requires_research_adapter=False)


def evidence(data):
    from .ue_member_application import annotate_evidence
    return annotate_evidence(_evidence(data),data)


def _annotate_els(result):
    from .deflection_scope import enabled
    if enabled(result['input_data']):return  # Explicit isolated component, not combined ELS.
    def mark(block,q,p):
        uniaxial=q==0. and p==0.
        block['family_ELS_scope']=dict(strong_uniaxial_actions=uniaxial,combined_ELS_approved=False,
            whole_member_approved=False,source='NBR14762:2010 §9.8.5 scalar Ief only; no combined effective section transfer')
        if not uniaxial:
            block.pop('index',None)
            block.update(status='not_evaluated',criterion_status='pending_combined_stiffness',reason=ELS_PENDING,diagnostic_only=True)
        return uniaxial
    if result.get('schema')=='tercas_batch_results_v1':
        for case in result['cases']:
            c=case['combination']
            if c['limit_state']!='ELS':continue
            uni=mark(case['evidence']['ELS'],c['q_vector']['parallel'],c['P_vector']['parallel'])
            case['evidence']['inclination']['resistance_status']=ELS_UNIAXIAL if uni else ELS_PENDING
            if not uni:
                for row in case['rows']:
                    row.update(**{'Índice':None,'Situação':'Pendente — rigidez ELS combinada','Observação':ELS_PENDING})
        from .batch import governing
        result['summary']=governing(result['cases'])
    else:
        from .direct_self_weight import calculation_inputs
        d=calculation_inputs(result['input_data'])
        uni=mark(result['ELS'],d.get('q_parallel_sls',0.),d.get('P_parallel_sls',0.))
        result['inclination_evidence']['ELS']['resistance_status']=ELS_UNIAXIAL if uni else ELS_PENDING


def _annotate_sources(result,record):
    origin=('Referência própria '+record['reference_id']+'; R01 ri=t, propriedades de linha e módulos exteriores. '
            'Catálogo somente documental; registro SHA256 '+REGISTRY_SHA+'.')
    def fields(d):
        for v in d.values():v['origin']=origin
    for key in ('input_snapshot','common_input_snapshot'):
        if key not in result:continue
        s=result[key]['selected_section']
        s['nominal_documentary_catalog']=dict(entry_id=s['entry_id'],source_url=s['source'],
            scope='Correspondência nominal/histórico somente, não fonte numérica.')
        s.update(entry_id=record['reference_id'],source=origin,active_numeric_reference_id=record['reference_id'])
        fields(s['fields'])
    def checks(block):
        if not isinstance(block,dict):return
        if 'input_fields' in block:
            block['nominal_documentary_entry_id']=block['entry_id']
            block['entry_id']=record['reference_id']
            fields(block['input_fields'])
    checks(result.get('section_checks'))
    containers=[c['evidence'] for c in result.get('cases',[])] if 'cases' in result else [result]
    for block in containers:
        checks(block.get('section_checks'))
        if 'NBR_branches' in block:
            d=block['NBR_branches']['distortional']
            d['own_reference_scope']=dict(Mdist_identified_Nmm=record['signed_scalar_capacities']['strong_positive']['Mdist_identified_Nmm'],
                Table14_exemption=False,source=record['source_record']['modal_criticals']['strong_distortional']['source'])
        evs=[block['inclination']] if 'inclination' in block else list(block.get('inclination_evidence',{}).values())
        for ev in evs:
            for sign,cap in ev.get('weak_axis_capacities',{}).items():
                key='weak_web_compressed' if sign=='positive' else 'weak_lips_compressed'
                r=record['signed_scalar_capacities'][key]
                cap['own_distortional_input']=dict(kind=r['distortion_input_kind'],
                    Mdist_identified_Nmm=r['Mdist_identified_Nmm'],Mdist_lower_bound_Nmm=r['Mdist_lower_bound_Nmm'],
                    is_exemption=False,physical_continuum_proof=False)
    result['weak_critical_reference']=None
    result['strong_critical_reference']=None


def calculate_reference(data):
    record=evidence(data)
    from .application import _calculate
    from .batch import _calculate_batch
    result=_calculate_batch(data,_calculate_case=_calculate) if data['load_mode']=='area' else _calculate(data)
    _annotate_els(result)
    _annotate_sources(result,record)
    result.update(ue_family_reference_evidence=record,whole_member_approved=False,
                  combined_ELS_approved=False,torsion_physical_loading_qualified=False,
                  app_route_connected=True,requires_research_adapter=False)
    gate()  # Fail if a frozen source changed during this operation.
    from .flexural_components import attach_fresh
    return attach_fresh(result,record)


def report(doc,result):
    """Describe the saved calculation snapshot, never requalify historical data."""
    r=result.get('ue_family_reference_evidence')
    if not r:return
    m=r['model'];t=m['t_mm']
    doc.add_heading(f'Família própria Ue100 — espessura {t:g} mm',1)
    from .roof_top_load import enabled as roof_enabled,LEGACY_COMPARATOR_NOTE
    top_active=roof_enabled(result.get('input_data',{})) and result.get('input_data',{}).get('member_application','purlin')=='purlin'
    if top_active:doc.add_paragraph(LEGACY_COMPARATOR_NOTE)
    doc.add_paragraph(r['scope'])
    doc.add_paragraph('Identidade numérica: '+r['reference_id']+'. Pierin é somente correspondência nominal; nenhum crítico ou sentido histórico foi consumido.')
    doc.add_paragraph('O vetor próprio conserva a geometria R01 arredondada/facetada, ri=t, e módulos exteriores. Não mistura propriedades do catálogo com críticos próprios.')
    doc.add_paragraph(f'Vão registrado: {m["L_mm"]:.15g} mm. Lx=Ly=Lz=L, K=Cb=Cm=1; garfos ideais e empenamento livre. Ne/Me/FLT da referência no CT, recalculados neste vão.')
    doc.add_paragraph('Críticos globais: '+'; '.join(k+'='+format(v,'.15g') for k,v in r['global_criticals'].items())+'.')
    doc.add_paragraph('Nenhuma dispensa da Tabela 14 nesta família de seis espessuras. D forte próprio efetivamente incluído no mínimo resistente.')
    web=r['signed_scalar_capacities']['weak_web_compressed']
    doc.add_paragraph(f'Alma comprimida: piso elástico discreto próprio={web["Mdist_lower_bound_Nmm"]:.15g} Nmm; Mdist identificado nulo. Não é modo identificado, dispensa ou prova da casca física. O piso não foi transferido de outra espessura.')
    for name,c in r['signed_scalar_capacities'].items():
        doc.add_paragraph(name+': W='+format(c['W_mm3'],'.15g')+' mm³; Wc='+format(c['Wc_mm3'],'.15g')+
            ' mm³; Ml='+format(c['Ml_Nmm'],'.15g')+' Nmm; Me='+format(c['Me_Nmm'],'.15g')+
            ' Nmm; MRd local/FLT/D='+ '/'.join(format(c[k],'.15g') for k in ('MRd_local_Nmm','MRd_FLT_Nmm','MRd_dist_Nmm'))+
            ' Nmm; mínimo='+format(c['MRd_Nmm'],'.15g')+' Nmm.')
    if not result.get('deflection_scope_evidence') and 'gross_biaxial_component_evidence' not in result and 'aa_web_component_evidence' not in result:
        doc.add_paragraph('ELS forte uniaxial: somente critério parcial quando as ações locais reais q e P paralelas forem nulas. Estados biaxiais permanecem sem índice ELS por rigidez combinada pendente. Não se transfere evidência de outra seção, carga ou comprimento.')
    from .load_application_policy import active as ct_active
    if not ct_active(result.get('input_data',{})):
        doc.add_paragraph('N=0 e torque primário imposto=0 apenas nesta componente matemática. PP físico no CG pode ser excêntrico ao centro de cisalhamento. Torção/empenamento físico, introdução local, ligações e aprovação global permanecem pendentes.')
    doc.add_paragraph('Fontes da emissão: '+json.dumps(r['source_documents'],ensure_ascii=False,sort_keys=True))
    doc.add_paragraph('SHA-256 das entradas desta referência: '+r['input_sha256'])


def scope_for(data):
    from .load_application_policy import source_scope
    return source_scope(data,SCOPE)
