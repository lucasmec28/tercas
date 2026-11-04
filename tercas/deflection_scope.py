"""Explicit opt-in to an isolated local uniaxial deflection component.

This is a model-scope change, not qualification of reduced biaxial stiffness.
The existing scalar MSE calculation and all its guards are left unchanged.
No action, result, source or historical output is silently converted.
"""
import copy

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
        'a componente isolada com o limite declarado; não aprova ELS completo ou o elemento.')


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
        formula_source='ABNT NBR14762:2010 §9.8.5, MSE escalar; fonte fornecida',
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
    result['deflection_scope_evidence'] = record
    result['ELS']['local_uniaxial_component'] = copy.deepcopy(record)
    result['ELS']['criterion_scope'] = record['criterion_scope']
    # Do not add/recover index or change numerical failures, status, deflection,
    # criticals or missing-property outcomes. Only the calculation scope changes.
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
            row['Observação'] = (row['Observação'] + ' ' + TEXT).strip()
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


def render_choice(st, data, key):
    """Optional in a staged copy; no automatic time-triggered activation."""
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
