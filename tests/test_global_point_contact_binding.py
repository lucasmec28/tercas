"""Saved contact acceptance only. No new resistance or physical declarations."""
import copy
import pytest

from tercas.application import example, calculate
from tercas.batch import calculate_batch
from tercas.global_verification import build_global_verification
from tercas.point_contact import (FIELD, SCHEMA, SCHEMA_V2, DECLARATIONS,
    blank_choice, reference_basis, _saved_digest, saved_records)


def data(schema=None, x=1500., force=1500.):
    d=example();d.update(x_uls=x,P_uls=force)
    if schema:
        c=blank_choice();c.update(schema=schema,enabled=True,c_mm=40.,
            origin='Synthetic QA: current contact and both web supports',basis=reference_basis(d))
        c['declarations']={k:True for k in DECLARATIONS};d[FIELD]=c
    return d


def local(result,cid='DIRECT_ELU'):
    return next(c for c in build_global_verification(result)['checks']
                if c['id']=='ELU:'+cid+':point_introduction_scope')


@pytest.fixture(scope='module')
def samples():
    return {'legacy':calculate(data()),'v1':calculate(data(SCHEMA)),
            'v2':calculate(data(SCHEMA_V2,20.)),
            'failed_v1':calculate(data(SCHEMA,force=30000.))}


@pytest.mark.parametrize('kind',['legacy','v1','v2','failed_v1'])
def test_legitimate_saved_numeric_result_and_input_are_preserved(samples,kind):
    r=copy.deepcopy(samples[kind]);before=copy.deepcopy(r);raw=r['NBR_branches']['point']
    c=local(r)
    assert c['status']==('meets' if raw['index']<=1 else 'fails')
    assert c['index']==raw['index'] and r==before
    assert not build_global_verification(r)['whole_member_approved']


@pytest.mark.parametrize('kind',['v1','v2'])
@pytest.mark.parametrize('mutation',['force','source','origin','digest','missing_digest',
    'contact_contract','position','input_force','geometry','declaration'])
@pytest.mark.parametrize('rehash',[False,True])
def test_typed_contact_swaps_never_receive_an_active_index(samples,kind,mutation,rehash):
    r=copy.deepcopy(samples[kind]);raw=r['NBR_branches']['point'];d=r['input_data']
    if mutation=='force':raw['force_N']+=1.
    elif mutation=='source':raw['source']='Different source'
    elif mutation=='origin':raw['origin']='Different contact detail'
    elif mutation=='digest':raw['evidence_sha256']='wrong'
    elif mutation=='missing_digest':raw.pop('evidence_sha256')
    elif mutation=='contact_contract':raw['contact_contract']['c_mm']+=1.
    elif mutation=='position':d['x_uls']+=1.
    elif mutation=='input_force':d['P_uls']+=1.
    elif mutation=='geometry':d['properties']['t']+=.01
    else:d[FIELD]['declarations']['no_local_stiffener']=False
    if rehash and mutation not in ('digest','missing_digest'):
        raw['evidence_sha256']=_saved_digest(raw)
    before=copy.deepcopy(r);c=local(r)
    assert c['status']=='pending' and c['index'] is None
    assert c['diagnostic_index']==raw['index'] and r==before
    assert 'resistência não recalculada' in c['reason']


@pytest.mark.parametrize('mutation',['force','origin','position','index','support',
    'support_origin','snapshot','typed_marker'])
def test_legacy_producer_keeps_original_scalar_and_snapshot_binding(samples,mutation):
    r=copy.deepcopy(samples['legacy']);raw=r['NBR_branches']['point']
    if mutation=='force':raw['force_N']+=1.
    elif mutation=='origin':raw['origin']='Different detail'
    elif mutation=='position':raw['patch_mm'][0]+=1.
    elif mutation=='index':raw['index']/=2.
    elif mutation=='support':r['input_data']['left_web']=False
    elif mutation=='support_origin':r['input_data']['support_origin']=''
    elif mutation=='snapshot':r['input_snapshot']['ULS']['P_N']+=1.
    else:raw['evidence_sha256']='not a legacy record'
    assert local(r)['status']=='pending'


@pytest.fixture(scope='module')
def batches():
    out={}
    for kind,schema in [('legacy',None),('v1',SCHEMA),('v2',SCHEMA_V2)]:
        d=data(schema);d.update(load_mode='area',selected_types=['ELU normal'])
        if schema:d[FIELD]['basis']=reference_basis(d)
        out[kind]=calculate_batch(d)
    return out


@pytest.mark.parametrize('kind',['legacy','v1','v2'])
def test_batch_real_contacts_and_support_limit_keep_their_distinct_scope(batches,kind):
    r=batches[kind];g=build_global_verification(r)
    for case in r['cases']:
        combo=case['combination'];raw=case['evidence']['NBR_branches']['point']
        if combo.get('point_position')=='center':
            c=local(r,combo['id']);assert c['status']==('meets' if raw['index']<=1 else 'fails')
            assert c['index']==raw['index']
        elif combo.get('point_position')=='support_limit':
            c=local(r,combo['id']);assert c['status']=='not_applicable' and c['index'] is None
            assert c['trace']['physical_contact_checked'] is False
    assert len(g['point_limit_exclusion_ids'])==4


@pytest.mark.parametrize('kind',['legacy','v1','v2'])
@pytest.mark.parametrize('mutation',['case_force','case_position','case_expression',
    'evidence_force','different_combination_contact'])
def test_batch_binding_uses_expected_combination_and_saved_action(batches,kind,mutation):
    r=copy.deepcopy(batches[kind])
    centers=[c for c in r['cases'] if c['combination'].get('point_position')=='center']
    case=centers[0];cid=case['combination']['id']
    # The producer shares the case and bundle dictionary; detach to model a
    # mismatched serialized case without changing the expected inventory.
    case['combination']=copy.deepcopy(case['combination'])
    if mutation=='case_force':case['combination']['P_N']+=1.
    elif mutation=='case_position':case['combination']['x_mm']+=1.
    elif mutation=='case_expression':case['combination']['expression']='Different combination'
    elif mutation=='evidence_force':case['evidence']['inclination']['P_vector']['normal']+=1.
    else:
        schema={'legacy':None,'v1':SCHEMA,'v2':SCHEMA_V2}[kind]
        other=calculate(data(schema,force=1250.))
        case['evidence']['NBR_branches']['point']=copy.deepcopy(other['NBR_branches']['point'])
    assert local(r,cid)['status']=='pending'


@pytest.mark.parametrize('kind',['legacy','v1','v2'])
def test_equal_local_contact_inputs_in_distinct_combinations_are_not_rejected(batches,kind):
    r=copy.deepcopy(batches[kind])
    centers=[c for c in r['cases'] if c['combination'].get('point_position')=='center']
    assert centers[0]['combination']['id']!=centers[1]['combination']['id']
    assert centers[0]['combination']['P_N']==centers[1]['combination']['P_N']
    centers[0]['evidence']['NBR_branches']['point']=copy.deepcopy(centers[1]['evidence']['NBR_branches']['point'])
    assert local(r,centers[0]['combination']['id'])['status']=='meets'


def test_saved_acceptance_never_calls_a_resistance_or_solver(samples,batches,monkeypatch):
    import tercas.point_contact as pc
    import tercas.core.anexo_d as ad
    import tercas.core.ramos_genericos as rg
    def forbidden(*a,**k):raise AssertionError('No resistance or solver during saved acceptance')
    monkeypatch.setattr(pc,'evaluate',forbidden);monkeypatch.setattr(ad,'frd',forbidden)
    monkeypatch.setattr(rg,'frd',forbidden);monkeypatch.setattr(rg,'calculate',forbidden)
    for r in list(samples.values())+list(batches.values()):build_global_verification(r)


def test_the_original_unrelated_record_reproduction_is_pending(samples):
    r=copy.deepcopy(samples['v1'])
    r['NBR_branches']['point']={'status':'computed','index':.1,'force_N':2000.,
                              'source':'unrelated','evidence_sha256':'wrong'}
    assert local(r)['status']=='pending' and local(r)['index'] is None


@pytest.mark.parametrize('raw',[None,[],0,'computed'])
def test_malformed_point_object_is_pending_without_throwing(samples,raw):
    r=copy.deepcopy(samples['v1']);r['NBR_branches']['point']=raw
    assert local(r)['status']=='pending' and local(r)['index'] is None


def test_origin_guard_is_shared_with_saved_contact_report(samples):
    r=copy.deepcopy(samples['v1']);raw=r['NBR_branches']['point']
    raw['origin']='Different origin';raw['evidence_sha256']=_saved_digest(raw)
    assert saved_records(r)[0]['status']=='pending' and local(r)['status']=='pending'
