import copy,json,math,time
from pathlib import Path
import pytest
from tercas import three_girt_en_mv as mv, en_simplified_interaction as core
from tercas.en_interaction_capacity_reference import REFERENCES
from tercas.three_girt_en_normal.application import _transport_polynomials
from tercas.three_girt_en_normal.en1993_normal_components import build_component_sections


def fixture():
    p=json.loads((Path(__file__).parents[1]/'tercas/data/torsion_profiles/ue100x50x17_t1.20.json').read_text())
    cert=build_component_sections(p);cap=core.capacities(p,cert)
    fields=dict(N=[-300.],Mx=[1e5,3e5,-3e5],My=[-3e4,4e4,-4e4])
    corrected,transport=_transport_polynomials(fields,cert)
    beam=dict(id='middle:0',girt='middle',length_mm=4000.,x_start_mm=0.,x_end_mm=4000.,
        normal_action_polynomials=dict(N_N=fields['N'],My_strong_Nmm=[-x for x in fields['Mx']],
            Mz_weak_Nmm=[-x for x in fields['My']]))
    # Missing torsional metadata is NOT zero. The scalar component still uses
    # transverse shears, while a complete member result requires EN6.1.6.
    case=dict(combination=dict(id='QA'),model={})
    return cert,cap,beam,case,dict(normal_action_reference=transport)


def test_N_and_biaxial_transport_retained_and_no_torque_zero_requirement():
    cert,cap,beam,case,row=fixture();out=mv.calculate_row({},case,beam,row,cap,cap['shear_capacity_lower_N']['strong'])
    mv.validate_internal(out)
    assert out['source_polynomials']['N']==[-300.]
    assert out['source_polynomials']['My']!=row['normal_action_reference']['original_polynomials_R01']['My']
    assert out['source_polynomials']['My']==row['normal_action_reference']['corrected_polynomials_R01']['My']
    assert not out['result']['torsional_shear_identically_zero']
    assert not out['result']['torsion_zero_required']
    assert out['result']['weak_transverse_shear_included']
    assert out['result']['component_qualified']
    assert not out['whole_member_approved']

@pytest.mark.parametrize('key',['capacity','source','flags','booleans','controls'])
def test_rehashed_component_rejects_semantic_corruption(key):
    cert,cap,beam,case,row=fixture();out=mv.calculate_row({},case,beam,row,cap,cap['shear_capacity_lower_N']['strong'])
    if key=='capacity':out['capacity_reference']['shear_capacity_geometry']['strong']['walls']=True
    if key=='source':out['source_polynomials']['N']=[True]
    if key=='flags':out['whole_member_approved']=True
    if key=='booleans':out['result']['torsion_zero_required']=0
    if key=='controls':out['result']['controls'][1]['intervals']['Mx']=[0.,0.]
    out['content_sha256']=core._sha({k:v for k,v in out.items() if k!='content_sha256'})
    with pytest.raises(ValueError):mv.validate_internal(out)


@pytest.fixture(scope='module')
def integrated():
    from tercas import three_girt_scope as scope
    from tercas.three_girt_warping import application as w
    from tercas.three_girt_en_normal import application as en
    from tercas.three_girt_axial import application as nbr
    from tercas.ue_family_reference import apply_geometry
    src=json.loads((Path(__file__).parent/'data/three_girt_normal_QA_input.json').read_text())
    data=apply_geometry(src['input_data'],3.35,4000.)
    data.update(load_mode='direct',q_uls=.1,q_sls=.1,q_parallel_uls=-.1,q_parallel_sls=-.1,
        P_uls=0.,P_sls=0.,actions_origin='Synthetic EN6.27 QA; not a physical project')
    g=copy.deepcopy(src['configuration']['three_girt'])
    g.update(brace_self_weight=False,direct_pp_uls_N_mm=0.,direct_pp_sls_N_mm=0.)
    demand=w.attach_g81(w.calculate(data,w.current_configuration(data,g),verification_scope=scope.SCHEMA))
    cfg=en.reference_configuration(demand)
    cfg.update(intact_section_model_declared=True,section_model_origin='Synthetic EN6.27 QA')
    with_en=en.attach(demand,cfg)
    start=time.perf_counter();result=nbr.attach(with_en,nbr.reference_configuration(with_en))
    print('EN_6_27_NBR_ATTACH_SECONDS',time.perf_counter()-start)
    return demand,result



def test_integrated_central_only_component_does_not_reduce_physical_network(integrated):
    from tercas.three_girt_en_normal import application as en
    from tercas.three_girt_assessment import application as assessment
    before,result=integrated
    assert before['cases']==result['cases']
    assert all({b['girt'] for b in c['model']['beams']}=={'upper','middle','lower'} for c in result['cases'])
    c=en.saved_component(result)
    actual=[r for r in c['rows'] if 'EN_bending_shear_component' in r]
    assert actual and all(r['girt']=='middle' for r in actual)
    expected=[b for c in result['cases'] if c['combination']['limit_state']=='ELU' for b in c['model']['beams'] if b['girt']=='middle']
    assert len(actual)==len(expected)==len(c['rows'])
    assert c['EN_bending_shear_schema']==mv.COLLECTION_SCHEMA
    assert not any('EN_bending_shear_error' in r for r in c['rows'])
    a=assessment.assess(result);checks={r['id']:r for r in a['checks']}
    assert checks['N_M_V_shear_reduction']['status']=='meets'
    assert checks['transverse_shear_resistance']['status']=='meets'
    assert checks['N_M_V_shear_reduction']['trace']['all_transverse_directions_included']
    assert not a['whole_member_approved']
    rows=mv.presentation_rows(c)
    assert [r['Travessa'] for r in rows]==['Central']
    assert rows[0]['Resultado']=='Suficiente no domínio salvo'


def test_EN_on_NBR_off_is_independent_and_EN_off_does_not_backfill(integrated):
    from tercas.three_girt_en_normal import application as en
    from tercas.three_girt_axial import application as nbr
    from tercas.three_girt_assessment import application as assessment
    result=copy.deepcopy(integrated[1]);result.pop(nbr.FIELD)
    assert en.saved_component(result)
    assert mv.presentation_rows(en.saved_component(result))[0]['Teto_interação_N_M_V_EN'] is not None
    checks={r['id']:r for r in assessment.assess(result)['checks']}
    assert checks['N_M_V_shear_reduction']['status']=='meets'
    assert checks['transverse_shear_resistance']['status']=='meets'
    result.pop(en.FIELD)
    assert en.saved_component(result) is None
    checks={r['id']:r for r in assessment.assess(result)['checks']}
    assert checks['N_M_V_shear_reduction']['status']=='pending'


def test_integrated_saved_read_and_word_do_not_recalculate(integrated,monkeypatch):
    from docx import Document
    from tercas.three_girt_en_normal import application as en, report
    from tercas.three_girt_warping import network
    result=json.loads(json.dumps(integrated[1],allow_nan=False));before=copy.deepcopy(result)
    def forbidden(*args,**kwargs):raise AssertionError('Read must not recompute mechanics/capacities')
    for module,key in [(mv,'calculate_row'),(mv,'prepare'),(mv,'populate'),(core,'capacities'),(core,'polynomial_bound'),
                       (en,'_profile_and_section'),(en,'build_component_sections'),(network,'solve')]:
        monkeypatch.setattr(module,key,forbidden)
    c=en.saved_component(result)
    assert mv.presentation_rows(c)
    doc=Document();report.append(doc,result)
    text='\n'.join(p.text for p in doc.paragraphs)
    assert 'Mf=0' in text and 'duas mesas' in text and '6.1.6' in text
    assert 'Não depende do checkbox nem de capacidades NBR' in text
    assert result==before


@pytest.mark.parametrize('mutation',['beam_source','normal_transport','inventory','duplicate_inventory','coverage','material','source_polynomial'])
def test_integrated_rehashed_corruption_and_scope_rejected(integrated,mutation):
    from tercas.three_girt_en_normal import application as en
    d=copy.deepcopy(integrated[1]);c=d[en.FIELD]
    row=c['rows'][0];out=row['EN_bending_shear_component']
    if mutation=='beam_source':out['source_beam_sha256']='0'*64
    elif mutation=='normal_transport':out['normal_action_reference']['additional_My_Nmm']+=1.
    elif mutation=='inventory':c['EN_bending_shear_schema']='unknown'
    elif mutation=='duplicate_inventory':c['rows'].append(copy.deepcopy(c['rows'][0]))
    elif mutation=='coverage':row.pop('EN_bending_shear_component')
    elif mutation=='material':out['capacity_reference']['material']['fyb_MPa']=350.
    else:out['source_polynomials']['Vweak'][0]+=1.
    out['content_sha256']=core._sha({k:v for k,v in out.items() if k!='content_sha256'})
    c['content_sha256']=en.fingerprint({k:v for k,v in c.items() if k!='content_sha256'})
    with pytest.raises(ValueError):en.saved_component(d)


def test_legacy_EN_snapshot_is_not_reclassified_or_recomputed(integrated,monkeypatch):
    from tercas.three_girt_en_normal import application as en
    d=copy.deepcopy(integrated[1]);c=d[en.FIELD]
    c.pop('EN_bending_shear_schema')
    for row in c['rows']:row.pop('EN_bending_shear_component',None)
    c['content_sha256']=en.fingerprint({k:v for k,v in c.items() if k!='content_sha256'})
    def forbidden(*args,**kwargs):raise AssertionError('Legacy must not compute new component')
    monkeypatch.setattr(mv,'prepare',forbidden);monkeypatch.setattr(mv,'populate',forbidden)
    before=copy.deepcopy(d)
    assert en.saved_component(d)==c
    assert mv.presentation_rows(c)==[]
    assert d==before


def test_new_capacity_failure_keeps_old_network_and_EN_stress(integrated,monkeypatch):
    from tercas.three_girt_en_normal import application as en
    from tercas.three_girt_axial import application as nbr
    d=copy.deepcopy(integrated[1]);before=copy.deepcopy(d['cases']);old=d[en.FIELD]
    def unavailable(*args,**kwargs):raise ValueError('QA EN6.27 capacity unavailable')
    monkeypatch.setattr(mv,'prepare',unavailable)
    d.pop(nbr.FIELD);d.pop(en.FIELD)
    out=en.attach(d,old['configuration']);c=en.saved_component(out)
    assert out['cases']==before
    assert c['EN_bending_shear_schema']==mv.COLLECTION_SCHEMA
    assert all('EN_bending_shear_component' not in r for r in c['rows'])
    assert all(r['EN_bending_shear_error']=='QA EN6.27 capacity unavailable' for r in c['rows'])
    assert all(r['normal']==oldr['normal'] and r['shear_interaction']==oldr['shear_interaction'] for r,oldr in zip(c['rows'],old['rows']))
    assert mv.presentation_rows(c)[0]['Resultado']=='Pendente'


@pytest.mark.parametrize('key,value',[('fy_MPa',350.),('fy_MPa',True),('t',2.),('h',110.),('bf',60.),('lip',15.),('ri_mm',2.)])
def test_saved_capacity_cannot_be_reassigned_to_other_declared_geometry_or_material(integrated,key,value):
    from tercas.three_girt_en_normal import application as en
    d=copy.deepcopy(integrated[1]);d['input_data']['properties'][key]=value
    with pytest.raises(ValueError,match='Geometria/material'):
        mv.validate_component(d[en.FIELD],d)
