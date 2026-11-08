import copy
import json
from io import BytesIO
import pytest
from docx import Document
from test_own_service_critical import data
from tercas.application import build_spec, calculate, rows
from tercas.batch import calculate_batch
from tercas import deflection_scope as scope
from tercas.core.especificacao_unica import evaluate


@pytest.mark.parametrize('index',[79,80,81,82])
@pytest.mark.parametrize('mode',['direct','area'])
def test_full_calculation_and_frozen_mle_report(index,mode,monkeypatch):
    from tercas.report import word,batch_word
    d=data(index);d['load_mode']=mode
    if mode=='area':
        d['selected_types']=['ELS rara']
        d['area_inputs'].update(permanent_kgf_m2=.1,live_kgf_m2=.1)
    before=copy.deepcopy(d)
    result=calculate(d) if mode=='direct' else calculate_batch(d)
    blocks=[c['evidence']['ELS'] for c in result['cases']] if mode=='area' else [result['ELS']]
    for b in blocks:
        assert b['status']=='computed_bending_component'
        assert b['index']>=0
        assert b['local_critical_evidence']['status']=='outside_Table12b_domain'
        assert b['service_mle_evidence']['calculation']['method']=='NBR9.8.5(a)_pointwise_MLE'
        assert 'No Ml inferred' in b['local_uniaxial_component']['effective_inertia_law']
        assert scope.recorded_local_objective(result,b)
    assert d==before
    saved=json.loads(json.dumps(result));before=copy.deepcopy(saved)
    monkeypatch.setattr('tercas.own_service_mle.evaluate',lambda *_:pytest.fail('Reader recalculated MLE'))
    binary=batch_word(saved) if mode=='area' else word(saved)
    text='\n'.join(p.text for p in Document(BytesIO(binary)).paragraphs)
    assert 'MLE de serviço próprio' in text
    assert 'Ml de serviço próprio' not in text
    assert saved==before


def test_bound_mle_does_not_modify_strength_or_invent_critical():
    d=data(79);spec=build_spec(d)
    assert spec['Ml']['value'] is None and spec['Ml_SLS']['value'] is None
    legacy=copy.deepcopy(d);legacy.pop(scope.FIELD)
    old=evaluate(build_spec(legacy));new=evaluate(spec)
    for k in ('NBR_branches','FLT_segments','section_checks'):assert old[k]==new[k]
    spec['MLE_SLS']['source_binding']['catalog_index']=80
    assert evaluate(spec)['ELS']['status']=='invalid_or_outside_implemented_domain'
    assert 'index' not in evaluate(spec)['ELS']


def test_excess_stress_pending_not_gross_pass():
    d=data(79);d.update(q_sls=100.,P_sls=0.)
    result=evaluate(build_spec(d))
    assert result['ELS']['status']=='invalid_or_outside_implemented_domain'
    assert 'index' not in result['ELS']


def test_coherent_catalog_transplant_rejected():
    from tercas import ue_catalog_reference as own
    from tercas.own_service_mle import qualify
    spec=build_spec(data(79))
    ev=spec['Ml_SLS']['evidence'];ev['source_binding']['catalog_index']=80
    ev['snapshot_sha256']=own.digest({k:v for k,v in ev.items() if k!='snapshot_sha256'})
    spec['MLE_SLS']=qualify(spec['Ml_SLS'])
    result=evaluate(spec)
    assert result['ELS']['status']=='invalid_or_outside_implemented_domain'
    assert 'Identidade geométrica' in result['ELS']['reason']


def test_ui_mle_local_route(monkeypatch):
    from test_ui_uniaxial_deflection_scope import imported,button
    d=data(79)
    app=imported(monkeypatch,d)
    button(app,'Calcular verificações disponíveis').click().run(timeout=60)
    assert not app.exception
    result=app.session_state.result
    assert result['ELS']['index']>=0
    assert result['ELS']['service_mle_evidence']['calculation']['method']=='NBR9.8.5(a)_pointwise_MLE'
    assert any(row['Verificação']==scope.PURLIN_ROW for row in rows(result))
    actual=app.session_state.last_input
    for key in ('L_mm','q_sls','P_sls','x_sls','ELS_limit_mm','catalog_index','deflection_model'):
        assert actual[key]==d[key]
    for key in ('h','bf','lip','t','ri_mm','E_MPa','G_MPa','fy_MPa','Ix_cm4'):
        assert actual['properties'][key]==d['properties'][key]
