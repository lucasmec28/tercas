"""Direct external actions plus known profile PP, without inventing decomposition.

The versioned PP adapter owns magnitudes. This module only assigns its existing
vectors to CG/top and invokes the existing Vlasov and AISI component solvers.
Legacy totals and a merely stored manual torsion choice never enter this route.
"""
import copy
import math

from . import direct_roof_separated as direct
from . import direct_self_weight as pp
from .torsion_vlasov.vlasov import METHOD, solve_member, NumericalQualificationError


POINT_SCOPE = 'Fixed user-supplied interior P position; not a->0+ or moving-load envelope'


def active(data):
    from .roof_top_load import enabled
    from .wall_girt_isolated import active as girt_active
    from .torsion_study import configuration
    from .load_application_policy import active as ct_active
    if ct_active(data):return pp.active(data)
    if girt_active(data):
        c=configuration(data)
        return bool(pp.active(data) and c and c['enabled'])
    return (pp.active(data) and data.get('member_application', 'purlin') == 'purlin'
            and enabled(data))


def actions(combo, geometry):
    """Keep both force components, even when their totals cancel."""
    if not geometry['coherent_torsion_section']:
        raise ValueError('Contorno torsional próprio necessário; não se presume excentricidade nula.')
    cg = geometry['CG_xy_mm']
    top = [cg[0] + geometry['x_from_CG_mm'], cg[1] + geometry['y_from_CG_mm']]
    out = []
    for name, vector, point in [('EXTERNAL', combo['external_q_vector'], False),
                                ('PP', combo['profile_PP_q_vector'], False),
                                ('P', combo['P_vector'], True)]:
        force = [vector['parallel'], -vector['normal']]
        if not any(force):
            continue
        a = dict(name=name, kind='point' if point else 'uniform',
                 application_xy_mm=list(geometry['declared_lines'][name] if 'declared_lines' in geometry else cg if name == 'PP' else top),
                 origin='PP separado no CG, incluído uma vez' if name == 'PP' else
                        ('Ação direta externa na linha local declarada da travessa, sem nova rotação' if 'declared_lines' in geometry else 'Ação direta externa na linha superior selecionada, sem nova rotação'))
        if geometry.get('load_application_policy'):
            a.update(application_xy_mm=list(geometry['SC_xy_mm']),origin=geometry['source'])
        if point:
            a.update(force_xy_N=force, couple_Nmm=0., s_mm=combo['x_mm'], existing_point_position='fixed')
        else:
            a.update(q_xy_N_mm=force, couple_N=0.)
        out.append(a)
    for i, axis in enumerate(('parallel', 'normal')):
        total = math.fsum(a['q_xy_N_mm'][i] for a in out if a['kind'] == 'uniform')
        expected = combo['q_vector'][axis] * (1. if i == 0 else -1.)
        if not math.isclose(total, expected, rel_tol=2e-12, abs_tol=1e-12):
            raise ValueError('Forças diretas não correspondem ao total combinado; não duplicar PP.')
    return out


def attach(result, choice):
    from .application import fingerprint
    from .roof_top_load import geometry
    from .torsion_study import section_for, scope_for, configuration
    from .torsion_vlasov.adapter import summarize_torsion_evidence
    from .aisi_torsion_component import attach_dense
    data = result['input_data']
    SCOPE=scope_for(data)
    from .ue_catalog_reference import claims_reference as catalog_claims, attach_resistance
    if (result.get('schema') != 'NBR14762_one_span_v1' or not active(data)
            or fingerprint(data) != result.get('input_fingerprint')):
        raise ValueError('Contrato direto separado incompatível com o resultado atual.')
    trace = pp.evidence(data)
    if trace != result.get('direct_self_weight_evidence'):
        raise ValueError('Peso próprio direto salvo divergente; recalcule explicitamente.')
    section = section_for(data)
    from .model_domain import evidence as model_evidence
    if model_evidence(data)['conflict']:
        raise ValueError(model_evidence(data)['conflict'])
    p = data['properties']; sp = section['properties']
    for key, value in [('A_mm2', p['A_cm2']*100), ('Ix_strong_mm4', p['Ix_cm4']*10000),
                       ('Iy_weak_mm4', p['Iy_cm4']*10000), ('J_mm4', p['J_mm4']), ('Cw_mm6', p['Cw_mm6'])]:
        if not math.isclose(sp[key], value, rel_tol=2e-12, abs_tol=1e-9):
            raise ValueError('Seção direta e contorno torsional divergentes: '+key)
    if (not catalog_claims(data) and not 3000 <= data['L_mm'] <= 6000) or p['t'] != section['thickness_mm']:
        raise ValueError('Espessura/vão fora do contorno próprio de torção.')
    from .wall_girt_isolated import active as girt_active, geometry as girt_geometry
    from .load_application_policy import active as ct_active, geometry as ct_geometry
    girt = girt_active(data) or (ct_active(data) and data.get('member_application')=='wall_girt')
    geo = ct_geometry(data) if ct_active(data) else girt_geometry(data) if girt else geometry(data)
    from .load_application_policy import active as ct_active, MODE as CT_MODE, lines as ct_lines
    ct=ct_active(data)
    supports = {side: dict(twist='fixed', warping='free_assumed', origin=
        'Hipótese R01: garfo ideal com empenamento livre; não comprova ligação real.')
        for side in ('left', 'right')}
    records = []
    for combo in direct.combinations(data):
        base = dict(combination_id=combo['id'], limit_state=combo['limit_state'], method=METHOD,
            coverage_complete=False, resistance_qualified=False, whole_member_approved=False,
            source_input_fingerprint=result['input_fingerprint'])
        try:
            analysis = solve_member(section=section, length_mm=data['L_mm'],
                E_MPa=data['properties']['E_MPa'], G_MPa=data['properties']['G_MPa'],
                actions=actions(combo, geo), supports=supports, combination_id=combo['id'],
                limit_state=combo['limit_state'], member_id='WALL_GIRT' if girt else 'PURLIN', elements_per_interval=32,
                action_accounting_origin=('Versioned direct external actions + PP once; supplied ELU/ELS factors preserved' if ct else 'Versioned direct external actions + PP once at CG; supplied ELU/ELS factors preserved'))
        except NumericalQualificationError as exc:
            records.append(dict(base, status='pending_numerical_qualification', missing=[str(exc)],
                                analysis=None, numerical_diagnostics=copy.deepcopy(exc.diagnostics)))
            continue
        analysis['analysis_domain']['point_position_scope'] = POINT_SCOPE
        records.append(dict(base, status='elastic_demand_computed', missing=analysis['missing'], analysis=analysis))
    out = copy.deepcopy(result)
    out['torsion_evidence'] = dict(schema='purlin_torsion_batch_evidence_v1', method=METHOD,
        source_input_fingerprint=result['input_fingerprint'], supports=supports, records=records,
        load_lines=dict(PP=dict(application_xy_mm=geo['CG_xy_mm']),
                        EXTERNAL=dict(xy_from_CG_mm=[geo['x_from_CG_mm'], geo['y_from_CG_mm']]),
                        P=dict(xy_from_CG_mm=[geo['x_from_CG_mm'], geo['y_from_CG_mm']])),
        computed_cases=sum(r['status']=='elastic_demand_computed' for r in records),
        pending_model_cases=0,
        pending_numerical_cases=sum(r['status']=='pending_numerical_qualification' for r in records),
        direct_load_basis=direct.BASIS, direct_self_weight=trace,
        source_combinations=direct.combinations(data), source_preserved=True,
        coverage_complete=False, whole_member_approved=False, resistance_qualified=False,
        scope=SCOPE, app_axis_mapping='physical q=[parallel,-normal]; Mforte_R01=-Mx_physical; Mfraco_R01=-My_physical')
    if girt:
        out['torsion_evidence']['load_lines']=copy.deepcopy(choice['load_lines'])
        out['torsion_evidence']['load_lines']['PP']={'application_xy_mm':list(geo['CG_xy_mm'])}
        out['torsion_evidence']['direct_load_basis']='direct_external_declared_lines_profile_PP_CG'
    if ct:
        from .load_application_policy import DIRECT_BASIS
        out['torsion_evidence']['direct_load_basis']=DIRECT_BASIS
        out['torsion_evidence']['load_application_policy']=CT_MODE
        out['torsion_evidence']['load_lines']=ct_lines(section,('PP','EXTERNAL','P'))
    out = attach_resistance(out, section) if catalog_claims(data) else attach_dense(out, section)
    from .isolated_en_application import attach_dense as attach_EN_dense
    out = attach_EN_dense(out, section)
    from .isolated_service_component import attach_dense as attach_service_dense
    out = attach_service_dense(out, section)
    out['torsion_evidence'] = summarize_torsion_evidence(out['torsion_evidence'])
    out['torsion_evidence'].update(choice_snapshot=copy.deepcopy(choice), scope_pt=SCOPE,
        load_line_choice_source='automatic_selected_roof_scheme_direct_separated',
        stored_manual_choice_preserved=configuration(data))
    if girt:
        out['torsion_evidence']['load_line_choice_source']='explicit_wall_girt_local_lines'
    if ct:out['torsion_evidence']['load_line_choice_source']='versioned_applied_load_model'
    out['whole_member_approved'] = False
    return out
