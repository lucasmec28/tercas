"""Fresh-only NBR components, bound to complete ELU actions and analytic replay.
No global verdict, denominator replacement, eigenproblem or historical migration.
"""
import copy
import math
from . import nbr_ue_family as provider
from . import roof_top_load as roof

FIELD = 'nbr_ue_family_application'
SCHEMA = 'nbr_ue_family_application_v3_rp23_candidate'
SCOPE = ('Componentes de flexão NBR, não aprovação resistente/global. Contorno próprio e '
         'referência nominal publicada são alternativas distintas; índices não são somados. '
         'Interação biaxial N=0 usa capacidades próprias concomitantes e qualificadas por sinal. '
         'Torção/bimomento, cortante e ELS combinado permanecem separados. Sem rigidez da telha.')


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
    from .nbr_family_biaxial import demand
    return demand(combo,L,axis,sign)


def _component(route, name, branch, demand, *, applicable=True, reason=None, approximate=False):
    cap = branch.get('MRd_Nmm')
    usable = branch.get('eligible') is True and isinstance(cap, (float, int)) and not isinstance(cap, bool) and math.isfinite(cap) and cap > 0
    from fractions import Fraction
    from .nbr_family_biaxial import _bound
    index = _bound(Fraction(demand['Msd_exact'])/Fraction(cap),True) if usable and applicable else None
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
        from .nbr_ue_shear_lag import assess as shear_lag_assess, MEMBER_MODEL
        shear_lag=shear_lag_assess(physical_span_mm=data['L_mm'],
            external_dimensions_mm=own['source_binding']['nominal_identity']['dimensions_mm'],
            actions=acts,member_model=MEMBER_MODEL)
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
        from .flt_height_effective import qualify_family, COMBINED_METHODS
        height = qualify_family(data, acts)
        height_capacity = dict(eligible=False,status='outside_documented_height_reference',reason=height['reason'])
        if height['elastic_reference_eligible']:
            binding=height['source_binding'];material=own['source_binding']['material']
            if (binding['nodes_sha256']!=own['source_binding']['nodes_sha256']
                or binding['material']!={k:material[k] for k in ('E_MPa','G_MPa','fy_MPa')}):
                raise ValueError('Altura FLT e resistência NBR pertencem a seções/materiais diferentes.')
            from .nbr_ue_family_expansion import OutsideMethod as ExpandedOutsideMethod
            try:
                height_capacity=provider.strong_capacity_at_me(data['catalog_index'],material=material,Me_Nmm=height['Me_Nmm'])
            except (provider.OutsideMethod,ExpandedOutsideMethod) as exc:
                height_capacity=dict(eligible=False,status='outside_height_resistance_method',reason=str(exc),MRd_Nmm=None)
            else:
                height_capacity.update(status=('computed_full_span_numerical_height_NBR_reference'
                    if height['method'] in COMBINED_METHODS else 'computed_documentary_height_NBR_reference'),reason=height['reason'])
        parts.append(_component('own_rounded_contour','FLT_height_effective_reference',height_capacity,strong,approximate=True))
        distortional_floor=None
        conventional_distortion=own['strong']['distortional']
        unresolved_Lcr=conventional_distortion.get('elastic_reference',{}).get('Lcrd_mm')
        if (not conventional_distortion['eligible'] and type(unresolved_Lcr) in (int,float)
                and math.isfinite(unresolved_Lcr) and data['L_mm']<unresolved_Lcr):
            from .nbr_ue_strong_distortional_floor import assess as assess_distortional_floor
            try:
                distortional_floor=assess_distortional_floor(data['catalog_index'],
                    material=own['source_binding']['material'],Msd_Nmm=strong['Msd_Nmm'])
            except provider.OutsideMethod as exc:
                distortional_floor=dict(eligible=False,MRd_lower_bound_Nmm=None,
                    status='outside_distortional_floor_method',scope=str(exc),snapshot_sha256=None)
            if distortional_floor['eligible'] and distortional_floor['source_binding']!=own['source_binding']:
                raise ValueError('Piso distorcional e resistência própria pertencem a fontes diferentes.')
            component=_component('own_rounded_contour','distortional_approximation_floor',
                dict(eligible=distortional_floor['eligible'],MRd_Nmm=distortional_floor['MRd_lower_bound_Nmm'],
                    status=distortional_floor['status'],reason=distortional_floor['scope']),strong,approximate=True)
            if component['index'] is not None:
                component.update(status='sufficient_approximation_floor_index',
                    reference_comparison='sufficient_under_adopted_approximation' if component['index']<=1 else 'inconclusive_floor_exceeded')
            component.update(
                capacity_lower_bound_only=True,capacity_measure='MRd_lower_bound_Nmm',
                floor_source_sha256=distortional_floor['snapshot_sha256'],failure_proven=False,
                physical_resistance_bound=False,floor_exceeded_means='inconclusive_not_failed')
            parts.append(component)
        energy_floor=None
        if not height_capacity.get('eligible') and pos['normal']['classification'] not in ('shear_center','stabilizing'):
            from .flt_height_nbr_floor import qualify_family as qualify_floor
            material=own['source_binding']['material']
            energy_floor=qualify_floor(data,acts,formula_nu=material['nu'],gamma=material['gamma'])
            bound=energy_floor['energy_floor']['source_binding']
            if (bound['nodes_sha256']!=own['source_binding']['nodes_sha256']
                or bound['material']!={k:material[k] for k in ('E_MPa','G_MPa','fy_MPa')}):
                raise ValueError('Piso de energia e resistência pertencem a fontes diferentes.')
            cap=dict(eligible=energy_floor['resistance_floor_eligible'],MRd_Nmm=energy_floor['MRd_lower_bound_Nmm'],
                status=energy_floor['status'],reason=energy_floor['reason'])
            component=_component('own_rounded_contour','FLT_height_energy_floor',cap,strong,approximate=True)
            if component['index'] is not None:
                component['index']=max(component['index'],energy_floor['utilization_upper_bound'])
                component['status']='sufficient_bound_index'
                component['reference_comparison']='sufficient_under_declared_operator' if component['index']<=1 else 'inconclusive_floor_exceeded'
            component.update(capacity_lower_bound_only=True,capacity_measure='MRd_lower_bound_Nmm',
                floor_source_sha256=energy_floor['snapshot_sha256'],failure_proven=False,
                floor_exceeded_means='inconclusive_not_failed')
            parts.append(component)
        for sign, branches in own['weak'].items():
            demand = _demand(combo, data['L_mm'], 'parallel', sign)
            for method in ('local', 'FLT_reference', 'distortional'):
                supported = method != 'FLT_reference' or pos['parallel']['classification'] in ('shear_center', 'stabilizing')
                parts.append(_component('own_rounded_contour', 'weak_' + sign + '_' + method,
                    branches[method], demand, applicable=supported,
                    reason='Posição individual desestabilizante/indeterminada no eixo fraco.' if not supported else None,
                    approximate=branches[method].get('elastic_approximation', False)))
        for component in parts:
            axis=component['demand']['axis'];gate=shear_lag['axes'][axis]
            if component['demand']['Msd_Nmm']>0 and not gate['qualified']:
                component.update(unqualified_diagnostic_index=component['index'],index=None,
                    previous_component_status=component['status'],status='pending_NBR_9_4_applicability',
                    reference_comparison=None,reason=gate['reason']+' Componente pura: '+component['reason'])
        record=dict(combination_id=combo['id'], limit_state='ELU', combination=copy.deepcopy(combo),
            actions=acts, load_position_by_axis=pos, components=parts, height_source=height,
            shear_lag_applicability=shear_lag,
            height_capacity=height_capacity,
            height_energy_floor=energy_floor,
            strong_distortional_floor=distortional_floor,
            weak_negative_complete=own['weak']['negative']['complete_reference_components'], whole_member_approved=False)
        from .nbr_family_member import build as member_interaction
        record['member_interaction']=member_interaction(record,sources,data['L_mm'])
        from .nbr_family_mv import build as build_mv
        record['strong_web_MV']=build_mv(record,sources,data['L_mm'])
        records.append(record)
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
    """Replay sources, inventory and extrema; opted-in mixed loads also replay Ritz."""
    saved = result.get(FIELD)
    if saved is None:
        return None
    if saved.get('schema') == 'nbr_ue_family_application_v1':
        from .nbr_ue_family_application_v1 import preserved as preserved_v1
        return preserved_v1(result)
    if saved.get('schema') == 'nbr_ue_family_application_v2':
        from .nbr_ue_family_application_v2 import preserved as preserved_v2
        return preserved_v2(result)
    if not _eligible(result['input_data']) or saved != _build(result):
        raise ValueError('NBR família: componentes, fontes, ações, casos ou aritmética divergentes; recalcule explicitamente.')
    return copy.deepcopy(saved)
