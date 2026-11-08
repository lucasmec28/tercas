"""Versioned choice of an isolated local uniaxial deflection component.

This is a model-scope change, not qualification of reduced biaxial stiffness.
The existing scalar MSE calculation and all its guards are left unchanged.
No action, result, source or historical output is silently converted.
"""
import copy
import math

FIELD = 'deflection_model'
MODE = 'local_uniaxial_component_v1'
LABEL = 'Flecha somente uniaxial local'
PURLIN_ROW = 'Flecha uniaxial — vertical local da terça'
GIRT_ROW = 'Flecha uniaxial — horizontal da travessa'
ROWS = (PURLIN_ROW, GIRT_ROW)
TEXT = ('Flecha uniaxial isolada no eixo local solicitado: vertical local da terça '
        '(normal à cobertura) ou horizontal da travessa (normal ao fechamento). '
        'Usa a componente normal das ações e Ix efetivo da flexão em torno de X. '
        'Não é a flecha vertical global da cobertura inclinada nem a resultante dos dois eixos. '
        'As ações paralelas permanecem nas entradas, combinações e verificações resistentes. '
        'O efeito delas na rigidez efetiva desta componente, a outra flecha e a parcela '
        'de torção/empenamento ficam fora deste modelo reduzido. O índice confronta somente '
        'a componente isolada com o limite declarado; não aprova ELS completo ou o elemento. '
        'Se a própria tensão elástica bruta excede fy, a flecha fica apenas diagnóstica. '
        'Essa guarda do aplicativo não verifica as tensões da seção efetiva. '
        'ELS combinado é uma análise adicional opcional, fora deste objetivo de flecha; '
        'sua ausência não constitui pendência normativa deste critério declarado.')

ELASTIC_GUARD_SCOPE = (
    'Guarda de consistência adotada pelo aplicativo, não nova prescrição da NBR: '
    'max(abs(Mx))/Wx bruto <= fy. Considera apenas a flexão forte isolada. '
    'O atendimento desta condição não prova elasticidade da seção efetiva, '
    'da solicitação biaxial ou da resposta com torção; não se infere Wef de Ief.')


def _elastic_guard(result):
    """Record a necessary gross-elastic check; never qualify effective stress.

    Use the *consumed* SLS snapshot, not editable input loads. This also keeps
    area/support-limit and separately prepared direct-load adapters consistent.
    A new calculation only may call this helper; rendering never calls it.
    """
    spec = result['input_snapshot']
    fields = spec['selected_section']['fields']
    W = fields['Wx_cm3']['value']
    fy = fields['fy_MPa']['value']
    positive = lambda x: type(x) in (int, float) and math.isfinite(x) and x > 0
    record = dict(schema='isolated_uniaxial_gross_elastic_guard_v1',
        scope=ELASTIC_GUARD_SCOPE, Wg_mm3=W*1000 if positive(W) else None,
        fy_MPa=fy if positive(fy) else None, max_abs_M_Nmm=None,
        sigma_gross_max_MPa=None, passed=None,
        effective_section_stress_qualified=False,
        source='Equilíbrio da viga biapoiada q/P; tensão elástica bruta M/Wg. '
               'Propriedades, material e ações do snapshot consumido.')
    if not positive(W) or not positive(fy):
        record.update(status='missing_gross_elastic_inputs',
            reason='Guarda elástica uniaxial pendente: Wx bruto e fy positivos com as propriedades do caso são necessários. Flecha apenas diagnóstica.')
        return record
    from .core.protocolo_ief import max_moment
    actions = spec['SLS']
    # max_moment is analytical equilibrium only; E, Ig and Ml are unused there.
    m = max_moment((spec['L_mm'], 1., 1., 1., actions['q_Nmm'], actions['P_N'], actions['x_mm']))
    sigma = m/record['Wg_mm3']
    passed = sigma <= fy
    record.update(max_abs_M_Nmm=m, sigma_gross_max_MPa=sigma, passed=passed,
        status='gross_elastic_guard_passed' if passed else 'gross_elastic_model_exceeded',
        reason=('Guarda bruta atendida; tensões da seção efetiva não qualificadas.' if passed else
                f'Tensão elástica bruta uniaxial {sigma:.9g} MPa > fy={fy:.9g} MPa. Flecha apenas diagnóstica, sem índice conclusivo.'))
    return record


def enabled(data):
    """Omitted means unchanged legacy policy; unknown values fail closed."""
    if FIELD not in data:return False
    from .biaxial_component import MODE as GROSS_MODE, eligible_choice
    from .aa_component import MODES as AA_MODES
    if not isinstance(data[FIELD], str) or data[FIELD] not in (MODE,GROSS_MODE,*AA_MODES):
        raise ValueError('Modelo de flecha não reconhecido; entradas não convertidas.')
    if data[FIELD] in (GROSS_MODE,*AA_MODES):
        if not eligible_choice(data):
            raise ValueError('Componente biaxial integral exclusiva das referências próprias Ue de viga isolada com aplicação explícita.')
        return False
    return True


def activate(data):
    """Explicit caller action. Returns a copy and leaves physical inputs intact."""
    out = copy.deepcopy(data)
    out[FIELD] = MODE
    return out


def _description(data, q, p, original_q=None, original_p=None):
    from .member_application import is_girt
    girt = is_girt(data)
    return dict(schema=MODE, text=TEXT,
        application='wall_girt' if girt else 'purlin',
        displacement_axis='local_normal_horizontal' if girt else 'local_normal_roof_vertical',
        displacement_label='Horizontal da travessa' if girt else 'Vertical local da terça, normal à cobertura',
        bending_axis='local_X_strong', inertia='Ix_effective',
        formula_source='ABNT NBR14762:2010 §9.8.5, MSE escalar; pp.51–52 (PDF57–58) da fonte fornecida',
        formula_source_sha256='c2a01615a3ce9e2b93aeb7fee757f7bf9dd932adaefbc242e848ce813dc82407',
        effective_inertia_law='lambda=sqrt(abs(Mx)/Ml); Ief=Ig for lambda<=0.673; otherwise min(Ig, Ig*(1-0.22/lambda)/lambda)',
        implementation_convention='Clamp Ief<=Ig disclosed for rounded coefficients; not a new normative formula.',
        displacement_method='Integral Mx(x)*unit_load_moment(x)/(E*Ief(x)), full simply supported physical span; same-sign q/P only.',
        model_scope='isolated_uniaxial_flexural_component',
        q_vector_N_mm=copy.deepcopy(q), P_vector_N=copy.deepcopy(p),
        original_q_vector_N_mm=copy.deepcopy(original_q if original_q is not None else q),
        original_P_vector_N=copy.deepcopy(original_p if original_p is not None else p),
        actual_parallel_actions_zero=((original_q if original_q is not None else q)['parallel'] == 0. and
                                     (original_p if original_p is not None else p)['parallel'] == 0.),
        interior_bending_parallel_actions_zero=(q['parallel'] == 0. and p['parallel'] == 0.),
        parallel_actions_removed_from_strength=False,
        combined_stiffness_qualified=False, combined_ELS_approved=False,
        total_displacement_evaluated=False, torsional_displacement_evaluated=False,
        whole_member_approved=False,
        criterion_scope='declared_limit_for_isolated_local_component_only')


def annotate_direct(result):
    """Call only on a newly calculated raw result, before combined-ELS gates."""
    data = result['input_data']
    if not enabled(data):return
    ev = result['inclination_evidence']['ELS']
    record = _description(data, ev['q_vector'], ev['P_vector'])
    guard = _elastic_guard(result)
    record['gross_elastic_guard'] = copy.deepcopy(guard)
    result['deflection_scope_evidence'] = record
    result['ELS']['local_uniaxial_component'] = copy.deepcopy(record)
    result['ELS']['criterion_scope'] = record['criterion_scope']
    # Only withdraw an existing conclusion. Numerical/missing-data failures
    # retain precedence, and no displacement or resistance is changed.
    if guard['passed'] is not True and result['ELS'].get('index') is not None:
        result['ELS'].pop('index')
        result['ELS'].update(criterion_status=guard['status'],
            diagnostic_only=True, reason=guard['reason'])
    ev['deflection_scope'] = copy.deepcopy(record)
    ev['resistance_status'] = TEXT
    result['combined_ELS_approved'] = False
    result['whole_member_approved'] = False


def annotate_batch(result):
    """Summarize already calculated per-state scopes; never rebuild old results."""
    data = result['input_data']
    if not enabled(data):return
    if result.get('schema') != 'tercas_batch_results_v1':return
    for case in result['cases']:
        combo = case['combination']
        if combo['limit_state'] != 'ELS':continue
        ev = case['evidence']['inclination']
        # For support-limit P, original vector is retained separately; the
        # interior scalar adapter correctly has zero P bending contribution.
        previous = case['evidence']['ELS']['local_uniaxial_component']
        record = _description(data, previous['q_vector_N_mm'], previous['P_vector_N'],
                              combo['q_vector'], combo['P_vector'])
        record['gross_elastic_guard'] = copy.deepcopy(previous['gross_elastic_guard'])
        record['case_id'] = combo['id']
        record['point_position'] = combo.get('point_position')
        case['evidence']['ELS']['local_uniaxial_component'] = record
        ev['deflection_scope'] = copy.deepcopy(record)
        ev['resistance_status'] = TEXT
    result['deflection_scope_evidence'] = dict(schema=MODE, text=TEXT,
        scope='per_case_isolated_local_uniaxial_component',
        combined_ELS_approved=False, whole_member_approved=False,
        total_displacement_evaluated=False)
    result['combined_ELS_approved'] = False


def presentation_rows(result, rows):
    """Render recorded scope only. An input token cannot requalify old output."""
    record = result.get('deflection_scope_evidence')
    if not isinstance(record, dict) or record.get('schema') != MODE:return rows
    from .member_application import is_girt
    girt = is_girt(result['input_data'])
    out = []
    for row in rows:
        if row['Verificação'] == 'Flecha vertical — eixo fraco':continue
        if row['Verificação'] in ('Flecha — flexão', 'Flecha horizontal — eixo forte'):
            row = copy.deepcopy(row)
            row['Verificação'] = GIRT_ROW if girt else PURLIN_ROW
            if row.get('Índice') is not None:
                row['Situação'] = ('Não atende' if row['Índice'] > 1 else 'Atende') + ' ao critério uniaxial isolado'
            elif result['ELS'].get('criterion_status') in ('gross_elastic_model_exceeded', 'missing_gross_elastic_inputs'):
                row['Situação'] = 'Pendente — guarda elástica uniaxial'
            row['Observação'] = (row['Observação'] + ' ' + record['text']).strip()
        out.append(row)
    return out


def report(doc, result):
    """Serialize the calculation snapshot, never infer from current input flags."""
    record = result.get('deflection_scope_evidence')
    if not isinstance(record, dict) or record.get('schema') != MODE:return
    doc.add_heading('Flecha uniaxial local — escopo reduzido', 1)
    doc.add_paragraph(record['text'])
    doc.add_paragraph('Não foram removidas as componentes paralelas das combinações de ações. '
                      'A flexão biaxial resistente é independente desta escolha de flecha. '
                      'Limites, fontes, sinais, posição de P e avisos numéricos da rota escalar são preservados.')
    # Stored evidence only. Older records remain exactly historical, with no
    # new calculation, read of live properties or retroactive pass/fail.
    containers = [(c['combination']['id'], c['evidence']['ELS']) for c in result.get('cases', [])
                  if c['combination']['limit_state'] == 'ELS'] if 'cases' in result else [('Direto', result['ELS'])]
    guards = [(name, block.get('local_uniaxial_component', {}).get('gross_elastic_guard'))
              for name, block in containers]
    if any(isinstance(g, dict) for _, g in guards):
        doc.add_paragraph(ELASTIC_GUARD_SCOPE)
        for name, guard in guards:
            if not isinstance(guard, dict):continue
            doc.add_paragraph(str(name)+': '+guard['reason']+
                (f" Mx máximo absoluto={guard['max_abs_M_Nmm']:.12g} Nmm; "
                 f"Wx bruto={guard['Wg_mm3']:.12g} mm³; "
                 f"σg,max={guard['sigma_gross_max_MPa']:.12g} MPa; fy={guard['fy_MPa']:.12g} MPa."
                 if guard['sigma_gross_max_MPa'] is not None else ''))


def render_choice(st, data, key):
    """Explicit control; defaults apply only through named creation actions."""
    if isinstance(data.get('three_girt_model'), dict) and data['three_girt_model'].get('enabled'):
        st.caption('Flecha uniaxial isolada inativa no diagnóstico 3D. A opção armazenada não altera rigidez, vínculos ou resultados do conjunto de três travessas.')
        return False
    active = st.checkbox(LABEL, value=enabled(data), key=key)
    if active:
        data[FIELD] = MODE
        # Clear only the mutually exclusive widget choice, before rendering it.
        # A hidden checkbox can otherwise retain a stale True across reruns.
        st.session_state[key+'_gross']=False
        st.session_state[key+'_aa']=False
        st.caption(TEXT)
    else:
        if data.get(FIELD)==MODE:data.pop(FIELD,None)
        from .biaxial_component import MODE as GROSS_MODE, LABEL as GROSS_LABEL, scope_text as gross_scope_text, eligible_choice, selected
        if eligible_choice(data):
            gross=st.checkbox(GROSS_LABEL,value=selected(data),key=key+'_gross')
            if gross:
                data[FIELD]=GROSS_MODE;st.caption(gross_scope_text(data))
                st.session_state[key+'_aa']=False
            else:
                if data.get(FIELD)==GROSS_MODE:data.pop(FIELD,None)
                from .aa_component_ui import render_choice as render_aa_choice
                render_aa_choice(st,data,key+'_aa')
    return active


def recorded_local_objective(result, raw):
    """Conservative scope proof from a fresh/bound snapshot, never input alone.

    No mechanical calculations or historical upgrades. Invalid optional service
    configurations are not treated as an absent request.
    """
    from .application import fingerprint
    from .isolated_service_component import configuration
    data=result.get('input_data', {})
    record=raw.get('local_uniaxial_component')
    summary=result.get('deflection_scope_evidence')
    if not isinstance(record,dict) or not isinstance(summary,dict):return False
    try:
        cfg=configuration(data)
        if cfg is not None and cfg['enabled']:return False
        if data.get(FIELD)!=MODE or fingerprint(data)!=result.get('input_fingerprint'):return False
        expected=_description(data,record['q_vector_N_mm'],record['P_vector_N'],
            record['original_q_vector_N_mm'],record['original_P_vector_N'])
        if any(record.get(k)!=v for k,v in expected.items()):return False
        if not isinstance(record.get('gross_elastic_guard'),dict):return False
        if result.get('schema')=='NBR14762_one_span_v1':
            return summary==record
        return (result.get('schema')=='tercas_batch_results_v1'
            and summary==dict(schema=MODE,text=TEXT,scope='per_case_isolated_local_uniaxial_component',
                combined_ELS_approved=False,whole_member_approved=False,total_displacement_evaluated=False))
    except (ValueError,TypeError,KeyError):return False
