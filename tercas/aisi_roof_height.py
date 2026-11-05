"""AISI-only per-ELU load-height capacities for the existing H4 component.

No NBR resistance or critical moment is consumed. This is a conditional
algebraic component, not proof of physical first-order applicability.
"""
import copy
import json
import math
from . import roof_top_load as roof
from .ltb_load_height import refined
from .aisi_torsion_component import digest,E_AISI,G_AISI,STIFFNESS_FACTOR,h4_state
from .torsion_vlasov.section import finite

SOURCE_PINS={'cd50bf66f299d1c072b5a45016cf2ffca777b390332d3386175c34d53c234931': 'b264cc83c0b3b4ab004218033830b26622fb8b547c65008392d9d6c45993636f', '13c8bf700cce34d8fb2bc607e9ae06c305cc59cd7e0e67234a38fb0218704638': '50224020267eac08c95a25178cd5cbd0fe568b3aca952c14f6be4bad5db57207', 'e30a0bd327deb1523b527a5737a9f14ac8f8fd189c884588c0339ef7c0b80e47': 'f70cb18ffe3fe1cb29dea23b82c13e40ae2094bb2c98b89566ce94105691c62e', '243974742f83ef47937ec56c938718a37b3e037248c4016eddae0d42af062746': 'a215d9e6188c847596f158319e0af2ad197335da34e33dcbce60db53f93b7dfa', 'c3d1e69d48f6ad2980e6779eb2509e42e07a2b957ce71c158095fda6b71a4e00': '27fef63931e61b393bccc285485ce10842f06ddcdfa99e0b7ecb9fae319b0047', '90bf516ec9761304d22aba266bdf9c2f06bf6f73bc6989b46194bbd5d218eab3': '4ee7aede9cc5e255269e3028170890993e2cabc7cdf5d6d1872ff36d274b4f76'}

SCHEMA='aisi2024_current_input_roof_height_g81_h4_v2'
MODEL=('Mcre nominal AISI por combinação, com altura de cada força conservativa; '
       'um vão, garfos ideais e empenamento livre, sem contenção da telha. '
       'Crítico linear de flexão forte; não inclui geometria pré-deformada nem '
       'efeitos geométricos das tensões da torção primária.')
ADEQUACY=('H4 é uma condição algébrica condicional. A adequação física da primeira '
          'ordem para as forças e geometria reais permanece não estabelecida; '
          'índice menor ou igual a 1 não resolve essa questão. O aviso de giro '
          'não é um limite normativo de aceitação. Não se exige um método '
          'não linear universal nem se apaga a torção para obter atendimento.')
INTERPRETATION=('Piso algébrico F2/F3/F4: H4 <= 1 demonstra somente a condição '
                'suficiente no modelo declarado; H4 > 1 é inconclusivo, não '
                'prova de falha pela resistência literal AISI.')


def enabled(data):
    return roof.enabled(data) and data.get('member_application','purlin')=='purlin'


def prepare(result,section):
    """Verify fresh inputs/source once; no eigensolve or demand solve here."""
    from .batch import area_bundle
    from .model_domain import evidence
    from .aisi_research.adapter import verify_bundle,ROOT
    data=result['input_data']
    if not enabled(data):return None
    if data.get('load_mode')!='area' or result.get('schema')!='tercas_batch_results_v1':
        raise ValueError('AISI topo requer ações por área separadas.')
    bundle=area_bundle(data)
    if bundle!=result.get('load_bundle') or bundle['combinations']!=[c['combination'] for c in result['cases']]:
        raise ValueError('Ações/combinações atuais divergentes da fonte AISI topo.')
    ids=[c['id'] for c in bundle['combinations']]
    if len(set(ids))!=len(ids):raise ValueError('Combinações duplicadas.')
    geometry=roof.geometry(data)
    if (not geometry['coherent_torsion_section'] or geometry['nodes_sha256']!=section['nodes_sha256']
            or geometry['section_profile_id']!=section['profile_id']):
        raise ValueError('Geometria da carga e contorno AISI não correspondem.')
    verify_bundle()
    rows=json.loads((ROOT/'inputs'/'elastic_inputs.json').read_text())['profiles']
    strong=next((r for r in rows if r['nodes_sha256']==section['nodes_sha256'] and r['profile_id']==section['profile_id']),None)
    reasons=[]
    if evidence(data)['conflict']:reasons.append(evidence(data)['conflict'])
    if not 3000<=finite(data['L_mm'],'L',True)<=6000:reasons.append('Vão fora de 3000–6000 mm da implementação AISI.')
    if finite(data['properties']['fy_MPa'],'Fy',True)>655:reasons.append('Fy fora do domínio material DSM adotado.')
    if strong is None:reasons.append('Sem críticos fortes AISI rastreados para este contorno (inclui Ue100 t=1,20).')
    source=dict(choice_snapshot=roof.configuration(data),geometry=geometry,
        section={k:copy.deepcopy(section[k]) for k in ('profile_id','nodes_sha256','content_sha256','properties','thickness_mm')},
        strong_source=copy.deepcopy(strong),strong_source_sha256=digest(strong),
        source_load_snapshot_sha256=roof._source_snapshot(result),length_mm=data['L_mm'],
        material=dict(E_MPa=E_AISI,G_MPa=G_AISI,Fy_MPa=data['properties']['fy_MPa']),
        model=MODEL,first_order_model_adequacy='not_established',adequacy_note=ADEQUACY,
        interpretation=INTERPRETATION,weak_load_height_qualified=False,
        geometric_load_height_included_in_nominal_Mcre=True,
        primary_torsion_geometric_stress_included=False,predeformed_geometry_included=False,
        actual_load_line_verified=False,actual_supports_verified=False,
        no_additional_user_inputs=True,global_promotion=False,missing=reasons)
    return dict(source=source,bundle=bundle,section=section,data=data)


def match_actions(elastic,demand,section):
    emap={a['name']:a for a in elastic}
    if len(emap)!=len(elastic) or len(demand)!=len(emap) or set(emap)!={a['name'] for a in demand}:
        raise ValueError('Identidade das ações AISI Mcre/demanda difere.')
    sc=section['properties']['shear_center_xy_mm']
    for d in demand:
        e=emap[d['name']];point=d['kind']=='point'
        if e['kind']!=d['kind']:raise ValueError('Tipo de ação AISI difere.')
        force=e['P_down_N'] if point else e['q_down_N_mm']
        vector=d['force_xy_N'] if point else d['q_xy_N_mm']
        if vector!=[0.,-force]:raise ValueError('Força não uniaxial ou divergente; não apagar componente fraca.')
        if point and e['s_mm']!=d['s_mm']:raise ValueError('Posição P AISI difere.')
        if d['couple_Nmm' if point else 'couple_N']!=0.:raise ValueError('Momento aplicado não contemplado pelo crítico puro.')
        if any(not math.isclose(x,y,rel_tol=1e-12,abs_tol=1e-9) for x,y in zip(d['application_xy_mm'],
                [sc[0]+e['x_from_SC_mm'],sc[1]+e['height_above_SC_mm']])):
            raise ValueError('Linha de aplicação AISI Mcre/demanda difere.')


def capacity_for(context,combo,demand_source):
    """One nominal AISI eigensolve, same ELU/actions as the existing demand."""
    from .aisi_research.aisi_candidate import flexural_floor
    src=context['source'];section=context['section'];p=section['properties']
    actions,parallel=roof._actions(context['bundle'],combo,src['geometry'])
    record=dict(combination_id=combo['id'],combination_sha256=digest(combo),
        source_combination=copy.deepcopy(combo),source_load_snapshot_sha256=src['source_load_snapshot_sha256'],
        actions=actions,actions_sha256=digest(actions),Mcre=None,strong_capacity=None,
        primary_torque_preserved=False,first_order_model_adequacy='not_established',
        whole_member_approved=False,physical_design_approved=False,NBR_capacities_used=False,
        status='pending_AISI_roof_capacity',missing=[])
    if combo['limit_state']!='ELU':raise ValueError('H4 não consome ELS.')
    if parallel:
        record['missing']=['Flexão fraca real em '+', '.join(parallel)+': efeito da linha de carga fora do crítico forte uniaxial. Nenhuma capacidade antiga no CT substitui este caso.']
        return record
    if not actions:
        record.update(status='no_nonzero_actions',missing=['Caso sem ações não nulas: Mcre e H4 não calculados; não se inventa um crítico.'])
        return record
    if src['missing']:record['missing']=copy.deepcopy(src['missing']);return record
    if (demand_source['section']['content_sha256']!=section['content_sha256']
            or demand_source['length_mm']!=src['length_mm']
            or demand_source['combination_id']!=combo['id']):
        raise ValueError('Identidade do membro/combinação AISI topo divergente.')
    if any(demand_source['support_hypotheses'][s]['twist']!='fixed' or
            demand_source['support_hypotheses'][s]['warping']!='free_assumed' for s in ('left','right')):
        raise ValueError('Crítico AISI topo exige garfos livres ao empenamento.')
    match_actions(actions,demand_source['loads'],section)
    try:
        elastic=refined(L_mm=src['length_mm'],E_MPa=E_AISI,G_MPa=G_AISI,
            Iweak_mm4=p['Iy_weak_mm4'],J_mm4=p['J_mm4'],Cw_mm6=p['Cw_mm6'],actions=actions)
    except (ValueError,ArithmeticError) as exc:
        record['missing']=['Crítico AISI topo não qualificado numericamente: '+str(exc)];return record
    record['Mcre']=elastic
    if elastic.get('numerically_converged') is not True or elastic.get('Me_Nmm') is None:
        record['missing']=['Crítico AISI topo indisponível: '+elastic.get('reason',elastic['status'])];return record
    row=src['strong_source'];scale=E_AISI/row['material']['E_MPa']
    try:
        cap=flexural_floor(src['material']['Fy_MPa']*row['exterior_moduli']['Wx_first_yield_mm3'],elastic['Me_Nmm'],
            scale*row['modal_criticals']['strong_local']['value_Nmm'],scale*row['modal_criticals']['strong_distortional']['value_Nmm'])
    except ValueError as exc:record['missing']=[str(exc)];return record
    cap.update(standard='AISI S100-2024',source_profile_id=row['profile_id'],source_nodes_sha256=row['nodes_sha256'],
        source_material=copy.deepcopy(row['material']),elastic_critical_scaling=scale,
        E_MPa=E_AISI,G_MPa=G_AISI,Fy_MPa=src['material']['Fy_MPa'],
        combination_sha256=digest(combo),Cb_applied_after_Mcre=False,NBR_MRd_used=False,
        nominal_Mcre_recalculated=True,holes_absent_assumed=True,
        scope='Conditional algebraic F2/F3/F4 floor at same-combination nominal AISI load-height Mcre')
    record.update(status='conditional_AISI_roof_capacity',strong_capacity=cap,missing=[])
    return record


def check_demand(record,analysis,section):
    """Identity/torque checks, not another demand calculation."""
    if record['strong_capacity'] is None:return
    match_actions(record['actions'],analysis['loads'],section)
    elastic=record['Mcre']
    if analysis['combination_id']!=record['combination_id']:raise ValueError('Combinação AISI não concomitante.')
    moment=max(abs(s['Mx_physical_Nmm']) for s in analysis['critical_states'])
    if not math.isclose(moment,elastic['maximum_reference_moment_Nmm'],rel_tol=1e-9,abs_tol=1e-7):
        raise ValueError('Momento de referência AISI Mcre/demanda diverge.')
    torques={r['name']:r['value'] for r in elastic['primary_torque_by_action']}
    for d in analysis['loads']:
        torque=d['torque_SC_Nmm' if d['kind']=='point' else 'torque_SC_N']
        if not math.isclose(torque,torques[d['name']],rel_tol=1e-12,abs_tol=1e-9):
            raise ValueError('Torque primário AISI não preservado.')
    record['primary_torque_preserved']=True


def validate_saved(result,ev):
    """Only saved identities and scalar consistency, no source/solver/curve call."""
    src=ev.get('roof_height_source')
    if not isinstance(src,dict):raise ValueError('Fonte AISI topo ausente.')
    expected=dict(model=MODEL,first_order_model_adequacy='not_established',adequacy_note=ADEQUACY,
        interpretation=INTERPRETATION,weak_load_height_qualified=False,
        geometric_load_height_included_in_nominal_Mcre=True,primary_torsion_geometric_stress_included=False,
        predeformed_geometry_included=False,actual_load_line_verified=False,actual_supports_verified=False,
        no_additional_user_inputs=True,global_promotion=False)
    if any(src.get(k)!=v for k,v in expected.items()):raise ValueError('Escopo AISI topo alterado.')
    if (src['choice_snapshot']!=roof.configuration(result['input_data']) or not enabled(result['input_data'])
            or src['source_load_snapshot_sha256']!=roof._source_snapshot(result)
            or src['strong_source_sha256']!=digest(src['strong_source'])
            or src['length_mm']!=result['input_data']['L_mm'] or src['material']!=ev['material']
            or ev.get('strong_flexural_capacity') is not None or ev.get('weak_flexural_capacity') is not None
            or ev.get('flexural_capacity_model')!=MODEL or ev.get('strong_capacity_mode')!='per_combination_roof_height'
            or ev.get('geometric_load_height_or_Wagner_effects_included') is not False):
        raise ValueError('Fonte/modelo AISI topo divergente.')
    strong=src['strong_source']
    if strong is not None and SOURCE_PINS.get(strong.get('nodes_sha256'))!=digest(strong):raise ValueError('Fonte forte AISI preservada não confere com a origem protegida.')
    if strong is not None and (strong['profile_id']!=src['section']['profile_id'] or strong['nodes_sha256']!=src['section']['nodes_sha256']):raise ValueError('Contorno da fonte forte AISI divergente.')
    if src['material']['Fy_MPa']!=result['input_data']['properties']['fy_MPa']:raise ValueError('Fy AISI difere da entrada preservada.')
    sp=src['section']['properties'];geometry=src['geometry'];p=result['input_data']['properties']
    if strong is not None and any(sp[k]!=strong['properties'][k] for k in sp):raise ValueError('Propriedades do contorno AISI alteradas.')
    cg=sp['centroid_xy_mm'];sc=sp['shear_center_xy_mm'];x=0. if src['choice_snapshot']['load_line']=='web_midplane' else (p['bf']-p['t'])/2
    expected_geometry=dict(h_mm=p['h'],bf_mm=p['bf'],t_mm=p['t'],height_above_SC_mm=p['h']-p['t']/2-sc[1],
        x_from_CG_mm=x-cg[0],x_from_SC_mm=x-sc[0],y_from_CG_mm=p['h']-p['t']/2-cg[1])
    if (any(not math.isclose(finite(geometry[k],k),v,rel_tol=1e-12,abs_tol=1e-9) for k,v in expected_geometry.items())
            or geometry['CG_xy_mm']!=cg or geometry['SC_xy_mm']!=sc
            or geometry['load_line']!=src['choice_snapshot']['load_line']
            or geometry['nodes_sha256']!=src['section']['nodes_sha256']
            or geometry['physical_load_line_verified'] is not False):raise ValueError('Geometria da linha AISI alterada.')
    g=ev['bimoment_capacity']
    if (g['Ba_Nmm2']!=.9*g['By_Nmm2'] or g['By_Nmm2']!=g['Fy_MPa']*g['Cw_mm6']/g['omega_max_mm2']
            or g['Fy_MPa']!=src['material']['Fy_MPa'] or g['Cw_mm6']!=src['section']['properties']['Cw_mm6']
            or g['section_content_sha256']!=src['section']['content_sha256']):
        raise ValueError('Capacidade G8.1 salva alterada.')
    combos=[c['combination'] for c in result['cases'] if c['combination']['limit_state']=='ELU']
    if [r['combination_id'] for r in ev['records']]!=[c['id'] for c in combos]:raise ValueError('Inventário ELU AISI topo divergente.')
    torsion={r['combination_id']:r for r in result['torsion_evidence']['records']}
    for r,c in zip(ev['records'],combos):
        h=r.get('roof_height');a=r.get('AISI_analysis');cap=h.get('strong_capacity') if isinstance(h,dict) else None
        if not a:
            if r.get('H4') is not None:raise ValueError('H4 sem demanda AISI.')
            continue
        if not isinstance(h,dict):raise ValueError('Capacidade AISI por combinação ausente.')
        if (h['combination_id']!=c['id'] or h['source_combination']!=c or h['combination_sha256']!=digest(c)
                or h['source_load_snapshot_sha256']!=src['source_load_snapshot_sha256']
                or h['actions_sha256']!=digest(h['actions']) or h['first_order_model_adequacy']!='not_established'
                or any(h.get(k) is not False for k in ('whole_member_approved','physical_design_approved','NBR_capacities_used'))):
            raise ValueError('Pareamento/escopo AISI topo alterado.')
        expected_actions,parallel=roof._actions(result['load_bundle'],c,src['geometry'])
        if h['actions']!=expected_actions:raise ValueError('Ações preservadas do crítico AISI divergentes das combinações.')
        if parallel and r.get('H4') is not None:raise ValueError('H4 biaxial fora do domínio de altura AISI.')
        original=torsion[c['id']]['analysis']
        if (a['source_combination']!=c or a['source_actions_sha256']!=digest(original['loads'])
                or a['actions']!=original['loads'] or a['support_hypotheses']!=original['support_hypotheses']
                or a['E_MPa']!=STIFFNESS_FACTOR*E_AISI or a['G_MPa']!=STIFFNESS_FACTOR*G_AISI
                or a['analysis_order']!=1 or a['axial_force_N']!=0.
                or original['section']['nodes_sha256']!=src['section']['nodes_sha256']):
            raise ValueError('Demanda/fonte AISI topo alterada.')
        giro=finite(a['max_abs_phi_rad'],'giro máximo AISI')
        witness=a['max_abs_phi_witness'];warn=a['numerics']['rotation_warning_rad']
        if (giro<0 or abs(witness['phi_rad'])!=giro or witness['combination_id']!=c['id']
                or r['first_order_small_rotation_warning']!=(giro>warn)
                or a['numerics']['rotation_warning_is_normative_limit'] is not False):
            raise ValueError('Diagnóstico de giro AISI alterado.')
        g=r['G81'];ba=ev['bimoment_capacity']['Ba_Nmm2']
        if g and (g['Ba_Nmm2']!=ba or g['ratio']!=abs(g['B_Nmm2'])/ba or g['threshold']!=1.
                or g['component_condition']!=(g['ratio']<=1.) or g['material_product_applicability_verified'] is not False):
            raise ValueError('Índice G8.1 salvo alterado.')
        if cap:
            m=h['Mcre'];strong=src['strong_source']
            if (not isinstance(m,dict) or m.get('numerically_converged') is not True
                    or cap['combination_sha256']!=digest(c) or cap['phi_b']!=.9
                    or cap['E_MPa']!=E_AISI or cap['G_MPa']!=G_AISI or cap['Fy_MPa']!=src['material']['Fy_MPa']
                    or cap['source_nodes_sha256']!=strong['nodes_sha256'] or cap['source_profile_id']!=strong['profile_id']
                    or cap['Mcre_Nmm']!=m['Me_Nmm'] or cap['NBR_MRd_used'] is not False
                    or cap['source_material']!=strong['material']
                    or cap['elastic_critical_scaling']!=E_AISI/strong['material']['E_MPa']
                    or cap['My_Nmm']!=src['material']['Fy_MPa']*strong['exterior_moduli']['Wx_first_yield_mm3']
                    or cap['Mcrl_Nmm']!=cap['elastic_critical_scaling']*strong['modal_criticals']['strong_local']['value_Nmm']
                    or cap['Mcrd_Nmm']!=cap['elastic_critical_scaling']*strong['modal_criticals']['strong_distortional']['value_Nmm']
                    or cap['Cb_applied_after_Mcre'] is not False or h['primary_torque_preserved'] is not True):
                raise ValueError('Capacidade/material AISI topo alterado.')
            if any(m.get(k) is not False for k in ('primary_torsion_resistance_included','primary_torsion_predeformation_included','local_distortional_modes_included','geometry_hypotheses_verified','whole_member_approved','production_resistance_authorized','ritz_eigenvalue_is_safe_lower_bound','convergence_is_error_bound')):
                raise ValueError('Qualificação do crítico AISI alterada.')
            for k in ('My_Nmm','Mcre_Nmm','Mcrl_Nmm','Mcrd_Nmm','Mne_floor_Nmm','Mnl_floor_Nmm','Mnd_floor_Nmm','Mn_floor_Nmm','Ma_floor_Nmm'):finite(cap[k],k,True)
            if cap['Mn_floor_Nmm']!=min(cap[k] for k in ('Mne_floor_Nmm','Mnl_floor_Nmm','Mnd_floor_Nmm')) or cap['Ma_floor_Nmm']!=.9*cap['Mn_floor_Nmm']:
                raise ValueError('Piso/fator AISI divergente.')
            my=cap['My_Nmm'];cre=cap['Mcre_Nmm']
            ne=my*(1-.25*my/cre) if cre>.5*my else cre
            if (cap['Mne_floor_Nmm']!=ne or cap['Mnl_floor_Nmm']!=ne/(1+.55*ne/cap['Mcrl_Nmm'])
                    or cap['Mnd_floor_Nmm']!=my/(1+.60*my/cap['Mcrd_Nmm']) or cap['beta']!=1.):
                raise ValueError('Relações algébricas do piso AISI alteradas.')
            match_actions(h['actions'],a['actions'],src['section'])
            torques={x['name']:x['value'] for x in m['primary_torque_by_action']}
            if any(not math.isclose(d['torque_SC_Nmm' if d['kind']=='point' else 'torque_SC_N'],torques[d['name']],rel_tol=1e-12,abs_tol=1e-9) for d in a['actions']):
                raise ValueError('Torque salvo AISI divergente.')
        interaction=r.get('H4')
        if interaction and (cap is None or h['status']!='conditional_AISI_roof_capacity' or h['missing'] or r['missing']):
            raise ValueError('H4 não pode ser emitido com crítico/capacidade pendente.')
        if interaction:
            w=interaction['witness']
            if (w['combination_id']!=c['id'] or w['limit_state']!='ELU' or w['My_physical_Nmm']!=0.
                    or not 0<=finite(w['x_mm'],'x H4')<=src['length_mm']
                    or interaction.get('interpretation')!=INTERPRETATION):raise ValueError('H4 salvo fora do recorte uniaxial.')
            check=h4_state(w,Max_Nmm=cap['Ma_floor_Nmm'] if cap else None,May_Nmm=None,Ba_Nmm2=ev['bimoment_capacity']['Ba_Nmm2'])
            if any(interaction[k]!=check[k] for k in ('terms','ratio','threshold','concomitant','N_N')) or interaction['algebraic_sufficient_condition']!=(check['ratio']<=1.):
                raise ValueError('Índice H4 salvo divergente.')
    if ev['H4_computed_cases']!=sum(r['H4'] is not None for r in ev['records']) or ev['G81_computed_cases']!=sum(r['G81'] is not None for r in ev['records']) or ev['pending_cases']!=sum(r['H4'] is None for r in ev['records']):
        raise ValueError('Contagem AISI topo divergente.')
