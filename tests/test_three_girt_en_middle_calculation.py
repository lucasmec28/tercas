"""The new EN scope skips resistance work, never the physical three-girt source."""
import copy
import json
import time
from collections import Counter
from io import BytesIO
from pathlib import Path

import pytest
from docx import Document

from tercas import three_girt_scope as scope
from tercas.three_girt_warping import application as w, network
from tercas.three_girt_en_normal import application as en
from tercas.three_girt_assessment import application as assessment
from tercas.ue_family_reference import apply_geometry


def config(demand):
    out=en.reference_configuration(demand)
    out.update(intact_section_model_declared=True,section_model_origin='Synthetic central EN scope QA')
    return out


def reseal(demand):
    component=demand[en.FIELD]
    component['source_demand_sha256']=en.fingerprint(en.mechanical_source(demand))
    component['content_sha256']=en.fingerprint({k:v for k,v in component.items() if k!='content_sha256'})


def measured(demand):
    """Count real envelope calls by their owning beam, without changing formulas."""
    calls=Counter();evaluators=Counter();torsions=Counter();current=[]
    owners={id(b['torsion_state_parameters']):b['girt'] for c in demand['cases'] for b in c['model']['beams']}
    torsion_field=en.f.torsion_field
    evaluator=en._physical_witness_evaluator;envelope=en.si.envelope
    def track_torsion(parameters):
        torsions[owners[id(parameters)]]+=1
        return torsion_field(parameters)
    def track_evaluator(case,beam,*args,**kwargs):
        current[:]=[beam['girt']];evaluators[beam['girt']]+=1
        return evaluator(case,beam,*args,**kwargs)
    def track_envelope(*args,**kwargs):
        assert current
        calls[current[0]]+=1
        return envelope(*args,**kwargs)
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(en,'_physical_witness_evaluator',track_evaluator)
        patch.setattr(en.si,'envelope',track_envelope)
        patch.setattr(en.f,'torsion_field',track_torsion)
        start=time.perf_counter();result=en.calculate(demand,config(demand));seconds=time.perf_counter()-start
    return result,dict(seconds=seconds,envelope_calls=dict(calls),evaluator_calls=dict(evaluators),torsion_validation_calls=dict(torsions))


@pytest.fixture(scope='module',params=[1.2,1.5,3.35])
def pair(request):
    source=json.loads((Path(__file__).parent/'data/three_girt_normal_QA_input.json').read_text())
    if request.param==1.2:
        from tercas import ue_reference
        from tercas.ue_member_application import apply,editable
        data=apply(ue_reference.load_reference(angle=source['input_data']['inclination']['value'],L_mm=4000.),'wall_girt')
        for key in ue_reference.EDITABLE | editable(data):
            if key in source['input_data']:data[key]=copy.deepcopy(source['input_data'][key])
    else:data=apply_geometry(source['input_data'],request.param,4000.)
    data.update(load_mode='direct',q_uls=.1,q_sls=.1,q_parallel_uls=-.1,q_parallel_sls=-.1,
                actions_origin='Synthetic scope QA; not a physical project')
    raw=copy.deepcopy(source['configuration']['three_girt'])
    raw.update(brace_self_weight=False,direct_pp_uls_N_mm=0.,direct_pp_sls_N_mm=0.)
    cfg=w.current_configuration(data,raw)
    old=w.attach_g81(w.calculate(data,cfg))
    new=w.attach_g81(w.calculate(data,cfg,verification_scope=scope.SCHEMA))
    old_before=copy.deepcopy(old);new_before=copy.deepcopy(new)
    old_en,old_metrics=measured(old);new_en,new_metrics=measured(new)
    assert old==old_before and new==new_before
    print('EN_SCOPE_METRICS '+json.dumps(dict(t_mm=request.param,legacy=old_metrics,central=new_metrics),sort_keys=True))
    return old,new,old_en,new_en,old_metrics,new_metrics


def test_exact_central_result_and_full_source_are_unchanged(pair):
    old,new,old_en,new_en,old_metrics,new_metrics=pair
    assert new==dict(old,verification_scope=scope.record(old['input_fingerprint']))
    assert new_en['schema']==en.CENTRAL_SCHEMA and old_en['schema']==en.SCHEMA
    assert new_en[scope.FIELD]==new[scope.FIELD] and scope.FIELD not in old_en
    assert new_en['rows']==[r for r in old_en['rows'] if r['girt']=='middle']
    assert new_en['per_member']=={'middle':old_en['per_member']['middle']}
    # Every other field, including all section certificates and false flags,
    # is bit-for-bit identical. Only the explicit scope and its digest change.
    omitted={'schema',scope.FIELD,'content_sha256','source_demand_sha256','rows','per_member'}
    assert {k:v for k,v in new_en.items() if k not in omitted}=={k:v for k,v in old_en.items() if k not in omitted}
    assert new_en['source_demand_sha256']==en.fingerprint(en.mechanical_source(new))
    assert all(new_en[k] is False for k in en.FALSE_FLAGS)
    assert all({b['girt'] for b in c['model']['beams']}==set(scope.LEVELS) for c in new['cases'])
    assert old_metrics['envelope_calls']['middle']>0
    assert new_metrics['envelope_calls']=={'middle':old_metrics['envelope_calls']['middle']}
    assert set(old_metrics['envelope_calls'])==set(scope.LEVELS)
    assert new_metrics['evaluator_calls']=={'middle':old_metrics['evaluator_calls']['middle']}
    assert new_metrics['torsion_validation_calls']==old_metrics['torsion_validation_calls']
    assert set(new_metrics['torsion_validation_calls'])==set(scope.LEVELS)


def test_new_snapshot_read_display_assessment_and_word_do_not_recalculate(pair,monkeypatch):
    demand=copy.deepcopy(pair[1]);demand[en.FIELD]=copy.deepcopy(pair[3])
    def forbidden(*a,**k):raise AssertionError('Saved EN read cannot recalculate')
    for module,name in ((w,'calculate'),(network,'solve'),(en,'calculate'),(en,'build_component_sections'),
                        (en,'_profile_and_section'),(en.si,'envelope')):
        monkeypatch.setattr(module,name,forbidden)
    before=en.fingerprint(demand)
    restored=json.loads(json.dumps(demand,allow_nan=False))
    assert en.saved_component(restored) is restored[en.FIELD]
    assert en.fingerprint(restored[en.FIELD])==en.fingerprint(demand[en.FIELD])
    result=assessment.assess(restored)
    checks=next(g for g in result['groups'] if g['id']=='EN_section')['checks']
    assert {r['id'] for r in checks}=={'EN:middle:normal','EN:middle:shear','EN:middle:interaction'}
    assert not result['whole_member_approved'] and not result['combined_ELS_approved']
    from tercas.three_girt_en_normal import ui,report
    assert {r['Travessa'] for r in ui.rows(en.saved_component(restored))}=={'Central'}
    doc=Document();report.append(doc,restored)
    assert not any(c.text in ('Superior','Inferior') for t in doc.tables for r in t.rows for c in r.cells)
    from tercas.three_girt_warping.report import word
    full=Document(BytesIO(word(restored,assessment=result)))
    outer=[t for t in full.tables if any(c.text in ('Superior','Inferior') for r in t.rows for c in r.cells)]
    assert len(outer)==1  # Full mechanical context is intentionally preserved.
    assert en.fingerprint(demand)==before and en.fingerprint(restored)==before


@pytest.mark.parametrize('schema',[en.LEGACY_SCHEMA,en.LEGACY_SHEAR_SCHEMA,en.LEGACY_EFFECTIVE_SCHEMA,en.SCHEMA])
@pytest.mark.parametrize('scoped_demand',[False,True])
def test_legacy_three_member_snapshots_keep_original_coverage(pair,monkeypatch,schema,scoped_demand):
    demand=copy.deepcopy(pair[int(scoped_demand)])
    demand[en.FIELD]=copy.deepcopy(pair[2]);demand[en.FIELD]['schema']=schema;reseal(demand)
    before=copy.deepcopy(demand)
    def forbidden(*a,**k):raise AssertionError('Historical read cannot recalculate or reclassify')
    for module,name in ((w,'calculate'),(network,'solve'),(en,'calculate'),(en,'build_component_sections'),(en.si,'envelope')):
        monkeypatch.setattr(module,name,forbidden)
    assert en.saved_component(demand) is demand[en.FIELD]
    assert en.verification_members(demand[en.FIELD],demand)==scope.LEVELS
    assert set(demand[en.FIELD]['per_member'])==set(scope.LEVELS)
    assert scope.FIELD not in demand[en.FIELD]
    assert demand==before


@pytest.mark.parametrize('mutation',[
    lambda d:d[en.FIELD].pop(scope.FIELD),
    lambda d:d.pop(scope.FIELD),
    lambda d:d[en.FIELD][scope.FIELD].update(verified_members=['upper']),
    lambda d:d[scope.FIELD].update(verified_members=['upper']),
    lambda d:d[en.FIELD][scope.FIELD].update(model_members=['middle']),
    lambda d:d[en.FIELD][scope.FIELD].update(source_input_fingerprint='changed'),
    lambda d:d[en.FIELD]['rows'].pop(),
    lambda d:d[en.FIELD]['rows'].append(copy.deepcopy(d[en.FIELD]['rows'][0])),
    lambda d:d[en.FIELD]['rows'].reverse(),
    lambda d:d[en.FIELD]['rows'][0].update(girt='upper'),
    lambda d:d[en.FIELD]['rows'][0].update(x_start_mm=1.),
    lambda d:d[en.FIELD]['per_member'].update(upper=copy.deepcopy(d[en.FIELD]['per_member']['middle'])),
    lambda d:d[en.FIELD].update(whole_member_approved=True),
])
def test_new_scope_and_coverage_tampering_rejected_after_rehash(pair,mutation):
    d=copy.deepcopy(pair[1]);d[en.FIELD]=copy.deepcopy(pair[3]);mutation(d);reseal(d)
    with pytest.raises(ValueError):en.saved_component(d)


@pytest.mark.parametrize('schema',[en.LEGACY_SCHEMA,en.LEGACY_SHEAR_SCHEMA,en.LEGACY_EFFECTIVE_SCHEMA,en.SCHEMA])
def test_central_cannot_be_downgraded_to_three_member_schema_even_rehashed(pair,schema):
    d=copy.deepcopy(pair[1]);d[en.FIELD]=copy.deepcopy(pair[3]);d[en.FIELD]['schema']=schema
    d[en.FIELD].pop(scope.FIELD);reseal(d)
    with pytest.raises(ValueError,match='coverage'):en.saved_component(d)


@pytest.mark.parametrize('mutation',[
    lambda d:d[en.FIELD].update(verification_scope=copy.deepcopy(d[scope.FIELD])),
    lambda d:d[en.FIELD].update(schema=en.CENTRAL_SCHEMA,verification_scope=copy.deepcopy(d[scope.FIELD])),
    lambda d:d[en.FIELD].update(schema=en.CENTRAL_SCHEMA),
])
def test_three_member_snapshot_cannot_be_relabelled_by_marker_or_schema(pair,mutation):
    d=copy.deepcopy(pair[1]);d[en.FIELD]=copy.deepcopy(pair[2]);mutation(d);reseal(d)
    with pytest.raises(ValueError):en.saved_component(d)


@pytest.mark.parametrize('level',['upper','lower'])
def test_source_context_required_even_after_all_hashes_are_rebuilt(pair,monkeypatch,level):
    d=copy.deepcopy(pair[1]);d[en.FIELD]=copy.deepcopy(pair[3])
    model=d['cases'][0]['model'];model['beams']=[b for b in model['beams'] if b['girt']!=level]
    model['demand_content_sha256']=w.fingerprint({k:v for k,v in model.items() if k!='demand_content_sha256'})
    reseal(d)
    def forbidden(*a,**k):raise AssertionError('Reject incomplete source before section/envelope work')
    monkeypatch.setattr(en,'build_component_sections',forbidden)
    monkeypatch.setattr(en.si,'envelope',forbidden)
    with pytest.raises(ValueError,match='coverage'):en.saved_component(d)
    with pytest.raises(ValueError,match='Missing physical member span'):en.calculate(d,config(d))
    assert assessment.assess(d)['pending_ids']==['saved_demand_integrity']


def test_invalid_outer_torsion_field_still_blocks_new_calculation_after_rehash(pair,monkeypatch):
    d=copy.deepcopy(pair[1]);model=d['cases'][0]['model']
    beam=next(b for b in model['beams'] if b['girt']=='upper')
    beam['torsion_state_parameters']['ECw_Nmm4']=-1.
    model['demand_content_sha256']=w.fingerprint({k:v for k,v in model.items() if k!='demand_content_sha256'})
    def forbidden(*a,**k):raise AssertionError('Invalid outer field precedes resistance work')
    monkeypatch.setattr(en.si,'envelope',forbidden)
    with pytest.raises(ValueError,match='Invalid exact torsion parameters'):en.calculate(d,config(d))


def test_central_snapshot_cannot_claim_computed_with_no_ELU_coverage(pair):
    d=copy.deepcopy(pair[1]);d[en.FIELD]=copy.deepcopy(pair[3])
    d['cases']=[c for c in d['cases'] if c['combination']['limit_state']=='ELS']
    d[en.FIELD]['rows']=[];d[en.FIELD]['per_member']={};reseal(d)
    with pytest.raises(ValueError,match='nonempty ELU coverage'):en.saved_component(d)
