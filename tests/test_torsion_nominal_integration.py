import copy
import json
from io import BytesIO
from decimal import Decimal
import pytest
from docx import Document
from tercas import ue_family_reference as family, torsion_study as torsion
from tercas.application import fingerprint
from tercas.study_completion import complete_result
from tercas.torsion_material import FIELD, deepen, preserved_details, available_cases
from tercas.torsion_material_ui import text_lines, bound


def inputs():
    d=family.load_reference(1.5,4000.,5.)
    d[torsion.FIELD]=torsion.blank_choice()
    d[torsion.FIELD]['load_lines']={r:dict(declared=True,xy_from_CG_mm=[2.*i-3.,i-2.],
        origin='Synthetic QA declaration, not a real project') for i,r in enumerate(torsion.ROLES)}
    return d


@pytest.fixture(scope='module')
def base():return complete_result(family.calculate_reference(inputs()))


@pytest.fixture(scope='module')
def detailed(base):return deepen(base,available_cases(base)[0])


def test_detail_is_opt_in_and_original_snapshot_is_unchanged(base,detailed):
    assert FIELD not in base and len(available_cases(base))==58
    assert {k:v for k,v in detailed.items() if k!=FIELD}==base
    assert detailed['global_verification']==base['global_verification']
    assert json.loads(json.dumps(detailed,allow_nan=False))==detailed
    packet=next(iter(preserved_details(detailed).values()))
    assert packet['all_existing_strength_and_ELS_results_unchanged']
    assert packet['source_combination']==base['cases'][0]['combination']
    assert packet['material_envelope']['fy_MPa']==base['input_data']['properties']['fy_MPa']
    assert packet['normative_resistance_qualified'] is False
    assert packet['whole_member_approved'] is False
    assert packet['material_envelope']['resistance_factor_applied'] is False


def test_only_selected_case_is_rebuilt_and_previous_detail_retained(base,detailed,monkeypatch):
    from tercas.torsion_vlasov import case_study
    old=case_study.attach_torsion_evidence;calls=[]
    def spy(source,**kw):
        calls.append([c['combination']['id'] for c in source['cases']])
        return old(source,**kw)
    monkeypatch.setattr(case_study,'attach_torsion_evidence',spy)
    selected=available_cases(base)[1];before=copy.deepcopy(detailed)
    out=deepen(detailed,selected)
    assert calls==[[selected]] and detailed==before
    assert len(preserved_details(out))==2
    assert {k:v for k,v in out.items() if k!=FIELD}==base


def test_selected_support_limit_preserves_pre_point_layer(base):
    case=next(c['combination'] for c in base['cases'] if c['combination'].get('point_position')=='support_limit'
              and c['combination'].get('P_N'))
    packet=preserved_details(deepen(base,case['id']))[case['id']]
    assert packet['source_combination']==case
    assert any(a.get('s_mm')==0. for a in packet['source_actions'] if a['kind']=='point')
    assert packet['source_analysis_domain']==next(r['analysis']['analysis_domain'] for r in base['torsion_evidence']['records'] if r['combination_id']==case['id'])


@pytest.mark.parametrize('mutation',['fingerprint','line','support','source_field','case_id'])
def test_invalid_reconstruction_fails_without_mutating_base(base,mutation):
    bad=copy.deepcopy(base);case=available_cases(base)[0]
    if mutation=='fingerprint':bad['input_data']['L_mm']+=1
    elif mutation=='line':bad['torsion_evidence']['load_lines']['CP']['xy_mm'][0]+=1
    elif mutation=='support':bad['torsion_evidence']['supports']['left']['warping']='fixed'
    elif mutation=='source_field':bad['torsion_evidence']['records'][0]['analysis']['max_abs_phi']['phi_rad']+=.01
    else:case='not-existing'
    before=copy.deepcopy(bad)
    with pytest.raises((ValueError,KeyError)):deepen(bad,case)
    assert bad==before


@pytest.mark.parametrize('mutation',['fingerprint','case','approved'])
def test_stale_or_unqualified_details_are_not_rendered(detailed,mutation):
    bad=copy.deepcopy(detailed)
    packet=next(iter(bad[FIELD]['records'].values()))
    if mutation=='fingerprint':bad[FIELD]['source_input_fingerprint']='stale'
    elif mutation=='case':packet['source_combination']['q_kN_m']+=1
    else:packet['whole_member_approved']=True
    with pytest.raises(ValueError):preserved_details(bad)


def test_material_text_and_word_do_not_recompute(detailed,monkeypatch):
    import tercas.torsion_material as module
    from tercas.report import batch_word
    def forbidden(*a,**k):raise AssertionError('An export must not solve anything')
    monkeypatch.setattr(module,'deepen',forbidden)
    before=copy.deepcopy(detailed);packet=next(iter(preserved_details(detailed).values()))
    text='\n'.join(text_lines(packet))
    assert 'sem coeficiente de resistência' in text and 'inclusive PP' in text
    doc=Document(BytesIO(batch_word(detailed)));alltext='\n'.join(p.text for p in doc.paragraphs)
    assert 'Tensões concomitantes — referência nominal de material' in alltext
    assert 'não é resistência NBR' in alltext and 'fibra exterior' in alltext
    assert detailed==before


@pytest.mark.parametrize('v',[0.,.00001,.113239,123.001,-.113239,-123.001])
def test_displayed_interval_rounds_outwards(v):
    lo=Decimal(bound(v).replace(',','.'));hi=Decimal(bound(v,True).replace(',','.'))
    assert lo<=Decimal.from_float(v)<=hi


def test_no_field_is_offered_when_torsion_disabled_or_pending():
    raw=family.calculate_reference(family.load_reference(1.5))
    assert available_cases(raw)==[] and preserved_details(raw)=={}
    d=inputs();d[torsion.FIELD]['load_lines']={}
    out=complete_result(family.calculate_reference(d))
    assert available_cases(out)==[]
    with pytest.raises(ValueError):deepen(out,out['cases'][0]['combination']['id'])
