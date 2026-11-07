"""No-solver policy tests; source mechanics are covered by EN preserved tests."""
import copy
import pytest

from tercas import isolated_en_application as en
from tercas import isolated_en_panorama as policy
from tercas.global_verification import build_global_verification, display_summary
from test_global_verification import fixture, statuses


def saved_source(*, catalog=False):
    result = fixture(parallel=.01)
    combos = [dict(id='DIRECT_'+s, limit_state=s,
        q_vector=copy.deepcopy(result['inclination_evidence'][s]['q_vector']),
        P_vector=copy.deepcopy(result['inclination_evidence'][s]['P_vector'])) for s in ('ELU', 'ELS')]
    result['torsion_evidence'] = dict(source_combinations=combos,
        records=[dict(combination_id=c['id'], limit_state=c['limit_state']) for c in combos])
    row = dict(combination_id='DIRECT_ELU', limit_state='ELU', status='computed',
        source_analysis_sha256='a'*64, source_summary_record_sha256='b'*64,
        check=dict(section_stress_criteria_sufficiently_satisfied=True),
        web_shear_component=dict(web_shear=dict(status='meets'), bending_shear_component=dict(component_qualified=True)))
    if catalog:row['check'] = dict(shear=dict(component_sufficient=True), mv=dict(component_sufficient=True))
    ev = dict(schema='synthetic_preserved_source', snapshot_sha256='c'*64,
        source_inventory=[dict(combination_id=c['id'], limit_state=c['limit_state'], source_combination=c) for c in combos],
        records=[row], ELU_cases=1, computed_cases=1, pending_cases=0)
    return result, ev


def install_context(monkeypatch, result, ev, *, catalog=False):
    calls = []
    def context(r, *, sectional=False):
        assert r is result
        calls.append(1)
        return dict(reason='Saved EN criteria', binding=dict(snapshot_sha256=ev['snapshot_sha256']),
                    sectional=policy.sectional_context(r, ev, catalog=catalog))
    monkeypatch.setattr(en, 'global_context', context)
    return calls


def test_listed_sufficient_conditions_never_global_approval(monkeypatch):
    result, ev = saved_source()
    # Zero parallel bending does not prove zero torsional point displacement.
    result['inclination_evidence']['ELS']['q_vector']['parallel'] = 0.
    calls = install_context(monkeypatch, result, ev)
    summary = build_global_verification(result)
    assert len(calls) == 1  # No per-combination preserved call.
    records = statuses(summary['checks'])
    for key in ('ELU:DIRECT_ELU:secondary_shear_scope', 'torsion_warping'):
        assert records[key]['status'] == 'meets'
        assert records[key]['criterion_kind'] == 'condition'
        assert records[key]['index'] is None
        assert records[key]['trace']['EN_indices_imported_into_NBR'] is False
    assert summary['status'] == 'inconclusivo'
    assert records['ELS:DIRECT_ELS:combined_ELS_scope']['status']=='pending'
    assert summary['display_summary'] == 'Inconclusivo: 1 pendência(s). Os critérios calculados não constituem aprovação global.'
    assert all(summary[k] is False for k in ('whole_member_approved', 'current_adapter_can_approve',
        'approved_within_declared_checklist', 'torsion_warping_qualified', 'combined_ELS_approved'))
    result['global_verification'] = summary
    en.validate_saved_global(result)


def test_catalogue_may_cover_two_shears_but_never_torsion(monkeypatch):
    result, ev = saved_source(catalog=True)
    install_context(monkeypatch, result, ev, catalog=True)
    summary = build_global_verification(result); records = statuses(summary['checks'])
    assert records['ELU:DIRECT_ELU:secondary_shear_scope']['status'] == 'meets'
    assert records['torsion_warping']['status'] == 'pending'
    result['global_verification'] = summary
    en.validate_saved_global(result)


@pytest.mark.parametrize('mutation', ['empty', 'duplicate', 'missing', 'torsion_duplicate', 'other_combination', 'other_vectors', 'pending', 'stress_inconclusive', 'mv_inconclusive', 'web_inconclusive', 'missing_mv'])
def test_no_vacuous_or_unbound_sufficiency(monkeypatch, mutation):
    result, ev = saved_source(); row = ev['records'][0]
    if mutation == 'empty':ev['source_inventory'] = []; ev['records'] = []
    elif mutation == 'duplicate':ev['source_inventory'].append(copy.deepcopy(ev['source_inventory'][0])); ev['records'].append(copy.deepcopy(row))
    elif mutation == 'missing':ev['records'] = []
    elif mutation == 'torsion_duplicate':result['torsion_evidence']['records'].append(copy.deepcopy(result['torsion_evidence']['records'][0]))
    elif mutation == 'other_combination':row['combination_id'] = 'OTHER'
    elif mutation == 'other_vectors':ev['source_inventory'][0]['source_combination']['q_vector']['parallel'] = .02
    elif mutation == 'pending':row.update(status='pending', check=None); ev.update(computed_cases=0,pending_cases=1)
    elif mutation == 'stress_inconclusive':row['check']['section_stress_criteria_sufficiently_satisfied'] = False
    elif mutation == 'mv_inconclusive':row['web_shear_component']['bending_shear_component']['component_qualified'] = False
    elif mutation == 'web_inconclusive':row['web_shear_component']['web_shear']['status'] = 'inconclusive'
    elif mutation == 'missing_mv':row['web_shear_component'].pop('bending_shear_component')
    install_context(monkeypatch, result, ev)
    summary = build_global_verification(result); records = statuses(summary['checks'])
    assert records['torsion_warping']['status'] == 'pending'
    assert records['torsion_warping']['index'] is None
    assert records['ELU:DIRECT_ELU:secondary_shear_scope']['status'] == ('meets' if mutation == 'stress_inconclusive' else 'pending')
    assert not summary['approved_within_declared_checklist']


@pytest.mark.parametrize('mutation', ['torsion', 'secondary', 'index', 'source', 'trace', 'counts', 'banner', 'approval', 'remove_policy', 'duplicate'])
def test_new_policy_rejects_semantic_tampering_even_with_refreshed_global_hash(monkeypatch, mutation):
    result, ev = saved_source(); install_context(monkeypatch, result, ev)
    result['global_verification'] = build_global_verification(result)
    summary = result['global_verification']; records = statuses(summary['checks'])
    if mutation == 'torsion':records['torsion_warping']['status'] = 'pending'
    elif mutation == 'secondary':records['ELU:DIRECT_ELU:secondary_shear_scope']['status'] = 'pending'
    elif mutation == 'index':records['torsion_warping']['index'] = .1
    elif mutation == 'source':records['torsion_warping']['source'] = 'NBR14762:2010'
    elif mutation == 'trace':records['torsion_warping']['trace']['case_bindings']['DIRECT_ELU']['source_analysis_sha256'] = 'd'*64
    elif mutation == 'counts':summary['counts']['pending'] = 0
    elif mutation == 'banner':summary['display_summary'] = 'Aprovado no checklist completo'
    elif mutation == 'approval':summary['approved_within_declared_checklist'] = True
    elif mutation == 'remove_policy':summary.pop('sectional_conditions_policy')
    elif mutation == 'duplicate':summary['checks'].append(copy.deepcopy(records['torsion_warping']))
    summary['self_hash'] = en.digest({k:v for k,v in summary.items() if k!='self_hash'})
    with pytest.raises(ValueError):en.validate_saved_global(result)


def test_valid_legacy_summary_is_not_requalified(monkeypatch):
    result, ev = saved_source(); install_context(monkeypatch, result, ev)
    context = en.global_context(result)
    legacy = dict(isolated_EN_binding=context['binding'], checks=[dict(id='torsion_warping', status='pending')], display_summary='Historical pending')
    result['global_verification'] = legacy; before = copy.deepcopy(result)
    en.validate_saved_global(result)
    assert result == before


def test_missing_result_source_cannot_keep_promoted_condition(monkeypatch):
    result, ev = saved_source(); install_context(monkeypatch, result, ev)
    result['global_verification'] = build_global_verification(result)
    monkeypatch.setattr(en, 'global_context', lambda *a, **kw: None)
    with pytest.raises(ValueError):en.validate_saved_global(result)


def test_batch_inventory_must_match_requested_cases():
    result, ev = saved_source()
    result['schema'] = 'tercas_batch_results_v1'
    result['cases'] = [dict(combination=i['source_combination'], evidence=dict(inclination=result['inclination_evidence'][i['limit_state']])) for i in ev['source_inventory']]
    result['load_bundle'] = dict(combinations=[c['combination'] for c in result['cases']])
    assert policy.sectional_context(result, ev)['joint_sufficient']
    result['load_bundle']['combinations'] = result['load_bundle']['combinations'][1:]
    with pytest.raises(ValueError):policy.sectional_context(result, ev)


def test_report_and_failed_banner_keep_listed_scope(monkeypatch):
    from tercas import roof_top_nbr, report_audit, roof_top_load_ui
    from tercas.study_completion import report_global
    from tercas.global_verification import aggregate, check
    result, ev = saved_source()
    result['inclination_evidence']['ELS']['q_vector']['parallel'] = 0.
    install_context(monkeypatch, result, ev)
    result['global_verification'] = build_global_verification(result)
    monkeypatch.setattr(roof_top_nbr, 'validate_saved_global', lambda *a: None)
    monkeypatch.setattr(report_audit, 'report_saved_issues', lambda *a: None)
    monkeypatch.setattr(roof_top_load_ui, 'report', lambda *a: None)
    class Doc:
        def __init__(self):self.text=[]
        def add_paragraph(self, text):self.text.append(text)
        def add_heading(self, text, level):self.text.append(text)
    doc=Doc();report_global(doc,result);text=' '.join(doc.text)
    assert 'ELU: critérios listados atendidos' in text
    assert 'ELS: critérios listados inconclusivos' in text
    assert 'ELU: aprovado' not in text and 'ELS: aprovado' not in text
    failed = aggregate(['failed'], [check('failed',limit_state='ELU',source='synthetic',qualified=True,index=2.)], inventory_qualified=True)
    failed['sectional_conditions_policy']=policy.POLICY
    assert 'Conclusão global fora do escopo' in display_summary(failed)
    assert 'Checklist declarado concluído' not in display_summary(failed)


def test_legitimate_els_only_inventory_stays_pending_without_corruption(monkeypatch):
    result, ev = saved_source()
    result['schema'] = 'tercas_batch_results_v1'
    combo = ev['source_inventory'][1]['source_combination']
    result['cases'] = [dict(combination=combo, evidence=dict(inclination=result['inclination_evidence']['ELS']))]
    result['load_bundle'] = dict(combinations=[combo])
    result['torsion_evidence']['records'] = result['torsion_evidence']['records'][1:]
    ev.update(source_inventory=ev['source_inventory'][1:], records=[], ELU_cases=0, computed_cases=0, pending_cases=0)
    section = policy.sectional_context(result, ev)
    assert not section['joint_sufficient'] and section['cases']=={} and section['ELU_cases']==0
    install_context(monkeypatch, result, ev)
    result['global_verification'] = build_global_verification(result)
    summary = result['global_verification']
    assert 'isolated_EN_binding' in summary
    assert 'missing_limit_state:ELU' in summary['pending_ids'] and 'torsion_warping' in summary['pending_ids']
    en.validate_saved_global(result)
