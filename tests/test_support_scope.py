"""User scope exclusion must never become approval or change mechanics."""
import copy
import json
from io import BytesIO
from pathlib import Path
import pytest
from docx import Document
from tercas import support_scope as scope
from tercas.application import example, calculate, build_spec
from tercas.batch import calculate_batch
from tercas import completion_requirements as requirements
from tercas import global_verification as global_checks


@pytest.fixture(scope='module')
def direct_pair():
    old=example()
    return calculate(old),calculate(scope.activate(old))


def strip_scope(result):
    out=copy.deepcopy(result)
    out.pop(scope.EVIDENCE,None)
    out.pop('input_fingerprint',None)
    out['input_data'].pop(scope.FIELD,None)
    for key in ('input_snapshot','common_input_snapshot'):
        out.get(key,{}).pop(scope.FIELD,None)
    branches=[out['NBR_branches']] if 'NBR_branches' in out else [c['evidence']['NBR_branches'] for c in out['cases'] if c['combination']['limit_state']=='ELU']
    for branch in branches:branch.pop('supports',None)
    return out


def test_new_direct_is_exact_same_mechanics_and_P_inside_span(direct_pair):
    old,new=direct_pair
    assert strip_scope(old)==strip_scope(new)
    assert old['NBR_branches']['point']==new['NBR_branches']['point']
    assert new['NBR_branches']['point']['status']=='computed'
    assert new['section_checks']==old['section_checks']
    for r in new['NBR_branches']['supports'].values():
        assert r==scope.decision() and r['index'] is None
        assert r['status'] not in ('meets','not_applicable','stiffener_exception_9_5_1')
        assert not r['support_approved'] and not r['normative_exemption']


def test_support_helper_not_executed_but_P_keeps_its_own_geometry(monkeypatch):
    from tercas.core import ramos_genericos as core
    monkeypatch.setattr(core,'support',lambda *a:pytest.fail('No active end-support evaluation'))
    data=scope.activate(example())
    fresh=calculate(data)
    assert fresh['NBR_branches']['point']['status']=='computed'
    data['left_web']=False
    assert calculate(data)['NBR_branches']['point']['status']=='not_evaluated'


def test_batch_support_limit_preserves_reactions_shear_and_interior_P():
    data=example();data.update(load_mode='area',selected_types=['ELU normal'])
    old=calculate_batch(data);new=calculate_batch(scope.activate(data))
    assert strip_scope(old)==strip_scope(new)
    limits=[c for c in new['cases'] if c['combination'].get('point_position')=='support_limit']
    assert limits and all(c['evidence']['inclination']['P_vector']['normal']>0 for c in limits)
    assert all(c['evidence']['NBR_branches']['point']['scope']=='mathematical_limit' for c in limits)


def test_scope_is_not_normative_approval_or_checklist_gate(direct_pair):
    _,new=direct_pair
    result=copy.deepcopy(new)
    result['global_verification']=global_checks.build_global_verification(result)
    g=result['global_verification']
    assert g['local_support_scope_exclusion']==scope.saved(result)
    assert any(r['id'].endswith(':point_introduction_scope') for r in g['checks'])
    assert any(r['id'].endswith(':shear') for r in g['checks'])
    checked=requirements.attach(result);r=requirements.saved(checked)
    support=next(x for x in r['records'] if x['id']=='support_web')
    assert r['schema']==requirements.SCOPED_SCHEMA and 'support_web' not in r['required_ids']
    assert support['requirement_state']==scope.STATE and support['index'] is None
    assert support['blocks_listed_scope_completion'] is False
    assert 'support_model' in r['required_ids'] and 'point_introduction' in r['required_ids']
    checks=[global_checks.check('support_force_introduction',limit_state='ELU',source='old',reason='pending'),
            global_checks.check('shear',limit_state='ELU',source='retained',index=.5,qualified=True)]
    filtered,evidence=scope.apply_inventory(result,checks)
    summary=global_checks.aggregate([r['id'] for r in filtered],filtered,inventory_qualified=True)
    assert summary['status']=='aprovado' and summary['counts']['not_applicable']==0
    assert evidence['support_approved'] is False


def test_new_local_support_execution_rejected_and_P_source_still_readable(direct_pair):
    from tercas.support_web import application as a,sources
    from tercas.support_web import completion
    _,new=direct_pair
    before=copy.deepcopy(new)
    assert len(sources.extract(new)['supports'])==2  # Physical force reader is retained.
    with pytest.raises(ValueError,match='fora do escopo'):a.calculate(new,{})
    with pytest.raises(ValueError,match='fora do escopo'):completion.build(new,{})
    assert new==before


def test_P_web_assessment_not_disabled():
    from tercas.ue_family_reference import load_reference
    from tercas.point_web import application as p
    data=scope.activate(load_reference(1.5));data.update(load_mode='direct',P_uls=100.,P_sls=50.)
    result=calculate(data);config=p.reference_configuration(result)
    assessment=p.calculate(result,config)
    assert assessment['rows'] and assessment['rows'][0]['source_record']['normal_N']==100.
    assert p.saved_assessment(result,assessment)==assessment


def test_legacy_results_and_readers_are_unchanged(direct_pair,monkeypatch):
    from tercas.support_web import application as a
    old,_=direct_pair;before=copy.deepcopy(old)
    cfg=a.reference_configuration(old);assessment=a.calculate(old,cfg)
    base=requirements.attach(old)
    def forbidden(*args,**kwargs):pytest.fail('Reader cannot evaluate or migrate')
    monkeypatch.setattr(scope,'annotate',forbidden)
    monkeypatch.setattr(scope,'activate',forbidden)
    assert scope.saved(old) is None
    assert requirements.saved(base)['schema']==requirements.SCHEMA
    assert 'support_web' in requirements.saved(base)['required_ids']
    assert a.saved_assessment(old,assessment)==assessment and old==before


@pytest.mark.parametrize('mutation',[lambda r:r[scope.EVIDENCE].update(support_approved=True),
    lambda r:r[scope.EVIDENCE].update(index=0.),lambda r:r[scope.EVIDENCE].update(normative_exemption=True),
    lambda r:r['input_data'].update(q_uls=123.),lambda r:r.pop(scope.EVIDENCE)])
def test_missing_tampered_or_unbound_evidence_fails_closed(direct_pair,mutation):
    r=copy.deepcopy(direct_pair[1]);mutation(r)
    with pytest.raises(ValueError):scope.saved(r)


@pytest.mark.parametrize('bad',[None,True,False,'unknown',{},[]])
def test_unknown_policy_is_not_overwritten(bad):
    data=example();data[scope.FIELD]=bad
    with pytest.raises(ValueError):scope.activate(data)
    with pytest.raises(ValueError):build_spec(data)


def test_saved_JSON_and_word_state_decision_without_recompute(direct_pair,monkeypatch):
    from tercas.report import word
    new=direct_pair[1];before=copy.deepcopy(new)
    restored=json.loads(json.dumps(new))
    assert scope.saved(restored)==scope.saved(new)
    monkeypatch.setattr(scope,'annotate',lambda *a:pytest.fail('No history conversion'))
    text='\n'.join(p.text for p in Document(BytesIO(word(restored))).paragraphs)
    assert scope.TITLE in text and 'Por decisão do usuário' in text
    assert 'não significa apoio aprovado nem dispensa normativa' in text
    assert 'Contato local de P dentro do vão' in text
    assert new==before


def test_current_network_mechanics_and_inventory_scope():
    from tercas.three_girt_warping import application as w
    from tercas.three_girt_assessment import application as assessment
    raw=json.loads((Path(__file__).parent/'data/three_girt_normal_QA_input.json').read_text())
    data=raw['input_data'];data.update(load_mode='direct',P_uls=0.,P_sls=0.,P_parallel_uls=0.,P_parallel_sls=0.)
    cfg=w.current_configuration(data,raw['configuration']['three_girt'])
    cfg['three_girt'].update(direct_pp_uls_N_mm=.02,direct_pp_sls_N_mm=.02,
        direct_brace_factor_uls=1.25,direct_brace_factor_sls=1.)
    old=w.calculate(data,cfg);new=w.calculate(scope.activate(data),cfg)
    assert old['cases'] and new['cases'] and old['status']==new['status']=='conditional_elastic_vlasov_demand'
    for first,second in zip(old['cases'],new['cases']):
        m1=copy.deepcopy(first['model']);m2=copy.deepcopy(second['model'])
        for m in (m1,m2):
            m.pop('source_input_fingerprint');m.pop('demand_content_sha256')
        assert m1==m2
    old_inventory=assessment.assess(old);fresh=assessment.assess(new)
    assert 'support_force_introduction' in old_inventory['pending_ids']
    assert 'support_force_introduction' not in {r['id'] for r in fresh['checks']}
    assert 'interior_force_introduction' in {r['id'] for r in fresh['checks']}
    assert 'transverse_shear_resistance' in {r['id'] for r in fresh['checks']}
    assert fresh['local_support_scope_exclusion']==scope.saved(new)
    assert assessment.saved_assessment(new,fresh)==fresh
    assert fresh['whole_member_approved'] is False
