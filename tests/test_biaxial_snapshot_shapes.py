"""Saved gross-biaxial records fail visibly without rerunning mechanics."""
import copy
from io import BytesIO
import pytest
from docx import Document
from tercas.application import calculate,rows
from tercas.batch import calculate_batch,governing
from tercas import ue_reference,ue_family_reference
from tercas.biaxial_component import activate,FIELD,ROW,digest,preserved_snapshot,presentation_rows
from tercas.report import word,batch_word
from tercas.global_verification import build_global_verification


@pytest.fixture(scope='module')
def direct_result():
    d=ue_family_reference.load_reference(1.5,4000.,5.)
    d.update(load_mode='direct',q_sls=.1,q_parallel_sls=.03,P_sls=100.,P_parallel_sls=-20.,x_sls=1700.)
    return calculate(activate(d))


@pytest.fixture(scope='module')
def area_result():
    return calculate_batch(activate(ue_reference.load_reference(angle=5.,L_mm=4000.)))


def reseal(r):
    ev=r[FIELD];ev['snapshot_sha256']=digest({k:v for k,v in ev.items() if k!='snapshot_sha256'})


def refuse(r,monkeypatch):
    from tercas.biaxial_gross import gross_mle,tensor_beam
    def forbidden(*a,**k):pytest.fail('Saved-record presentation must not recalculate')
    monkeypatch.setattr(gross_mle,'assess_case',forbidden)
    monkeypatch.setattr(gross_mle,'load_geometry',forbidden)
    monkeypatch.setattr(tensor_beam,'solve_response',forbidden)
    before=copy.deepcopy(r)
    with pytest.raises(ValueError):preserved_snapshot(r)
    shown=presentation_rows(r,r['summary']) if 'cases' in r else rows(r)
    normal=next(x for x in shown if x['Verificação']==ROW)
    assert normal['Índice'] is None and 'inválido' in normal['Situação']
    gv=build_global_verification(r)
    assert gv['whole_member_approved'] is False and gv['combined_ELS_approved'] is False
    blob=(batch_word if 'cases' in r else word)(r)
    doc=Document(BytesIO(blob))
    assert any('Registro da componente biaxial inválido' in p.text for p in doc.paragraphs)
    assert r==before


@pytest.mark.parametrize('kind',['null_walls','string_walls','dict_walls','extrema_array','displacement_array','normal_array'])
def test_rehashed_nested_shapes_fail_visibly(direct_result,monkeypatch,kind):
    r=copy.deepcopy(direct_result);e=r[FIELD]['records']['DIRECT_ELS']
    if kind=='null_walls':e['screen']['walls']=[None]*5
    elif kind=='string_walls':e['screen']['walls']='12345'
    elif kind=='dict_walls':e['screen']['walls']={str(i):None for i in range(5)}
    elif kind=='extrema_array':e['response']['extrema']=[]
    elif kind=='displacement_array':e['response']['extrema']['displacement']=[]
    else:e['response']['extrema']['displacement']['normal']=[]
    reseal(r);refuse(r,monkeypatch)


@pytest.mark.parametrize('kind',['missing','force_zero','flag_number','wrong_side','reaction_zero'])
def test_support_layer_is_not_optional_or_replaceable(area_result,monkeypatch,kind):
    r=copy.deepcopy(area_result)
    e=next(x for x in r[FIELD]['records'].values() if x['case']['point_position']=='support_limit')
    response=e['response'];layer=response['support_transfer_limit']
    if kind=='missing':response.pop('support_transfer_limit')
    elif kind=='force_zero':layer['original_P_N']=[0.,0.]
    elif kind=='flag_number':layer['finite_point_on_support']=0
    elif kind=='wrong_side':layer['V_before_N']=layer['V_after_N']
    else:response['reactions_N']['left']=[0.,0.]
    reseal(r);refuse(r,monkeypatch)


@pytest.mark.parametrize('kind',['reaction_array','reaction_bool','invented_layer'])
def test_finite_point_keeps_its_own_reactions_and_no_limit_layer(direct_result,monkeypatch,kind):
    r=copy.deepcopy(direct_result);response=r[FIELD]['records']['DIRECT_ELS']['response']
    if kind=='reaction_array':response['reactions_N']=[]
    elif kind=='reaction_bool':response['reactions_N']['left'][0]=True
    else:response['support_transfer_limit']={}
    reseal(r);refuse(r,monkeypatch)


@pytest.mark.parametrize('bad',[None,[],123,'',' '])
def test_inconclusive_reason_must_be_text_even_with_consistent_links(area_result,monkeypatch,bad):
    r=copy.deepcopy(area_result)
    cid=next(k for k,v in r[FIELD]['records'].items() if not v['qualified_gross_flexural_component'])
    r[FIELD]['records'][cid]['reason']=bad
    c=next(x for x in r['cases'] if x['combination']['id']==cid)
    c['evidence']['ELS']['reason']=bad;c['rows'][0]['Observação']=bad
    r['summary']=governing(r['cases'])
    reseal(r);refuse(r,monkeypatch)


def test_reference_label_cannot_break_presentation_when_links_are_resealed(direct_result,monkeypatch):
    r=copy.deepcopy(direct_result);r[FIELD]['reference_id']=None
    r[FIELD]['records']['DIRECT_ELS']['reference_id']=None
    reseal(r);refuse(r,monkeypatch)
