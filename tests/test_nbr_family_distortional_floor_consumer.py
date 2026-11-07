"""No Lm or restraint invented when consuming the all-halfwave model floor."""
import copy
import pytest
from tercas import nbr_ue_family_application as app,ue_catalog_reference as own,nbr_family_panorama as panorama
from tercas.application import fingerprint
from test_nbr_ue_family_application import source


def short(q=.03):
    result=source(53,q=q);d=result['input_data'];d.update(L_mm=800.,P_uls=0.,P_parallel_uls=0.,x_uls=400.,x_sls=400.)
    d['segments']=[dict(start_mm=0.,end_mm=800.,Ly_effective_mm=800.,Lz_effective_mm=800.,Cb_mode='one',restraint_provenance='Synthetic physical span only')]
    result['input_fingerprint']=fingerprint(d);return own.attach_source(result)


@pytest.mark.parametrize('q',[.03,10000.])
def test_short_member_fallback_keeps_conventional_reference_and_floor_distinct(q):
    result=app.attach(short(q));ev=result[app.FIELD];row=ev['records'][0];floor=row['strong_distortional_floor']
    assert floor is not None and floor['member_length_required'] is False
    assert not floor['effective_lengths_used'] and not floor['physical_supports_created']
    conventional=next(p for p in row['components'] if p['route']=='own_rounded_contour' and p['method']=='distortional')
    p=next(p for p in row['components'] if p['method']=='distortional_approximation_floor')
    assert conventional['index'] is None and conventional['capacity_Nmm'] is None
    assert p['index'] is not None and p['capacity_lower_bound_only'] and not p['physical_resistance_bound']
    assert p['capacity_Nmm']==floor['MRd_lower_bound_Nmm']
    result['model_domain_evidence']=dict(status='fixed_model_domain',conflict=False)
    checks,_=panorama.apply(result,[]);dist=next(r for r in checks if r['id']=='ELU:DIRECT_ELU:distortional')
    assert dist['status']==('meets' if p['index']<=1 else 'pending')
    assert dist['status']!='fails'
    bad=copy.deepcopy(result);bad[app.FIELD]['records'][0]['strong_distortional_floor']['MRd_lower_bound_Nmm']*=2
    bad[app.FIELD]['snapshot_sha256']=own.digest(bad[app.FIELD])
    with pytest.raises(ValueError):app.preserved(bad)


def test_long_reference_does_not_rewrite_existing_distortion():
    r=app.attach(source(53))[app.FIELD]['records'][0]
    assert r['strong_distortional_floor'] is None
    assert not any(p['method']=='distortional_approximation_floor' for p in r['components'])


def test_optional_floor_outside_method_does_not_discard_other_results(monkeypatch):
    from tercas import nbr_ue_strong_distortional_floor as floor,nbr_ue_family as provider
    def outside(*a,**k):raise provider.OutsideMethod('Synthetic numerical-domain failure')
    monkeypatch.setattr(floor,'assess',outside)
    result=app.attach(short());row=result[app.FIELD]['records'][0]
    p=next(p for p in row['components'] if p['method']=='distortional_approximation_floor')
    assert p['index'] is None and p['capacity_Nmm'] is None
    assert row['strong_distortional_floor']['status']=='outside_distortional_floor_method'
    assert row['strong_web_MV']['web_shear']['criterion_status']=='meets'
    assert app.preserved(result)==result[app.FIELD]
