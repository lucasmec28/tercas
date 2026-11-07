"""Synthetic EN300 opt-in, persistence and presentation integration."""
import copy
import json
import pytest
from docx import Document
from tercas import isolated_en_ue125_300_application as en
from tercas import isolated_en_ue125_300_ui as ui
from tercas import isolated_en_ue_catalog_application as old
from tercas import ue_catalog_reference as own
from en_ue_test_helpers import inputs,run


def data():
    d=inputs(26);d['properties'].update(fy_MPa=300.,fu_MPa=400.)
    d['steel_name']='USI-CIVIL 300';d=own.activate(d)
    d[en.CHOICE]=en.choice(d,declared=True,origin='Synthetic nominal intact QA')
    return d


@pytest.fixture(scope='module')
def result():return run(data())


def test_explicit_material_and_no_inherited_declaration():
    d=data();assert en._domain(d,en.configuration(d)) is None
    d.pop(en.CHOICE);d[old.CHOICE]=old.choice(d,declared=True,origin='Historical250')
    assert en.configuration(d) is None
    d[en.CHOICE]=en.choice(d,declared=True,origin='New300');d['properties']['fu_MPa']=410.
    assert en.reset_changed_declaration(d)
    assert not d[en.CHOICE]['intact_section_model_declared']
    assert en._domain(d,en.configuration(d))


def test_dense_snapshot_roundtrip_without_solver(result,monkeypatch):
    from tercas import direct_torsion,catalog_torsion_section,en_ue125_300_builder
    def fail(*a,**k):raise AssertionError('Saved readers must not solve or build')
    monkeypatch.setattr(direct_torsion,'solve_member',fail)
    monkeypatch.setattr(catalog_torsion_section,'prepare',fail)
    # The authority validates the frozen builder file, but must never call it.
    for name in ('build','build_qualified_component_sections'):
        if hasattr(en_ue125_300_builder,name):monkeypatch.setattr(en_ue125_300_builder,name,fail)
    r=json.loads(json.dumps(result));ev=en.preserved(r)
    assert ev['computed_cases']==1 and ev['ELS_cases_excluded']==1
    assert old.FIELD not in r
    check=ev['records'][0]['check'];assert check['material']==en.MATERIAL
    assert check['source_analysis_material']==dict(E_MPa=200000.,G_MPa=77000.)
    assert check['source_analysis_sha256']==ev['records'][0]['source_analysis_sha256']
    assert all(ev[k] is False for k in en.FLAGS)
    doc=Document();ui.report(doc,r);text='\n'.join(p.text for p in doc.paragraphs)
    assert ui.TITLE in text and '300 MPa' in text and 'DIRECT_ELU' in text and 'Denominadores' in text
    from tercas.isolated_en_application import validate_saved_global
    validate_saved_global(r)
    assert r['global_verification']['whole_member_approved'] is False


@pytest.mark.parametrize('mutation',['profile','material','option','normal','count','hash'])
def test_saved_binding_rejects_changes(result,mutation):
    r=copy.deepcopy(result)
    if mutation=='profile':r['input_data']['ue_catalog_reference']['catalog_index']=25
    elif mutation=='material':r['input_data']['properties']['fy_MPa']=250.
    elif mutation=='option':r['input_data'][en.CHOICE]['enabled']=False
    elif mutation=='normal':r[en.FIELD]['normal_snapshot']['material']['fyb_MPa']=250.
    elif mutation=='count':r[en.FIELD]['computed_cases']=0
    else:r[en.FIELD]['records'][0]['source_analysis_sha256']='0'*64
    with pytest.raises(ValueError):en.preserved(r)


def test_only_els_never_qualifies_section():
    d=data();d.update(load_mode='area',selected_types=['ELS quase permanente'])
    d=own.activate(d);d=en.activate(d,model_origin='Synthetic ELS-only QA')
    r=run(d);ev=en.preserved(r)
    assert ev['ELU_cases']==0 and ev['computed_cases']==0 and ev['ELS_cases_excluded']>0
    context=en.global_context(r,sectional=True)
    assert context['sectional']['joint_sufficient'] is False
    assert 'Nenhuma combinação ELU' in context['reason']
    assert 'Nenhum caso ELU' in '\n'.join(ui.text_lines(ev))


def test_activate_only_adds_choice():
    d=data();d.pop(en.CHOICE);before=copy.deepcopy(d)
    changed=en.activate(d,model_origin='Synthetic explicit new declaration')
    assert d==before and changed.pop(en.CHOICE)['intact_section_model_declared'] is True
    assert changed==before


@pytest.mark.parametrize('change',['uniform_couple','point_couple','warping','twist','missing_support','rotation_warning','normative','physical'])
def test_original_torsion_hypothesis_contract(change):
    d={'roof_top_load':dict(schema='roof_top_load_v1',enabled=True,load_line='web_midplane',
        end_restraint='fork_free_warping',intermediate_restraints='none')}
    source=dict(numerics=dict(rotation_warning_rad=.05,rotation_warning_is_normative_limit=False),
        analysis_domain=dict(small_rotation_kinematics=True,physical_hypotheses_verified=False),loads=[dict(kind='uniform',couple_N=0.),dict(kind='point',couple_Nmm=0.)],
        support_hypotheses={side:dict(twist='fixed',warping='free_assumed') for side in ('left','right')})
    en._validate_source_contract(source,d)
    if change=='uniform_couple':source['loads'][0]['couple_N']=.1
    elif change=='point_couple':source['loads'][1]['couple_Nmm']=.1
    elif change=='warping':source['support_hypotheses']['left']['warping']='restrained_assumed'
    elif change=='twist':source['support_hypotheses']['right']['twist']='free'
    elif change=='missing_support':source['support_hypotheses'].pop('left')
    elif change=='rotation_warning':source['numerics']['rotation_warning_rad']=1.
    elif change=='normative':source['numerics']['rotation_warning_is_normative_limit']=True
    else:source['analysis_domain']['physical_hypotheses_verified']=True
    with pytest.raises(ValueError):en._validate_source_contract(source,d)
