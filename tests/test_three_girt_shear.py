import copy,json,math
from pathlib import Path
import numpy as np
import pytest
from tercas import three_girt_shear as s
from tercas.core.flt_vrd import vrd
from tercas.three_girt_warping import application as w
from tercas.three_girt_axial import application as nbr
from tercas.ue_family_reference import apply_geometry

@pytest.mark.parametrize('ratio',[10.,1.08*math.sqrt(200000*5/250),1.2*math.sqrt(200000*5/250),2.*math.sqrt(200000*5/250)])
def test_NBR_three_branches_preserved(ratio):
    t=1.5;h=ratio*t
    r=vrd(h,t,250.,200000.)
    if ratio<=1.08*math.sqrt(4000):expected=.6*250*h*t/1.1
    elif ratio<=1.4*math.sqrt(4000):expected=.65*t*t*math.sqrt(5*250*200000)/1.1
    else:expected=.905*200000*5*t**3/h/1.1
    assert r['VRd_N']==pytest.approx(expected)

@pytest.mark.parametrize('lam',[.3,.83,.83001,1.399999,1.4,1.40001,2.,5.])
def test_EN_lower_capacity_bounds_every_smaller_web_slenderness(lam):
    t=1.;h=1+lam/(.346*math.sqrt(250/210000))
    cap=s.en_web_lower_capacity(h_mm=h,t_mm=t,fyb_MPa=250.)
    for actual in np.r_[np.linspace(1e-8,lam,2000),[x for x in (.83,.83000000001,1.39999999999,1.4) if x<=lam]]:
        f=.58*250 if actual<=.83 else .48*250/actual if actual<1.4 else .67*250/actual**2
        assert cap['fbv_lower_MPa']<=f+1e-10

@pytest.mark.parametrize('coeff',[[0.,6e6,-6e6],[3e6,-20e6,16e6],[-3e6,20e6,-16e6],[5e5],[0.,1e6]])
def test_concomitant_quartic_envelope_dense_check(coeff):
    out=s.concomitant_mv(M_coeff=coeff,length_mm=4000.,MRd_local_Nmm=3e6,VRd_N=10000.,x_start_mm=200.)
    m=np.polynomial.Polynomial(coeff);v=-m.deriv()/4000;u=np.linspace(0,1,200001)
    dense=(m(u)/3e6)**2+(v(u)/10000)**2
    assert out['maximum']['index_squared']>=float(max(dense))-1e-10
    assert out['maximum']['index_squared']==pytest.approx(float(max(dense)),rel=1e-8,abs=1e-10)
    for p in out['states']:
        assert p['Mstrong_Nmm']==pytest.approx(m(p['u']))
        assert p['Vweb_N']==pytest.approx(v(p['u']))
    assert not out['whole_member_approved'] and not out['N_M_V_B_T_qualified']

@pytest.fixture(scope='module')
def component():
    src=json.loads((Path(__file__).parent/'data/three_girt_normal_QA_input.json').read_text())
    data=apply_geometry(src['input_data'],3.35,4000.)
    data['load_mode']='direct';data.update(q_uls=.4,q_sls=.3,P_uls=0.,P_sls=0.)
    g=copy.deepcopy(src['configuration']['three_girt'])
    g.update(direct_pp_uls_N_mm=.07,direct_pp_sls_N_mm=.056,direct_brace_factor_uls=1.25,direct_brace_factor_sls=1.)
    demand=w.attach_g81(w.calculate(data,w.current_configuration(data,g)))
    return demand,nbr.attach(demand,nbr.reference_configuration(demand))


def test_producer_snapshot_separate_weak_shear_and_N(component):
    demand,result=component;c=nbr.saved_component(result);out=s.saved(c)
    assert out is not None,c.get('web_shear_error')
    assert len(out['rows'])==len(c['rows'])==out['ELU_segments']
    assert out['EN_capacity'] is None
    assert any(r['N_N']!=0 for r in out['rows'])
    assert any(not r['weak_shear_identically_zero'] for r in out['rows'])
    for r in out['rows']:
        assert r['NBR_MV']['MRd_denominator_Nmm']==c['capacities']['bending']['strong_positive']['MRd_local_Nmm']
        assert not r['N_M_V_B_T_qualified']
    assert result['cases']==demand['cases']
    assert s.presentation_rows(c)


def test_EN_capacity_is_not_NBR_denominator(component):
    from tercas.three_girt_en_normal import application as en
    demand,_=component;cfg=en.reference_configuration(demand)
    cfg.update(intact_section_model_declared=True,section_model_origin='Synthetic test')
    with_en=en.attach(demand,cfg)
    result=nbr.attach(with_en,nbr.reference_configuration(with_en));out=s.saved(nbr.saved_component(result))
    assert out is not None,result[nbr.FIELD].get('web_shear_error')
    assert out['EN_capacity']['gamma_M0']==1. and out['NBR_capacity']['gamma']==1.1
    assert out['EN_capacity']['hw_mm']!=out['NBR_capacity']['h_flat_mm']
    assert all(r['EN_web_shear'] is not None for r in out['rows'])


def test_snapshot_read_does_not_calculate_and_tamper_rejected(component,monkeypatch):
    _,result=component;c=nbr.saved_component(result)
    monkeypatch.setattr(s,'calculate_validated',lambda *a:(_ for _ in ()).throw(AssertionError('No recomputation')))
    assert s.saved(c)
    for key in ('whole_member_approved','panel_restraint_credit','tie_strength_checked','first_order_network_stability_qualified'):
        edited=copy.deepcopy(c);edited['web_shear_component'][key]=True
        edited['web_shear_component']['content_sha256']=nbr.fingerprint({k:v for k,v in edited['web_shear_component'].items() if k!='content_sha256'})
        with pytest.raises(ValueError):s.saved(edited)
    old=copy.deepcopy(c);old.pop('web_shear_component')
    assert s.saved(old) is None

@pytest.mark.parametrize('value',[True,0.,-1.,float('nan'),float('inf'),'1'])
def test_invalid_capacity_inputs_fail_closed(value):
    with pytest.raises(ValueError):s.en_web_lower_capacity(h_mm=100.,t_mm=value,fyb_MPa=250.)


def test_global_inventory_reports_new_web_without_promoting_network(component):
    from tercas.three_girt_assessment.application import assess
    _,result=component;inventory=assess(result);byid={r['id']:r for r in inventory['checks']}
    shear=byid['transverse_shear_resistance'];interaction=byid['N_M_V_shear_reduction']
    assert shear['status']==interaction['status']=='pending'
    assert 'foi avaliada' in shear['reason'] and 'cortante fraco' in shear['reason']
    assert 'mesma seção' in interaction['reason']
    assert byid['member_stability_and_analysis']['status']=='pending'
    assert not inventory['whole_member_approved']
