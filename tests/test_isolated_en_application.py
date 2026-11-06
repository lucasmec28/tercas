import copy
import json
from io import BytesIO
import pytest
from docx import Document

from tercas import isolated_en_application as en, isolated_en_stress as bound
from tercas import isolated_en_ui as ui, aisi_torsion_component as aisi
from tercas import ue_family_reference as family
from tercas.application import calculate
from tercas.study_completion import complete_result
from test_direct_torsion import inputs
from test_torsion_nominal_integration import inputs as area_inputs


def declared(data):
    data[en.CHOICE]=en.choice(data,declared=True,origin='Hipótese sintética explícita: seção intacta, sem furos.')
    return data


def run(data):return complete_result(calculate(data))


@pytest.fixture(scope='module')
def direct():return run(declared(inputs(P=20.)))


@pytest.fixture(scope='module')
def area():
    d=declared(area_inputs());d['selected_types']=['ELU normal']
    return complete_result(family.calculate_reference(d))


def test_direct_chain_and_material(direct):
    ev=en.preserved(direct)
    assert ev['computed_cases']==1 and ev['ELS_cases_excluded']==1 and ev['pending_cases']==0
    assert ev['source_fy_MPa']==250. and ev['material']==en.MATERIAL
    assert aisi.preserved(direct)['H4_computed_cases']==1
    assert 'torsion_warping' in direct['global_verification']['pending_ids']
    assert not direct['whole_member_approved']
    assert en.preserved(json.loads(json.dumps(direct)))==ev


def test_area_inventory_and_support_limit_complete(area):
    ev=en.preserved(area)
    expected=[c['combination']['id'] for c in area['cases'] if c['combination']['limit_state']=='ELU']
    assert [r['combination_id'] for r in ev['records']]==expected
    assert ev['computed_cases']==len(expected) and not ev['pending_cases']
    assert any(c['combination'].get('point_position')=='support_limit' for c in area['cases'])
    assert all(r['check']['full_member_field_covered'] for r in ev['records'])
    assert aisi.preserved(area)


def test_absent_disabled_legacy_and_missing_declaration():
    d=inputs();r=run(d);assert en.FIELD not in r and en.CHOICE not in r['input_data']
    d[en.CHOICE]=en.choice(d,enabled=False);r=run(d);assert en.FIELD not in r
    d[en.CHOICE]=en.choice(d);r=run(d);ev=en.preserved(r)
    assert not ev['computed_cases'] and ev['pending_cases']==1
    assert 'Declaração' in ev['reason']
    d=declared(inputs());d.pop('direct_load_basis');r=run(d)
    assert en.preserved(r)['computed_cases']==0


def test_material_and_incompatible_reference_fail_closed(direct):
    from tercas.application import fingerprint
    for key,value in [('fy_MPa',350.),('fy_MPa',True)]:
        r=copy.deepcopy(direct);r.pop(en.FIELD);r['input_data']['properties'][key]=value
        r['input_data'][en.CHOICE]=en.choice(r['input_data'],declared=True,origin='QA')
        r['input_fingerprint']=fingerprint(r['input_data']);r=en.finalize(r)
        assert r[en.FIELD]['computed_cases']==0 and 'Material fora' in r[en.FIELD]['reason']
    r=copy.deepcopy(direct);r.pop(en.FIELD);r['input_data'].pop('ue_family_reference')
    r['input_data'][en.CHOICE]=en.choice(r['input_data'],declared=True,origin='QA')
    r['input_fingerprint']=fingerprint(r['input_data']);r=en.finalize(r)
    assert 'Sem referência' in r[en.FIELD]['reason']


def test_section_span_and_application_changes():
    from tercas.ue_member_application import apply
    d=declared(inputs());same=family.apply_span(d,4500.)
    assert same[en.CHOICE]==d[en.CHOICE]
    other=family.apply_geometry(d,2.25,4000.)
    assert other[en.CHOICE]['enabled'] and not other[en.CHOICE]['intact_section_model_declared']
    assert other[en.CHOICE]['model_origin']==''
    wall=apply(d,'wall_girt')
    assert wall[en.CHOICE]['enabled'] and not wall[en.CHOICE]['intact_section_model_declared']


def reseal(r):
    ev=r[en.FIELD]
    for row in ev['records']:
        check=row.get('check')
        if check:check['content_sha256']=bound._sha({k:v for k,v in check.items() if k!='content_sha256'})
    ev['snapshot_sha256']=en.digest({k:v for k,v in ev.items() if k!='snapshot_sha256'})


@pytest.mark.parametrize('mutation',['index','status','flags','scope','material','inventory','choice','count','control','dense_hash','case','summary'])
def test_rehashed_corruption_rejected(direct,mutation):
    r=copy.deepcopy(direct);ev=r[en.FIELD];row=ev['records'][0];c=row['check']
    if mutation=='index':c['criteria']['normal']['index_upper_bound']=0.
    elif mutation=='status':c['criteria']['normal']['criterion']='failed'
    elif mutation=='flags':c['whole_member_approved']=True
    elif mutation=='scope':c['excluded']=[]
    elif mutation=='material':c['material']['fyb_MPa']=300.
    elif mutation=='inventory':ev['records']=[]
    elif mutation=='choice':ev['configuration']['model_origin']='Outra origem'
    elif mutation=='count':ev['computed_cases']=99
    elif mutation=='control':c['criteria']['normal']['bound_control']['is_physical_state']=True
    elif mutation=='dense_hash':row['source_analysis_sha256']='a'*64
    elif mutation=='case':c['combination_id']='OTHER'
    elif mutation=='summary':r['torsion_evidence']['records'][0]['analysis']['E_MPa']=1.
    reseal(r)
    with pytest.raises(ValueError):en.preserved(r)


def test_saved_ui_word_no_solver_sources_or_sections(direct,monkeypatch):
    from tercas import torsion_study
    from tercas.three_girt_en_normal import en1993_normal_components
    def fail(*a,**kw):raise AssertionError('Reading saved EN must not calculate')
    monkeypatch.setattr(en,'check_member',fail)
    monkeypatch.setattr(torsion_study,'section_for',fail)
    monkeypatch.setattr(en1993_normal_components,'build_component_sections',fail)
    before=copy.deepcopy(direct);ev=en.preserved(direct);doc=Document();ui.report(doc,direct)
    text='\n'.join(p.text for p in doc.paragraphs)
    assert 'DIRECT_ELU' in text and '144,337567' in text and 'inconclusivo' in text
    assert ui.rows(ev)[0]['Teto cisalhamento EN']>0
    assert direct==before


def test_global_inventory_reports_covered_stresses_without_approval(direct):
    en.validate_saved_global(direct)
    record=next(c for c in direct['global_verification']['checks'] if c['id']=='torsion_warping')
    assert record['status']=='pending' and record['index'] is None
    assert 'Tensões EN §6.1.6 avaliadas em 1' in record['reason']
    assert 'EN6.1.5' in record['reason'] and 'EN6.1.10' in record['reason']
    r=copy.deepcopy(direct);r['global_verification']['isolated_EN_binding']['snapshot_sha256']='a'*64
    with pytest.raises(ValueError,match='snapshots diferentes'):en.validate_saved_global(r)


def test_source_summary_limit_cannot_be_removed_even_with_all_hashes_refreshed(area):
    r=copy.deepcopy(area);ev=r[en.FIELD]
    source=next(s for s in r['torsion_evidence']['records'] if s['analysis'] and s['analysis'].get('support_limit_states'))
    source['analysis']['support_limit_states']=[]
    row=next(x for x in ev['records'] if x['combination_id']==source['combination_id'])
    row['source_summary_record_sha256']=en.digest(source)
    ev['source_torsion_snapshot_sha256']=en.digest(r['torsion_evidence'])
    reseal(r)
    with pytest.raises(ValueError,match='before-P'):en.preserved(r)


@pytest.mark.parametrize('malformed',[None,'invalid',True,[]])
def test_malformed_network_marker_yields_controlled_pending(direct,malformed):
    from tercas.application import fingerprint
    r=copy.deepcopy(direct);r.pop(en.FIELD)
    r['input_data']['three_girt_model']=malformed
    r['input_fingerprint']=fingerprint(r['input_data'])
    out=en.finalize(r)
    assert out['input_data']['three_girt_model']==malformed
    assert not out[en.FIELD]['computed_cases'] and 'malformado' in out[en.FIELD]['reason']
    assert en.preserved(out)['pending_cases']==1
