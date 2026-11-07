import copy
import pytest
from tercas import nbr_family_panorama as p, nbr_family_member as member
from tercas import nbr_ue_family_application as app
from test_nbr_family_member import fixture,part


def packet(monkeypatch,weak_missing=False):
    row,sources=fixture()
    if weak_missing:part(row,'weak_positive_FLT_reference')['index']=None
    row['member_interaction']=member.build(row,sources,10.)
    ev=dict(schema='nbr_ue_family_application_v2',records=[row],sources=sources,
        resistance_lengths=dict(Lx_mm=10.,Ly_mm=10.,Lz_mm=10.,origin='synthetic'),physical_span_mm=10.)
    result={app.FIELD:ev,'model_domain_evidence':dict(status='fixed_model_domain',conflict=False)}
    monkeypatch.setattr(app,'preserved',lambda r:ev)
    return result


def old():return [dict(id='ELU:synthetic:'+k,status='pending') for k in ('local','distortional','FLT:1','FLT_height','FLT_coverage','biaxial','MV','shear')]


def test_overlay_replaces_only_authenticated_current_conditions(monkeypatch):
    result=packet(monkeypatch);records,binding=p.apply(result,old())
    ids=[r['id'] for r in records]
    assert len(ids)==len(set(ids))==7
    assert 'ELU:synthetic:FLT:1' not in ids and 'ELU:synthetic:FLT_height' not in ids
    assert next(r for r in records if r['id'].endswith(':MV'))['status']=='pending'
    assert next(r for r in records if r['id'].endswith(':biaxial'))['status']=='fails'
    result['global_verification']=dict(checks=records,**{p.BINDING:binding})
    p.validate_saved(result)


def test_missing_actual_weak_flt_remains_pending(monkeypatch):
    result=packet(monkeypatch,True);records,binding=p.apply(result,old())
    assert next(r for r in records if r['id'].endswith(':FLT:family'))['status']=='pending'
    assert next(r for r in records if r['id'].endswith(':biaxial'))['status']=='pending'
    assert next(r for r in records if r['id'].endswith(':local'))['status']!='pending'


@pytest.mark.parametrize('mutation',['missing','old','index','binding'])
def test_saved_panorama_corruption_rejected(monkeypatch,mutation):
    result=packet(monkeypatch);records,binding=p.apply(result,old())
    result['global_verification']=dict(checks=records,**{p.BINDING:binding})
    if mutation=='missing':records.pop()
    elif mutation=='old':records.append(dict(id='ELU:synthetic:FLT:1',status='meets'))
    elif mutation=='index':next(r for r in records if r['id'].endswith(':biaxial'))['index']=0.
    else:binding['source_packet_sha256']='forged'
    with pytest.raises(ValueError):p.validate_saved(result)


def test_legacy_and_empty_no_requalification(monkeypatch):
    result=packet(monkeypatch);result[app.FIELD]['schema']='nbr_ue_family_application_v1'
    original=old();before=copy.deepcopy(original)
    assert p.apply(result,original)==(original,None) and original==before
    p.validate_saved(result)
    result[app.FIELD]['schema']='nbr_ue_family_application_v2';result[app.FIELD]['records']=[]
    assert p.apply(result,original)==(original,None)


def test_model_domain_conflict_keeps_all_current_records_pending(monkeypatch):
    result=packet(monkeypatch);result['model_domain_evidence']['conflict']=True
    records,binding=p.apply(result,old())
    current=[r for r in records if r['id'] in binding['record_ids']]
    assert all(r['status']=='pending' for r in current)
