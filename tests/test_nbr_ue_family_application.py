"""Synthetic complete-family consumer, source replay and presentation tests."""
import copy
import json
import pytest
from docx import Document
from tercas import nbr_ue_family_application as app, nbr_ue_family_ui as ui
from tercas import ue_catalog_reference as own, pierin_ue_registry as registry
from tercas.application import fingerprint
from en_ue_test_helpers import inputs


def source(index=26, mode='direct', q=.03, py=.2):
    data=inputs(index,mode=mode,L=6000.)
    data.update(q_uls=q,q_parallel_uls=.001,P_parallel_uls=py,P_uls=10.,x_uls=2000.)
    result=dict(input_data=data,input_fingerprint=fingerprint(data),schema='NBR14762_one_span_v1',legacy_capacity=123.)
    if mode=='area':
        from tercas.batch import area_bundle
        bundle=area_bundle(data)
        result.update(schema='tercas_batch_results_v1',load_bundle=bundle,cases=[dict(combination=c) for c in bundle['combinations']])
    return own.attach_source(result)


@pytest.mark.parametrize('index',registry.new_study_indices())
def test_complete_family_components_used_in_actual_direct_cases(index):
    old=source(index);new=app.attach(old);ev=new[app.FIELD]
    assert app.FIELD not in old and new['legacy_capacity']==123.
    assert len(ev['records'])==1 and ev['ignored_ELS_cases']==1
    record=ev['records'][0]
    assert record['combination_id']=='DIRECT_ELU'
    nominal=[c for c in record['components'] if c['route']=='published_nominal_reference']
    assert len(nominal)==2 and all(c['index'] is not None for c in nominal)
    assert all(c['capacity_Nmm']>0 for c in nominal)
    assert not ev['whole_member_approved'] and not ev['legacy_denominators_replaced']
    assert record['load_position_by_axis']['normal']['classification']=='destabilizing'
    classical=next(c for c in record['components'] if c['method']=='FLT_reference')
    assert classical['index'] is None
    assert all(c['demand']['axis']=='parallel' for c in record['components'] if c['method'].startswith('weak'))


def test_stabilizing_actions_enable_classical_without_height_bonus():
    ev=app.attach(source(q=-1.))[app.FIELD]
    assert ev['records'][0]['load_position_by_axis']['normal']['classification']=='destabilizing'
    old=source(q=-1.);old['input_data']['P_uls']=0.
    old['input_fingerprint']=fingerprint(old['input_data']);old=own.attach_source(old)
    ev=app.attach(old)[app.FIELD];row=ev['records'][0]
    assert row['load_position_by_axis']['normal']['classification']=='stabilizing'
    assert next(c for c in row['components'] if c['method']=='FLT_reference')['index']>0


def test_effective_lengths_change_reference_not_demands():
    from tercas.resistance_effective_lengths import declare
    old=source();a=app.attach(old)[app.FIELD]
    old['input_data']=declare(old['input_data'],Lx_mm=3000.,Ly_mm=3500.,Lz_mm=4000.,origin='synthetic test')
    old['input_fingerprint']=fingerprint(old['input_data']);old=own.attach_source(old)
    b=app.attach(old)[app.FIELD]
    ac=a['records'][0]['components'];bc=b['records'][0]['components']
    # Fresh full-span q+P now uses the existing reference, while shortened
    # resistance lengths retain a separate sufficient floor component.
    ad={(c['route'],c['method']):c['demand'] for c in ac}
    bd={(c['route'],c['method']):c['demand'] for c in bc}
    assert all(ad[key]==bd[key] for key in ad.keys() & bd.keys())
    assert bd['own_rounded_contour','FLT_height_energy_floor']==ad['own_rounded_contour','FLT_height_effective_reference']
    assert next(c for c in ac if c['method']=='FLT_reference')['capacity_Nmm']!=next(c for c in bc if c['method']=='FLT_reference')['capacity_Nmm']
    assert b['physical_span_mm']==6000.


def test_area_inventory_and_each_elu_not_only_governing():
    new=app.attach(source(mode='area'));ev=new[app.FIELD]
    assert len(ev['records'])==sum(c['limit_state']=='ELU' for c in new['load_bundle']['combinations'])
    assert len(ev['records'])>1
    assert app.preserved(json.loads(json.dumps(new)))==ev
    bad=copy.deepcopy(new);bad['cases'].pop()
    with pytest.raises(ValueError):app.preserved(bad)


@pytest.mark.parametrize('mutation',[
    lambda e:e['records'].pop(),
    lambda e:e['records'][0]['actions'].pop(),
    lambda e:e['records'][0]['components'][0].update(index=0.),
    lambda e:e['records'][0]['components'][0].update(capacity_Nmm=1e20),
    lambda e:e['records'][0]['components'][0]['demand']['witness'].update(x_mm=0.),
    lambda e:e['sources']['published_nominal_reference']['strong']['local'].update(MRd_Nmm=1e20),
    lambda e:e.update(whole_member_approved=True),
    lambda e:e['inventory'].pop(),
])
def test_full_replay_rejects_rehashed_forgery(mutation):
    new=app.attach(source());mutation(new[app.FIELD])
    new[app.FIELD]['snapshot_sha256']=own.digest(new[app.FIELD])
    with pytest.raises(ValueError):app.preserved(new)


def test_new_negative_reference_remains_sign_specific_and_not_member_approval():
    row=app.attach(source(py=-100.))[app.FIELD]['records'][0]
    assert row['weak_negative_complete']
    assert not row['whole_member_approved']
    distortion=next(c for c in row['components'] if c['method']=='weak_negative_distortional')
    assert distortion['approximate']
    negative=next(c for c in row['components'] if c['method']=='weak_negative_local')
    positive=next(c for c in row['components'] if c['method']=='weak_positive_local')
    assert negative['demand']['Msd_Nmm']>0 and positive['demand']['Msd_Nmm']==0
    assert negative['demand']['witness']['My_Nmm']<0


def test_ui_word_json_and_legacy_are_read_only(monkeypatch):
    from tercas import roof_top_load
    monkeypatch.setattr(roof_top_load,'refined',lambda **kw:pytest.fail('reader invokes eigen solver'))
    new=app.attach(source());assert app.preserved(json.loads(json.dumps(new)))==new[app.FIELD]
    class UI:
        def __init__(self):self.tables=[]
        def subheader(self,*a):pass
        def caption(self,*a):pass
        def warning(self,*a):pytest.fail(str(a))
        def dataframe(self,rows,**kw):self.tables.append(rows)
    count=len(new[app.FIELD]['records'][0]['components'])
    st=UI();ui.show(st,new);assert len(st.tables[0])==count and len(st.tables[1])==1
    doc=Document();ui.report(doc,new);assert len(doc.tables)==1 and len(doc.tables[0].rows)==count+1
    legacy=source();before=copy.deepcopy(legacy)
    assert app.preserved(legacy) is None
    ui.report(Document(),legacy);assert legacy==before


@pytest.mark.parametrize('disabled',[False,True])
def test_missing_or_disabled_roof_scheme_keeps_local_and_explicit_position_pending(disabled):
    old=source()
    if disabled:old['input_data']['roof_top_load']['enabled']=False
    else:old['input_data'].pop('roof_top_load')
    old['input_fingerprint']=fingerprint(old['input_data']);old=own.attach_source(old)
    row=app.attach(old)[app.FIELD]['records'][0]
    assert row['load_position_by_axis']['normal']['classification']=='unknown'
    local=next(c for c in row['components'] if c['method']=='local' and c['route']=='own_rounded_contour')
    assert local['index']>0
    assert next(c for c in row['components'] if c['method']=='FLT_reference')['index'] is None


def test_unverified_height_eigenvalue_cannot_create_new_family_capacity():
    old=source();expected=app.attach(old)[app.FIELD]
    old['roof_top_load_evidence']={'Me_Nmm':1e99,'snapshot_sha256':'forged'}
    actual=app.attach(old)[app.FIELD]
    # The current reference is recomputed from authenticated actions/geometry;
    # neither the fake critical value nor its claimed hash can enter capacity.
    assert actual==expected
    row=actual['records'][0]
    assert row['height_source']['Me_Nmm']!=1e99
    assert row['height_source']['elastic_reference_eligible']


def test_completion_pipeline_includes_new_packet_without_old_denominator_changes(monkeypatch):
    from tercas import study_completion, torsion_study, aisi_torsion_component, isolated_en_application, roof_top_load, roof_top_nbr
    for module, name in [(torsion_study,'attach'),(aisi_torsion_component,'finalize'),
                         (isolated_en_application,'finalize'),(roof_top_load,'attach'),(roof_top_nbr,'attach')]:
        monkeypatch.setattr(module,name,lambda result:result)
    monkeypatch.setattr(study_completion,'build_global_verification',lambda result:dict(status='inconclusivo'))
    result=study_completion.complete_result(source())
    assert app.FIELD in result and not result['whole_member_approved']
    assert result['legacy_capacity']==123.
    assert not result['completion_snapshot']['historical_results_requalified']


@pytest.mark.parametrize('network',[{'enabled':True}, 'malformed', ['enabled'], {'enabled':'false'}])
def test_network_active_or_malformed_never_consumes_isolated_demands(network,monkeypatch):
    old=source();old['input_data']['three_girt_model']=network
    old['input_fingerprint']=fingerprint(old['input_data'])
    old['existing_network_component']={'N_N':500.,'unchanged':True}
    monkeypatch.setattr(app,'_inventory',lambda result:pytest.fail('network entered isolated inventory'))
    new=app.attach(old);ev=new[app.FIELD]
    assert ev['status']=='outside_isolated_N0_domain' and not ev['records']
    assert ev['pending_reason'] and ev['sources'] is None
    assert new['existing_network_component']==old['existing_network_component']
    assert app.preserved(new)==ev


def test_source_packet_does_not_copy_unrelated_result_fields(monkeypatch):
    from tercas import nbr_ue_family as provider
    from tercas.resistance_effective_lengths import configuration
    original = source()
    baseline = app._build(original)
    expected_packet = provider.attach(original, fresh_calculation=True,
        lengths=configuration(original['input_data']),
        load_position=baseline['sources']['own_rounded_contour']['load_position'])[provider.FIELD]
    class Poison:
        def __deepcopy__(self, memo):
            raise AssertionError('Source packet copied unrelated whole-result evidence')
    original['unrelated_EN_ELU_evidence'] = Poison()
    actual_attach = provider.attach
    argument_keys = []
    def record_inputs(result, **kwargs):
        argument_keys.append(set(result))
        return actual_attach(result, **kwargs)
    monkeypatch.setattr(provider, 'attach', record_inputs)
    actual = app._build(original)
    assert argument_keys == [{'input_data'}]
    assert actual == baseline
    # Includes identical source digest and every source field, not a digest-only test.
    encode = lambda value: json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False).encode()
    assert encode(actual['sources']) == encode(expected_packet)


def test_distortional_inapplicability_count_requires_exact_status_and_proof():
    ev=app._build(source())
    positive=ev['method_coverage']['own_rounded_contour:weak_positive_distortional']
    negative=ev['method_coverage']['own_rounded_contour:weak_negative_distortional']
    assert positive['not_applicable_cases']==1 and positive['pending_cases']==0
    assert positive['indexed_cases']==0
    proof=ev['sources']['own_rounded_contour']['weak']['positive']['local']['proof']
    assert positive['not_applicable_basis']==dict(status='not_applicable_lips_in_tension',proof=proof)
    assert negative['not_applicable_cases']==0 and negative['pending_cases']==0
    assert negative['indexed_cases']==1
    assert negative['not_applicable_basis'] is None
    row=next(c for c in ev['records'][0]['components'] if c['method']=='weak_positive_distortional')
    assert row['index'] is None and row['capacity_Nmm'] is None
    for change in ('proof', 'status', 'eligible'):
        sources=copy.deepcopy(ev['sources']);weak=sources['own_rounded_contour']['weak']['positive']
        if change=='proof':weak['local']['proof']['lips_in_tension_for_positive_pure_weak']=False
        elif change=='status':weak['distortional']['status']='susceptibility_not_resolved'
        else:weak['distortional']['eligible']=False
        assert app._not_applicable_basis(row,sources) is None
    for count in ev['method_coverage'].values():
        assert count['total_ELU_cases']==count['indexed_cases']+count['not_applicable_cases']+count['pending_cases']


def test_coverage_summary_is_visible_in_ui_and_word(monkeypatch):
    new=app.attach(source());captions=[]
    class UI:
        def subheader(self,*a):pass
        def caption(self,text):captions.append(text)
        def warning(self,*a):pytest.fail(str(a))
        def dataframe(self,*a,**kw):pass
    ui.show(UI(),new)
    summary=ui.coverage_summary(new[app.FIELD])
    assert summary in captions and '1 dispensados/não aplicáveis, 0 pendentes' in summary
    assert '0 dispensados/não aplicáveis, 1 pendentes' in summary
    doc=Document();ui.report(doc,new)
    assert summary in [p.text for p in doc.paragraphs]


def test_table14_exemption_is_not_an_unresolved_susceptibility():
    component=dict(route='own_rounded_contour',method='distortional',index=None,status='not_required_table14')
    sources=dict(own_rounded_contour=dict(strong=dict(distortional=dict(
        eligible=True,status='not_required_table14',MRd_Nmm=None,table14=dict(exempt=True,source='synthetic proof')))))
    assert app._not_applicable_basis(component,sources)==dict(status='not_required_table14',proof=sources['own_rounded_contour']['strong']['distortional']['table14'])
    sources['own_rounded_contour']['strong']['distortional']['table14']['exempt']=False
    assert app._not_applicable_basis(component,sources) is None
