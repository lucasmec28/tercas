import copy
import json
import math
from io import BytesIO
from pathlib import Path
import pytest
from docx import Document
from tercas.ue_family_reference import apply_geometry
from tercas.three_girt_warping.application import calculate as solve,current_configuration,attach_g81
from tercas.three_girt_en_normal import application as a
from tercas.three_girt_axial import application as nbr

FIXTURE=Path(__file__).parent/'data'/'three_girt_normal_QA_input.json'


def demand_for(t=2.65):
    source=json.loads(FIXTURE.read_text());data=apply_geometry(source['input_data'],t,4000.)
    data['project']=f'Synthetic EN normal QA t={t}; not a physical design'
    return attach_g81(solve(data,current_configuration(data,source['configuration']['three_girt'])))


def config(demand):
    c=a.reference_configuration(demand)
    c.update(intact_section_model_declared=True,section_model_origin='Synthetic QA intact nominal section')
    return c

@pytest.fixture(scope='module')
def demand():return demand_for()

@pytest.fixture(scope='module')
def result(demand):return a.calculate(demand,config(demand))


def test_current_case_retains_all_coverage_and_partial_scope(demand,result):
    assert len(result['rows'])==108
    assert result['ELU_combinations']==12 and result['ELS_combinations_excluded']==7
    assert result['section_fibers_checked']==832
    assert all(result[k] is False for k in a.FALSE_FLAGS)
    assert result['resistance_material_E_MPa']==210000 and result['demand_material_E_MPa']==200000
    for item in result['per_member'].values():
        assert item['complete'] is False and item['complete_envelope'] is None
        assert item['partial_maximum'] is not None
        assert item['blocking_components']==['My_negative']
    assert result['per_member']['middle']['partial_maximum']['concomitant_7DOF_state']['N_N']!=0


def test_witness_recomposition_at_same_exterior_fiber(result):
    props=result['component_sections']['gross_properties']
    for row in result['rows']:
        for piece in row['pieces']:
            if not piece['complete']:
                assert piece['maximum_absolute'] is None
                continue
            w=piece['maximum_absolute'];s=w['concomitant_7DOF_state'];x,y=w['section_fiber']['fiber_xy_relative_to_gross_CG_mm']
            physical=s['N_N']/props['A_mm2']-s['My_strong_Nmm']*y/props['Ix_strong_mm4']+s['Mz_weak_Nmm']*x/props['Iy_weak_mm4']+w['stress_contributions_MPa']['B']
            assert physical==pytest.approx(w['sigma_MPa'],abs=2e-7)
            assert sum(w['stress_contributions_MPa'].values())==pytest.approx(w['sigma_MPa'],abs=2e-7)
            assert row['x_start_mm']<=w['x_mm']<=row['x_end_mm']
            assert s['x_mm']==w['x_mm']
            assert w['section_fiber']['thickness_face_sign'] in (-1,1)


def test_no_network_or_NBR_capacity_calculation(demand,monkeypatch):
    from tercas.three_girt_warping import network
    def forbidden(*args,**kwargs):raise AssertionError('Not part of the EN normal calculation')
    monkeypatch.setattr(network,'solve',forbidden)
    monkeypatch.setattr(nbr,'_capacities',forbidden)
    assert a.calculate(demand,config(demand))['schema']==a.SCHEMA


def test_15mm_retains_reduced_compression_block_without_gross_fallback():
    d=demand_for(1.5);r=a.calculate(d,config(d))
    certificate=r['component_sections']['components']
    assert certificate['N_compression']['eligible'] is False
    assert certificate['N_compression']['sigma_coefficients_c0_cx_cy'] is None
    assert certificate['Mx_positive']['eligible'] is True
    assert r['per_member']['upper']['partial_maximum'] is not None
    assert 'N_compression' in r['per_member']['middle']['blocking_components']
    assert r['per_member']['middle']['observed_normal_exceedance'] is True
    assert r['per_member']['middle']['normal_criterion']=='above_1_at_checked_state_full_envelope_incomplete'
    assert all(p['complete_envelope'] is None for p in r['per_member'].values())


@pytest.mark.parametrize('change',[
    lambda d:d.pop('load_bundle'),
    lambda d:(d['cases'].pop(0),d['load_bundle']['combinations'].pop(0)),
    lambda d:d['cases'].reverse(),
    lambda d:d['cases'][0]['model']['beams'][0]['normal_action_polynomials']['N_N'].__setitem__(0,123.)])
def test_mutated_demand_rejected(demand,change):
    d=copy.deepcopy(demand);change(d)
    with pytest.raises((ValueError,KeyError)):a.calculate(d,config(d))

@pytest.mark.parametrize('change',[
    lambda c:c.update(intact_section_model_declared=False),
    lambda c:c.update(section_model_origin=''),
    lambda c:c.update(demand_input_fingerprint='bad'),
    lambda c:c.update(section_model='assumed_unchecked')])
def test_explicit_scope_required(demand,change):
    c=config(demand);change(c)
    with pytest.raises(ValueError):a.calculate(demand,c)


def test_saved_EN_and_NBR_hashes_coexist_without_recalculation(demand,result,monkeypatch):
    d=copy.deepcopy(demand);d[a.FIELD]=copy.deepcopy(result)
    d=nbr.attach(d,nbr.reference_configuration(d))
    from tercas.three_girt_warping import network,report
    def forbidden(*args,**kwargs):raise AssertionError('Saved display/export cannot recompute')
    monkeypatch.setattr(network,'solve',forbidden)
    monkeypatch.setattr(a,'calculate',forbidden)
    monkeypatch.setattr(a,'build_component_sections',forbidden)
    monkeypatch.setattr(nbr,'calculate',forbidden)
    assert a.saved_component(d)==result
    assert nbr.saved_component(d) is not None
    doc=Document(BytesIO(report.word(d)))
    text='\n'.join(p.text for p in doc.paragraphs)
    assert 'Componente normal N Mx My B pela EN' in text
    assert 'sigma–tau' in text
    assert 'inventário de tração' not in text.lower()
    d[a.FIELD]['whole_member_approved']=True
    d[a.FIELD]['content_sha256']=a.fingerprint({k:v for k,v in d[a.FIELD].items() if k!='content_sha256'})
    with pytest.raises(ValueError):a.saved_component(d)


def test_attach_order_is_explicit(demand):
    with_nbr=nbr.attach(demand,nbr.reference_configuration(demand))
    with pytest.raises(ValueError,match='before'):a.attach(with_nbr,config(with_nbr))


def test_saved_source_mutation_rejected(demand,result):
    d=copy.deepcopy(demand);d[a.FIELD]=copy.deepcopy(result)
    d['cases'][0]['model']['beams'][0]['states'][0]['N_N']=10.
    with pytest.raises(ValueError):a.saved_component(d)


def test_default_off_historical_word_still_exports(demand):
    from tercas.three_girt_warping.report import word
    old=nbr.attach(demand,nbr.reference_configuration(demand))
    assert a.saved_component(old) is None
    doc=Document(BytesIO(word(old)))
    assert not any('Componente normal N Mx My B pela EN' in p.text for p in doc.paragraphs)


def test_direct_central_N_M_B_complete_and_proportional():
    source=json.loads(FIXTURE.read_text());indices=[]
    for factor in (1.,20.):
        data=apply_geometry(copy.deepcopy(source['input_data']),2.65,4000.)
        data.update(load_mode='direct',q_uls=.1*factor,q_sls=.1*factor,
            q_parallel_uls=-.1*factor,q_parallel_sls=-.1*factor,
            actions_origin='Synthetic proportional QA, not real project')
        raw=copy.deepcopy(source['configuration']['three_girt'])
        raw.update(brace_self_weight=False,direct_pp_uls_N_mm=0.,direct_pp_sls_N_mm=0.)
        d=attach_g81(solve(data,current_configuration(data,raw)));r=a.calculate(d,config(d))
        central=r['per_member']['middle'];assert central['complete']
        w=central['complete_envelope'];s=w['concomitant_7DOF_state']
        assert all(s[k]!=0 for k in ('N_N','My_strong_Nmm','Mz_weak_Nmm','B_equilibrium_Nmm2'))
        indices.append(w['normal_index'])
        assert r['whole_member_approved'] is False
    assert indices[0]<1<indices[1]
    assert indices[1]/indices[0]==pytest.approx(20.,rel=1e-12)
