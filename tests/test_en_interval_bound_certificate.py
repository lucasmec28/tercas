"""Proof arithmetic/coverage checks require neither a network nor extrema."""
import copy
from decimal import Decimal, localcontext
import math
import numpy as np
import pytest
from tercas.three_girt_en_normal import bound_certificate as bc, shear_interaction as si


def row():
    return dict(segment_index=0,face=1,sigma=np.array([[25.,400.,-400.],[3.,2.,-1.],[0.,0.,0.]]),
        omega=np.array([.3,-.2,0.]),tau=np.array([[10.,4.,-2.],[2.,-1.,1.],[1.,0.,0.]]),
        tw_weight=np.array([.1,.2,-.1]),normal_xy=[0.,1.],xy_start=np.zeros(2),xy_delta=np.array([1.,0.]),
        sigma_roundoff_scale=831.,tau_roundoff_scale=22.,tw_roundoff_scale=.4)


def proof(paths=None):
    return dict(schema=bc.SCHEMA,faces=[dict(segment_index=0,face=1,paths=[''] if paths is None else paths)])


@pytest.mark.parametrize('h,x',[(0.,0.),(0.,.7),(.00000001,.37),(3.2,.999),(10.,1.),(10.,1e-15)])
def test_hyperbolic_interval_against_decimal(h,x):
    with localcontext() as ctx:
        ctx.prec=90
        H=Decimal(h);X=Decimal(x);z2=(H*X)**2
        c=ct=X*X/2;s=st=X
        for n in range(1,180):
            ct=ct*z2/((2*n+1)*(2*n+2));st=st*z2/((2*n)*(2*n+1))
            c+=ct;s+=st
        for interval,exact in zip(bc.hyperbolic(h,x),(c,s)):
            assert Decimal(interval[0])<=exact<=Decimal(interval[1])


@pytest.mark.parametrize('paths',[[],['0'],['0','0','1'],['','0'],['00','1'],['1','0'],['a']])
def test_missing_duplicate_overlapping_and_unordered_leaves(paths):
    with pytest.raises(ValueError):list(bc.boxes(paths,0.,1.))


def test_dyadic_coverage_and_tiny_interval():
    assert len(list(bc.boxes(['00','01','1'],0.,1.)))==3
    assert list(bc.boxes([''],.5,math.nextafter(.5,1.)))==[(.5,math.nextafter(.5,1.),0.,1.)]
    with pytest.raises(ValueError):list(bc.boxes(['0','1'],.5,math.nextafter(.5,1.)))


def test_certificate_contains_signed_physical_field_without_search(monkeypatch):
    def forbidden(*a,**k):raise AssertionError('No extrema or adaptive envelope in verifier')
    monkeypatch.setattr(si.f,'stress_extrema',forbidden);monkeypatch.setattr(si,'envelope',forbidden)
    r=row();tor=dict(h=2.,B0=-3.,U=7.,V=-4.);tw=dict(h=2.,B0=2.,U=4.,V=-1.)
    upper=bc.verify(proof(['00','01','10','11']),[r],tw,tor,0.,1.,250.)
    for x in np.linspace(0,1,33):
        for u in np.linspace(0,1,31):
            s,t=si._evaluate(r,tor,tw,x,u)
            for key,value in zip(bc.KEYS,(abs(s)/250.,abs(t)*math.sqrt(3)/250.,math.hypot(s,math.sqrt(3)*t)/275.)):
                assert value<=upper[key]
    altered=proof();altered['faces'][0]['face']=-1
    with pytest.raises(ValueError):bc.verify(altered,[r],tw,tor,0.,1.,250.)


@pytest.mark.parametrize('tiny',[False,True])
def test_optional_certificate_return_and_conservative_decision(monkeypatch,tiny):
    r=row();tor=dict(h=0.,B0=0.,U=0.,V=0.)
    monkeypatch.setattr(si,'section_fields',lambda *a:([r],tor))
    kwargs=dict(left=.5,right=math.nextafter(.5,1.)) if tiny else {}
    args=({},dict(N=[0.],Mx=[0.],My=[0.]),{},tor,[0.],1.)
    legacy=si.envelope(*args,max_refinements=0,bounds_only_tiny=True,**kwargs)
    result=si.envelope(*args,max_refinements=0,bounds_only_tiny=True,certify_bounds=True,**kwargs)
    assert 'bound_certificate' not in legacy
    assert result['bound_certificate']==proof()
    for key in bc.KEYS:
        assert result[key]['index_upper_bound']>=legacy[key]['index_upper_bound']
        assert result[key]['witness']==legacy[key]['witness']
        assert result[key]['index_lower_witness']==legacy[key]['index_lower_witness']


@pytest.mark.parametrize('h,a,b',[(0.,0.,1.),(3.578,0.,1.),(10.,0.,1.),(10.,.93,1.),(1e-9,.2,.7)])
def test_taylor_bernstein_hyperbolic_tail_contains_decimal(h,a,b):
    controls,tail=bc.field_bernstein(h,1e6,-2e6,3e5,a,b)
    for i in range(17):
        x=a+(b-a)*(i/16)
        with localcontext() as ctx:
            ctx.prec=80
            H=Decimal(h);X=Decimal(x);z2=(H*X)**2
            c=ct=X*X/2;s=st=X
            for n in range(1,180):
                ct=ct*z2/((2*n+1)*(2*n+2));st=st*z2/((2*n)*(2*n+1));c+=ct;s+=st
            exact=Decimal(1e6)+Decimal(-2e6)*c+Decimal(3e5)*s
            lo=bc.down(min(v[0] for v in controls)-tail);hi=bc.up(max(v[1] for v in controls)+tail)
            assert Decimal(lo)<=exact<=Decimal(hi)


def test_stress_arithmetic_cache_is_content_addressed_not_snapshot_trust():
    bc._stress_bound_cached.cache_clear()
    r=row();field=dict(h=3.2,B0=10.,U=4.,V=-2.)
    def cached(record,ff=field):
        return bc.stress_bound(record,'sigma','omega',ff,0.,1.,0.,1.,'sigma_roundoff_scale',.5)
    expected=bc._stress_bound_uncached(r,'sigma','omega',field,0.,1.,0.,1.,'sigma_roundoff_scale',.5)
    assert cached(r)==expected
    assert cached(copy.deepcopy(r))==expected
    assert bc._stress_bound_cached.cache_info().hits==1
    r['sigma'][0,0]+=1000.
    assert cached(r)>expected
    newer=dict(field,B0=field['B0']+10000.)
    assert cached(r,newer)>cached(r)
    # Even on a hot numerical cache, forged/incomplete coverage is checked.
    with pytest.raises(ValueError):bc.verify(proof(['0']),[r],field,field,0.,1.,250.)


@pytest.mark.parametrize('bad',[True,float('nan'),float('inf'),'1'])
def test_invalid_cache_scalar_cannot_alias_a_valid_entry(bad):
    r=row();field=dict(h=3.2,B0=10.,U=4.,V=-2.)
    r['sigma_roundoff_scale']=bad
    with pytest.raises(ValueError):
        bc.stress_bound(r,'sigma','omega',field,0.,1.,0.,1.,'sigma_roundoff_scale',.5)


def test_failed_arithmetic_is_never_inserted_into_cache():
    bc._stress_bound_cached.cache_clear()
    r=row();r['sigma'][:]=1e308;field=dict(h=0.,B0=0.,U=0.,V=0.)
    with pytest.raises(ArithmeticError):
        bc.stress_bound(r,'sigma','omega',field,0.,1.,0.,1.,'sigma_roundoff_scale',.5)
    assert bc._stress_bound_cached.cache_info().currsize==0


@pytest.mark.parametrize('h',[0.,1e-12,3.2,10.])
def test_vector_controls_match_scalar_operation_order_exactly(h):
    from en_scalar_stress_oracle import scalar_stress_bound
    rng=np.random.default_rng(204811)
    for index in range(32):
        r=row();r['sigma']=rng.normal(size=(3,3))*10**(index%10-4)
        r['omega']=rng.normal(size=3)*10**(index%6-5)
        field=dict(h=h,B0=float(rng.normal()*1e6),U=float(rng.normal()*1e6),V=float(rng.normal()*1e6))
        left,right=sorted(rng.random(2));u0,u1=sorted(rng.random(2))
        if index%8==0:right=math.nextafter(left,1.)
        expected=scalar_stress_bound(r,'sigma','omega',field,left,right,u0,u1,'sigma_roundoff_scale',.5)
        actual=bc._stress_bound_uncached(r,'sigma','omega',field,left,right,u0,u1,'sigma_roundoff_scale',.5)
        assert actual==expected


def test_compact_cache_preserves_actual_signed_zero_and_rejects_wrong_shape():
    bc._stress_bound_cached.cache_clear();r=row();field=dict(h=0.,B0=0.,U=0.,V=0.)
    r['sigma'][2,0]=0.
    bc.stress_bound(r,'sigma','omega',field,0.,1.,0.,1.,'sigma_roundoff_scale',.5)
    r['sigma'][2,0]=-0.
    bc.stress_bound(r,'sigma','omega',field,0.,1.,0.,1.,'sigma_roundoff_scale',.5)
    assert bc._stress_bound_cached.cache_info().misses==2
    r['sigma']=np.zeros((3,4))
    with pytest.raises(ValueError,match='quadratic'):
        bc.stress_bound(r,'sigma','omega',field,0.,1.,0.,1.,'sigma_roundoff_scale',.5)


def test_success_cache_eviction_retains_no_input_payload():
    from tercas.three_girt_en_normal import replay_cache as rc
    cache=rc.SuccessCache(1);a=rc.key('v1',b'a'*100000);b=rc.key('v1',b'b'*100000)
    assert a!=b and len(a)==32
    cache.put(a,1.);assert cache.get(a)==1.
    cache.put(b,2.);assert cache.get(a) is rc.MISSING and cache.get(b)==2.
    assert cache.retained_bytes()<1024
    assert rc.key('v1',b'a',b'bc')!=rc.key('v1',b'ab',b'c')
    assert rc.key('v1',b'a')!=rc.key('v2',b'a')


def test_face_batch_matches_complete_scalar_certificate_exactly():
    from en_scalar_stress_oracle import scalar_stress_bound
    rng=np.random.default_rng(51024);rows=[]
    for i in range(23):
        r=row();r['segment_index']=i;r['sigma']=rng.normal(size=(3,3))*1e5
        r['tau']=rng.normal(size=(3,3))*1e3;r['omega']=rng.normal(size=3)*.02
        r['tw_weight']=rng.normal(size=3)*.03;rows.append(r)
    field=dict(h=3.8,B0=1e4,U=-2e4,V=3e4);tw=dict(h=3.8,B0=-4e4,U=5e4,V=6e4)
    certificate=dict(schema=bc.SCHEMA,faces=[dict(segment_index=i,face=1,paths=['0','10','11'] if i%2 else ['']) for i in range(len(rows))])
    expected=dict.fromkeys(bc.KEYS,0.)
    for face,r in zip(certificate['faces'],rows):
        for box in bc.boxes(face['paths'],.1,.9):
            s=scalar_stress_bound(r,'sigma','omega',field,*box,'sigma_roundoff_scale',sum(abs(r['omega'])))
            t=scalar_stress_bound(r,'tau','tw_weight',tw,*box,'tau_roundoff_scale',r['tw_roundoff_scale'])
            vals=(bc.up(s/250.),bc.up(bc.up(t*bc.up(math.sqrt(3)))/250.),
                  bc.up(bc.up(math.sqrt(bc.up(bc.up(s*s)+bc.up(3*bc.up(t*t)))))/bc.down(1.1*250.)))
            for key,value in zip(bc.KEYS,vals):expected[key]=max(expected[key],value)
    bc._stress_bound_cached.cache_clear()
    assert bc.verify(certificate,rows,tw,field,.1,.9,250.)==expected
    assert bc.verify(certificate,rows,tw,field,.1,.9,250.)==expected
