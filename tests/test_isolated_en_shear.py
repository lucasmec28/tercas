"""Independent web-force/capacity checks, saved semantics and legacy coverage."""
import copy
import json
import math

import numpy as np
import pytest
from docx import Document

from tercas import isolated_en_application as en, isolated_en_stress as stress
from tercas import isolated_en_shear as web, isolated_en_ui as ui
from tercas.torsion_vlasov.vlasov import evaluate, solve_member
from tercas.torsion_vlasov.adapter import support_limit_before_point
from test_isolated_en_stress import make
from test_isolated_en_application import direct, reseal


def check(p,r):
    return stress.check_web_shear(r,p,intact_section_model_declared=True,model_origin='QA intact')


@pytest.mark.parametrize('t',[1.2,1.5,2.,2.25,2.65,3.,3.35])
def test_seven_pinned_webs_against_independent_formula_and_force_samples(t):
    p,r=make(t);before=copy.deepcopy(r);out=check(p,r)
    hw=100.-t;lam=.346*(hw/t)*math.sqrt(250./210000.)
    fbv=.58*250. if lam<=.83 else .48*250./lam if lam<1.4 else .67*250./lam**2
    assert out['capacity']['Vw_Rd_lower_N']==pytest.approx(hw*t*fbv,rel=1e-14)
    assert out['capacity']['hw_mm']==hw and out['web_area_mm2']==hw*t
    assert out['capacity']['hw_mm']!=100.-4*t  # Do not use NBR flat web.
    values=[abs(evaluate(r,i,u)['Vy_N']) for i in range(len(r['elements'])) for u in np.linspace(0.,1.,41)]
    assert max(values)<=out['maximum_Vweb_abs_upper_N']
    assert max(values)==pytest.approx(out['maximum_Vweb_abs_upper_N'],rel=1e-12)
    assert out['axes']['derivative']=='Vy=dMx/ds'
    assert out['web_shear']['status']=='meets'
    assert out['no_web_shear_reduction']['transverse_component_threshold_met'] is True
    assert out['no_web_shear_reduction']['status']=='pending'
    assert not out['no_web_shear_reduction']['shear_reduction_waiver_qualified']
    assert all(out[key] is False for key in web.FLAGS)
    assert r==before and json.loads(json.dumps(out,allow_nan=False))==out


def test_two_point_load_sides_reversal_and_large_forces():
    p,r=make(reversal=True);a=check(p,r)
    end=next(x for x in a['pieces'] if x['source_piece'].get('b_mm')==1700.)
    start=next(x for x in a['pieces'] if x['source_piece'].get('a_mm')==1700.)
    left=sum(end['Vweb_end_intervals_N'][1])/2
    right=sum(start['Vweb_end_intervals_N'][0])/2
    assert right-left==pytest.approx(-500.)
    p,r=make(scale=-1.,reversal=True);b=check(p,r)
    assert b['maximum_Vweb_abs_upper_N']==pytest.approx(a['maximum_Vweb_abs_upper_N'],rel=1e-12)
    p,r=make(scale=1000.);large=check(p,r)
    assert large['web_shear']['status']=='inconclusive'
    assert large['web_shear']['observed_failure'] is False
    assert large['no_web_shear_reduction']['status']=='pending'


def test_weak_and_torsional_shear_never_replaced_by_web_capacity():
    p,r=make(pure_torsion=True);out=check(p,r)
    assert out['maximum_Vweb_abs_upper_N']<1e-10
    assert out['weak_shear_identically_zero'] is True
    assert not out['torsional_shear_buckling_qualified']
    assert any(abs(s['Tsv_Nmm'])>0. or abs(s['Tw_Nmm'])>0. for s in r['critical_states'])
    p,r=make();out=check(p,r)
    assert out['weak_shear_identically_zero'] is False
    assert out['weak_shear_resistance_qualified'] is False


def point_at_support(limit):
    p,r=make();section=r['section']
    d=solve_member(section=section,length_mm=4000.,E_MPa=200000.,G_MPa=200000./2.6,
        actions=[dict(name='P',kind='point',force_xy_N=[0.,-500.],couple_Nmm=0.,
            application_xy_mm=section['properties']['shear_center_xy_mm'],s_mm=0.,
            existing_point_position='support_limit' if limit else 'fixed',origin='QA')],
        supports={s:dict(twist='fixed',warping='free_assumed',origin='QA') for s in ('left','right')},
        combination_id='QA_ELU',limit_state='ELU',member_id='P1',
        action_accounting_origin='QA',elements_per_interval=8)
    if limit:
        d['analysis_domain']['point_position_scope']='Prescribed a->0+ left-support limit'
        d['support_limit_states']=[support_limit_before_point(d)]
    return p,d


def test_before_point_support_limit_is_not_lost_or_confused_with_fixed_load():
    p,r=point_at_support(True);out=check(p,r)
    assert out['maximum_Vweb_abs_upper_N']==pytest.approx(500.)
    assert len(out['pieces'])==len(r['elements'])+1
    assert out['pieces'][-1]['source_piece']['kind']=='support_limit'
    r['support_limit_states']=[]
    with pytest.raises(ValueError,match='before-P'):check(p,r)
    p,r=point_at_support(False);out=check(p,r)
    assert out['maximum_Vweb_abs_upper_N']<1e-10
    assert len(out['pieces'])==len(r['elements'])


def test_strict_criteria_at_half_and_unity_without_tolerance():
    for ratio in (0.,.5,np.nextafter(.5,np.inf),1.,np.nextafter(1.,np.inf)):
        shear,reduction=web._criteria(ratio,True)
        assert (reduction['status']=='meets')==(ratio<=.5)
        assert (shear['status']=='meets')==(ratio<=1.)
        assert shear['observed_failure'] is False


def test_application_direct_json_word_and_global_remain_separate(direct):
    for result in (direct,):
        ev=en.preserved(result)
        assert all('web_shear_component' in row for row in ev['records'])
        assert ev==en.preserved(json.loads(json.dumps(result,allow_nan=False)))
        en.validate_saved_global(result)
        context=en.global_context(result)['reason']
        assert 'Cortante da alma EN6.1.5 avaliado' in context
        assert 'EN6.27' in context and 'torsionais' in context
        assert not result['whole_member_approved']
        doc=Document();ui.report(doc,result);text='\n'.join(p.text for p in doc.paragraphs)
        assert 'hw=H−t' in text and 'before-P' in text
        assert all(r['Teto cortante transversal da alma EN'] is not None for r in ui.rows(ev))


def reseal_web(result):
    for row in result[en.FIELD]['records']:
        w=row.get('web_shear_component')
        if w:w['content_sha256']=stress._sha({k:v for k,v in w.items() if k!='content_sha256'})
    reseal(result)


@pytest.mark.parametrize('mutation',['axis','area','capacity','gamma_bool','ratio','threshold','scope','coverage','bound','flags','source','weak','before','waiver'])
def test_rehashed_saved_corruption_rejected(direct,mutation):
    result=copy.deepcopy(direct);w=result[en.FIELD]['records'][0]['web_shear_component']
    if mutation=='axis':w['axes']['web_shear']='Vx_N'
    elif mutation=='area':w['web_area_mm2']*=1.1
    elif mutation=='capacity':w['capacity']['Vw_Rd_lower_N']*=2
    elif mutation=='gamma_bool':w['capacity']['gamma_M0']=True
    elif mutation=='ratio':w['web_shear']['index_upper']=0.
    elif mutation=='threshold':w['no_web_shear_reduction']['threshold']=1.
    elif mutation=='scope':w['scope']='Approved all shear'
    elif mutation=='coverage':w['pieces'].pop()
    elif mutation=='bound':w['maximum_Vweb_abs_upper_N']=0.
    elif mutation=='flags':w['general_N_M_V_interaction_qualified']=True
    elif mutation=='source':w['source_demand_sha256']='a'*64
    elif mutation=='weak':w['weak_shear_identically_zero']=not w['weak_shear_identically_zero']
    elif mutation=='before':w['pieces'][0]['source_piece']['kind']='support_limit'
    elif mutation=='waiver':w['no_web_shear_reduction']['shear_reduction_waiver_qualified']=True
    reseal_web(result)
    with pytest.raises(ValueError):en.preserved(result)


def test_legacy_and_saved_read_do_not_calculate_sources_or_capacities(direct,monkeypatch):
    import tercas.three_girt_shear as shared
    def fail(*a,**kw):raise AssertionError('No calculation on saved read')
    monkeypatch.setattr(en,'check_member',fail)
    monkeypatch.setattr(en,'check_web_shear',fail)
    monkeypatch.setattr(web,'calculate_validated',fail)
    monkeypatch.setattr(web,'en_web_lower_capacity',fail)
    monkeypatch.setattr(shared,'en_web_lower_capacity',fail)
    assert en.preserved(direct)
    ui.report(Document(),direct)
    old=copy.deepcopy(direct)
    for row in old[en.FIELD]['records']:row.pop('web_shear_component')
    reseal(old);before=copy.deepcopy(old);ev=en.preserved(old)
    assert old==before
    assert all(r['Teto cortante transversal da alma EN'] is None for r in ui.rows(ev))
    assert 'Histórico não recalculado' in ' '.join(ui.text_lines(ev))
    assert 'Permanecem separados o cortante' in en.global_context(old)['reason']


def test_waiver_only_in_proven_pure_strong_bending_shear_domain():
    p,r=make();s=r['section']
    pure=solve_member(section=s,length_mm=4000.,E_MPa=200000.,G_MPa=200000./2.6,
        actions=[dict(name='q',kind='uniform',q_xy_N_mm=[0.,-.15],couple_N=0.,
            application_xy_mm=s['properties']['shear_center_xy_mm'],origin='QA pure shear-center load')],
        supports={side:dict(twist='fixed',warping='free_assumed',origin='QA') for side in ('left','right')},
        combination_id='PURE_ELU',limit_state='ELU',member_id='P',
        action_accounting_origin='QA',elements_per_interval=8)
    out=check(p,pure)
    assert all(out['waiver_domain'].values())
    assert out['no_web_shear_reduction']['shear_reduction_waiver_qualified'] is True
    assert out['no_web_shear_reduction']['status']=='meets'
    assert out['general_N_M_V_interaction_qualified'] is False
    assert out['whole_member_approved'] is False
    for ratio in (0.,.25,.5):
        _,reduction=web._criteria(ratio,False)
        assert reduction['transverse_component_threshold_met'] is True
        assert reduction['shear_reduction_waiver_qualified'] is False
        assert reduction['status']=='pending'


def test_new_component_failure_preserves_existing_mechanics_and_stress(direct,monkeypatch):
    from tercas import aisi_torsion_component as aisi
    from test_isolated_en_application import run
    def fail(*a,**kw):raise ValueError('QA new web component unavailable')
    monkeypatch.setattr(en,'check_web_shear',fail)
    result=run(copy.deepcopy(direct['input_data']))
    ev=en.preserved(result);row=ev['records'][0]
    assert row['status']=='computed' and row['check']==direct[en.FIELD]['records'][0]['check']
    assert row['web_shear_error']=='QA new web component unavailable'
    assert 'web_shear_component' not in row
    assert result['torsion_evidence']==direct['torsion_evidence']
    assert aisi.preserved(result)==aisi.preserved(direct)
    for key in ('section_checks','FLT_segments','ELS','NBR_branches'):
        assert result[key]==direct[key]
    assert not result['whole_member_approved']


def test_legacy_network_threshold_reading_does_not_claim_whole_section_waiver(monkeypatch):
    from tercas import three_girt_shear as network
    saved=dict(rows=[dict(girt='middle',combination_id='QA',
        NBR_web_shear=dict(index=.2),NBR_MV=dict(maximum=dict(index_squared=.3,x_mm=0.)),
        EN_web_shear=dict(index_upper=.1),EN_no_web_shear_reduction=dict(status='meets'),
        weak_shear_identically_zero=True)],stability_scope='QA pending')
    before=copy.deepcopy(saved)
    monkeypatch.setattr(network,'saved',lambda _:saved)
    rows=network.presentation_rows({})
    assert rows[0]['Redução_por_V_EN']=='Limiar da alma ≤0,5; registro histórico restrito'
    doc=Document();network.append_report(doc,{})
    text='\n'.join(p.text for p in doc.paragraphs)
    assert 'Registro histórico restrito à alma' in text
    assert 'não foi reclassificado' in text
    assert 'não demonstra dispensa' in text
    assert saved==before


def test_rehashed_zero_web_demand_cannot_replace_nonzero_compact_source(direct):
    result=copy.deepcopy(direct);w=result[en.FIELD]['records'][0]['web_shear_component']
    assert abs(result['torsion_evidence']['records'][0]['analysis']['field_envelopes']['Vy_N']['maximum_absolute']['value'])>1.
    for p in w['pieces']:
        p['Vweb_end_intervals_N']=[[0.,0.],[0.,0.]];p['Vweb_abs_upper_N']=0.
    w['maximum_Vweb_abs_upper_N']=0.
    from tercas.torsion_vlasov.intervals import Interval as I
    ratio=float((I(0.)/w['capacity']['Vw_Rd_lower_N']).hi)
    w['web_shear'],w['no_web_shear_reduction']=web._criteria(ratio,all(w['waiver_domain'].values()))
    reseal_web(result)
    with pytest.raises(ValueError,match='extremos Vy'):en.preserved(result)


def test_rehashed_piece_force_cannot_disagree_with_compact_witness(direct):
    result=copy.deepcopy(direct);row=result[en.FIELD]['records'][0];w=row['web_shear_component']
    summary=result['torsion_evidence']['records'][0]['analysis']
    witness=next(s for s in summary['witnesses'] if abs(s['Vy_N'])>1.)
    piece=next(p for p in w['pieces'] if p['source_piece']['element_id']==witness['element_id'])
    # Reverse the complete interval without changing its absolute maximum.
    piece['Vweb_end_intervals_N']=[[-hi,-lo] for lo,hi in piece['Vweb_end_intervals_N']]
    reseal_web(result)
    with pytest.raises(ValueError,match='testemunha compacta Vy'):en.preserved(result)
