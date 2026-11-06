"""Formula, interval, domain, source and snapshot regression for EN6.27."""
import copy,json,math
from pathlib import Path
import numpy as np
import pytest
from tercas import en_simplified_interaction as c
from tercas.en_interaction_capacity_reference import REFERENCES, qualified_reference

def with_originals(fields):
    fields=copy.deepcopy(fields)
    for key in ('Mx','My'):fields.setdefault(key+'_original',copy.deepcopy(fields[key]))
    return fields

@pytest.mark.parametrize('t',[1.2,1.5,2.,2.25,2.65,3.,3.35])
def test_capacity_floor_uses_effective_operators_not_normalization_effort(t):
    from tercas.three_girt_en_normal.en1993_normal_components import build_component_sections
    p=json.loads((Path(__file__).parents[1]/f'tercas/data/torsion_profiles/ue100x50x17_t{t:.2f}.json').read_text())
    cert=build_component_sections(p);cap=c.capacities(p,cert)
    assert cap==qualified_reference(t,cert['content_sha256'])
    assert cap['signed_capacity_floor']==REFERENCES[t]['signed_capacity_floor']
    nodes=np.array(p['nodes_xy_mm']);cg=np.array(cert['gross_properties']['centroid_xy_mm']);d=np.diff(nodes,axis=0)
    normal=np.column_stack([-d[:,1],d[:,0]])/np.linalg.norm(d,axis=1)[:,None]
    points=np.concatenate([nodes[:-1],nodes[1:],nodes[:-1]+t/2*normal,nodes[1:]+t/2*normal,
        nodes[:-1]-t/2*normal,nodes[1:]-t/2*normal])-cg
    for key,floor in cap['signed_capacity_floor'].items():
        coeff=np.array(cert['components'][key]['sigma_coefficients_c0_cx_cy'])
        direct=250./np.max(np.abs(coeff[0]+points@coeff[1:]))
        assert floor<=direct and direct-floor<1.000001
    cert['components']['Mx_positive']['ULS_pure_effort_signed']=1e99
    with pytest.raises(ValueError):c.capacities(p,cert)

@pytest.mark.parametrize('nu',[0.,.25,.5,.500001,.8,1.,1.2])
def test_scalar_eq6_27_threshold_and_domain(nu):
    cap=REFERENCES[2.];m=c._normal_limits(cap)['Mx'];v=cap['shear_capacity_lower_N']['strong']
    pair={k:[0.,0.] for k in ('N','Mx','My','Vstrong','Vweak')};pair['Mx']=[.2*m,.2*m];pair['Vstrong']=[nu*v,nu*v]
    pair.update(Mx_original=pair['Mx'][:],My_original=pair['My'][:])
    z=c.objective(pair,cap,v)
    assert z['index_upper']==pytest.approx(.2+max(0.,2*nu-1)**2,rel=1e-12)
    if nu<.5:assert z['shear_penalty_upper']==0.
    assert c.verdict(z['index_upper'],z['shear_ratio_upper'],weak_zero=True,torsion_zero=False)['torsion_zero_required'] is False
    assert c.verdict(z['index_upper'],z['shear_ratio_upper'],weak_zero=False,torsion_zero=True)['weak_transverse_shear_included'] is True


def test_concurrent_polynomials_bound_dense_samples_without_mixed_witness():
    cap=REFERENCES[1.2];limits=c._normal_limits(cap);v=cap['shear_capacity_lower_N']['strong']
    fields=dict(N=[50.],Mx=[.1*limits['Mx'],2*limits['Mx'],-2*limits['Mx']],
        My=[-.2*limits['My'],.4*limits['My']],Vstrong=[.8*v,-1.6*v],Vweak=[.3*v,-.5*v])
    out=c.polynomial_bound(with_originals(fields),cap,v,weak_zero=True,torsion_zero=True)
    u=np.linspace(0,1,10001)
    nr=sum(np.abs(np.polynomial.polynomial.polyval(u,fields[k]))/limits[k] for k in ('N','Mx','My'))
    vr=np.abs(np.polynomial.polynomial.polyval(u,fields['Vstrong']))/v
    wr=np.abs(np.polynomial.polynomial.polyval(u,fields['Vweak']))/cap['shear_capacity_lower_N']['weak']
    assert np.max(nr+np.maximum(np.maximum(0.,2*vr-1)**2,np.maximum(0.,2*wr-1)**2))<=out['index_upper']
    assert all(x['is_physical_state'] is False for x in out['controls'])
    c.validate_polynomial_bound(out,cap,v,weak_zero=True,torsion_zero=True)
    bad=copy.deepcopy(out);bad['index_upper']=0.
    with pytest.raises(ValueError):c.validate_polynomial_bound(bad,cap,v,weak_zero=True,torsion_zero=True)

@pytest.mark.parametrize('t',[1.2,1.5,2.,2.25,2.65,3.,3.35])
def test_both_shear_capacity_floors_use_distinct_rotated_web_geometry(t):
    cap=REFERENCES[t]
    for axis,height,count in (('strong',100.,1),('weak',50.,2)):
        hw=height-t;lam=.346*hw/t*math.sqrt(250./210000.)
        fbv=.58*250. if lam<=.83 else .48*250./lam if lam<1.4 else .67*250./lam**2
        assert cap['shear_capacity_lower_N'][axis]==count*hw*t*fbv
        assert cap['shear_capacity_geometry'][axis]['walls']==count
        assert cap['shear_capacity_geometry'][axis]['hw_upper_mm']==hw
    assert cap['shear_capacity_lower_N']['strong']!=cap['shear_capacity_lower_N']['weak']


def test_weak_shear_above_half_is_not_ignored():
    cap=REFERENCES[2.];limits=c._normal_limits(cap)
    fields=dict(N=[0.],Mx=[.3*limits['Mx']],My=[.1*limits['My']],
        Vstrong=[0.],Vweak=[.95*cap['shear_capacity_lower_N']['weak']])
    out=c.polynomial_bound(with_originals(fields),cap,cap['shear_capacity_lower_N']['strong'],weak_zero=False,torsion_zero=False)
    assert out['index_upper']>1.
    assert out['status']=='inconclusive_upper_bound' and not out['observed_failure']
    assert out['controls'][0]['weak_shear_ratio_upper']>=.95
    assert out['controls'][0]['shear_penalty_upper']>=.9**2


def test_favorable_centroid_transport_cannot_reduce_sufficient_bound():
    cap=REFERENCES[1.2];limits=c._normal_limits(cap);v=cap['shear_capacity_lower_N']['strong']
    fields=dict(N=[-100.],Mx=[.1*limits['Mx']],My=[.05*limits['My']],
        Mx_original=[.3*limits['Mx']],My_original=[.2*limits['My']],Vstrong=[0.],Vweak=[0.])
    out=c.polynomial_bound(with_originals(fields),cap,v,weak_zero=True,torsion_zero=False)
    assert out['index_upper']>=100./limits['N']+.3+.2
    assert out['index_upper']==pytest.approx(100./limits['N']+.3+.2,rel=1e-12)
    # A favorable original strong/corrected weak combination also has to be covered.
    fields['My']=[.4*limits['My']]
    out=c.polynomial_bound(with_originals(fields),cap,v,weak_zero=True,torsion_zero=False)
    assert out['index_upper']>=100./limits['N']+.3+.4


@pytest.mark.parametrize('bad',[[],[True],[float('nan')],[1.,2.,3.,4.],['1']])
def test_invalid_action_polynomial_cannot_become_zero(bad):
    cap=REFERENCES[2.]
    fields=dict(N=[0.],Mx=bad,My=[0.],Vstrong=[0.],Vweak=[0.])
    with pytest.raises(ValueError):c.polynomial_bound(with_originals(fields),cap,cap['shear_capacity_lower_N']['strong'],weak_zero=True,torsion_zero=True)


def test_original_moments_must_be_explicit_even_when_N_zero():
    cap=REFERENCES[2.]
    fields=dict(N=[0.],Mx=[0.],My=[0.],Vstrong=[0.],Vweak=[0.])
    with pytest.raises(ValueError,match='Seven explicit'):
        c.polynomial_bound(fields,cap,cap['shear_capacity_lower_N']['strong'],weak_zero=True,torsion_zero=True)
