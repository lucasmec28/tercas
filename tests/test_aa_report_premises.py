"""Editorial R3: AA ceilings never inherit the gross-only Word premise."""
import copy
from io import BytesIO
import pytest
from docx import Document
from tercas import aa_component as aa, biaxial_component as gross
from tercas import ue_reference as ue, ue_family_reference as family
from tercas.application import calculate
from tercas.batch import calculate_batch
from tercas.ue_member_application import apply
from tercas.study_completion import complete_result
from tercas.report import word, batch_word

NOTICE='O resumo global reproduz o estado originalmente salvo.'


def text(blob):
    d=Document(BytesIO(blob))
    return '\n'.join([p.text for p in d.paragraphs]+[c.text for t in d.tables for r in t.rows for c in r.cells])


def inputs(mode,application='wall_girt',batch=False):
    L=6000. if mode==aa.POSITIVE_MODE else 4000.
    d=ue.load_reference(angle=5.,L_mm=L) if mode==aa.LOCAL_MODE else family.load_reference(1.5,L,5.)
    d.update(load_mode='area' if batch else 'direct',q_sls=0.,q_parallel_sls=.305,
             P_sls=0.,P_parallel_sls=0.,x_sls=L/2,selected_types=['ELS rara'])
    if mode==aa.LOCAL_MODE:d.update(q_parallel_sls=.6,P_parallel_sls=-1200.)
    if mode==aa.POSITIVE_MODE:d.update(q_parallel_sls=.2024009036485318)
    if application=='wall_girt':d=apply(d,application)
    return aa.activate(d,mode)


@pytest.fixture(scope='module')
def direct_results():
    return {(m,a):complete_result(calculate(inputs(m,a))) for m in aa.MODES for a in ('purlin','wall_girt')}


@pytest.fixture(scope='module')
def batch_results():
    return {m:complete_result(calculate_batch(inputs(m,batch=True))) for m in aa.MODES}


def assert_aa_premise(content,axis):
    assert 'Método AA: teto conservador da componente '+axis in content
    assert 'admitindo redução apenas da alma e exigindo demonstração de mesas e lábios integrais' in content
    assert 'Teto não é flecha exata.' in content
    assert 'teto acima do limite ou estado sem demonstração permanece inconclusivo' in content
    assert 'tensor bruto próprio' not in content


@pytest.mark.parametrize('mode',aa.MODES)
@pytest.mark.parametrize('application',['purlin','wall_girt'])
def test_direct_premise_covers_actual_reduced_methods(mode,application,direct_results):
    r=direct_results[mode,application];before=copy.deepcopy(r)
    routes={aa.MODE:'web_control_hull',aa.LOCAL_MODE:'finite_local_partition',aa.POSITIVE_MODE:'web_control_hull'}
    assert r[aa.FIELD]['records']['DIRECT_ELS']['response']['route']==routes[mode]
    content=text(word(r))
    assert_aa_premise(content,'horizontal normal ao fechamento' if application=='wall_girt' else 'normal à cobertura')
    assert NOTICE not in content
    assert r==before


@pytest.mark.parametrize('mode',aa.MODES)
def test_girt_batch_premise_retains_concurrent_axes_and_horizontal_criterion(mode,batch_results):
    r=batch_results[mode];before=copy.deepcopy(r);content=text(batch_word(r))
    assert_aa_premise(content,'horizontal normal ao fechamento')
    assert 'Vetores horizontal/vertical concomitantes preservados; limite wall_els aplicado somente à horizontal.' in content
    assert NOTICE not in content
    assert r==before


@pytest.mark.parametrize('kind',['hash','null','absent'])
@pytest.mark.parametrize('batch',[False,True])
def test_invalid_history_marks_global_summary_as_saved_without_recalculation(kind,batch,direct_results,batch_results,monkeypatch):
    r=copy.deepcopy(batch_results[aa.MODE] if batch else direct_results[aa.MODE,'wall_girt'])
    if kind=='hash':r[aa.FIELD]['snapshot_sha256']='0'*64
    elif kind=='null':r[aa.FIELD]=None
    else:r.pop(aa.FIELD)
    before=copy.deepcopy(r)
    def denied(*a,**kw):pytest.fail('Word must not calculate or access live sources')
    monkeypatch.setattr(aa,'_bundle',denied);monkeypatch.setattr(aa,'_sources',denied)
    monkeypatch.setattr('tercas.application.calculate',denied)
    monkeypatch.setattr('tercas.batch.calculate_batch',denied)
    monkeypatch.setattr('tercas.study_completion.complete_result',denied)
    content=text(batch_word(r) if batch else word(r))
    assert 'Registro do teto AA inválido' in content
    assert NOTICE in content and 'Suas contagens não foram recompostas após a recusa deste registro AA' in content
    assert content.index(NOTICE)<content.index('Estado conjunto das verificações')
    assert r['global_verification']['display_summary'] in content
    assert_aa_premise(content,'horizontal normal ao fechamento')
    assert r==before


def test_invalid_history_without_global_record_does_not_invent_one(direct_results):
    r=copy.deepcopy(direct_results[aa.MODE,'wall_girt']);r[aa.FIELD]=None;r.pop('global_verification')
    before=copy.deepcopy(r);content=text(word(r))
    assert 'Registro do teto AA inválido' in content and NOTICE not in content
    assert 'Estado conjunto das verificações' not in content and r==before


def test_above_criterion_remains_inconclusive_with_bound_language():
    d=inputs(aa.MODE);d['wall_els']['normal_denominator']=4e6
    r=complete_result(calculate(d));before=copy.deepcopy(r)
    assert r['ELS']['criterion_status']=='inconclusive_bound_above_limit' and 'index' not in r['ELS']
    content=text(word(r));assert_aa_premise(content,'horizontal normal ao fechamento')
    assert NOTICE not in content and r==before


@pytest.mark.parametrize('batch',[False,True])
def test_existing_gross_word_premise_is_unchanged(batch):
    d=inputs(aa.MODE,batch=batch);d['deflection_model']=gross.MODE
    r=complete_result(calculate_batch(d) if batch else calculate(d));before=copy.deepcopy(r)
    content=text(batch_word(r) if batch else word(r))
    expected=('Flecha horizontal: componente flexional biaxial com tensor bruto próprio somente quando o crivo suficiente demonstra seção integral.' if batch else 'A componente normal da flexão biaxial utiliza o tensor bruto próprio somente nos estados demonstrados pelo crivo suficiente.')
    assert expected in content and 'Método AA:' not in content and NOTICE not in content
    assert r==before
