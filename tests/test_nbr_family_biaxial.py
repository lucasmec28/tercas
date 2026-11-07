"""Synthetic exact continuous interaction, independent equilibrium controls."""
import copy
from fractions import Fraction as F
import pytest
from tercas import nbr_family_biaxial as b


def combo(qx=2.,qy=4.,px=0.,py=0.,a=5.):
    return dict(x_mm=a,q_vector=dict(normal=qx,parallel=qy),P_vector=dict(normal=px,parallel=py))


def caps(x=50.,xp=50.,y=100.,yp=100.):
    return dict(Mx_positive=x,Mx_negative=xp,My_positive=y,My_negative=yp)


def moment(q,p,a,L,x):
    return (q*L/2+p*(L-a)/L)*x-q*x*x/2-p*max(0.,x-a)


def test_uniform_analytical_midspan_and_exact_boundary():
    e=b.interaction(combo(),10.,caps())
    assert e['governing']['x_exact']=='5'
    assert e['governing']['index_exact']=='1'
    assert e['governing']['index_upper']==e['governing']['index_lower']==1.
    assert e['criterion_status']=='meets'
    assert len(e['envelope_certificate'])==8
    assert not e['resistance_qualified'] and not e['whole_member_approved']


@pytest.mark.parametrize('sx',[-1,1])
@pytest.mark.parametrize('sy',[-1,1])
def test_asymmetric_denominators_select_actual_sign(sx,sy):
    c=combo(2*sx,4*sy);r=caps(50,25,100,50)
    e=b.interaction(c,10.,r)
    expected=F(25,50 if sx>0 else 25)+F(50,100 if sy>0 else 50)
    assert F(e['governing']['index_exact'])==expected
    assert e['criterion_status']==('meets' if expected<=1 else 'fails')


def test_unused_signed_capacities_not_required_and_zero_needs_none():
    e=b.interaction(combo(),10.,caps(xp=None,yp=None))
    assert e['governing']['index_exact']=='1'
    assert e['missing']==[]
    z=b.interaction(combo(0,0),10.,dict.fromkeys(b.NAMES))
    assert z['governing']['index_exact']=='0'
    assert not any(z['active_signed_branches'].values())


def test_sign_reversal_requires_both_not_just_midspan_sign():
    c=combo(2.,0.,-11.,0.,2.)
    e=b.interaction(c,10.,caps(xp=None,yp=None))
    assert e['active_signed_branches']['Mx_negative']
    assert e['active_signed_branches']['Mx_positive']
    assert e['missing']==['Mx_negative'] and e['governing'] is None


@pytest.mark.parametrize('a',[0.,1.,3.,5.,9.,10.])
def test_offcentre_and_end_loads_against_independent_dense_equilibrium(a):
    c=combo(2.,-3.,-8.,25.,a);r=caps(50.,80.,60.,110.)
    e=b.interaction(c,10.,r)
    def direct(x):
        mx=moment(2.,-8.,a,10.,x);my=moment(-3.,25.,a,10.,x)
        return abs(mx)/r['Mx_positive' if mx>=0 else 'Mx_negative']+abs(my)/r['My_positive' if my>=0 else 'My_negative']
    sampled=max(direct(i/1000) for i in range(10001))
    assert sampled<=e['governing']['index_upper']+1e-14
    assert e['governing']['index_lower']-sampled<1e-6
    assert abs(direct(e['governing']['x_mm'])-e['governing']['index_lower'])<1e-13


@pytest.mark.parametrize('mutate',[
    lambda e:e['envelope_certificate'].pop(),
    lambda e:e['sign_certificate'].pop(),
    lambda e:e['governing'].update(x_mm=0.,index_upper=0.,index_lower=0.,index_exact='0'),
    lambda e:e.update(whole_member_approved=True),
    lambda e:e['capacities_Nmm'].update(My_positive=1e50),
])
def test_resealed_arithmetic_corruption_rejected(mutate):
    c=combo();r=caps();e=b.interaction(c,10.,r)
    mutate(e)
    with pytest.raises(ValueError):b.validate_saved(e,c,10.,r)


@pytest.mark.parametrize('value',[False,0.,-1.,float('nan'),float('inf')])
def test_invalid_capacity_is_not_missing(value):
    r=caps();r['Mx_positive']=value
    with pytest.raises(ValueError):b.interaction(combo(),10.,r)


def test_inputs_immutable():
    c=combo();r=caps();before=copy.deepcopy((c,r))
    e=b.interaction(c,10.,r)
    assert (c,r)==before
    assert b.validate_saved(copy.deepcopy(e),c,10.,r)==e


def test_component_demand_is_directed_exact_not_float_extremum():
    c=combo(2.,0.,a=.55);e=b.demand(c,1.1,'normal')
    expected=F(2.)*F(1.1)**2/8
    assert F(e['Msd_exact'])==expected
    assert F(e['Msd_Nmm'])>=expected
    assert e['witness']['x_exact']==str(F(1.1)/2)
    assert b.demand(c,1.1,'normal','negative')['Msd_exact']=='0'
