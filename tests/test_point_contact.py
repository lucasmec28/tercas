"""Bounded declaration/input integration. Synthetic fixtures are not projects."""
import copy
import json
import math
from io import BytesIO
from decimal import Decimal, localcontext
import pytest
from docx import Document
from tercas.application import example, calculate, build_spec, fingerprint
from tercas.point_contact import (FIELD, SCHEMA, DECLARATIONS, blank_choice,
                                  configuration, evaluate, reference_basis, basis_matches, saved_records)
from tercas.core.anexo_d import frd, classify
from tercas.global_verification import build_global_verification, attach_global_verification


def declared(c=40.):
    choice = blank_choice()
    choice.update(enabled=True, c_mm=c, origin='QA sintético: contato e hipóteses declarados, não condição real.')
    choice['declarations'] = {k: True for k in DECLARATIONS}
    return choice


def ready():
    d = example()
    d[FIELD] = declared()
    d[FIELD]['basis'] = reference_basis(d)
    return d


def branch(data):
    return evaluate(data, build_spec(data))


def mechanics(result):
    """Drop only input identities and the explicitly affected local branch."""
    r = copy.deepcopy(result)
    r['input_data'].pop(FIELD, None)
    r.pop('input_fingerprint', None)
    r['NBR_branches'].pop('point')
    for name in ('ue_family_reference_evidence', 'ue_reference_evidence'):
        if name in r:
            r[name].pop('input_sha256', None)
    return r


def test_absent_and_disabled_preserve_legacy_exactly_except_input_identity():
    d = example()
    baseline = calculate(d)
    assert FIELD not in d
    d[FIELD] = blank_choice()
    current = calculate(d)
    assert current['NBR_branches']['point'] == baseline['NBR_branches']['point']
    assert mechanics(current) == mechanics(baseline)
    assert current['input_fingerprint'] != baseline['input_fingerprint']
    assert d[FIELD]['c_mm'] is None and not any(d[FIELD]['declarations'].values())


@pytest.mark.parametrize('mutation', ['schema', 'enabled_int', 'extra', 'missing', 'decl_missing', 'decl_extra', 'decl_int', 'c_bool', 'c_nan', 'c_inf', 'c_string', 'origin_type'])
def test_malformed_contract_is_rejected_without_silent_repair(mutation):
    d = ready(); c = d[FIELD]
    if mutation == 'schema': c['schema'] = 'future'
    elif mutation == 'enabled_int': c['enabled'] = 1
    elif mutation == 'extra': c['unknown'] = True
    elif mutation == 'missing': c.pop('c_mm')
    elif mutation == 'decl_missing': c['declarations'].pop(next(iter(DECLARATIONS)))
    elif mutation == 'decl_extra': c['declarations']['invented'] = True
    elif mutation == 'decl_int': c['declarations'][next(iter(DECLARATIONS))] = 1
    elif mutation == 'c_bool': c['c_mm'] = True
    elif mutation == 'c_nan': c['c_mm'] = float('nan')
    elif mutation == 'c_inf': c['c_mm'] = float('inf')
    elif mutation == 'c_string': c['c_mm'] = '40'
    elif mutation == 'origin_type': c['origin'] = 123
    with pytest.raises(ValueError): configuration(d)
    with pytest.raises(ValueError): build_spec(d)


@pytest.mark.parametrize('name', list(DECLARATIONS))
def test_each_undeclared_condition_keeps_local_check_pending(name):
    d = ready(); d[FIELD]['declarations'][name] = False
    b = branch(d)
    assert b['status'] == 'not_evaluated' and 'index' not in b
    assert b['missing_declarations'] == [name]
    assert b['physical_conditions_verified'] is False


@pytest.mark.parametrize('c', [None, 0, -1, 19.999999])
def test_missing_invalid_or_below_table_contact_stays_pending(c):
    d = ready(); d[FIELD]['c_mm'] = c
    assert configuration(d) == d[FIELD]
    b = branch(d)
    assert b['status'] == 'not_evaluated' and 'index' not in b
    assert d[FIELD]['c_mm'] == c


def test_origin_is_required_without_inventing_one():
    d = ready(); d[FIELD]['origin'] = ' '
    assert branch(d)['status'] == 'not_evaluated'


def test_existing_legacy_inputs_remain_literal_and_other_mechanics_equal():
    d = example(); d.update(patch_mm=None, left_web=False, right_web=False,
                            patch_origin='Legado sem contato', support_origin='Garfos, não ligação real')
    original = copy.deepcopy(d); baseline = calculate(d)
    d[FIELD] = declared()
    d[FIELD]['basis'] = reference_basis(d)
    current = calculate(d)
    assert {k: v for k, v in d.items() if k != FIELD} == original
    assert {k: v for k, v in current['input_data'].items() if k != FIELD} == original
    assert current['input_snapshot'] == baseline['input_snapshot']
    assert mechanics(current) == mechanics(baseline)
    b = current['NBR_branches']['point']
    assert b['status'] == 'computed' and b['FRd_N'] == 10124.936073865776
    assert b['domain']['opposite_clear_distance_mm'] is None
    assert b['domain']['classification_basis'] == 'no_opposite_concentrated_force_declared'
    assert current['NBR_branches']['supports'] == baseline['NBR_branches']['supports']
    assert not current['whole_member_approved']


@pytest.mark.parametrize('parallel', [-1., 1., 1e-300])
@pytest.mark.parametrize('normal', [0., 1500.])
def test_any_parallel_point_component_prevents_local_approval(normal, parallel):
    d = ready(); d.update(P_uls=normal, P_parallel_uls=parallel)
    b = calculate(d)['NBR_branches']['point']
    assert b['status'] == 'not_evaluated' and 'index' not in b
    assert b['parallel_force_N'] == parallel


def test_negative_point_and_no_point_are_distinct():
    d = ready(); d['P_uls'] = -100.
    assert branch(d)['status'] == 'not_evaluated'
    d['P_uls'] = 0.
    assert branch(d)['status'] == 'not_applicable'


def test_end_distance_uses_physical_contact_edge_and_strict_boundary():
    d = ready(); h = 100 - 2*(2+2); boundary = 1.5*h+d[FIELD]['c_mm']/2
    d['x_uls'] = boundary
    d[FIELD]['basis'] = reference_basis(d)
    b = branch(d)
    assert b['status'] == 'not_evaluated' and b['domain']['end_distance_mm'] == 1.5*h
    d['x_uls'] = boundary+1e-8
    d[FIELD]['basis'] = reference_basis(d)
    assert branch(d)['status'] == 'computed'
    d['x_uls'] = d['L_mm']-boundary
    d[FIELD]['basis'] = reference_basis(d)
    assert branch(d)['status'] == 'not_evaluated'


@pytest.mark.parametrize('kind', ['c_min', 'ht', 'ct', 'ch', 'ri_u', 'ri_ue'])
def test_table_boundary_and_immediately_outside(kind):
    d = ready(); spec = build_spec(d); f = spec['selected_section']['fields']
    spec['selected_section']['family'] = 'U'
    if kind == 'c_min':
        d[FIELD]['c_mm'] = 20.; outside = lambda: d[FIELD].update(c_mm=20.-1e-8)
    elif kind == 'ht':
        f['t']['value']=1.; f['ri_mm']['value']=1.; f['h']['value']=204.
        outside = lambda: f['h'].update(value=204.+1e-8)
    elif kind == 'ct':
        f['t']['value']=1.; f['ri_mm']['value']=1.; f['h']['value']=154.; d[FIELD]['c_mm']=210.
        outside = lambda: d[FIELD].update(c_mm=210.+1e-8)
    elif kind == 'ch':
        d[FIELD]['c_mm']=184.
        outside = lambda: d[FIELD].update(c_mm=184.+1e-8)
    elif kind == 'ri_u':
        outside = lambda: f['ri_mm'].update(value=2.+1e-8)
    else:
        spec['selected_section']['family']='Ue';f['ri_mm']['value']=10.
        outside = lambda: f['ri_mm'].update(value=10.+1e-8)
    assert evaluate(d,spec)['status']=='computed'
    outside()
    assert evaluate(d,spec)['status']=='not_evaluated'


@pytest.mark.parametrize('no_opposite,distance', [(True,1.), (1,None), (False,None)])
def test_no_opposite_declaration_rejects_ambiguous_or_undeclared_data(no_opposite,distance):
    with pytest.raises(ValueError): classify(94.,1000.,distance,no_opposite_force=no_opposite)


def test_classification_extension_is_identical_to_existing_single_flange_formula():
    args=dict(h=94.,t=1.5,ri=1.5,c=40.,fy=250.,end_distance=1980.,connected=False,lip=True)
    old=frd(**args,opposite_clear_distance=141.)
    new=frd(**args,opposite_clear_distance=None,no_opposite_force=True)
    assert new==old
    with localcontext() as ctx:
        ctx.prec=50
        D=Decimal
        oracle=D('15.8')*D('1.5')**2*D(250)*(1-D('.23')*(D('1.5')/D('1.5')).sqrt())*(1+D('.14')*(D(40)/D('1.5')).sqrt())*(1-D('.01')*(D(94)/D('1.5')).sqrt())/D('1.35')
        assert new == pytest.approx(float(oracle), rel=2e-15)
        assert D(1500)/oracle == pytest.approx(D('0.18650787614660270760'), rel=D('1e-19'))


@pytest.mark.parametrize('family', ['single','family'])
def test_own_ue_contract_accepts_only_separate_option_and_preserves_protected_legacy(family):
    from tercas import ue_reference as single, ue_family_reference as group
    module = single if family=='single' else group
    data = module.load_reference() if family=='single' else module.load_reference(1.5)
    original = copy.deepcopy(data)
    data[FIELD] = declared()
    data[FIELD]['basis'] = reference_basis(data)
    assert module.assess(data)['active'] and module.assess(data)['calculable']
    changed = module.apply_span(data,4500.)
    assert changed[FIELD] == data[FIELD]
    for name in ('patch_mm','patch_origin','left_web','right_web','support_origin'):
        assert data[name] == original[name]
    for name,value in [('patch_mm',40.),('left_web',True),('right_web',True),('support_origin','new')]:
        bad=copy.deepcopy(data);bad[name]=value
        assert not module.assess(bad)['active']
    bad=copy.deepcopy(data);bad[FIELD]['declarations']['no_opposite_flange_force']=1
    assert not module.assess(bad)['active']


def test_own_family_direct_synthetic_oracle_and_all_other_results_unchanged():
    from tercas import ue_family_reference as module
    d=module.load_reference(1.5);d.update(load_mode='direct',q_uls=.1,q_sls=.05,P_uls=1500.,P_sls=0.,x_uls=2000.,x_sls=2000.)
    baseline=calculate(d);d[FIELD]=declared();d[FIELD]['basis']=reference_basis(d);current=calculate(d)
    assert mechanics(current)==mechanics(baseline)
    assert current['NBR_branches']['point']['FRd_N']==pytest.approx(8042.5557943780323,rel=2e-15)
    assert current['NBR_branches']['point']['index']==pytest.approx(.1865078761466027,rel=2e-15)


def test_support_limit_keeps_pending_and_never_uses_contact_as_point_position():
    from tercas.batch import calculate_batch,area_bundle
    d=example();d.update(load_mode='area',selected_types=['ELU normal'])
    baseline_bundle=area_bundle(d);baseline=calculate_batch(d);d[FIELD]=declared();d[FIELD]['basis']=reference_basis(d)
    current=calculate_batch(d)
    assert area_bundle(d)==baseline_bundle
    assert current['summary']==baseline['summary']
    for old,new in zip(baseline['cases'],current['cases']):
        assert old['combination']==new['combination'] and old['rows']==new['rows']
        e0=copy.deepcopy(old['evidence']);e1=copy.deepcopy(new['evidence'])
        e0['NBR_branches'].pop('point');e1['NBR_branches'].pop('point')
        assert e0==e1
        if new['combination'].get('point_position')=='support_limit':
            assert new['evidence']['NBR_branches']['point']==old['evidence']['NBR_branches']['point']
            assert new['evidence']['NBR_branches']['point']['status']=='not_evaluated'
    g0=build_global_verification(baseline);g1=build_global_verification(current)
    assert g1['whole_member_approved'] is False
    assert g1['maximum_available_check']['index']==g0['maximum_available_check']['index']
    assert all('CENTRO' not in key for key in g1['pending_ids'] if 'point_introduction_scope' in key)
    assert len([key for key in g1['pending_ids'] if 'APOIO' in key and 'point_introduction_scope' in key])==4


def test_report_and_export_transcribe_option_without_revalidating_or_calculating(monkeypatch):
    from tercas.report import word
    import tercas.point_contact as module
    d=ready();result=attach_global_verification(calculate(d));before=copy.deepcopy(result)
    restored=json.loads(json.dumps(result,ensure_ascii=False,allow_nan=False))
    assert restored==result and restored['input_data'][FIELD]==d[FIELD]
    def forbidden(*args,**kwargs):raise AssertionError('Historical presentation must not evaluate or validate.')
    monkeypatch.setattr(module,'evaluate',forbidden);monkeypatch.setattr(module,'configuration',forbidden)
    text='\n'.join(p.text for p in Document(BytesIO(word(result))).paragraphs)
    assert 'Introdução local de P — declarações salvas' in text
    assert '40.0 mm' in text and d[FIELD]['origin'] in text
    assert 'P no limite junto ao apoio continua fora do subconjunto' in text
    assert result==before


@pytest.mark.parametrize('mutation', ['span', 'position', 'application', 'section', 'material'])
def test_changed_physical_context_requires_explicit_reconfirmation(mutation):
    d=ready();saved=copy.deepcopy(d[FIELD])
    if mutation=='span':d['L_mm']+=100.
    elif mutation=='position':d['x_uls']+=100.
    elif mutation=='application':d['member_application']='wall_girt'
    elif mutation=='section':d['catalog_index']+=1
    else:d['properties']['fy_MPa']+=1.
    assert not basis_matches(d)
    assert d[FIELD]==saved
    # The comparison itself never changes declarations or updates their basis.
    d[FIELD]['basis']=reference_basis(d)
    assert basis_matches(d)


def test_inactive_direct_position_title_and_origin_do_not_change_area_binding():
    d=ready();d['load_mode']='area';d[FIELD]['basis']=reference_basis(d)
    d.update(x_uls=1.,project='Outro título',actions_origin='Outra origem')
    d[FIELD]['origin']='Detalhe esclarecido sem mudança física'
    assert basis_matches(d)
    from tercas.batch import area_bundle,case_inputs
    combo=next(c for c in area_bundle(d)['combinations'] if c['id'].endswith('CENTRO') and c['limit_state']=='ELU')
    assert branch(case_inputs(d,combo))['status']=='computed'


def test_null_binding_stays_pending_without_filling_it():
    d=ready();d[FIELD]['basis']=None
    assert branch(d)['status']=='not_evaluated' and d[FIELD]['basis'] is None


def test_catalog_scan_cannot_reuse_physical_declaration_for_other_section():
    from tercas.catalog_scan import inputs_for_section
    from tercas.catalogs import entries
    d=ready()
    index=next(i for i,e in enumerate(entries()) if i!=d['catalog_index'])
    transformed=inputs_for_section(d,index)
    assert transformed[FIELD]==d[FIELD]
    assert not basis_matches(transformed)


def test_huge_contact_integer_is_value_error_not_overflow():
    d=ready();d[FIELD]['c_mm']=10**400
    with pytest.raises(ValueError):configuration(d)


def test_nonfinite_index_stays_pending():
    d=ready();d['P_uls']=1e308
    spec=build_spec(d);spec['selected_section']['fields']['fy_MPa']['value']=1e-300
    b=evaluate(d,spec)
    assert b['status']=='not_evaluated' and 'index' not in b
    assert 'Índice local não representável' in b['reason']


def test_saved_complement_never_promotes_unlinked_history_and_is_read_only(monkeypatch):
    import tercas.point_contact as module
    d=ready();r=calculate(d);before=copy.deepcopy(r)
    old=copy.deepcopy(r);old['NBR_branches']['point'].pop('contact_contract')
    def forbidden(*args,**kw):raise AssertionError('Saved renderer must not solve/revalidate.')
    monkeypatch.setattr(module,'evaluate',forbidden);monkeypatch.setattr(module,'configuration',forbidden)
    records=saved_records(r)
    assert len(records)==1 and records[0]['status']=='computed'
    records=saved_records(old)
    assert len(records)==1 and records[0]['status']=='pending' and records[0]['index'] is None
    assert r==before


@pytest.mark.parametrize('mutation', ['force','ratio','criterion','parallel','null_contract','trace_x','trace_c','trace_end','trace_opposite','basis','digest','missing_digest'])
def test_saved_adversarial_snapshot_stays_pending_without_numbers(mutation):
    r=calculate(ready());raw=r['NBR_branches']['point']
    if mutation=='force':raw['force_N']+=1.
    elif mutation=='ratio':raw['index']*=2.
    elif mutation=='criterion':raw['criterion_status']='fails'
    elif mutation=='parallel':r['input_data']['P_parallel_uls']=1.
    elif mutation=='null_contract':raw['contact_contract']=None
    elif mutation=='trace_x':raw['domain']['x_mm']+=1.
    elif mutation=='trace_c':raw['domain']['c_mm']+=1.
    elif mutation=='trace_end':raw['domain']['end_distance_mm']+=1.
    elif mutation=='trace_opposite':raw['domain']['opposite_clear_distance_mm']=1000.
    elif mutation=='basis':r['input_data'][FIELD]['basis']['L_mm']+=1.
    elif mutation=='digest':raw['evidence_sha256']='bad'
    else:raw.pop('evidence_sha256')
    before=copy.deepcopy(r);record=saved_records(r)[0]
    assert record['status']=='pending' and record['index'] is None and record['FRd_N'] is None
    assert r==before


@pytest.mark.parametrize('field', ['H_external_mm','t_mm','ri_mm','fy_MPa','h_flat_mm'])
def test_saved_geometry_links_checked_even_with_recomputed_digest(field):
    from tercas.point_contact import _saved_digest
    r=calculate(ready());raw=r['NBR_branches']['point']
    raw['domain'][field]+=1.
    raw['evidence_sha256']=_saved_digest(raw)
    record=saved_records(r)[0]
    assert record['status']=='pending' and record['index'] is None


def test_active_contact_cannot_change_three_girt_mechanics_or_emit_local_check():
    from tercas.three_girt_application import defaults,calculate as calculate_three
    d=example();d.update(member_application='wall_girt',P_uls=0.,P_sls=0.,P_parallel_uls=0.,P_parallel_sls=0.,q_uls=.2,q_sls=.15,q_parallel_uls=.12,q_parallel_sls=.1)
    c=defaults();c.update(enabled=True,geometry_declared=True,axial_bars_declared=True,connections_declared=True,load_line_declared=True,
        origin='Synthetic QA',sc_y_mm=17.,sc_z_mm=0.,sc_origin='Synthetic QA',load_y_from_CG_mm=12.,load_z_from_CG_mm=5.,direct_pp_uls_N_mm=.04,direct_pp_sls_N_mm=.03,direct_brace_factor_uls=1.4,direct_brace_factor_sls=1.)
    d['three_girt_model']=c
    a=calculate_three(d);d[FIELD]=declared();d[FIELD]['basis']=reference_basis(d);b=calculate_three(d)
    assert 'NBR_branches' not in b and not saved_records(b)
    a.pop('input_fingerprint');b.pop('input_fingerprint');b['input_data'].pop(FIELD)
    assert a==b and b['whole_member_approved'] is False



def test_underflowed_positive_index_remains_pending_instead_of_zero():
    d=ready();d['P_uls']=5e-324
    b=evaluate(d,build_spec(d))
    assert b['status']=='not_evaluated' and 'index' not in b
    assert 'Índice local não representável' in b['reason']


def test_refused_saved_complement_does_not_rewrite_global_counts():
    r=attach_global_verification(calculate(ready()));saved_global=copy.deepcopy(r['global_verification'])
    r['NBR_branches']['point']['evidence_sha256']='invalid'
    item=saved_records(r)[0]
    assert item['status']=='pending' and 'contagens não foram recompostas' in item['reason']
    assert r['global_verification']==saved_global
