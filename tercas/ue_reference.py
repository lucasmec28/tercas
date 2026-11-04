"""Explicit, self-contained Ue100 R01 bending-component consumption contract.

A marker is consent, never qualification. Every protected field and every source
file is checked at each public calculation. No research-tree imports or catalogue
conversion. Local and signed global scalar branches are not a whole-member proof.
"""
import copy
import hashlib
import json
import math
import numbers
from pathlib import Path

FIELD = 'ue_reference'
VERSION = 'ue100_own_reference_20261103_r1'
REPORTING_VERSION = 'ue100_components_own_snapshot_sources_20261103_r2'
ID = 'Ue100x50x17x1.20_rounded_R01_209nodes_nu0p3'
REFERENCES = ('Ue100',)
ROOT = Path(__file__).with_name('data') / 'ue_reference'
MANIFEST_SHA256 = 'f5139130fcef62d75f57c889b1faa9a0e7ec53345f72d1f084bd8bc66dd6430c'
DECISION_SHA256 = '42a3b2de4ec8e74bcc1949b6a6a3802e30bc117a5c47a54e7bc454e6c5343875'
SCOPE = ('Referência numérica própria Ue100×50×17×1,20, R01 arredondada de 209 nós, ri=1,20 mm. '
         'Propriedades integrais do mesmo contorno e fibras exteriores; local forte pela Tabela 12(b), '
         'locais fracos e D dos lábios por FSM própria. Pierin define somente a correspondência nominal, '
         'nenhum crítico ou sentido de Pierin é consumido. E=200000 MPa, ν=0,3, G=E/2,6, fy=250 MPa. '
         'Vão contínuo permitido de 3000 a 6000 mm inclusive; Lx=Ly=Lz=L, K=Cb=Cm=1. '
         'Garfos ideais, empenamento livre, N=0 e torque primário imposto=0. Telha sem contato '
         'nem contribuição estrutural, somente ações. O torque físico do PP no CG está fora desta '
         'idealização. Componentes locais/FLT por sentido e interação escalar §9.9; sem aprovação '
         'física, ELS completo, torção, resistência 3D ou aprovação global.')
FROZEN = ('Seção, material, fontes, sentidos, piso D, vínculos e domínio permanecem congelados. '
          'Somente ações, inclinação e identificação são editáveis; o vão exige Prévia/Aplicar. '
          'Ne/Me/FLT são recalculados no vão atual, sem comprimentos destravados independentes '
          'ou apoios intermediários. Alteração protegida abre inspeção sem reparo automático.')
TRACE_NOTE = ('Alma comprimida: entrada D legada é piso elástico conservador de 850000 Nmm; '
              'Mdist identificado permanece nulo, não há dispensa de D. Lábios comprimidos: '
              'Mdist próprio identificado = 1668845,1785399402 Nmm. Tabela 14 dispensa somente '
              'o eixo forte. A evidência MLE de 34 estados específicos de 4 m não é transferida '
              'por ID, inclinação, carga ou comprimento. ELS forte uniaxial mantém somente o critério parcial '
              'quando q e P paralelos reais são zero; com flexão biaxial, rigidez combinada pendente.')
ELS_STATUS = ('Pendente: rigidez efetiva combinada e ELS completo não qualificados nesta rota. '
              'Nesta solicitação biaxial, a flecha escalar é apenas diagnóstico, sem índice de atendimento. '
              'Ausência de qualificação não significa falha do elemento.')
UNAXIAL_ELS_STATUS = ('Componente forte uniaxial: q e P paralelos locais reais iguais a zero. '
                     'Ief escalar e critério informado preservados quando aplicáveis; guardas de posição, '
                     'sentido das ações e avisos numéricos mantidas. Não é ELS completo nem aprovação global.')
ELS_POLICY = ('Qualificação por ações locais reais de cada estado: somente q_parallel=P_parallel=0 '
              'permite o critério parcial forte uniaxial. Outros estados ficam pendentes por rigidez '
              'combinada; os 34 estados MLE de 4 m não são transferidos automaticamente.')
EDITABLE = {'project', 'actions_origin', 'load_mode', 'area_inputs', 'selected_types',
            'q_uls', 'q_sls', 'P_uls', 'P_sls', 'x_uls', 'x_sls',
            'q_parallel_uls', 'q_parallel_sls', 'P_parallel_uls', 'P_parallel_sls',
            'deflection_model', 'torsion_model', 'point_contact'}


def number(value, name='Vão'):
    if isinstance(value, bool) or not isinstance(value, numbers.Real):
        raise ValueError(name + ' deve ser real finito, sem coerção.')
    try:
        result = float(value)
    except (ValueError, TypeError, OverflowError) as exc:
        raise ValueError(name + ' fora da representação numérica.') from exc
    if not math.isfinite(result) or value != result:
        raise ValueError(name + ' não pode ser arredondado para entrar no domínio.')
    return result


def gate():
    """Recheck on every call; never cache source trust across reruns."""
    raw = (ROOT / 'sources.json').read_bytes()
    if hashlib.sha256(raw).hexdigest() != MANIFEST_SHA256:
        raise ValueError('Manifesto Ue alterado; referência desativada.')
    manifest = json.loads(raw)
    payload = {}
    for filename, item in manifest['files'].items():
        content = (ROOT / filename).read_bytes()
        if hashlib.sha256(content).hexdigest() != item['sha256']:
            raise ValueError('Documento fonte Ue alterado: ' + filename)
        payload[filename] = json.loads(content) if filename.endswith('.json') else content.decode('utf-8')
    decision = payload['length_decision.json']
    if (manifest['reference_id'] != ID or decision['reference_id'] != ID or
            manifest['files']['length_decision.json']['sha256'] != DECISION_SHA256 or
            decision['accepted_length_extension'] is not True or
            decision['accepted_for_NBR_9_8_2_3_web_elastic_floor'] is not True or
            decision['length_domain_inclusive_mm'] != [3000., 6000.] or
            decision['Mdist_identified_Nmm'] is not None or
            decision['web_nonapplicability_accepted'] is not False):
        raise ValueError('Decisão Ue não concede este domínio.')
    lips = payload['lips_decision.json']
    if lips['reference_id'] != ID or lips['accepted_for_NBR_9_8_2_3_lips_Mdist'] is not True:
        raise ValueError('Decisão D dos lábios incompatível.')
    return manifest, payload


def _strength(W, Wc, Ml, Me, Mdist=None):
    def rho(x):return 1. if x <= .673 else (1. - .22 / x) / x
    fy, gamma = 250., 1.1
    lam = math.sqrt(Wc * fy / Me)
    chi = 1. if lam <= .6 else 1.11 * (1. - .278 * lam * lam) if lam < 1.336 else 1. / lam**2
    local = W * fy * rho(math.sqrt(W * fy / Ml)) / gamma
    flt = chi * Wc * fy * rho(math.sqrt(chi * Wc * fy / Ml)) / gamma
    dist = None if Mdist is None else W * fy * rho(math.sqrt(W * fy / Mdist)) / gamma
    return {'MRd_local_Nmm': local, 'MRd_FLT_Nmm': flt, 'MRd_dist_Nmm': dist,
            'MRd_Nmm': min(local, flt) if dist is None else min(local, flt, dist)}


def reference(L_mm=4000.):
    L = number(L_mm)
    if not 3000. <= L <= 6000.:
        raise ValueError('Domínio próprio Ue: 3000 ≤ L ≤ 6000 mm, sem arredondar ou limitar a entrada.')
    manifest, payload = gate()
    ref = copy.deepcopy(payload['vector.json'])
    p = ref['properties']; m = ref['model']
    nx = math.pi**2 * m['E_MPa'] * p['Ix_mm4'] / L**2
    ny = math.pi**2 * m['E_MPa'] * p['Iy_mm4'] / L**2
    kt = m['G_MPa'] * p['J_mm4'] + math.pi**2 * m['E_MPa'] * p['Cw_mm6'] / L**2
    nz = kt / p['r0_mm']**2
    root = math.sqrt(p['j_mm']**2 + kt / nx)
    me = {'strong_positive': math.sqrt(ny * kt), 'strong_negative': math.sqrt(ny * kt),
          'weak_web_compressed': nx * (root + p['j_mm']),
          'weak_lips_compressed': kt / (root + p['j_mm'])}
    floor = float(payload['length_decision.json']['Mdist_lower_bound_Nmm'])
    lips = payload['lips_decision.json']['Mdist_Nmm']
    for key, row in ref['resistances_exterior_primary'].items():
        critical = floor if key == 'weak_web_compressed' else lips if key == 'weak_lips_compressed' else None
        row.update(Me_Nmm=me[key], **_strength(row['W_mm3'], row['Wc_mm3'], row['Ml_Nmm'], me[key], critical))
        row['known_min_Nmm'] = row['MRd_Nmm']
    w = ref['resistances_exterior_primary']['weak_web_compressed']
    # Specific-floor monotonic branch and plateau check from reviewed floor_curve.
    lam = math.sqrt(w['W_mm3'] * m['fy_MPa'] / floor)
    rho = (1. - .22 / lam) / lam
    if not (lam > .673 and rho <= 1. and 1. - .44 / .673 > 0.):
        raise ValueError('Piso fora da prova escalar revisada.')
    w.update(Mdist_Nmm=None, Mdist_identified_Nmm=None, Mdist_lower_bound_Nmm=floor)
    m.update(L_mm=L, stability_lengths=dict(Lx_mm=L, Ly_mm=L, Lz_mm=L))
    ref['global_criticals'] = dict(Nex_N=nx, Ney_N=ny, Nez_N=nz, Me_strong_Nmm=me['strong_positive'])
    ref['active_numeric_source']['current_span_mm'] = L
    return ref


def source(reference_id='Ue100', angle=0, L_mm=4000.):
    """Construct an unactivated complete vector, never repair an imported object."""
    if reference_id not in REFERENCES:raise ValueError('Referência Ue não registrada.')
    angle = number(angle, 'Inclinação')
    ref = reference(L_mm); L = ref['model']['L_mm']
    manifest, payload = gate()
    d = copy.deepcopy(payload['canonical.json'])
    d.update(L_mm=L, ELS_limit_mm=L/d['ELS_down_denominator'], member_application='purlin')
    d['project'] = f'Ensaio numérico {ID}, L={L:g}, θ={angle:+g}; não é projeto'
    d['inclination']['value'] = angle
    for key in ('end_mm', 'Ly_top_effective_mm', 'Ly_bottom_effective_mm', 'Lz_effective_mm'):
        d['segments'][0][key] = L
    for row in d['weak_axis'].values():
        row.update(Nex_N=ref['global_criticals']['Nex_N'], Nez_N=ref['global_criticals']['Nez_N'])
    # Same reviewed provenance, generated from the current immutable source vector.
    d['weak_axis']['positive']['provenance'] = (
        'R01 mesmo contorno/material; lado comprimido web. Fonte modal própria rastreada; não Pierin. '
        'signed_scalar_branches_with_certified_discrete_floor Entrada D = piso elástico conservador '
        f'{ref["active_numeric_source"]["web_Mdist_lower_bound_Nmm"]:g} Nmm, não autovalor D identificado. '
        f'Modelo R01 209 nós S-S, L={L:g} mm no intervalo validado 3000–6000 mm; '
        'N0, torque imposto0, Cb=Cm1; Ne/Me/FLT recalculados neste vão. '
        'Uso escalar NBR9.8.2 e interação9.9, sem prova espectral da tensão biaxial real e sem aprovação física.')
    d['active_numeric_reference'] = copy.deepcopy(ref['active_numeric_source'])
    d['ue_model'] = dict(reference_id=ID, N_N=0., imposed_primary_torque_Nmm=0.,
        nu=.3, Kx=1., Ky=1., Kz=1., Cb=1., Cm=1., supports='ideal forks; warping free',
        cladding='no contact or restraint; actions only', effective_lengths_mm=dict(Lx=L, Ly=L, Lz=L),
        member_application='purlin', whole_member_approved=False, combined_ELS_approved=False)
    d['ue_source_documents'] = dict(manifest_sha256=MANIFEST_SHA256,
        length_decision_sha256=DECISION_SHA256,
        vector_sha256=manifest['files']['vector.json']['sha256'],
        lips_decision_sha256=manifest['files']['lips_decision.json']['sha256'])
    return d


def claims_reference(data):
    if not isinstance(data, dict):return False
    active = data.get('active_numeric_reference')
    return (FIELD in data or 'ue_model' in data or 'ue_source_documents' in data or
            isinstance(active, dict) and active.get('reference_id') == ID)


def _protected(data):
    from .ue_member_application import editable
    out = {k: copy.deepcopy(v) for k, v in data.items() if k not in EDITABLE | editable(data) | {FIELD}}
    if isinstance(out.get('inclination'), dict):out['inclination'].pop('value', None)
    return out


def assess(data):
    """Read-only check, including complete physical vectors and source documents."""
    failed = dict(eligible=False, active=False, calculable=False, reference_id=None, action_errors=[])
    if not isinstance(data, dict):return dict(failed, reasons=['Objeto JSON inválido.'])
    try:
        from .ue_member_application import expected as application_expected
        expected = application_expected(source(L_mm=data.get('L_mm')),data)
    except (OSError, ValueError, TypeError, KeyError, ArithmeticError) as exc:
        return dict(failed, reasons=[str(exc)])
    from .homogeneous_reference import differences, _editor_errors, _action_errors
    changed = differences(_protected(data), _protected(expected))
    reasons = ['Campos protegidos divergentes: ' + ', '.join(changed)] if changed else []
    reasons.extend(_editor_errors(data, expected))
    from .ue_member_application import editor_errors as application_editor_errors
    reasons.extend(application_editor_errors(data))
    token = dict(schema=VERSION, reference_id=ID)
    if FIELD in data and differences(data[FIELD], token):reasons.append('Marcador próprio Ue inválido.')
    action_errors = _action_errors(data, expected) if not reasons else []
    active = not reasons and data.get(FIELD) == token
    return dict(eligible=not reasons, active=active, calculable=active and not action_errors,
                reference_id='Ue100' if not reasons else None, reasons=reasons, action_errors=action_errors)


def activate(data):
    state = assess(data)
    if not state['eligible']:raise ValueError('Referência Ue não ativada: ' + '; '.join(state['reasons']))
    out = copy.deepcopy(data); out[FIELD] = dict(schema=VERSION, reference_id=ID)
    return out


def load_reference(reference_id='Ue100', angle=0, L_mm=4000.):
    return activate(source(reference_id, angle, L_mm))


def apply_span(data, L_mm):
    """Only explicit application may rewrite length-derived fields. Keep actions."""
    state = assess(data)
    if not state['active']:raise ValueError('Ative uma referência Ue íntegra antes de alterar o vão.')
    from .ue_member_application import expected as application_expected,editable
    out = application_expected(source(L_mm=L_mm, angle=data['inclination']['value']),data)
    for key in EDITABLE | editable(data):
        if key in data:out[key] = copy.deepcopy(data[key])
        else:out.pop(key, None)
    out[FIELD] = copy.deepcopy(data[FIELD])
    return out


def _evidence(data):
    state = assess(data)
    if not state['calculable']:
        raise ValueError('Cálculo da referência Ue desativado: ' + '; '.join(
            state['reasons'] or state['action_errors'] or ['ative explicitamente a referência.']))
    manifest, _ = gate(); ref = reference(data['L_mm'])
    from .deflection_scope import enabled, TEXT
    isolated = enabled(data)
    from .flexural_components import selected as gross_selected, scope_text as gross_scope_text
    gross=gross_selected(data)
    from .application import fingerprint
    return dict(schema=VERSION, reporting_version=REPORTING_VERSION, reference_id=ID,
        scope=SCOPE, frozen_scope=FROZEN,
        distortion_note=(TRACE_NOTE.split(' A evidência MLE')[0] if isolated or gross else TRACE_NOTE),
        ELS_status=(TEXT if isolated else gross_scope_text(data) if gross else ELS_POLICY),
        input_sha256=fingerprint(data), source_documents=copy.deepcopy(data['ue_source_documents']),
        source_manifest=manifest, active_numeric_source=ref['active_numeric_source'],
        model=ref['model'], global_criticals=ref['global_criticals'],
        signed_scalar_capacities=ref['resistances_exterior_primary'],
        nominal_documentary_reference='Pierin: somente prioridade/correspondência nominal Ue100×50×17×1,20.',
        active_numeric_reference='Propriedades próprias R01; Tabela12(b) forte; FSM própria fraca por sentido; piso D da alma revisado.',
        combined_ELS_approved=False, combined_stress_spectrum_certified=False,
        source_ELS_evidence_transferred=False, physical_conditions_verified=False,
        whole_member_approved=False)


def evidence(data):
    from .ue_member_application import annotate_evidence
    return annotate_evidence(_evidence(data),data)


def _pending_els(result):
    """Gate combined stiffness by actual local actions, never angle or case ID."""
    from .deflection_scope import enabled
    if enabled(result['input_data']):return  # Explicit isolated component, not combined ELS.
    def uniaxial(q, p):return q == 0. and p == 0.
    def mark(block, qualified):
        block['ue_ELS_scope'] = dict(strong_uniaxial_actions=qualified,
            source='NBR14762:2010 §9.8.5; reviewed stage3 scalar Ief; no biaxial reduced law transfer',
            combined_ELS_approved=False, whole_member_approved=False)
        if qualified:return  # Preserve existing numerical/load guard outcomes exactly.
        block.pop('index', None)
        block.update(status='not_evaluated', criterion_status='pending_combined_stiffness', reason=ELS_STATUS,
                     diagnostic_only=True, combined_ELS_approved=False)
    if result.get('schema') == 'tercas_batch_results_v1':
        for case in result['cases']:
            if case['combination']['limit_state'] != 'ELS':continue
            combo=case['combination']
            qualified=uniaxial(combo['q_vector']['parallel'],combo['P_vector']['parallel'])
            mark(case['evidence']['ELS'],qualified)
            case['evidence']['inclination']['resistance_status'] = UNAXIAL_ELS_STATUS if qualified else ELS_STATUS
            if not qualified:
                for row in case['rows']:
                    row.update(**{'Índice': None, 'Situação': 'Pendente — rigidez ELS combinada', 'Observação': ELS_STATUS})
        from .batch import governing
        result['summary'] = governing(result['cases'])
    else:
        d=result['input_data']
        qualified=uniaxial(d.get('q_parallel_sls',0.),d.get('P_parallel_sls',0.))
        mark(result['ELS'],qualified)
        result['inclination_evidence']['ELS']['resistance_status'] = UNAXIAL_ELS_STATUS if qualified else ELS_STATUS



def _own_snapshot_origins(result, record):
    """Reclassify consumed source metadata only; equal catalogue numbers are not sources.

    Input JSON and all numeric values are untouched. The legacy adapter's
    catalogue selection/history is retained only as explicitly documentary data.
    """
    origin = ('Referência própria R01 Ue100, 209 nós: geometria declarada ri=1,20 mm, '
              'propriedades do contorno próprio e material declarado no vetor congelado. '
              'Nenhum valor desta seção é tomado do catálogo por coincidência numérica. '
              'Manifesto próprio SHA-256: ' + record['source_documents']['manifest_sha256'] + '.')
    def fields(values):
        for item in values.values():item['origin'] = origin
    def checks(block):
        if isinstance(block, dict) and 'input_fields' in block:
            fields(block['input_fields'])
            block['nominal_documentary_entry_id'] = block.get('nominal_documentary_entry_id', block['entry_id'])
            block['entry_id'] = record['reference_id']
            block['history_scope'] = 'Histórico operacional do adaptador de catálogo, somente documental; não é fonte dos valores consumidos.'
    for key in ('input_snapshot', 'common_input_snapshot'):
        snapshot = result.get(key)
        if not isinstance(snapshot, dict) or 'selected_section' not in snapshot:continue
        section = snapshot['selected_section']
        if 'nominal_documentary_catalog' not in section:
            section['nominal_documentary_catalog'] = {
                'entry_id': section['entry_id'], 'source_url': section['source'],
                'scope': 'Correspondência nominal e histórico do adaptador somente; não é fonte numérica da referência própria.'}
        section['entry_id'] = record['reference_id']
        section['source'] = origin
        section['active_numeric_reference_id'] = record['reference_id']
        section['history_scope'] = 'Histórico operacional do adaptador de catálogo, somente documental; não é fonte dos valores consumidos.'
        fields(section['fields'])
    checks(result.get('section_checks'))
    for case in result.get('cases', []):checks(case.get('evidence', {}).get('section_checks'))


def calculate_reference(data):
    record = evidence(data)
    from .application import _calculate
    from .batch import _calculate_batch
    result = _calculate_batch(data, _calculate_case=_calculate) if data['load_mode'] == 'area' else _calculate(data)
    _pending_els(result)
    _own_snapshot_origins(result, record)
    # These documentary catalogue lookups are not active numerical inputs.
    result['weak_critical_reference'] = None
    result['strong_critical_reference'] = None
    result['ue_reference_evidence'] = record
    result['whole_member_approved'] = False
    from .flexural_components import attach_fresh
    return attach_fresh(result,record)


def report(doc, result):
    """Use this result's snapshot only, never requalify historical output."""
    record = result.get('ue_reference_evidence')
    if not record:return
    doc.add_heading('Referência própria Ue100 — componentes de flexão', 1)
    for key in ('scope', 'frozen_scope', 'distortion_note', 'ELS_status',
                'nominal_documentary_reference', 'active_numeric_reference'):
        doc.add_paragraph(record[key])
    L = record['model']['L_mm']
    doc.add_paragraph(f'Vão registrado: {L:.15g} mm; Lx=Ly=Lz=L, K=Cb=Cm=1. Ne/Me/FLT recalculados neste vão.')
    doc.add_paragraph('Críticos recalculados: ' + '; '.join(f'{key}: {value:.15g}' for key, value in record['global_criticals'].items()) + '.')
    doc.add_paragraph('Piso D da alma: ' + str(record['active_numeric_source']['web_Mdist_lower_bound_Nmm']) +
                      ' Nmm. Mdist identificado: não identificado (nulo); D não dispensado.')
    labels = {'manifest_sha256': 'Manifesto SHA-256', 'length_decision_sha256': 'Decisão de vão SHA-256',
              'vector_sha256': 'Vetor SHA-256', 'lips_decision_sha256': 'Decisão D lábios SHA-256'}
    doc.add_paragraph('\n'.join(labels.get(name, name) + ': ' + sha for name, sha in record['source_documents'].items()))
    # The input fingerprint is already printed at the end of the common report.
    if record['input_sha256'] != result.get('input_fingerprint'):
        doc.add_paragraph('SHA-256 das entradas da referência: ' + record['input_sha256'])
    doc.add_paragraph('Sem aprovação global, física, de ELS completo ou de torção. Evidência ELS de casos específicos não transferida.')
