"""Synthetic consumer/read boundaries; no application solve."""
import copy
import pytest
from tercas import roof_catalog_positive as consumer
from tercas.roof_top_nbr_ui import biaxial_row,replace_biaxial_rows
from tercas.roof_top_nbr import COMPUTED
from test_roof_biaxial_positive import combo

SOURCE={'weak_positive_reference':{'MRd_positive_reference_Nmm':50.}}
POSITION={'applicable':True}


def test_positive_consumer_and_existing_row_contract():
    c=combo();r=consumer.fields(c,10.,100.,SOURCE,POSITION)
    consumer.validate_fields(r,c,10.,100.,SOURCE,POSITION)
    row=biaxial_row(dict(r,combination_id='synthetic',status=COMPUTED))
    assert row['Índice']==.5
    assert r['biaxial']['whole_member_approved'] is False


def test_negative_pending_not_hidden_by_positive_combination():
    pos=dict(consumer.fields(combo(),10.,100.,SOURCE,POSITION),combination_id='positive',status=COMPUTED)
    negc=combo(qy=-1.,py=6.,a=2.)
    neg=dict(consumer.fields(negc,10.,100.,SOURCE,POSITION),combination_id='reversal',status=COMPUTED)
    consumer.validate_fields(neg,negc,10.,100.,SOURCE,POSITION)
    assert neg['biaxial_pending']['missing']==['weak_negative']
    rows=replace_biaxial_rows([], [pos,neg],None)
    assert rows[0]['Situação'].startswith('Parcial')


def test_classifier_is_independent_of_positive_moment():
    c=combo();r=consumer.fields(c,10.,100.,SOURCE,{'applicable':False})
    assert r=={}
    forged=consumer.fields(c,10.,100.,SOURCE,POSITION)
    with pytest.raises(ValueError):consumer.validate_fields(forged,c,10.,100.,SOURCE,{'applicable':False})


def test_zero_capacity_omitted_without_fake_Me():
    c=combo(qy=0.);r=consumer.fields(c,10.,100.,SOURCE,POSITION)
    consumer.validate_fields(r,c,10.,100.,SOURCE,POSITION)
    cap=r['biaxial']['weak_axis_capacities']['positive']
    assert cap=={'MRd_Nmm':None}


@pytest.mark.parametrize('mutation',[
    lambda r:r['biaxial']['positive_arithmetic_certificate']['envelope_certificate'].pop(),
    lambda r:r['biaxial'].update(governing=dict(x_mm=0.,Mx_Nmm=0.,My_Nmm=0.,index=0.)),
    lambda r:r['biaxial'].update(whole_member_approved=True),
    lambda r:r['biaxial'].update(extra_approval=True),
    lambda r:r.update(biaxial_pending={}),
])
def test_outer_promotion_or_false_maximum_rejected(mutation):
    c=combo();r=copy.deepcopy(consumer.fields(c,10.,100.,SOURCE,POSITION));mutation(r)
    with pytest.raises(ValueError):consumer.validate_fields(r,c,10.,100.,SOURCE,POSITION)


@pytest.fixture(scope='module')
def integrated():
    import json
    from pathlib import Path
    from tercas import roof_top_nbr
    # Existing frozen synthetic Me certificate, not a real project.
    saved=json.loads((Path(__file__).parent/'fixtures/ue125_roof_nbr_v1_reader.json').read_text())
    return roof_top_nbr.attach(saved)


def test_full_consumer_roundtrip_report_and_no_solver(integrated,monkeypatch):
    import json
    from tercas import roof_top_nbr as nbr,roof_top_load as roof
    from tercas.roof_top_nbr_ui import report,presentation_inclination
    from docx import Document
    def fail(*args,**kwargs):raise AssertionError('Reader called solver')
    monkeypatch.setattr(roof,'refined',fail);monkeypatch.setattr(nbr,'flt_mse',fail)
    e=nbr.preserved(json.loads(json.dumps(integrated,allow_nan=False)))
    assert e['source_section']['kind']==consumer.KIND
    row=e['records'][0]
    assert row['biaxial']['governing']['index']>0
    assert row['MRd_bending_component_Nmm']==min(row['MRd_section_effective_Nmm'],row['MRd_distortional_Nmm'],row['FLT']['MRd_flt_Nmm'])
    assert e['whole_member_approved'] is False
    doc=Document();report(doc,integrated)
    assert 'Interação §9.9:' in '\n'.join(p.text for p in doc.paragraphs)
    updated=presentation_inclination(integrated,{'ELU':{'states':[]}})
    assert updated['ELU']['weak_axis_capacities']['positive']['annex_e']=={}


@pytest.mark.parametrize('mutation',[
    lambda r:r['roof_top_nbr_component']['records'][0]['biaxial']['positive_arithmetic_certificate']['envelope_certificate'].pop(),
    lambda r:r['roof_top_nbr_component']['records'][0]['biaxial']['positive_arithmetic_certificate']['sign_certificate'][0].update(after_P=0),
    lambda r:r['roof_top_nbr_component']['records'][0]['biaxial'].update(governing=dict(x_mm=0.,Mx_Nmm=0.,My_Nmm=0.,index=0.)),
    lambda r:r['roof_top_nbr_component']['source_section']['weak_positive_reference'].update(MRd_positive_reference_Nmm=1e20),
    lambda r:r['roof_top_nbr_component']['records'][0].pop('biaxial'),
])
def test_integrated_rehash_cannot_forge_positive(integrated,mutation):
    from tercas import roof_top_nbr as nbr
    from test_roof_catalog_nbr import rehash
    r=copy.deepcopy(integrated);mutation(r);rehash(r)
    with pytest.raises(ValueError):nbr.preserved(r)


@pytest.mark.parametrize('sign',[1,-1,0])
def test_fresh_synthetic_solver_sign_routes(sign):
    from test_roof_catalog_nbr import inputs
    from tercas import roof_top_load as roof,roof_top_nbr as nbr
    from tercas.application import calculate
    d=inputs(parallel=sign*.03)
    d.update(P_parallel_uls=sign*3.,P_parallel_sls=sign*1.)
    r=nbr.attach(roof.attach(calculate(d)));e=nbr.preserved(r)
    assert e['whole_member_approved'] is False
    assert len(e['records'])==1 and e['ignored_ELS_cases']==1
    if sign>0:
        assert e['records'][0]['biaxial']['governing']['My_Nmm']>0
    elif sign<0:
        assert e['records'][0]['status']=='pending'
        assert 'biaxial' not in e['records'][0]
    else:
        assert e['records'][0]['status']==nbr.COMPUTED
        assert 'biaxial' not in e['records'][0]
        assert e['records'][0]['MRd_bending_component_Nmm']>0


@pytest.mark.parametrize('only_ELS',[False,True])
def test_area_inventory_and_prescribed_P_positions(only_ELS):
    from test_roof_catalog_nbr import inputs
    from tercas import roof_top_load as roof,roof_top_nbr as nbr
    from tercas.batch import calculate_batch
    from tercas.global_verification import build_global_verification
    d=inputs();d.update(load_mode='area',
        selected_types=['ELS quase permanente'] if only_ELS else ['ELU normal','ELS quase permanente'],
        area_inputs=dict(spacing_m=1.5,permanent_kgf_m2=8.,live_kgf_m2=25.,wind_up_kgf_m2=60.,wind_down_kgf_m2=40.),
        inclination=dict(value=5.,unit='degrees',spacing_basis='roof',permanent_basis='roof',live_basis='horizontal',wind_basis='roof'))
    r=nbr.attach(roof.attach(calculate_batch(d)));ev=nbr.preserved(r)
    inventory=roof.combination_inventory(r)
    assert [(row['combination_id'],row['limit_state']) for row in ev['records']]==[(c['id'],c['limit_state']) for c in inventory if c['limit_state']=='ELU']
    assert ev['ignored_ELS_cases']==2
    if only_ELS:
        assert ev['records']==[] and ev['status']=='no_ELU_selected'
        assert 'missing_limit_state:ELU' in build_global_verification(r)['pending_ids']
    else:
        assert ev['computed_cases']==40 and ev['pending_cases']==0
        assert all('biaxial' in row for row in ev['records']), [(row['combination_id'],row.get('biaxial_pending')) for row in ev['records'] if 'biaxial' not in row]
        assert {c['point_position'] for c in inventory if c.get('point_position')} >= {'support_limit','center'}
        for row,c in zip(ev['records'],[c for c in inventory if c['limit_state']=='ELU']):
            assert row['source_combination_sha256']==roof.digest(c)
            proof=row['biaxial']['positive_arithmetic_certificate']
            assert proof['minimum_My_Nmm']>=0
        r['global_verification']=build_global_verification(r);nbr.validate_saved_global(r)
        assert r['global_verification']['whole_member_approved'] is False
        assert 'torsion_warping' in r['global_verification']['pending_ids']


def test_zero_weak_report_states_reduction_without_invented_capacity(integrated,monkeypatch):
    from tercas import roof_top_nbr_ui as ui,roof_top_nbr as nbr
    from docx import Document
    evidence=copy.deepcopy(integrated[nbr.FIELD])
    evidence['records'][0].update(consumer.fields(combo(qy=0.),10.,100.,SOURCE,POSITION))
    # Presentation unit test, not a forged qualified snapshot.
    monkeypatch.setattr(ui,'preserved',lambda result:evidence)
    doc=Document();ui.report(doc,{})
    text='\n'.join(p.text for p in doc.paragraphs)
    assert 'MyRd=não exigido: My identicamente zero, redução ao ramo forte' in text
