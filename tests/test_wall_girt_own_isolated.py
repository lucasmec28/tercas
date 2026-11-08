import copy
import pytest
from tercas import ue_catalog_reference as own, wall_girt_isolated as girt
from tercas import direct_self_weight as pp, deflection_scope
from tercas.application import defaults,build_spec
from tercas.core.especificacao_unica import evaluate
from tercas.pierin_ue_registry import new_study_indices


def data(index=0,mode='direct'):
    d=pp.activate(defaults(index));d.update(member_application='wall_girt',load_mode=mode,
        q_sls=.001,P_sls=1.,q_uls=.002,P_uls=2.)
    d=deflection_scope.activate(own.activate(d));d['torsion_model']=girt.choice()
    for role in ('EXTERNAL','P','CP','V_Cima','V_Baixo'):
        d['torsion_model']['load_lines'][role]=dict(declared=True,xy_from_CG_mm=[3.,7.],origin='Synthetic declared point; not facade geometry')
    return d


def test_complete_family_local_els_and_identity():
    counts={'MSE':0,'MLE':0}
    for i in new_study_indices():
        d=data(i);before=copy.deepcopy(d);spec=build_spec(d);r=evaluate(spec)
        assert own.source_binding(d)['schema']==own.GIRT_SCHEMA
        assert spec['route_domain'] is None
        assert r['ELS']['status']=='computed_bending_component'
        counts['MLE' if 'service_mle_evidence' in r['ELS'] else 'MSE']+=1
        assert spec['SLS']['q_Nmm']==d['q_sls']
        trace=pp.evidence(d)
        assert trace['states']['sls']['profile_PP_q_N_mm']['normal']==0.
        assert trace['states']['sls']['profile_PP_q_N_mm']['parallel']==pytest.approx(d['properties']['mass_kg_m']*.00980665)
        assert d==before
    assert counts=={'MSE':62,'MLE':4}


def test_application_change_requires_new_adoption_and_history():
    from test_ue_catalog_recovery import inputs
    old=inputs();d=copy.deepcopy(old);d['member_application']='wall_girt'
    with pytest.raises(ValueError):own.validate(d)
    fresh=own.activate(d)
    assert own.validate(fresh)
    assert fresh['roof_top_load']==old['roof_top_load']
    fresh['member_application']='purlin'
    with pytest.raises(ValueError):own.validate(fresh)


def test_lines_required_not_inherited_and_no_network():
    from tercas.torsion_study import blank_choice
    d=data();cg=own.section_for(d)['properties']['centroid_xy_mm']
    d['torsion_model']=blank_choice()
    with pytest.raises(ValueError,match='não se transferem'):girt.points(d,cg)
    d=data();d['torsion_model']['load_lines']['P']['declared']=False
    with pytest.raises(ValueError,match='P'):girt.points(d,cg)
    d=data();d['three_girt_model']={'enabled':True}
    with pytest.raises(ValueError,match='rede'):own.validate(d)


def test_direct_force_positions_pp_once_and_moment_arm():
    from tercas.direct_roof_separated import combinations
    from tercas.direct_torsion import actions
    d=data();d['torsion_model']['load_lines']['P']['xy_from_CG_mm']=[-5.,11.]
    geo=girt.geometry(d);cg=geo['CG_xy_mm'];c=combinations(d)[0];a=actions(c,geo)
    by={x['name']:x for x in a}
    assert by['PP']['application_xy_mm']==cg
    assert by['EXTERNAL']['application_xy_mm']==[cg[0]+3.,cg[1]+7.]
    assert by['P']['application_xy_mm']==[cg[0]-5.,cg[1]+11.]
    assert by['PP']['q_xy_N_mm'][1]==0
    assert by['P']['force_xy_N']==[0.,-d['P_uls']]
    assert sum(x['q_xy_N_mm'][0] for x in a if x['kind']=='uniform')==c['q_vector']['parallel']


def test_torque_independent_cross_product_in_mouth_down_frame():
    from tercas.direct_roof_separated import combinations
    from tercas.direct_torsion import actions
    d=data();geo=girt.geometry(d);sc=geo['SC_xy_mm'];cg=geo['CG_xy_mm']
    a={a['name']:a for a in actions(combinations(d)[0],geo)}
    def cross(action):
        x,y=action['application_xy_mm'];fx,fy=action.get('q_xy_N_mm',action.get('force_xy_N'))
        return (x-sc[0])*fy-(y-sc[1])*fx
    assert cg[1]==pytest.approx(sc[1],abs=1e-10)
    assert cross(a['PP'])==pytest.approx(0.,abs=1e-10)
    assert cross(a['EXTERNAL'])==pytest.approx(-(cg[0]+3.-sc[0])*d['q_uls'])
    assert abs(cross(a['EXTERNAL']))>1e-5


@pytest.mark.parametrize('mode',['direct','area'])
def test_fresh_solver_EN_and_saved_replay(mode):
    from tercas.application import calculate
    from tercas.batch import calculate_batch
    from tercas.study_completion import complete_result
    from tercas import isolated_en_ue_family_application as en
    from tercas.aisi_torsion_component import FIELD as AISI
    d=data(26,mode);d=en.activate(d,model_origin='Synthetic intact girt; no physical approval')
    r=complete_result(calculate(d) if mode=='direct' else calculate_batch(d))
    assert r['torsion_evidence']['computed_cases']>0
    assert r[AISI]['G81_computed_cases']>0
    assert r[en.FIELD]['stress_computed_cases']>0,r[en.FIELD]['records']
    assert all(x['status']!='pending' for x in r[en.FIELD]['records'])
    assert en.preserved(r) is not None
    assert own.preserved(r) is not None
    assert not r['whole_member_approved']
    import json
    saved=json.loads(json.dumps(r));assert en.preserved(saved)
    # Exact saved load coordinates cannot be moved by rehashing declarations.
    bad=copy.deepcopy(saved)
    bad['input_data']['torsion_model']['load_lines']['P' if mode=='direct' else 'CP']['xy_from_CG_mm'][0]+=1
    with pytest.raises(ValueError):en.preserved(bad)


@pytest.mark.parametrize('mode',['direct','area'])
def test_authenticated_per_action_heights_for_strength_consumers(mode):
    from tercas.direct_roof_separated import combinations
    from tercas.batch import area_bundle
    d=data(26,mode);b=area_bundle(d) if mode=='area' else None
    c=next(x for x in (b['combinations'] if b else combinations(d)) if x['limit_state']=='ELU')
    a=girt.height_actions(d,b,c);s=own.section_for(d);cg=s['properties']['centroid_xy_mm'];sc=s['properties']['shear_center_xy_mm']
    assert girt.height_model_adopted(d)
    for row in a:
        if row['name']=='PP':
            assert row['q_down_N_mm']==0
            assert row['height_above_SC_mm']==pytest.approx(0.,abs=1e-10)
            assert row['x_from_SC_mm']==cg[0]-sc[0]
        else:
            assert row['height_above_SC_mm']==cg[1]+7.-sc[1]
            assert row['x_from_SC_mm']==cg[0]+3.-sc[0]
    bad=copy.deepcopy(c);bad['q_vector']['normal']+=1
    with pytest.raises(ValueError,match='divergente'):girt.height_actions(d,b,bad)
    for record in d['torsion_model']['load_lines'].values():record['declared']=False
    for row in girt.height_actions(d,b,c):
        if row['name']!='PP':assert row['height_above_SC_mm'] is None and row['x_from_SC_mm'] is None


def test_legacy_girt_PP_text_and_basis_not_reinterpreted():
    from tercas.direct_roof_separated import combinations,BASIS
    old=pp.activate(defaults(26));old['member_application']='wall_girt'
    assert pp.evidence(old)['scope']==pp.TEXT
    assert pp.evidence(old)['external_application']=='selected_top_load_line'
    assert all(c['load_basis']==BASIS for c in combinations(old))
    fresh=data(26)
    assert pp.evidence(fresh)['external_application']=='declared_local_action_lines'
    assert all(c['load_basis']=='direct_external_declared_lines_profile_PP_CG' for c in combinations(fresh))


def test_girt_source_adoption_preserves_restorable_history():
    from tercas.ue_catalog_ui import preserve_then_load
    from tercas.pierin_ue_registry_ui import HISTORY,restore
    original=defaults(26);old_result={'immutable_old_study':'sentinel'}
    state={'base':copy.deepcopy(original),'last_input':copy.deepcopy(original),'result':copy.deepcopy(old_result)}
    def load(new):
        state['base']=copy.deepcopy(new);state['last_input']=copy.deepcopy(new);state.pop('result',None)
    preserve_then_load(state,data(26),load)
    assert state[HISTORY][0]['result']==old_result
    assert state[HISTORY][0]['last_input']==original
    restore(state,0)
    assert state['result']==old_result and state['last_input']==original
