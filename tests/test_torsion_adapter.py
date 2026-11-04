import copy
import json
from pathlib import Path
import sys

import numpy as np
import pytest

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from tercas.torsion_vlasov.section import load_profile,section_demands
from tercas.torsion_vlasov.adapter import attach_torsion_evidence,active_action_roles,load_lines_from_cg,fingerprint,support_limit_before_point,summarize_torsion_evidence
from tercas.torsion_vlasov.vlasov import solve_member,evaluate
from vlasov_reference import Problem,ExactStateReference


from functools import lru_cache

@lru_cache(maxsize=1)
def _current_snapshot():
    from tercas.ue_family_reference import load_reference, calculate_reference
    return calculate_reference(load_reference(1.5,4000.,5.))

def fixture():
    return copy.deepcopy(_current_snapshot())


def reduced_snapshot(ids):
    r=fixture();r['cases']=[c for c in r['cases'] if c['combination']['id'] in ids]
    r['load_bundle']['combinations']=[c['combination'] for c in r['cases']]
    return r


def section():return load_profile(ROOT/'tercas/data/torsion_profiles/ue100x50x17_t1.50.json')


def supports():return {end:dict(twist='fixed',warping='free_assumed',origin='Frozen R01 ideal fork, not real connection certification') for end in ('left','right')}


def lines(s):
    return load_lines_from_cg(s,{k:dict(declared=True,xy_from_CG_mm=[i*3.,i*2.],origin='Distinct synthetic line for '+k)
        for i,k in enumerate(('CP','SC','V_Cima','V_Baixo','P'))})


def test_nonmutating_adapter_preserves_loads_and_existing_results():
    source=fixture();names=[c['id'] for c in source['load_bundle']['combinations']]
    chosen=[names[0],next(n for n in names if n.endswith('CENTRO')),next(n for n in names if n.endswith('APOIO'))]
    r=reduced_snapshot(chosen);old=copy.deepcopy(r);s=section()
    out=attach_torsion_evidence(r,section=s,load_lines=lines(s),supports=supports(),elements_per_interval=8)
    assert r==old
    evidence=out.pop('torsion_evidence');assert out==old
    assert evidence['computed_cases']==3 and evidence['pending_model_cases']==0
    for record,c in zip(evidence['records'],r['cases']):
        a=record['analysis'];combo=c['combination']
        q=np.sum([l['q_xy_N_mm'] for l in a['loads'] if l['kind']=='uniform'],axis=0)
        np.testing.assert_allclose(q,[combo['q_vector']['parallel'],-combo['q_vector']['normal']],rtol=2e-12,atol=1e-12)
        pp=[l for l in a['loads'] if l['name']=='PP'];assert len(pp)==1
        assert pp[0]['application_xy_mm']==s['properties']['centroid_xy_mm']
        assert not record['coverage_complete'] and not record['resistance_qualified']
        if combo.get('point_position')=='support_limit':
            assert a['support_limit_states'][0]['element_index'] is None
            assert 'before P' in a['support_limit_states'][0]['position_limit']


def test_fibre_signs_agree_with_R01_capacity_senses_before_B():
    s=section();nodes=np.asarray(s['nodes_xy_mm']);cg=s['properties']['centroid_xy_mm']
    top=int(np.argmax(nodes[:,1]));web=int(np.argmin(nodes[:,0]));lip=int(np.argmax(nodes[:,0]))
    strong=section_demands(s,N_N=0,Mx_Nmm=-1e5,My_Nmm=0,Vx_N=0,Vy_N=0,Tsv_Nmm=0,Tw_Nmm=0,B_Nmm2=0)
    weak=section_demands(s,N_N=0,Mx_Nmm=0,My_Nmm=-1e5,Vx_N=0,Vy_N=0,Tsv_Nmm=0,Tw_Nmm=0,B_Nmm2=0)
    def node_stress(r,i):
        if i<len(r['segments']):return r['segments'][i]['sigma_midline_MPa_coeff'][0]
        c=r['segments'][-1]['sigma_midline_MPa_coeff'];return sum(c)
    assert node_stress(strong,top)<0  # compression: positive R01 strong moment
    assert node_stress(weak,web)<0  # compression: positive R01 weak moment
    assert node_stress(weak,lip)>0
    assert nodes[top,1]>cg[1]


def test_missing_external_lines_pending_but_PP_is_not_missing():
    r=fixture();out=attach_torsion_evidence(r,section=section(),load_lines={},supports=supports(),elements_per_interval=4)
    ev=out['torsion_evidence'];assert ev['computed_cases']==0 and ev['pending_model_cases']==len(r['cases'])
    assert all('PP' not in reason for case in ev['records'] for reason in case['missing'])
    assert all(case['analysis'] is None for case in ev['records'])


def test_active_roles_and_explicit_coordinate_conversion():
    s=section();assert active_action_roles(fixture())==['PP','CP','SC','V_Cima','V_Baixo','P']
    raw={'CP':dict(declared=True,xy_from_CG_mm=[0,7],origin='test'),'SC':dict(declared=False)}
    l=load_lines_from_cg(s,raw)
    np.testing.assert_allclose(l['CP']['xy_mm'],np.array(s['properties']['centroid_xy_mm'])+[0,7])
    assert 'SC' not in l
    with pytest.raises(ValueError,match='Self-weight'):load_lines_from_cg(s,{'PP':dict(declared=True,xy_from_CG_mm=[1,0],origin='invalid')})


def test_support_limit_before_P_matches_independent_ODE_limit():
    s=section();L=4000.;E=200000.;G=E/2.6;m=.3;T=5000.;S=G*s['properties']['J_mm4'];D=E*s['properties']['Cw_mm6']
    sc=s['properties']['shear_center_xy_mm']
    r=solve_member(section=s,length_mm=L,E_MPa=E,G_MPa=G,actions=[
        dict(name='q',kind='uniform',q_xy_N_mm=[0,0],couple_N=m,application_xy_mm=sc,origin='synthetic'),
        dict(name='P',kind='point',force_xy_N=[0,0],couple_Nmm=T,s_mm=0,application_xy_mm=sc,origin='a->0+ synthetic limit')],
        supports=supports(),combination_id='LIMIT',limit_state='REFERENCE',member_id='P1',action_accounting_origin='synthetic complete actions',elements_per_interval=64)
    before=support_limit_before_point(r);after=evaluate(r,0,0.)
    assert np.isclose(before['T_Nmm']-after['T_Nmm'],T)
    assert before['B_Nmm2']==after['B_Nmm2'] and before['phi_rad']==after['phi_rad']
    errors=[]
    for a in (1.,.1,.01,.001,.0001):
        o=ExactStateReference(Problem(length=L,S=S,D=D,m0=m,point_actions=((a/L,T,0.),)))
        at=o.at(a/2)
        # Scaled full state converges to before-P; torsional jump is not lost.
        errors.append(max(abs(at['phi']-before['phi_rad']),abs(at['psi']-before['psi_per_mm'])*L,
            abs(at['B']-before['B_Nmm2'])*L*L/D,abs(at['T']-before['T_Nmm'])*L**3/D))
    assert errors[-1]<errors[0]/9000 and errors[-1]<1e-6


@pytest.mark.parametrize('tamper',['fingerprint','property','case','PP','nodes_identity','reference_identity','bundle_length'])
def test_stale_or_mixed_inputs_fail_closed(tamper):
    r=fixture();s=section()
    if tamper=='fingerprint':r['input_fingerprint']='not-current'
    elif tamper=='property':r['input_data']['properties']['Cw_mm6']*=1.01;r['input_fingerprint']=fingerprint(r['input_data'])
    elif tamper=='case':r['cases'][0]['combination']['q_vector']['normal']+=.01
    elif tamper=='PP':r['load_bundle']['case_vectors_N_mm']['PP']['normal']*=1.01
    elif tamper=='bundle_length':r['load_bundle']['L_mm']+=1.
    else:
        r['input_data']['ue_family_sources']['nodes_sha256' if tamper=='nodes_identity' else 'reference_id']='wrong identity'
        r['input_fingerprint']=fingerprint(r['input_data'])
    with pytest.raises(ValueError):attach_torsion_evidence(r,section=s,load_lines=lines(s),supports=supports())


def test_summary_keeps_exact_signed_concomitant_witnesses_and_is_nonmutating():
    r=fixture();names=[c['id'] for c in r['load_bundle']['combinations']]
    r=reduced_snapshot([names[0],next(n for n in names if n.endswith('APOIO'))]);s=section()
    complete=attach_torsion_evidence(r,section=s,load_lines=lines(s),supports=supports(),elements_per_interval=8)['torsion_evidence']
    before=copy.deepcopy(complete);summary=summarize_torsion_evidence(complete)
    assert complete==before
    assert not summary['coverage_complete'] and summary['computed_cases']==2
    for original,compact in zip(complete['records'],summary['records']):
        a=original['analysis'];b=compact['analysis']
        assert b['support_reactions']==a['support_reactions'] and b['numerics']==a['numerics']
        assert 'elements' not in b and 'nodes_xy_mm' not in b['section']
        for field,env in b['field_envelopes'].items():
            vals=[s[field] for s in a['critical_states'] if s.get(field) is not None]
            assert env['minimum']['value']==min(vals) and env['maximum']['value']==max(vals)
            for item in env.values():
                w=b['witnesses'][item['witness_index']]
                source=next(s for s in a['critical_states'] if s['element_id']==w['element_id'] and s['x_mm']==w['x_mm'] and s['u']==w['u'] and s['side']==w['side'] and s.get('position_limit')==w.get('position_limit'))
                assert all(source[k]==v for k,v in w.items()) and item['value']==w[field]
    assert json.loads(json.dumps(summary,allow_nan=False))==summary


def test_pending_numerical_gate_preserves_case_and_compact_status():
    r=fixture();one=next(c for c in r['cases'] if c['combination']['id'].endswith('CENTRO'))
    r=reduced_snapshot([one['combination']['id']]);r['cases'][0]['combination']['x_mm']=.01
    r['cases'][0]['combination']['point_position']='fixed'
    r['load_bundle']['combinations']=[copy.deepcopy(r['cases'][0]['combination'])]
    s=section();out=attach_torsion_evidence(r,section=s,load_lines=lines(s),supports=supports())
    ev=out['torsion_evidence'];assert ev['computed_cases']==0 and ev['pending_numerical_cases']==1
    rec=ev['records'][0];assert rec['status']=='pending_numerical_qualification' and rec['analysis'] is None
    assert 'L/100' in rec['missing'][0]
    assert summarize_torsion_evidence(ev)['records']==ev['records']
