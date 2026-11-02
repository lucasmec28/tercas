"""Adopted U table overlay: identity, compatibility, legacy and output contracts."""
import copy,json
from io import BytesIO
from pathlib import Path
import pytest
from docx import Document
from tercas.application import defaults,build_spec,calculate,fingerprint
from tercas.catalogs import entries,critical_defaults
from tercas.core.local_table12 import local_critical
from tercas.catalog_scan import inputs_for_section,scan_catalog
from tercas.strong_pierin import reference_for_index,reference_for_inputs,qualify,SECTION_FIELDS
from tercas.batch import calculate_batch
from tercas.report import word,batch_word

U=next(i for i,e in enumerate(entries()) if e['family']=='U' and e['dimensions_mm']==dict(h=100,bf=50,lip=0,t=2))
MISSING=[i for i,e in enumerate(entries()) if e['family']=='U' and reference_for_index(i)['status']=='not_tabulated']


def legacy(index=U,E=200000.,scan=False):
    d=defaults(index);p=d['properties'];p['E_MPa']=E
    r=local_critical('U',p['h'],p['bf'],p['t'],p['Wx_cm3']*1000,E,D_mm=p['lip'])
    d.update(Ml_Nmm=r['Ml_Nmm'],critical_origin=critical_defaults(index)['critical_origin']+'; Ml calculado: '+r['origin'])
    if scan:d['critical_origin']+='; derivação com E do aço selecionado: '+r['origin']
    return d


def loaded(index=U):
    d=defaults(index);d.update(q_uls=.1,q_sls=.1,route_domain=True,ELS_limit_mm=3000/180,ELS_origin='synthetic L/180')
    d['segments']=[dict(start_mm=0.,end_mm=3000.,Ly_effective_mm=3000.,Lz_effective_mm=3000.,Cb_mode='one',restraint_provenance='synthetic')]
    return d


def test_exact_reference_inventory_units_and_missing_thickness():
    rows=[reference_for_index(i) for i in range(209)]
    assert sum(r['status']=='tabulated_adopted_reference' for r in rows)==124
    assert len(MISSING)==2
    assert [entries()[i]['name'] for i in MISSING]==['U 100 x 75 x 3,00','U 250 x 100 x 6,35']
    r=reference_for_index(U);assert r['Mlx_Nmm']==3510000 and r['Nl_N']==84160
    assert r['PDF_page']==9 and r['printed_page']==29 and r['table']==1
    assert r['source_E_MPa']==200000 and r['source_G_MPa'] is None and r['source_nu'] is None
    assert not r['axial_calculation_implemented'] and r['section_property_convention_pending']
    assert r['source_geometry_convention_unresolved'] and not r['whole_member_approved']
    r['dimensions_mm']['t']=200;assert reference_for_index(U)['dimensions_mm']['t']==2


def test_default_overlay_without_mutating_workbook_or_weak_reference():
    from tercas.weak_catalog import critical_hypothesis
    for i,e in enumerate(entries()):
        d=defaults(i);ref=reference_for_index(i);s=build_spec(d)
        assert d['Mdist_Nmm']==e['critical_values']['Mdist_Nmm']
        if ref['status']=='tabulated_adopted_reference':
            assert e['critical_values']['Ml_Nmm'] is None and e['critical_values']['Nl_N'] is None
            assert d['Ml_Nmm']==ref['Mlx_Nmm']==s['Ml']['value']
            assert d['critical_origin']==ref['source_origin']
            assert s['strong_critical_qualification']['fields']['Ml']['status']=='adopted_reference_original_configuration'
            assert not s['strong_critical_qualification']['warnings']
            assert critical_hypothesis(i)['positive']['Ml_Nmm'] is None
        elif e['family']=='U':
            assert 'Tabela 12' in d['critical_origin'] and s['Ml']['value']==d['Ml_Nmm']
        elif e['critical_values']['Ml_Nmm'] is not None:
            assert d['Ml_Nmm']==e['critical_values']['Ml_Nmm']


@pytest.mark.parametrize('key,value',[('E_MPa',100000.),('E_MPa',400000.),('G_MPa',38500.),('G_MPa',200000/2.6),('E_MPa',None),('G_MPa',None)])
def test_new_table_blocks_elastic_edits_without_fallback_or_mutation(key,value):
    d=loaded();d['properties'][key]=value;before=copy.deepcopy(d);z=calculate(d)
    assert d==before and z['input_data']==before
    assert z['input_snapshot']['Ml']['value'] is None
    assert z['NBR_branches']['local']['status']=='not_evaluated'
    assert z['ELS']['status']=='not_evaluated'
    assert all('index' not in f for f in z['FLT_segments'])
    assert z['strong_critical_reference']['use_status']=='not_evaluated_incompatible_pierin_reference'
    assert any('Sem escala nem fallback' in w for w in z['critical_warnings'])
    assert not z['whole_member_approved']


@pytest.mark.parametrize('field',SECTION_FIELDS)
def test_modified_section_properties_block_reference(field):
    d=defaults(U);d['properties'][field]=(d['properties'][field] or 1)+1
    effective,r=qualify(d);assert effective['value'] is None
    assert any(field in s for s in r['compatibility_reasons'])


def test_fy_fu_not_elastic_critical_parameters_and_restore():
    d=defaults(U);d['properties'].update(fy_MPa=345.,fu_MPa=450.)
    assert build_spec(d)['Ml']['value']==3510000
    d['properties']['E_MPa']=100000.;assert build_spec(d)['Ml']['value'] is None
    d['properties']['E_MPa']=200000.;assert build_spec(d)['Ml']['value']==3510000


@pytest.mark.parametrize('change',['origin','value','foreign_row','foreign_missing_row','foreign_Ue'])
def test_free_text_value_or_row_cannot_requalify_automatic_reference(change):
    d=defaults(U)
    if change=='origin':d['properties']['E_MPa']=100000.;d['critical_origin']='renamed free text'
    elif change=='value':d['Ml_Nmm']*=2
    else:
        target={'foreign_row':83,'foreign_missing_row':MISSING[0],'foreign_Ue':0}[change]
        fresh=defaults(target);d['catalog_index']=target;d['properties']=fresh['properties']
    before=copy.deepcopy(d);s=build_spec(d)
    assert s['Ml']['value'] is None and d==before


def test_independent_manual_different_value_not_relabelled_or_certified():
    d=loaded();d['properties']['E_MPa']=100000.
    d.update(Ml_Nmm=1234567.,critical_origin='Independent supplied elastic analysis for exact section; synthetic only')
    z=calculate(d);assert z['input_snapshot']['Ml']['value']==1234567
    assert z['strong_critical_reference']['use_status']=='reference_only_existing_input_preserved'
    assert z['strong_critical_reference']['compatibility_reasons']
    assert not z['whole_member_approved']


@pytest.mark.parametrize('E',[100000.,200000.,400000.])
def test_legacy_direct_and_recomputed_routes_are_preserved(E):
    d=legacy(E=E,scan=True);before=copy.deepcopy(d);s=build_spec(json.loads(json.dumps(d)))
    assert s['Ml']['value']==d['Ml_Nmm'] and d==before
    assert s['strong_critical_qualification']['fields']['Ml']['status']=='automatic_table12_recomputed_for_current_E'
    assert s['strong_critical_qualification']['pierin_U_reference']['use_status']=='reference_only_existing_input_preserved'
    old=legacy();old['properties']['E_MPa']=E
    assert (build_spec(old)['Ml']['value'] is not None)==(E==200000.)


def test_scan_reselection_is_explicit_adoption_not_legacy_rewrite():
    old=legacy(E=100000.,scan=True);before=copy.deepcopy(old)
    fresh=inputs_for_section(old,U)
    assert old==before and fresh['Ml_Nmm']==3510000 and fresh['properties']['E_MPa']==100000.
    assert build_spec(fresh)['Ml']['value'] is None
    assert 'Pierin2013' in fresh['critical_origin']
    scan=scan_catalog(old,[U]);assert not scan['rows'][0]['criteria_satisfied']
    assert scan['rows'][0]['strong_critical_reference']['use_status'].startswith('not_evaluated')
    assert any('nova seleção' in n for n in scan['notes'])
    for i in MISSING:
        d=inputs_for_section(old,i);assert build_spec(d)['Ml']['value']==d['Ml_Nmm']
        assert d['Ml_Nmm']>0 and 'Tabela 12' in d['critical_origin']


def test_outputs_trace_reference_and_distinguish_axial_document_only():
    d=loaded();z=calculate(d);r=z['strong_critical_reference']
    assert json.loads(json.dumps(z))['strong_critical_reference']==r
    assert not r['axial_calculation_implemented']
    assert r['Nl_N']==84160 and r['source_nu'] is None
    text='\n'.join(p.text for p in Document(BytesIO(word(z))).paragraphs)
    assert 'Mlx tabelado = 3,51' in text and 'Nl tabelado = 84,16' in text
    assert 'não há verificação axial' in text and 'linha média permanece pendente' in text
    d.update(load_mode='area',selected_types=['ELU normal','ELS rara']);b=calculate_batch(d)
    assert b['strong_critical_reference']['Nl_N']==84160
    assert all(c['evidence']['strong_critical_qualification']['pierin_U_reference']['id']==r['id'] for c in b['cases'])
    text='\n'.join(p.text for p in Document(BytesIO(batch_word(b))).paragraphs)
    assert 'Mlx tabelado = 3,51' in text and 'não há verificação axial' in text


def test_ui_legacy_does_not_upgrade_on_calculation_and_new_profile_adopts():
    from streamlit.testing.v1 import AppTest
    a=AppTest.from_file(str(Path(__file__).resolve().parents[1]/'app.py'))
    old=legacy();a.session_state.base=old;a.run(timeout=30)
    assert not a.exception
    assert any('entrada legada/manual preservada' in t.value for t in a.caption)
    next(b for b in a.button if b.label.startswith('Calcular')).click().run(timeout=30)
    assert not a.exception and a.session_state.result['input_data']['Ml_Nmm']==old['Ml_Nmm']
    assert a.session_state.result['strong_critical_reference']['use_status']=='reference_only_existing_input_preserved'


def test_hybrid_table12_origin_cannot_adopt_Pierin_by_numeric_edit():
    d=legacy(83);d['Ml_Nmm']=reference_for_index(83)['Mlx_Nmm']
    s=build_spec(d);assert s['Ml']['value'] is None
    assert qualify(d)[0]['value'] is None
    r=calculate_batch(dict(d,load_mode='area',selected_types=['ELU normal']))['strong_critical_reference']
    assert r['use_status']=='not_evaluated_incompatible_pierin_reference'
    assert 'Origem automática Tabela 12' in r['reason']


def test_verified_legacy_numeric_coincidence_does_not_change_source():
    original=legacy(83);target=reference_for_index(83)['Mlx_Nmm']
    E=200000.*target/original['Ml_Nmm']
    d=legacy(83,E=E,scan=True);assert d['Ml_Nmm']==pytest.approx(target)
    s=build_spec(d)
    assert s['Ml']['value']==d['Ml_Nmm']
    assert s['strong_critical_qualification']['fields']['Ml']['status']=='automatic_table12_recomputed_for_current_E'
    assert s['strong_critical_qualification']['pierin_U_reference']['legacy_table12_verified']
    assert qualify(d)[0] is None and not s['strong_critical_qualification']['warnings']
