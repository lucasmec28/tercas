"""NBR service criteria preparation and linear point kinematics, without a solve.

No old load combination, scalar deflection or torsion field is converted into
qualified combined service. Appendix A limits are not rotational limits.
"""
import copy
import math

SOURCE = 'ABNT NBR14762:2010 §9.8.5 e Anexo A, A.2–A.3 / Tabela A.1 notas a,e,f,g'
SOURCE_SHA256 = 'c2a01615a3ce9e2b93aeb7fee757f7bf9dd932adaefbc242e848ce813dc82407'
SCHEMA = 'isolated_purlin_service_preparation_v1'
KINEMATICS_SCHEMA = 'concomitant_linear_point_displacement_v1'
CRITERIA = ('same_direction_rare', 'opposing_characteristic_variable_only')


def _finite(value, label, positive=False):
    if type(value) not in (int, float) or not math.isfinite(value) or (positive and value <= 0):
        raise ValueError(label+': número finito'+(' positivo' if positive else '')+' necessário.')
    return float(value)


def _text(value, label):
    if not isinstance(value, str) or not value.strip():
        raise ValueError(label+': identificação explícita necessária.')
    return value


def table_a1_limit(length_mm, criterion):
    """Normative *criterion definition*, not selection of a displacement model."""
    L = _finite(length_mm, 'Vão teórico entre apoios', True)
    if criterion not in CRITERIA:
        raise ValueError('Critério de terça da Tabela A.1 desconhecido.')
    denominator = 180 if criterion == CRITERIA[0] else 120
    return dict(criterion=criterion, theoretical_span_mm=L, denominator=denominator,
        limit_mm=L/denominator, source=SOURCE, source_sha256=SOURCE_SHA256,
        source_printed_pages=[69, 70, 71], source_pdf_pages=[75, 76, 77],
        action_rule=('Combinações raras de serviço, usando variáveis no mesmo sentido da ação permanente.'
                     if denominator == 180 else
                     'Somente ações variáveis de sentido oposto à permanente (sucção), com valor característico; sem PP/CP.'),
        displacement_rule='Selecionar ponto, direção e parcela de deslocamento conforme A.2.4 e A.3.3; a flecha normal local não é automaticamente vertical global.',
        other_requirement='Evitar empoçamento, especialmente em coberturas de pequena declividade (nota g).',
        stricter_project_limits_permitted=True, service_approved=False)


def prepare(result):
    """Read frozen area sources and prepare missing cases, never change the matrix."""
    data = result.get('input_data', {})
    L = data.get('L_mm')
    if type(L) not in (int, float) or not math.isfinite(L) or L <= 0:
        return dict(schema=SCHEMA, status='missing_span', criteria=[], missing=['Vão teórico entre apoios.'],
                    combined_ELS_approved=False, source_matrix_changed=False)
    criteria = [table_a1_limit(L, c) for c in CRITERIA]
    out = dict(schema=SCHEMA, status='prepared_not_calculated', criteria=criteria,
        source_matrix_changed=False, source_result_schema=result.get('schema'),
        combined_ELS_approved=False, whole_member_approved=False,
        same_direction_rare_case_ids=[], opposite_only_case_ids=[], prepared_cases=[],
        missing=['Ponto, direção e referência/corda dos deslocamentos relevantes.',
                 'Rigidez de serviço compatível com o campo combinado conforme §9.8.5.',
                 'Aplicabilidade da análise conforme §8.1 e avaliação de empoçamento (Anexo A, nota g).'])
    if result.get('schema') != 'tercas_batch_results_v1' or data.get('load_mode') != 'area':
        out['missing'].append('Ações características separadas e família de combinações para confrontar as notas e/f; ações diretas combinadas não permitem inferi-las.')
        return out
    bundle = result.get('load_bundle', {})
    combos = bundle.get('combinations', [])
    for c in combos:
        coeff = c.get('coefficients', {})
        if (c.get('limit_state') != 'ELS' or not isinstance(coeff, dict)
                or set(coeff)-{'PP','CP','SC','V_Cima','V_Baixo','P'}
                or any(type(v) not in (int,float) or not math.isfinite(v) or v < 0 for v in coeff.values())):
            continue
        if (c.get('type') == 'ELS rara' and coeff.get('V_Cima', 0) == 0
                and coeff.get('PP') == 1 and coeff.get('CP') == 1):
            # Candidate identity only. Its particular psi factors / requested
            # displacement portion are not certified by this inventory.
            out['same_direction_rare_case_ids'].append(c['id'])
        if (coeff.get('V_Cima') == 1 and all(v == 0 for k,v in coeff.items() if k != 'V_Cima')):
            out['opposite_only_case_ids'].append(c['id'])
    vector = bundle.get('case_vectors_N_mm', {}).get('V_Cima')
    if (isinstance(vector, dict) and set(vector) == {'normal','parallel'}
            and all(type(v) in (int,float) and math.isfinite(v) for v in vector.values())):
        if all(v == 0 for v in vector.values()):
            out['opposite_action_status'] = 'explicitly_zero_characteristic_wind'
        else:
            out['opposite_action_status'] = 'requires_separate_response'
            out['prepared_cases'].append(dict(id='SERVICE_A1_F_CHARACTERISTIC_SUCTION',
                limit_state='ELS', type='Tabela A.1 nota f', coefficients={'V_Cima':1.},
                q_vector=copy.deepcopy(vector), P_vector={'normal':0.,'parallel':0.},
                criterion=CRITERIA[1], source='case_vectors_N_mm.V_Cima do bundle salvo',
                self_weight_added=False, permanent_loads_included=False,
                status='prepared_not_calculated', displacement_mm=None, index=None))
            if not out['opposite_only_case_ids']:
                out['missing'].append('Resposta para sucção característica isolada da nota f; uma combinação de resultado ascendente com PP/CP não a substitui.')
    else:
        out['opposite_action_status'] = 'missing_characteristic_source'
        out['missing'].append('Vetor característico de sucção ausente; não inferido como zero.')
    if not out['same_direction_rare_case_ids']:
        out['missing'].append('Combinação rara candidata de mesmo sentido não consta da seleção salva.')
    return out


_BINDING = ('combination_id','member_id','section_id','analysis_id','stiffness_id','coordinate_system','reference_line_id')


def point_displacement(state, *, offset_xy_mm, projection_xy, left, right, limit_mm=None):
    """Transform co-located u/phi and subtract the SAME point's end chord.

    Each state is an atomic result from a single analysis/stiffness. Axes x,y
    are right handed with positive phi about the longitudinal axis. `offset`
    is from the displacement reference line O to the desired point P in the
    undeformed cross-section. The function has no stiffness qualification or
    continuum envelope proof, so all numbers remain linear diagnostics.
    """
    states = (left, state, right)
    for r in states:
        if not isinstance(r,dict):raise ValueError('Estado concomitante necessário.')
        if r.get('limit_state') != 'ELS':raise ValueError('Somente estados de serviço.')
        for key in _BINDING:_text(r.get(key), key)
        for key in ('station_mm','ux_mm','uy_mm','phi_rad'):_finite(r.get(key),key)
    for r in states:
        if any(r[key] != state[key] for key in _BINDING):
            raise ValueError('Combinação, seção, referência ou rigidez de origem divergentes.')
    a,s,b = (r['station_mm'] for r in states)
    if not a <= s <= b or a == b:raise ValueError('Posição ou corda inválida.')
    def pair(v,label):
        if not isinstance(v,(list,tuple)) or len(v)!=2:raise ValueError(label+': duas componentes necessárias.')
        return [_finite(x,label) for x in v]
    rx,ry=pair(offset_xy_mm,'Ponto de serviço');nx,ny=pair(projection_xy,'Direção')
    if not math.isclose(nx*nx+ny*ny,1.,rel_tol=1e-12,abs_tol=1e-12):
        raise ValueError('A direção deve ser um vetor unitário explícito.')
    values=[]
    for r in states:
        x=r['ux_mm']-ry*r['phi_rad'];y=r['uy_mm']+rx*r['phi_rad']
        values.append([_finite(x,'ux no ponto'),_finite(y,'uy no ponto')])
    t=(s-a)/(b-a)
    chord=[(1-t)*values[0][i]+t*values[2][i] for i in (0,1)]
    relative=[values[1][i]-chord[i] for i in (0,1)]
    projected=_finite(nx*relative[0]+ny*relative[1],'Projeção relativa')
    if limit_mm is not None:limit_mm=_finite(limit_mm,'Limite declarado',True)
    return dict(schema=KINEMATICS_SCHEMA, binding={k:state[k] for k in _BINDING},
        station_mm=s, reference_stations_mm=[a,b], offset_xy_mm=[rx,ry], projection_xy=[nx,ny],
        point_displacement_xy_mm=values[1], chord_displacement_xy_mm=chord,
        relative_displacement_xy_mm=relative, projected_relative_mm=projected,
        diagnostic_ratio=None if limit_mm is None else _finite(abs(projected)/limit_mm,'Razão diagnóstica'),
        physical_rotation_qualified=False, first_order_applicability_qualified=False,
        effective_stiffness_qualified=False, continuous_envelope_qualified=False,
        combined_ELS_approved=False, whole_member_approved=False,
        scope='Cinemática linear concomitante no ponto; não é previsão física de grande giro nem verificação ELS completa.',
        formula='uP=(ux_O-ry*phi, uy_O+rx*phi); deslocamento relativo à corda dos extremos do mesmo ponto.')
