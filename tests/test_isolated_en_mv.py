import copy,json
import numpy as np
import pytest
from docx import Document
from tercas import isolated_en_stress as stress, isolated_en_application as a, isolated_en_ui as ui
from tercas import isolated_en_mv as mv, en_simplified_interaction as core
from test_isolated_en_stress import make
from test_isolated_en_shear import point_at_support
from test_isolated_en_application import direct, reseal


def pure_web():
    from tercas.torsion_vlasov.vlasov import solve_member
    p,r=make();s=r['section']
    d=solve_member(section=s,length_mm=4000.,E_MPa=200000.,G_MPa=200000./2.6,
        actions=[dict(name='q',kind='uniform',q_xy_N_mm=[0.,-.15],couple_N=0.,
            application_xy_mm=s['properties']['shear_center_xy_mm'],origin='QA')],
        supports={side:dict(twist='fixed',warping='free_assumed',origin='QA') for side in ('left','right')},
        combination_id='PURE_ELU',limit_state='ELU',member_id='P',action_accounting_origin='QA',elements_per_interval=8)
    return p,d


def check(p,d):
    return stress.check_web_shear(d,p,intact_section_model_declared=True,model_origin='QA')['bending_shear_component']

@pytest.mark.parametrize('t',[1.2,1.5,2.,2.25,2.65,3.,3.35])
def test_all_sections_include_both_transverse_shears_keep_separate_torsion(t):
    p,d=make(t);before=copy.deepcopy(d);out=check(p,d)
    assert out['status']=='sufficient'
    assert out['component_qualified'] and not out['torsional_interaction_qualified']
    assert out['weak_transverse_shear_included'] and not out['torsion_zero_required']
    assert out['transverse_subproblem_sufficient']
    assert len(out['pieces'])==len(d['elements'])
    assert d==before
    assert json.loads(json.dumps(out,allow_nan=False))==out


def test_zero_torque_and_weak_shear_can_qualify_new_component():
    p,d=pure_web();out=check(p,d)
    assert out['component_qualified'] and out['shear_reduction_waived']
    assert out['status']=='sufficient' and not out['whole_member_approved']


def test_large_and_reversed_torsion_no_physical_failure_claim():
    p,d=make(scale=100.);out=check(p,d)
    assert out['index_upper']>1 and not out['observed_failure']
    p,d=make();positive=check(p,d)
    p,d=make(scale=-1.);negative=check(p,d)
    assert negative['index_upper']==pytest.approx(positive['index_upper'],rel=1e-12)


def test_support_limit_keeps_before_point_and_fixed_does_not_invent_it():
    p,d=point_at_support(True);out=check(p,d)
    assert out['pieces'][-1]['source_piece']['kind']=='support_limit'
    assert len(out['pieces'])==len(d['elements'])+1
    p,d=point_at_support(False);out=check(p,d)
    assert len(out['pieces'])==len(d['elements'])


def reseal_mv(result):
    for row in result[a.FIELD]['records']:
        w=row['web_shear_component'];m=w['bending_shear_component']
        m['content_sha256']=core._sha({k:v for k,v in m.items() if k!='content_sha256'})
        w['content_sha256']=core._sha({k:v for k,v in w.items() if k!='content_sha256'})
    reseal(result)

@pytest.mark.parametrize('mutation',['capacity','source','scope','flags','domain','index','controls','before','normal_actions'])
def test_rehashed_corruption_fails_closed(direct,mutation):
    result=copy.deepcopy(direct);out=result[a.FIELD]['records'][0]['web_shear_component']['bending_shear_component']
    if mutation=='capacity':out['capacity_reference']['signed_capacity_floor']['Mx_positive']*=2
    elif mutation=='source':out['source_demand_sha256']='a'*64
    elif mutation=='scope':out['scope']='All checked'
    elif mutation=='flags':out['whole_member_approved']=True
    elif mutation=='domain':out['torsional_shear_identically_zero']=True;out['torsion_zero_required']=True
    elif mutation=='index':out['index_upper']=0.
    elif mutation=='controls':out['pieces'][0]['controls'][0]['intervals']['Mx']=[0.,0.]
    elif mutation=='before':out['pieces'].pop()
    else:out['normal_actions']='N omitted'
    reseal_mv(result)
    with pytest.raises(ValueError):a.preserved(result)


def test_saved_UI_Word_and_legacy_no_recalculation(direct,monkeypatch):
    def fail(*args,**kwargs):raise AssertionError('No fresh computation on read')
    monkeypatch.setattr(mv,'calculate',fail);monkeypatch.setattr(core,'capacities',fail)
    monkeypatch.setattr(core,'polynomial_bound',fail)
    ev=a.preserved(direct);rows=ui.rows(ev)
    assert all(r['Teto M–V adicional EN6.27'] is not None for r in rows)
    doc=Document();ui.report(doc,direct);text='\n'.join(p.text for p in doc.paragraphs)
    assert 'Mf=0' in text and 'primeiro escoamento' in text and 'complementares' in text
    old=copy.deepcopy(direct)
    for row in old[a.FIELD]['records']:
        w=row['web_shear_component'];w.pop('bending_shear_component')
        w['content_sha256']=core._sha({k:v for k,v in w.items() if k!='content_sha256'})
    reseal(old);assert a.preserved(old)
    assert all(r['Teto M–V adicional EN6.27'] is None for r in ui.rows(a.preserved(old)))


def test_unsampled_piece_cannot_drop_moments_even_with_all_hashes_and_indices_rebuilt(direct):
    result=copy.deepcopy(direct);row=result[a.FIELD]['records'][0]
    out=row['web_shear_component']['bending_shear_component']
    summary=next(r['analysis'] for r in result['torsion_evidence']['records'] if r['combination_id']==row['combination_id'])
    witnessed={s['element_id'] for s in summary['witnesses']}
    piece=next(p for p in out['pieces'] if p['source_piece']['element_id'] not in witnessed)
    for ctrl in piece['controls']:
        for key in ('Mx','My','Mx_original','My_original','Vweak'):ctrl['intervals'][key]=[0.,0.]
        ctrl.update(core.objective(ctrl['intervals'],out['capacity_reference'],out['web_capacity_lower_N']))
    piece['index_upper']=max(c['index_upper'] for c in piece['controls'])
    piece['shear_ratio_upper']=max(c['shear_ratio_upper'] for c in piece['controls'])
    piece.update(core.verdict(piece['index_upper'],piece['shear_ratio_upper'],
        weak_zero=piece['weak_shear_identically_zero'],torsion_zero=piece['torsional_shear_identically_zero']))
    out['index_upper']=max(p['index_upper'] for p in out['pieces'])
    out['shear_ratio_upper']=max(p['shear_ratio_upper'] for p in out['pieces'])
    out.update(core.verdict(out['index_upper'],out['shear_ratio_upper'],
        weak_zero=out['weak_shear_identically_zero'],torsion_zero=out['torsional_shear_identically_zero']))
    reseal_mv(result)
    with pytest.raises(ValueError,match='fonte salva'):a.preserved(result)


def test_additional_component_failure_preserves_web_and_source(monkeypatch):
    p,d=make();before=copy.deepcopy(d)
    def unavailable(*args,**kwargs):raise ValueError('QA EN6.27 unavailable')
    monkeypatch.setattr(mv,'calculate',unavailable)
    out=stress.check_web_shear(d,p,intact_section_model_declared=True,model_origin='QA')
    assert out['web_shear']['status']=='meets'
    assert 'bending_shear_component' not in out
    assert out['bending_shear_error']=='QA EN6.27 unavailable'
    assert d==before and not out['whole_member_approved']


def test_saved_polynomial_identity_refuses_piece_crossing_point_jump():
    summary=dict(loads=[dict(kind='point',s_mm=1700.,force_xy_N=[30.,-60.])],
        support_reactions=dict(left_force_xy_N=[-10.,30.]))
    with pytest.raises(ValueError,match='salto de carga'):
        mv._saved_source_controls(summary,dict(kind='element',a_mm=1500.,b_mm=1900.))
