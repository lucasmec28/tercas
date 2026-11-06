"""Independent stress sampling versus conservative whole-field EN bounds."""
import copy
import json
import math
from pathlib import Path

import numpy as np
import pytest

from tercas.isolated_en_stress import check_member
from tercas.torsion_vlasov.section import from_frozen_profile
from tercas.torsion_vlasov.vlasov import solve_member, evaluate
from tercas.three_girt_en_normal.en1993_normal_components import build_component_sections

ROOT=Path(__file__).resolve().parents[1]


def make(t=2., scale=1., *, pure_torsion=False, reversal=False):
    p=json.loads((ROOT/f'tercas/data/torsion_profiles/ue100x50x17_t{t:.2f}.json').read_text())
    s=from_frozen_profile(p)
    actions=[dict(name='q',kind='uniform',q_xy_N_mm=[scale*.025,scale*-.15],
        couple_N=scale*.7,application_xy_mm=[0.,99.],origin='synthetic test'),
        dict(name='P',kind='point',force_xy_N=[scale*30.,scale*(500 if reversal else -60.)],
        couple_Nmm=scale*400.,application_xy_mm=[24.,99.],s_mm=1700.,origin='synthetic test')]
    if pure_torsion:
        for a in actions:a['q_xy_N_mm' if a['kind']=='uniform' else 'force_xy_N']=[0.,0.]
    r=solve_member(section=s,length_mm=4000.,E_MPa=200000.,G_MPa=200000./2.6,
        actions=actions,supports={side:dict(twist='fixed',warping='free_assumed',origin='synthetic test')
            for side in ('left','right')},combination_id='QA_ELU',limit_state='ELU',member_id='P1',
        action_accounting_origin='synthetic complete test',elements_per_interval=8)
    return p,r


def check(p,r,**kw):
    return check_member(r,p,intact_section_model_declared=True,model_origin='Synthetic intact nominal section',**kw)


def sample_independent(p,r):
    """Direct formula at actual concomitant states; no production bound helpers."""
    c=build_component_sections(p);s=r['section'];pr=s['properties'];th=s['thickness_mm']
    xy=np.asarray(s['nodes_xy_mm'])-pr['centroid_xy_mm'];d=np.diff(xy,axis=0)
    n=np.column_stack([-d[:,1],d[:,0]])/np.linalg.norm(d,axis=1)[:,None]
    om=np.asarray(s['omega_nodes_mm2']);stat=np.asarray(s['segment_static_coefficients'])
    maxima=dict(normal=0.,shear=0.,interaction=0.)
    for e in range(len(r['elements'])):
        for x in (0.,.137,.5,.883,1.):
            st=evaluate(r,e,x);mx=st['Mx_physical_Nmm'];my=st['My_physical_Nmm']
            cx=np.asarray(c['components']['Mx_positive' if mx>=0 else 'Mx_negative']['sigma_coefficients_c0_cx_cy'])
            cy=np.asarray(c['components']['My_positive' if my>=0 else 'My_negative']['sigma_coefficients_c0_cx_cy'])
            for u in (0.,.27,.5,.79,1.):
                pos=xy[:-1]+u*d;omega=om[:-1]+u*np.diff(om)
                primitive=stat[:,:,0]+u*stat[:,:,1]+u*u*stat[:,:,2]
                flow=-(st['Vx_N']*primitive[:,0]/pr['Iy_weak_mm4']
                    +st['Vy_N']*primitive[:,1]/pr['Ix_strong_mm4']
                    +st['Tw_Nmm']*primitive[:,2]/pr['Cw_mm6'])/th
                for face in (-1,1):
                    ext=pos+face*th/2*n
                    sigma=mx*(cx[0]+ext@cx[1:])+my*(cy[0]+ext@cy[1:])+st['B_Nmm2']*omega/pr['Cw_mm6']
                    tau=flow-face*st['Tsv_Nmm']*th/pr['J_mm4']
                    vals=dict(normal=np.max(abs(sigma))/250.,shear=np.max(abs(tau))/(250/math.sqrt(3)),
                        interaction=np.max(np.sqrt(sigma*sigma+3*tau*tau))/275.)
                    for key in maxima:maxima[key]=max(maxima[key],float(vals[key]))
    return maxima


@pytest.mark.parametrize('t',[1.2,1.5,2.,2.25,2.65,3.,3.35])
def test_all_thicknesses_bound_independent_concomitant_samples(t):
    p,r=make(t);before=copy.deepcopy(r);z=check(p,r);actual=sample_independent(p,r)
    assert r==before
    assert z['full_member_field_covered']
    for key, value in actual.items():assert value<=z['criteria'][key]['index_upper_bound']
    assert z['section_stress_criteria_sufficiently_satisfied']
    assert not z['whole_member_approved'] and not z['complete_EN_design_qualified']
    assert not z['NBR_capacities_used'] and not z['AISI_capacities_used']
    assert json.loads(json.dumps(z,allow_nan=False))==z
    for rec in z['criteria'].values():assert rec['bound_control']['is_physical_state'] is False


@pytest.mark.parametrize('scale',[1.,-1.,-2.])
def test_sign_reversals_and_interior_moment_sign_changes(scale):
    p,r=make(1.2,scale,reversal=True);z=check(p,r);actual=sample_independent(p,r)
    for key,value in actual.items():assert value<=z['criteria'][key]['index_upper_bound']


def test_proportionality_and_reversal_of_signed_operator_union():
    p,r=make();a=check(p,r)
    for factor in (-1.,2.):
        p,r=make(scale=factor);b=check(p,r)
        for key in a['criteria']:
            assert b['criteria'][key]['index_upper_bound']==pytest.approx(abs(factor)*a['criteria'][key]['index_upper_bound'],rel=1e-12)


def test_torsional_shear_present_with_zero_transverse_shear():
    p,r=make(pure_torsion=True);z=check(p,r);actual=sample_independent(p,r)
    assert actual['shear']>0.
    for st in r['critical_states']:
        assert st['Vx_N']==0 and st['Vy_N']==0
    assert actual['shear']<=z['criteria']['shear']['index_upper_bound']


def test_upper_above_one_never_reported_as_observed_failure():
    p,r=make(scale=100.);z=check(p,r)
    assert not z['section_stress_criteria_sufficiently_satisfied']
    assert all(c['criterion']=='inconclusive_upper_bound' for c in z['criteria'].values())
    assert all(c['observed_exceedance'] is False for c in z['criteria'].values())


@pytest.mark.parametrize('mutation',['ELS','N','qualification','gap','extent','section'])
def test_unsupported_or_incomplete_source_fails_closed(mutation):
    p,r=make()
    if mutation=='ELS':r['limit_state']='ELS'
    if mutation=='N':r['analysis_domain']['axial_force_in_this_model_N']=1.
    if mutation=='qualification':r['numerics']['qualification_passed']=False
    if mutation=='gap':r['elements'][1]['a_mm']+=1.
    if mutation=='extent':r['elements'].pop()
    if mutation=='section':r['section']['properties']['Cw_mm6']*=1.1
    with pytest.raises(ValueError):check(p,r)


def test_intact_section_model_is_not_assumed():
    p,r=make()
    with pytest.raises(ValueError,match='declaration'):
        check_member(r,p)
    with pytest.raises(ValueError,match='origin'):
        check_member(r,p,intact_section_model_declared=True)


def test_exact_zero_field_and_fixed_support_point_do_not_fail_sqrt():
    p,r=make(scale=0.)
    z=check(p,r)
    assert z['section_stress_criteria_sufficiently_satisfied']
    assert all(c['index_upper_bound']<1e-10 for c in z['criteria'].values())


def support_member(*,limit,include_state=True):
    from tercas.torsion_vlasov.adapter import support_limit_before_point
    p=json.loads((ROOT/'tercas/data/torsion_profiles/ue100x50x17_t2.00.json').read_text())
    sec=from_frozen_profile(p)
    r=solve_member(section=sec,length_mm=4000.,E_MPa=200000.,G_MPa=200000/2.6,
        actions=[dict(name='P',kind='point',force_xy_N=[0.,0.],couple_Nmm=2e6,
            application_xy_mm=sec['properties']['centroid_xy_mm'],s_mm=0.,
            existing_point_position='support_limit' if limit else 'fixed',origin='QA explicit endpoint semantics')],
        supports={s:dict(twist='fixed',warping='free_assumed',origin='QA') for s in ('left','right')},
        combination_id='SUPPORT_ELU',limit_state='ELU',member_id='P',action_accounting_origin='QA',elements_per_interval=8)
    if limit:
        r['analysis_domain']['point_position_scope']='Prescribed a->0+ left-support limit, not an all-position envelope'
        if include_state:r['support_limit_states']=[support_limit_before_point(r)]
    return p,r


def test_support_limit_requires_complete_before_P_state_and_keeps_its_shear():
    p,r=support_member(limit=True);z=check(p,r)
    assert z['criteria']['shear']['index_upper_bound']>1
    assert z['criteria']['shear']['criterion']=='inconclusive_upper_bound'
    p,r=support_member(limit=True,include_state=False)
    with pytest.raises(ValueError,match='before-P'):check(p,r)
    p,r=support_member(limit=True);r['support_limit_states'][0]['Tw_Nmm']=0.
    with pytest.raises(ValueError,match='before-P'):check(p,r)


def test_exact_support_point_is_not_turned_into_support_limit():
    p,r=support_member(limit=False);z=check(p,r)
    assert z['criteria']['shear']['index_upper_bound']<1e-10
    r['loads'][0].pop('existing_point_position')
    with pytest.raises(ValueError,match='semantics'):check(p,r)
