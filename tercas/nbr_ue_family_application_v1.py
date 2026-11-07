"""Fresh-only NBR components, bound to complete ELU actions and analytic replay.
No global verdict, denominator replacement, eigenproblem or historical migration.
"""
import copy
import math
from . import nbr_ue_family_v1 as provider
from . import roof_top_load as roof

FIELD = 'nbr_ue_family_application'
SCHEMA = 'nbr_ue_family_application_v1'
SCOPE = ('Componentes de flexão NBR, não aprovação resistente/global. Contorno próprio e '
         'referência nominal publicada são alternativas distintas; índices não são somados. '
         'Sem torção/bimomento, interação biaxial ou ELS combinado. Sem rigidez da telha.')


def _eligible(data):
    from .ue_catalog_reference import claims_reference
    from .pierin_ue_registry import new_study_indices
    return claims_reference(data) and data.get('catalog_index') in new_study_indices()


def _outside_domain(result):
    data = result['input_data']
    network = data.get('three_girt_model', {})
    if not isinstance(network, dict) or (network and type(network.get('enabled')) is not bool):
        return 'Modelo de três travessas malformado; nenhuma reconstrução de viga isolada N=0 autorizada.'
    if network.get('enabled') or data.get('member_application', 'purlin') != 'purlin':
        return 'Rede/travessa com ações próprias e possível força axial: consumidor de cobertura isolada N=0 não aplicado.'
    if result.get('schema') not in ('NBR14762_one_span_v1', 'tercas_batch_results_v1'):
        return 'Resultado não identificado como viga isolada N=0; ações e componentes existentes preservados.'
    return None


def _inventory(result):
    data = result['input_data']
    from .application import fingerprint
    if fingerprint(data) != result.get('input_fingerprint'):
        raise ValueError('NBR família: entradas divergentes.')
    from .ue_catalog_reference import validate, preserved
    validate(data)
    if preserved(result) is None:
        raise ValueError('NBR família: evidência do contorno ausente.')
    if data.get('load_mode') == 'area':
        from .batch import area_bundle
        bundle = area_bundle(data)
        if bundle != result.get('load_bundle'):
            raise ValueError('NBR família: parcelas de área divergentes das entradas.')
        combos = bundle['combinations']
        if [c.get('combination') for c in result.get('cases', [])] != combos:
            raise ValueError('NBR família: inventário de casos incompleto/divergente.')
    else:
        from .direct_self_weight import evidence
        from .direct_roof_separated import combinations
        if evidence(data) is None:
            return [], None, 'Ações diretas sem convenção explícita de PP separado; componentes sem índices.'
        if result.get('schema') != 'NBR14762_one_span_v1':
            raise ValueError('NBR família: schema de demanda direta incompatível.')
        combos, bundle = combinations(data), None
    if len({(c['id'], c['limit_state']) for c in combos}) != len(combos):
        raise ValueError('NBR família: identidades de combinação duplicadas.')
    return combos, bundle, None


def _position(actions, axis):
    rows = []
    for action in actions:
        uniform = action['kind'] == 'uniform'
        force = action[('q_down_N_mm' if uniform else 'P_down_N') if axis == 'normal'
                       else ('q_parallel_N_mm' if uniform else 'P_parallel_N')]
        coordinate = action['height_above_SC_mm' if axis == 'normal' else 'x_from_SC_mm']
        if not force:
            continue
        term = None if coordinate is None else force * coordinate * (-1 if axis == 'normal' else 1)
        state = 'unknown' if term is None else 'destabilizing' if term < 0 else 'stabilizing' if term > 0 else 'shear_center'
        rows.append(dict(name=action['name'], kind=action['kind'], force=force,
                         coordinate_mm=coordinate, stiffness_term=term, classification=state))
    states = [r['classification'] for r in rows]
    state = ('unknown' if 'unknown' in states else 'destabilizing' if 'destabilizing' in states
             else 'stabilizing' if 'stabilizing' in states else 'shear_center')
    return dict(classification=state, individual_actions=rows,
                favorable_height_used=False, physical_position_verified=False)


def _demand(combo, L, axis, sign=None):
    """Exact extrema on every quadratic piece; physical L and simultaneous witness."""
    from .roof_biaxial_positive import _pieces, _coefficients, _stations, _state
    xs = set()
    for lo, hi, after in _pieces(combo, L):
        xs.update(_stations(_coefficients(combo, L, after, axis), lo, hi))
    states = [_state(x, combo, L, 1., 1.) for x in sorted(xs)]
    key = 'Mx_Nmm' if axis == 'normal' else 'My_Nmm'
    def demand(s):
        return abs(s[key]) if sign is None else max(0., s[key] * (1 if sign == 'positive' else -1))
    witness = max(states, key=demand)
    return dict(Msd_Nmm=demand(witness), witness={k: v for k, v in witness.items() if k != 'index'},
                candidate_x_mm=sorted(xs), axis=axis, sign=sign,
                physical_span_mm=L, exact_piecewise_extremum=True)


def _component(route, name, branch, demand, *, applicable=True, reason=None, approximate=False):
    cap = branch.get('MRd_Nmm')
    usable = branch.get('eligible') is True and isinstance(cap, (float, int)) and not isinstance(cap, bool) and math.isfinite(cap) and cap > 0
    index = demand['Msd_Nmm'] / cap if usable and applicable else None
    return dict(route=route, method=name, capacity_Nmm=cap, demand=copy.deepcopy(demand),
        index=index, status='component_index' if index is not None else branch.get('status', 'pending'),
        reason=reason or branch.get('reason') or branch.get('status') or '',
        reference_comparison=('within_reference' if index <= 1 else 'exceeds_reference') if index is not None else None,
        approximate=approximate, whole_member_approved=False)


def _not_applicable_basis(component, sources):
    """Only exact source exemptions count; an absent scalar alone proves nothing."""
    if component['route'] != 'own_rounded_contour' or component['index'] is not None:
        return None
    own = sources['own_rounded_contour']
    if component['method'] == 'weak_positive_distortional':
        branch = own['weak']['positive']['distortional']
        proof = own['weak']['positive']['local'].get('proof', {})
        status = 'not_applicable_lips_in_tension'
        if (component['status'] == status and branch.get('status') == status
                and branch.get('eligible') is True and branch.get('MRd_Nmm') is None
                and proof.get('lips_in_tension_for_positive_pure_weak') is True):
            return dict(status=status, proof=copy.deepcopy(proof))
    elif component['method'] == 'distortional':
        branch = own['strong']['distortional']
        proof = branch.get('table14', {})
        status = 'not_required_table14'
        if (component['status'] == status and branch.get('status') == status
                and branch.get('eligible') is True and branch.get('MRd_Nmm') is None
                and proof.get('exempt') is True):
            return dict(status=status, proof=copy.deepcopy(proof))
    return None


def _build(result):
    data = result['input_data']
    reason = _outside_domain(result)
    if reason:
        from .application import fingerprint
        if fingerprint(data) != result.get('input_fingerprint'):
            raise ValueError('NBR família: entradas divergentes.')
        return dict(schema=SCHEMA, source_input_fingerprint=result['input_fingerprint'], scope=SCOPE,
            sources=None, records=[], inventory=[], method_coverage={}, pending_reason=reason,
            status='outside_isolated_N0_domain', ignored_ELS_cases=0,
            legacy_denominators_replaced=False, whole_member_approved=False)
    combos, bundle, pending = _inventory(result)
    from .resistance_effective_lengths import configuration
    lengths = configuration(data)
    if roof.enabled(data):
        geo = roof.geometry(data)
    else:
        from .ue_catalog_reference import section_for
        section = section_for(data)
        props = section['properties']
        geo = dict(coherent_torsion_section=True, height_above_SC_mm=None,
            x_from_SC_mm=None, CG_xy_mm=props['centroid_xy_mm'],
            SC_xy_mm=props['shear_center_xy_mm'], nodes_sha256=section['nodes_sha256'],
            source='Posição externa não declarada; PP permanece no CG do contorno próprio.')
    action_inventory = []
    for combo in combos:
        if combo['limit_state'] != 'ELU':
            continue
        if bundle is None:
            from .direct_roof_separated import actions
            acts = actions(combo, geo, include_parallel=True)[0]
        else:
            acts = roof._actions(bundle, combo, geo, include_parallel=True)[0]
        action_inventory.append((combo, acts))
    aggregate_position = _position([a for _, acts in action_inventory for a in acts], 'normal')['classification']
    if not action_inventory:
        aggregate_position = 'unknown'
    # The provider needs inputs only. Its detached-result contract would copy
    # every unrelated EN/ELU field if given the full result just to read a packet.
    attached = provider.attach({'input_data': data}, fresh_calculation=True, lengths=lengths,
                               load_position=aggregate_position)
    sources = attached[provider.FIELD]
    own, nominal = sources['own_rounded_contour'], sources['published_nominal_reference']
    if roof.enabled(data) and own['source_binding']['nodes_sha256'] != geo.get('nodes_sha256'):
        raise ValueError('NBR família: contorno resistente e posição das ações divergentes.')
    records = []
    for combo, acts in action_inventory:
        pos = {axis: _position(acts, axis) for axis in ('normal', 'parallel')}
        strong = _demand(combo, data['L_mm'], 'normal')
        parts = []
        for method, branch in nominal['strong'].items():
            parts.append(_component('published_nominal_reference', method, branch, strong,
                reason=nominal['reference_hypothesis']))
        for method, branch in own['strong'].items():
            supported = method != 'FLT_reference' or pos['normal']['classification'] in ('shear_center', 'stabilizing')
            parts.append(_component('own_rounded_contour', method, branch, strong, applicable=supported,
                reason=('Posição desestabilizante/indeterminada: FLT clássico não resolve altura.' if not supported
                        else 'FLT clássico CT/estabilizante; comprimentos resistentes declarados, Cb=1, sem benefício de altura.' if method == 'FLT_reference'
                        else None), approximate=branch.get('elastic_approximation', False)))
        # Existing height remains in its original route. A self-hashed Me is
        # not an independent eigenvalue proof and cannot create a new capacity.
        height = dict(eligible=False, status='separate_existing_height_route',
            reason='Altura desestabilizante exige operador especializado em L físico. '
                   'Resultados existentes permanecem separados; nova rota requer prova independente de Me, não apenas hash.',
            physical_span_mm=data['L_mm'], manual_effective_lengths_used=False)
        parts.append(_component('own_rounded_contour', 'FLT_height_physical_span', height, strong))
        for sign, branches in own['weak'].items():
            demand = _demand(combo, data['L_mm'], 'parallel', sign)
            for method in ('local', 'FLT_reference', 'distortional'):
                supported = method != 'FLT_reference' or pos['parallel']['classification'] in ('shear_center', 'stabilizing')
                parts.append(_component('own_rounded_contour', 'weak_' + sign + '_' + method,
                    branches[method], demand, applicable=supported,
                    reason='Posição individual desestabilizante/indeterminada no eixo fraco.' if not supported else None))
        records.append(dict(combination_id=combo['id'], limit_state='ELU', combination=copy.deepcopy(combo),
            actions=acts, load_position_by_axis=pos, components=parts, height_source=height,
            weak_negative_complete=own['weak']['negative']['complete_reference_components'], whole_member_approved=False))
    coverage = {}
    for record in records:
        for component in record['components']:
            key = component['route'] + ':' + component['method']
            count = coverage.setdefault(key, dict(total_ELU_cases=0, indexed_cases=0,
                not_applicable_cases=0, pending_cases=0, not_applicable_basis=None))
            count['total_ELU_cases'] += 1
            basis = _not_applicable_basis(component, sources)
            if component['index'] is not None:
                count['indexed_cases'] += 1
            elif basis is not None:
                count['not_applicable_cases'] += 1
                count['not_applicable_basis'] = basis
            else:
                count['pending_cases'] += 1
    return dict(schema=SCHEMA, source_input_fingerprint=result['input_fingerprint'], scope=SCOPE,
        method_coverage=coverage, sources=sources, records=records, pending_reason=pending,
        inventory=copy.deepcopy(combos), ignored_ELS_cases=sum(c['limit_state'] == 'ELS' for c in combos),
        legacy_denominators_replaced=False, whole_member_approved=False,
        resistance_lengths=lengths, physical_span_mm=data['L_mm'])


def attach(result):
    if not _eligible(result['input_data']):
        return result
    out = copy.deepcopy(result)
    out[FIELD] = _build(result)
    return out


def preserved(result):
    """Replay analytic sources, inventory, actions and extrema, never eigen solve."""
    saved = result.get(FIELD)
    if saved is None:
        return None
    if not _eligible(result['input_data']) or saved != _build(result):
        raise ValueError('NBR família: componentes, fontes, ações, casos ou aritmética divergentes; recalcule explicitamente.')
    return copy.deepcopy(saved)
