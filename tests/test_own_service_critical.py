import copy
import json
from io import BytesIO
from docx import Document
import pytest
from tercas.application import defaults, build_spec
from tercas.core.especificacao_unica import evaluate
from tercas import ue_catalog_reference as own, direct_self_weight as pp, roof_top_load as roof
from tercas import deflection_scope as scope
from tercas.pierin_ue_registry import new_study_indices
from tercas.own_service_critical import qualify


def data(index=0):
    d=pp.activate(defaults(index));d['roof_top_load']=roof.choice()
    d.update(q_sls=.001,P_sls=1.,ELS_limit_mm=20.,ELS_origin='Synthetic limit')
    return scope.activate(own.activate(d))


def test_complete_family_coverage_and_strength_bit_exact():
    passed=[];pending=[]
    for i in new_study_indices():
        d=data(i);before=copy.deepcopy(d)
        legacy=copy.deepcopy(d);legacy.pop(scope.FIELD)
        a=build_spec(legacy);b=build_spec(d)
        assert {k:v for k,v in b.items() if k not in ('Ml_SLS','MLE_SLS','deflection_model')}==a
        old=evaluate(a);new=evaluate(b)
        for key in ('NBR_branches','FLT_segments','section_checks'):
            assert json.dumps(new[key],sort_keys=True)==json.dumps(old[key],sort_keys=True)
        ev=new['ELS']['local_critical_evidence']
        assert ev['source_binding']==own.source_binding(d)
        assert ev['snapshot_sha256']==own.digest({k:v for k,v in ev.items() if k!='snapshot_sha256'})
        if ev['status']=='computed_own_contour_Table12b':
            passed.append(i);assert new['ELS']['status']=='computed_bending_component'
        else:
            pending.append(i);assert new['ELS']['status']=='computed_bending_component'
            assert new['ELS']['service_mle_evidence']['calculation']['method']=='NBR9.8.5(a)_pointwise_MLE'
        assert d==before
    assert len(passed)==62
    assert pending==[79,80,81,82]


@pytest.mark.parametrize('sign',[-1,1])
def test_direct_signed_actions_full_span_and_pp_once(sign):
    d=data();d.update(q_sls=sign*.05,P_sls=sign*5.)
    from tercas.direct_self_weight import calculation_inputs
    spec=build_spec(d);expected=calculation_inputs(d)
    assert spec['SLS']['q_Nmm']==expected['q_sls']
    assert spec['SLS']['P_N']==expected['P_sls']
    assert spec['L_mm']==d['L_mm']
    assert spec['Ml']['value'] is None
    assert spec['Ml_SLS']['value']>0


@pytest.mark.parametrize('field,value',[('E_MPa',210000.),('fy_MPa',345.),('Ix_cm4',15.)])
def test_stale_identity_rejected(field,value):
    d=data();d['properties'][field]=value
    with pytest.raises(ValueError):qualify(d)


def test_saved_report_reads_frozen_evidence_without_requalifying(monkeypatch):
    d=data();spec=build_spec(d);r=evaluate(spec)
    r['deflection_scope_evidence']={'schema':scope.MODE,'text':scope.TEXT}
    saved=json.loads(json.dumps(r));before=copy.deepcopy(saved)
    monkeypatch.setattr(own,'source_binding',lambda *_:pytest.fail('Historical rendering reopened sources'))
    doc=Document();scope.report(doc,saved)
    text='\n'.join(p.text for p in doc.paragraphs)
    assert 'Ml de serviço próprio' in text and 'Sem alteração dos denominadores ELU/FLT' in text
    assert saved==before


@pytest.mark.parametrize('change',['mode','value','geometry','material','domain'])
def test_core_rejects_unbound_service_override(change):
    spec=build_spec(data())
    if change=='mode':spec.pop('deflection_model')
    if change=='value':spec['Ml_SLS']['value']*=2
    if change=='geometry':spec['selected_section']['fields']['Ix_cm4']['value']*=2
    if change=='domain':spec['model_domain_evidence']['conflict']='Conflicting panel'
    if change=='material':spec['selected_section']['fields']['E_MPa']['value']*=2
    with pytest.raises(ValueError):evaluate(spec)


def test_area_adapter_keeps_signed_combinations_and_pp_exactly_once():
    from tercas.batch import area_bundle, case_inputs
    d=data();d['load_mode']='area';d['selected_types']=['ELS rara']
    d['area_inputs'].update(permanent_kgf_m2=1.,wind_up_kgf_m2=20.,wind_down_kgf_m2=10.)
    before=copy.deepcopy(d)
    bundle=area_bundle(d)
    signs=set()
    for combo in bundle['combinations']:
        spec=build_spec(case_inputs(d,combo))
        assert spec['SLS']['q_Nmm']==combo['q_N_mm']
        assert spec['L_mm']==d['L_mm']
        result=evaluate(spec)
        assert result['ELS']['status']=='computed_bending_component'
        signs.add(1 if combo['q_N_mm']>0 else -1)
    assert signs=={-1,1} and d==before


@pytest.mark.parametrize('mode',['direct','area'])
def test_full_calculation_json_word_and_saved_read(mode,monkeypatch):
    from tercas.application import calculate,rows
    from tercas.batch import calculate_batch
    from tercas.report import word,batch_word
    d=data();d['load_mode']=mode
    if mode=='area':
        d['selected_types']=['ELS rara']
        d['area_inputs'].update(permanent_kgf_m2=.1,live_kgf_m2=.1)
    result=calculate(d) if mode=='direct' else calculate_batch(d)
    blocks=[c['evidence']['ELS'] for c in result['cases']] if mode=='area' else [result['ELS']]
    assert all(b['status']=='computed_bending_component' for b in blocks)
    assert all(b['local_critical_evidence']['status']=='computed_own_contour_Table12b' for b in blocks)
    saved=json.loads(json.dumps(result));before=copy.deepcopy(saved)
    monkeypatch.setattr('tercas.own_service_critical.qualify',lambda *_:pytest.fail('Reader recalculated critical'))
    binary=batch_word(saved) if mode=='area' else word(saved)
    doc=Document(BytesIO(binary))
    assert 'Ml de serviço próprio' in '\n'.join(p.text for p in doc.paragraphs)
    assert saved==before


def test_service_critical_and_elastic_deflection_independent_arithmetic():
    import math
    d=data();d.update(q_sls=.001,P_sls=0.)
    spec=build_spec(d);p=d['properties'];eta=p['bf']/p['h']
    k=sum(c*eta**i for i,c in enumerate((81,-730,4261,-12304,17919,-12796,3574)))
    w=p['Ix_cm4']*1e4/(p['h']/2.)
    expected=k*math.pi**2*p['E_MPa']/(12*(1-.3**2))*(p['t']/p['h'])**2*w
    assert spec['Ml_SLS']['value']==pytest.approx(expected,rel=1e-13)
    q=spec['SLS']['q_Nmm'];L=spec['L_mm'];ig=p['Ix_cm4']*1e4
    assert q*L**2/8/expected<.673**2
    result=evaluate(spec)
    assert result['ELS']['deflection_mm']==pytest.approx(5*q*L**4/(384*p['E_MPa']*ig),rel=1e-10)


@pytest.mark.parametrize('index',[0,79])
def test_coherent_rehash_cannot_forge_service_critical(index):
    spec=build_spec(data(index));scalar=spec['Ml_SLS'];ev=scalar['evidence']
    scalar['value']=1e30
    ev['status']='computed_own_contour_Table12b'
    ev.setdefault('formula',{})['Ml_Nmm']=1e30
    ev['snapshot_sha256']=own.digest({k:v for k,v in ev.items() if k!='snapshot_sha256'})
    with pytest.raises(ValueError):evaluate(spec)
