"""Public routing, self-contained sources and snapshot-only family reports."""
import copy
import json
from io import BytesIO
from pathlib import Path
import shutil
import pytest
from docx import Document
from tercas import ue_family_reference as f
from tercas.application import calculate
from tercas.batch import calculate_batch
from tercas.report import word,batch_word


@pytest.fixture(scope='module')
def area_result():
    return calculate_batch(f.load_reference(2.65,3000.,5.))


def test_public_area_route_and_individual_provenance(area_result):
    r=area_result
    assert len(r['cases'])==58
    assert r['app_route_connected'] is True and r['requires_research_adapter'] is False
    for k in ('whole_member_approved','combined_ELS_approved','torsion_physical_loading_qualified'):
        assert r[k] is False
    assert r['weak_critical_reference'] is None and r['strong_critical_reference'] is None
    rec=r['ue_family_reference_evidence']
    assert rec['weak_web_Mdist_identified_Nmm'] is None and rec['strong_Table14_exemption'] is False
    assert rec['model']['t_mm']==2.65
    s=r['common_input_snapshot']['selected_section']
    assert s['entry_id']==rec['reference_id']
    assert all('Referência própria' in v['origin'] and rec['reference_id'] in v['origin'] for v in s['fields'].values())
    for c in r['cases']:
        if c['combination']['limit_state']=='ELS':
            assert c['evidence']['ELS'].get('index') is None
            assert all(row['Índice'] is None for row in c['rows'])
        else:
            assert c['evidence']['NBR_branches']['distortional']['status']=='computed'


def test_public_direct_route_and_uniaxial_els_criterion():
    d=f.load_reference(3.35,4000.,0.)
    d.update(load_mode='direct',q_uls=.2,q_sls=.1,P_uls=150.,P_sls=100.)
    r=calculate(d)
    assert r['ue_family_reference_evidence']['model']['t_mm']==3.35
    assert r['ELS'].get('index') is not None
    d['q_parallel_sls']=.05
    q=calculate(d)
    assert q['ELS'].get('index') is None
    assert q['whole_member_approved'] is False


@pytest.mark.parametrize('variant',['marked','marker_only','model_only','documents_only','evidence_only','mixed_old'])
def test_all_public_entrypoints_reject_invalid_family_claims(variant):
    from tercas.application import defaults
    from tercas.catalog_scan import scan_catalog,inputs_for_section
    from tercas.three_girt_application import calculate as three
    d=defaults(20);d['load_mode']='area'
    source=f.load_reference(1.5)
    if variant=='marked':d=source;d['properties']['G_MPa']=77000.
    elif variant=='marker_only':d[f.FIELD]=source[f.FIELD]
    elif variant=='model_only':d['ue_family_model']=source['ue_family_model']
    elif variant=='documents_only':d['ue_family_sources']=source['ue_family_sources']
    elif variant=='evidence_only':d['ue_family_reference_evidence']={}
    else:
        from tercas.ue_reference import load_reference
        d=load_reference();d[f.FIELD]=source[f.FIELD]
    before=copy.deepcopy(d)
    for action in (lambda:calculate(d),lambda:calculate_batch(d),lambda:three(d),
                   lambda:scan_catalog(d),lambda:inputs_for_section(d,21)):
        with pytest.raises(ValueError):action()
        assert d==before


@pytest.mark.parametrize('name',['elastic_registry.json','consumption_decision.json','independent_resistance_receipt.json','sources.json'])
def test_packaged_source_tamper_fails_without_research_access(tmp_path,monkeypatch,name):
    target=tmp_path/'data';shutil.copytree(f.ROOT,target)
    monkeypatch.setattr(f,'ROOT',target)
    assert len(f.gate())==6
    (target/name).write_bytes((target/name).read_bytes()+b' ')
    with pytest.raises(ValueError):f.reference(1.5)


def test_sources_work_in_relocated_data_directory(tmp_path,monkeypatch):
    baseline=f.reference(2.25,4750.)
    target=tmp_path/'only_packaged_sources';shutil.copytree(f.ROOT,target)
    monkeypatch.setattr(f,'ROOT',target)
    assert f.reference(2.25,4750.)==baseline


def test_word_is_snapshot_only_and_has_no_legacy_source_claim(area_result,monkeypatch):
    monkeypatch.setattr(f,'gate',lambda:(_ for _ in ()).throw(RuntimeError('current source deliberately unavailable')))
    content=batch_word(copy.deepcopy(area_result))
    doc=Document(BytesIO(content));text='\n'.join(p.text for p in doc.paragraphs)
    assert 'Família própria Ue100 — espessura 2.65 mm' in text
    assert 'piso elástico discreto próprio=5940000 Nmm' in text
    assert 'Mdist identificado nulo' in text
    assert 'Nenhuma dispensa da Tabela 14' in text
    assert 'sem índice ELS' in text
    assert 'NÃO É APROVAÇÃO GLOBAL' in text
    assert 'Ml,y — referência oficial adotada' not in text
    assert area_result['ue_family_reference_evidence']['reference_id'] in text


def test_exact_input_result_json_roundtrip(area_result):
    d=area_result['input_data']
    assert calculate_batch(json.loads(json.dumps(d)))==area_result
    assert json.loads(json.dumps(area_result))==area_result


def test_explicit_section_and_span_change_preserves_actions_not_floor():
    a=f.load_reference(1.5,4000.,-5.)
    a.update(project='Projeto preservado',q_uls=.1,x_uls=3500.,load_mode='direct')
    a['area_inputs']['permanent_kgf_m2']=17.
    b=f.apply_geometry(a,3.35,3000.)
    assert a['properties']['t']==1.5 and b['properties']['t']==3.35
    assert a['area_inputs']==b['area_inputs'] and a['project']==b['project']
    assert a['x_uls']==b['x_uls']==3500.
    assert a['weak_axis']['positive']['Mdist_Nmm']!=b['weak_axis']['positive']['Mdist_Nmm']
    assert a[f.FIELD]['reference_id']!=b[f.FIELD]['reference_id']
    assert f.assess(b)['active'] and not f.assess(b)['calculable']
