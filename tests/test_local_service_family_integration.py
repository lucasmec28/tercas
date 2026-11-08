"""Fresh family service integration. All inputs below are synthetic."""
import copy
import json
from docx import Document
import pytest
from test_own_service_critical import data
from tercas.application import build_spec, _calculate
from tercas.core.especificacao_unica import evaluate
from tercas.direct_self_weight import calculation_inputs
from tercas import deflection_scope


def opposing_data(index=0):
    d=data(index)
    d.update(L_mm=6000., x_sls=2950., x_uls=2950., q_sls=.001, P_sls=-3.7)
    # Make the CONSUMED service q exactly .001, leaving PP included once.
    d['q_sls']-=calculation_inputs(d)['q_sls']-.001
    return d


def test_signed_mse_fresh_consumer_and_strength_unchanged():
    spec=build_spec(opposing_data())
    old=copy.deepcopy(spec)
    old.pop('Ml_SLS');old.pop('deflection_model')
    before=evaluate(old);after=evaluate(spec)
    assert after['ELS']['status']=='computed_bending_component'
    assert after['ELS']['service_mse_signed_evidence']['method']=='NBR9.8.5(b)_pointwise_MSE_signed'
    assert len(after['ELS']['service_mse_signed_evidence']['stationary_points_mm'])==3
    assert after['ELS']['x_mm']>4000
    for key in ('NBR_branches','FLT_segments','section_checks'):
        assert after[key]==before[key]
    assert spec['SLS']['q_Nmm']==pytest.approx(.001)


def test_signed_fresh_annotation_and_word_snapshot(monkeypatch):
    result=_calculate(opposing_data())
    assert result['ELS']['index']>=0
    assert result['deflection_scope_evidence']['service_method']=='NBR9.8.5(b)_pointwise_MSE_signed'
    saved=json.loads(json.dumps(result));before=copy.deepcopy(saved)
    import tercas.nbr_service_strong_mse_signed as signed
    monkeypatch.setattr(signed,'peak_deflection',lambda **_:pytest.fail('Report recalculated service'))
    doc=Document();deflection_scope.report(doc,saved)
    assert 'Todos os pontos estacionários' in '\n'.join(p.text for p in doc.paragraphs)
    assert saved==before


def test_quadrature_failure_never_retains_index(monkeypatch):
    import tercas.nbr_service_strong_mse_signed as signed
    def failure(**_):raise ArithmeticError('Synthetic quadrature failure')
    monkeypatch.setattr(signed,'peak_deflection',failure)
    result=evaluate(build_spec(opposing_data()))
    assert result['ELS']['status']=='invalid_or_outside_implemented_domain'
    assert 'index' not in result['ELS']
    assert 'quadrature failure' in result['ELS']['reason']


def test_legacy_signed_protocol_not_silently_changed():
    spec=build_spec(opposing_data())
    spec['Ml']=dict(value=spec['Ml_SLS']['value'],origin='Synthetic legacy critical')
    spec.pop('Ml_SLS');spec.pop('deflection_model')
    result=evaluate(spec)
    assert result['ELS']['status']=='invalid_or_outside_implemented_domain'
    assert 'mesmo sentido' in result['ELS']['reason']


@pytest.mark.parametrize('index',[79,80,81,82])
def test_four_mle_rows_keep_separate_route_for_opposing_actions(index):
    result=evaluate(build_spec(opposing_data(index)))
    assert result['ELS']['status']=='computed_bending_component'
    assert result['ELS']['service_mle_evidence']['calculation']['method']=='NBR9.8.5(a)_pointwise_MLE'
    assert 'service_mse_signed_evidence' not in result['ELS']

