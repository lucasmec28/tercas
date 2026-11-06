"""Pure synthetic scalar cases, no project fixture or structural solver."""
import copy
import pytest
from tercas import roof_biaxial_positive as b


def combo(qx=2., px=0., qy=1., py=0., a=5.):
    return dict(x_mm=a, q_vector=dict(normal=qx, parallel=qy),
                P_vector=dict(normal=px, parallel=py))


def test_positive_two_polynomials_per_piece():
    c=combo();r=b.interaction(c,10.,100.,50.)
    assert r['governing']==dict(x_mm=5.,Mx_Nmm=25.,My_Nmm=12.5,index=.5)
    assert len(r['envelope_certificate'])==4
    assert b.validate_saved(r,c,10.,100.,50.)==r


def test_zero_weak_needs_no_capacity():
    c=combo(qy=0.);r=b.interaction(c,10.,100.)
    assert r['positive_capacity_Nmm'] is None
    assert r['My_identically_zero'] is True
    assert r['governing']['index']==.25
    b.validate_saved(r,c,10.,100.)


def test_negative_interior_with_nonnegative_breakpoint():
    # qy<0 gives a convex piece; positive My(P) hides a negative interior.
    c=combo(qy=-1.,py=6.,a=2.)
    r=b.interaction(c,10.,100.,50.)
    assert r['maximum_My_Nmm']>0
    assert r['minimum_My_Nmm']<0
    assert r['missing']==['weak_negative'] and r['governing'] is None
    b.validate_saved(r,c,10.,100.,50.)


def test_missing_positive_capacity():
    c=combo();r=b.interaction(c,10.,100.)
    assert r['missing']==['weak_positive']
    b.validate_saved(r,c,10.,100.)


@pytest.mark.parametrize('a',[0.,2.,5.,10.])
@pytest.mark.parametrize('qx,px',[(2.,0.),(-2.,0.),(2.,-8.),(-2.,8.)])
def test_mixed_strong_sign_and_point_endpoints(a,qx,px):
    c=combo(qx=qx,px=px,a=a);r=b.interaction(c,10.,100.,50.)
    b.validate_saved(r,c,10.,100.,50.)
    # Dense check is test oracle only; production is fully continuous.
    for i in range(1001):
        assert b._state(i/100,c,10.,100.,50.)['index'] <= r['governing']['index']+1e-12


@pytest.mark.parametrize('mutation',[
    lambda r:r['sign_certificate'].pop(),
    lambda r:r['envelope_certificate'].pop(),
    lambda r:r['sign_certificate'][0].update(minimum_My_Nmm=1.),
    lambda r:r['envelope_certificate'][0].update(coefficients=[1.,0.,0.]),
    lambda r:r.update(candidate_count=999),
    lambda r:r.update(governing=dict(x_mm=0.,Mx_Nmm=0.,My_Nmm=0.,index=0.)),
    lambda r:r.update(whole_member_approved=True),
    lambda r:r.update(positive_capacity_Nmm=500.),
    lambda r:r.update(arithmetic_criterion_status='fails'),
])
def test_tamper_rejected_even_without_trusting_outer_hash(mutation):
    c=combo();r=copy.deepcopy(b.interaction(c,10.,100.,50.));mutation(r)
    with pytest.raises(ValueError):b.validate_saved(r,c,10.,100.,50.)


def test_negative_proof_cannot_be_promoted():
    c=combo(qy=-1.,py=6.,a=2.);r=b.interaction(c,10.,100.,50.)
    r.update(status='computed_arithmetic_only',missing=[])
    with pytest.raises(ValueError):b.validate_saved(r,c,10.,100.,50.)


@pytest.mark.parametrize('value',[True,0.,-1.,float('inf'),float('nan')])
def test_invalid_strong_capacity(value):
    with pytest.raises(ValueError):b.interaction(combo(),10.,value,50.)


@pytest.mark.parametrize('mutation',[
    lambda r:r['sign_certificate'][0].update(after_P=0),
    lambda r:r['envelope_certificate'][0].update(after_P=0),
    lambda r:r['governing'].update(index=True),
    lambda r:r.update(candidate_count=True),
    lambda r:r.update(unapproved_extra=True),
    lambda r:r['envelope_certificate'][0]['coefficients'].__setitem__(2, False),
])
def test_strict_types_and_keys(mutation):
    c=combo();r=b.interaction(c,10.,100.,50.);mutation(r)
    with pytest.raises(ValueError):b.validate_saved(r,c,10.,100.,50.)


def test_finite_input_overflow_rejected():
    with pytest.raises(ValueError):b.interaction(combo(qx=1e308),1e308,100.,50.)



def test_zero_zero_governing_station_cannot_be_boolean():
    c=combo(qx=0.,qy=0.)
    r=b.interaction(c,10.,100.)
    assert r['governing']['x_mm']==0.
    r['governing']['x_mm']=False
    with pytest.raises(ValueError):b.validate_saved(r,c,10.,100.)
