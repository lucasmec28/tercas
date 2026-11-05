"""Independent checks of the new sufficient My-negative panel proof."""
import copy
import json
import math
from pathlib import Path
import numpy as np
import pytest
from tercas.three_girt_en_normal import en1993_normal_components as c
from tercas.three_girt_en_normal import application as a
from tercas.three_girt_en_normal import field_envelope as f
ROOT=Path(__file__).parents[1]/'tercas/data/torsion_profiles'


def profile(t):return json.loads((ROOT/f'ue100x50x17_t{t:.2f}.json').read_text())


def independent_my150_fixed_point(xy, t=1.5):
    """Rebuild physical web cuts and centroid without certificate geometry helpers."""
    ds=np.diff(xy,axis=0);length=np.linalg.norm(ds,axis=1)
    web_lo=min(xy[60:149,1]);web_width=max(xy[60:149,1])-web_lo
    critical=4*math.pi**2*210000/(12*(1-.3**2))*(t/web_width)**2
    rho=1.
    for _ in range(100):
        area=0.;first=np.zeros(2);vertices=[];retained=[]
        limits=(web_lo+rho*web_width/2,web_lo+(1-rho/2)*web_width)
        for i,d in enumerate(ds):
            cuts={0.,1.}
            if 60<=i<148 and d[1]!=0:
                cuts.update(float((value-xy[i,1])/d[1]) for value in limits
                            if 0<(value-xy[i,1])/d[1]<1)
            cuts=sorted(cuts)
            for lo,hi in zip(cuts,cuts[1:]):
                middle=xy[i]+(lo+hi)/2*d
                if 60<=i<148 and limits[0]<middle[1]<limits[1]:continue
                da=t*length[i]*(hi-lo);area+=da;first+=da*middle
                retained.append((i,lo,hi))
                normal=np.array([-d[1],d[0]])/length[i]
                for u in (lo,hi):
                    vertices.extend(xy[i]+u*d+side*t/2*normal for side in (-1,0,1))
        center=first/area;vertices=np.array(vertices)
        scale=250/max(abs(vertices[:,0]-center[0]))
        peak=-math.inf
        for i in range(60,148):
            normal=np.array([-ds[i,1],ds[i,0]])/length[i]
            for point in xy[i:i+2]:
                for side in (-1,0,1):
                    peak=max(peak,scale*(center[0]-(point+side*t/2*normal)[0]))
        lam=math.sqrt(peak/critical)
        target=1. if lam<=.5+math.sqrt(.03) else (lam-.22)/lam**2
        if abs(target-rho)<1e-13:break
        rho=target
    else:raise AssertionError('Independent My150 fixed point did not converge')
    return dict(center=center,scale=scale,rho=rho,residual=target-rho,
                area=area,vertices=vertices,retained=retained,web_peak=peak)


@pytest.mark.parametrize('t',[1.2,1.5,2.,2.25,2.65,3.,3.35])
def test_independent_outstand_width_lambda_and_pointwise_dominance(t):
    p=profile(t);cert=c.build_component_sections(p);v=cert['components']['My_negative']
    xy=np.asarray(p['nodes_xy_mm']);length=np.linalg.norm(np.diff(xy,axis=0),axis=1)
    center=np.sum(length[:,None]*(xy[:-1]+xy[1:])/2,axis=0)/sum(length)
    scale=250/max(abs(xy[:,0]-center[0]));bounds=v['outstand_flange_bounds']
    amplitude=250.
    if t in (1.2,1.5):
        independent=independent_my150_fixed_point(xy,t)
        center=independent['center'];scale=independent['scale'];amplitude=172. if t==1.2 else 149.
        assert independent['area']==pytest.approx(v['effective_properties']['A_mm2'],abs=2e-10)
        assert center==pytest.approx(v['effective_properties']['centroid_xy_mm'],abs=2e-11)
        assert independent['rho']==pytest.approx(v['local_panels'][2]['rho'],abs=2e-13)
    for bound,(start,end) in zip(bounds,((20,60),(148,188))):
        lo=min(xy[start:end+1,0]);hi=max(xy[start:end+1,0]);width=hi-lo
        psi=-.25 if t==1.2 else 0.
        k=1.7-5*psi+17.1*psi**2
        critical=k*math.pi**2*210000/(12*(1-.3**2))*(t/width)**2
        assert bound['b_mm']==pytest.approx(width,abs=1e-12)
        assert bound['sigma_cr_MPa']==pytest.approx(critical,rel=2e-14)
        assert bound['lambda_p']==pytest.approx(math.sqrt(amplitude/critical),rel=2e-14)
        assert bound['bound_psi']==psi and bound['bound_stress_ends_MPa']==[amplitude,psi*amplitude]
        gaps=[];lower_constraints=[];upper_constraints=[]
        for i in range(start,end):
            d=xy[i+1]-xy[i];n=np.array([-d[1],d[0]])/np.linalg.norm(d)
            for u in np.linspace(0,1,9):
                for face in (-1,0,1):
                    pt=xy[i]+u*d+face*t/2*n
                    actual=scale*(center[0]-pt[0]);majorant=amplitude*(1-(1-psi)*(pt[0]-lo)/width)
                    gaps.append(actual-majorant)
                    q=1-(1-psi)*(pt[0]-lo)/width
                    if q>0:lower_constraints.append(actual/q)
                    elif q<0:upper_constraints.append(actual/q)
                    else:assert actual<=0.
        if t in (1.2,1.5):
            assert math.ceil(max(0.,max(lower_constraints)))==amplitude
            assert not upper_constraints or amplitude<=min(upper_constraints)
            assert bound['rho']==1. and bound['lambda_p']<=.748
            assert max(gaps)<=-.614
        assert max(gaps)<=0
        assert max(gaps)==pytest.approx(bound['maximum_actual_minus_bound_MPa'],abs=2e-12)
        assert bound['lip_stress_domain_audit']['max_offset_face_compression_MPa']<0
        assert not bound['physical_As_assumed_wholly_tensile'] and not bound['Eq5_17_used']
    assert v['eligible'] and v['sigma_coefficients_c0_cx_cy'] is not None


def test_helper_rejects_compressed_lip_or_failed_dominance():
    p=profile(2.65);nodes,t,props,groups,_=c._geometry(p)
    scale=250/max(abs(nodes[:,0]-props['centroid_xy_mm'][0]));field=np.array([scale*props['centroid_xy_mm'][0],-scale,0.])
    good=c._tension_lip_outstand_bound(nodes,t,groups[0],groups[1],field)
    assert good['integral_bound']
    reverse=c._tension_lip_outstand_bound(nodes,t,groups[0],groups[1],-field)
    assert not reverse['integral_bound'] and not reverse['lip_is_noncompressive']
    too_high=field.copy();too_high[0]+=200
    bad=c._tension_lip_outstand_bound(nodes,t,groups[0],groups[1],too_high)
    assert bad['lip_is_noncompressive']
    assert not bad['pointwise_dominance_demonstrated'] and not bad['integral_bound']


def test_historical_certificate_is_not_requalified():
    old=json.loads((Path(__file__).parent/'data/EN_normal_265_legacy_certificate.json').read_text())
    c.verify_component_sections(old)
    assert old['method_revision']=='Eq5.17_integral_ULS_fixed_point_20261104'
    assert not old['components']['My_negative']['eligible']
    with pytest.raises(ValueError):c.require_component(old,'My',-1.)
    current=c.build_component_sections(profile(2.65))
    assert current['components']['My_negative']['eligible']
    for key in c.PURE_ACTIONS:
        if key!='My_negative':assert current['components'][key]==old['components'][key]


def test_coalescence_retains_exact_sign_requirements_and_requires_identical_coefficients():
    polys=dict(N=[0.],Mx=[0.],My=[.1,-1.,1.]);cert=c.build_component_sections(profile(2.65))
    original=f.sign_intervals(polys);assert len(original)>1
    merged=a._integral_sign_intervals(polys,cert)
    assert len(merged)==1 and merged[0]['left']==0 and merged[0]['right']==1
    assert merged[0]['required_signs']['My']==[-1,1]
    assert merged[0]['coalesced_exact_sign_intervals']==len(original)
    thinner=c.build_component_sections(profile(1.5))
    assert a._integral_sign_intervals(polys,thinner)==original
    unequal=copy.deepcopy(cert);unequal['components']['My_negative']['sigma_coefficients_c0_cx_cy'][1]*=2
    assert a._integral_sign_intervals(polys,unequal)==original


@pytest.mark.parametrize('h',[0.,1.,6.])
def test_coalesced_envelope_matches_original_sign_partition(h):
    cert=c.build_component_sections(profile(2.65))
    polys=dict(N=[-100.],Mx=[187500.,-1000000.,1000000.],My=[100000.,-1000000.,1000000.])
    coeff={axis:cert['components'][name]['sigma_coefficients_c0_cx_cy']
           for axis,name in [('N','N_tension'),('Mx','Mx_positive'),('My','My_positive')]}
    fibers=[[-15.,-50.],[-15.,50.],[35.,-50.],[35.,50.]]
    omega=[-.000001,.000001,.000002,-.000002]
    torsion=dict(h=h,B0=1e7,U=-2e7,V=1e7)
    original=f.sign_intervals(polys)
    separate=[f.envelope(polys,coeff,fibers,omega,torsion,row['left'],row['right'])['maximum_absolute'] for row in original]
    combined=a._integral_sign_intervals(polys,cert)
    assert len(combined)==1
    actual=f.envelope(polys,coeff,fibers,omega,torsion,combined[0]['left'],combined[0]['right'])['maximum_absolute']
    assert abs(actual['sigma_MPa'])==pytest.approx(max(abs(v['sigma_MPa']) for v in separate),rel=2e-13,abs=2e-10)
    for axis in polys:
        assert combined[0]['required_signs'][axis]==sorted({v for row in original for v in row['required_signs'][axis]})


@pytest.mark.parametrize('t',[1.2,1.5,2.,2.25])
def test_Eq4_4_web_trial_uses_full_pure_ULS_face_compression_and_fixed_point(t):
    p=profile(t);cert=c.build_component_sections(p);v=cert['components']['My_negative']
    xy=np.asarray(p['nodes_xy_mm']);ds=np.diff(xy,axis=0);ls=np.linalg.norm(ds,axis=1)
    cg=np.sum(ls[:,None]*(xy[:-1]+xy[1:])/2,axis=0)/sum(ls)
    scale=250/max(abs(xy[:,0]-cg[0]));peak=-math.inf
    gross_cg=cg.copy()
    if t in (1.2,1.5):
        independent=independent_my150_fixed_point(xy,t)
        cg=independent['center'];scale=independent['scale']
    for i in range(60,148):
        normal=np.array([-ds[i,1],ds[i,0]])/ls[i]
        for point in xy[i:i+2]:
            for face in (-1,0,1):peak=max(peak,scale*(cg[0]-(point+face*t/2*normal)[0]))
    web=v['local_panels'][2]
    if t in (1.2,1.5):
        expected=math.sqrt(peak/web['sigma_cr_MPa'])
        target=(expected-.22)/expected**2
        assert web['slenderness_reference_stress_MPa']==pytest.approx(peak,abs=2e-12)
        assert web['lambda_p']==pytest.approx(expected,rel=2e-14)
        assert web['rho']==pytest.approx(independent['rho'],abs=2e-13)
        assert abs(target-web['rho'])<1e-13
        assert v['fixed_point_iteration_audit']['converged']
        assert v['fixed_point_iteration_audit']['final_recheck']
        assert v['eligible'] and v['effective_properties']['A_mm2']<cert['gross_properties']['A_mm2']
        assert all(v['local_panels'][i]['rho']==1. for i in (0,1,3,4))
        assert all(row['integral_bound'] for row in v['outstand_flange_bounds'])
        coeff=np.asarray(v['sigma_coefficients_c0_cx_cy']);effort=v['ULS_pure_effort_signed']
        vertices=independent['vertices']
        recomputed=effort*(coeff[0]+(vertices-gross_cg)@coeff[1:])
        assert max(abs(recomputed))==pytest.approx(250.,rel=2e-14)
        assert -recomputed==pytest.approx(scale*(cg[0]-vertices[:,0]),abs=2e-12)
        # Independent Gauss quadrature checks N=0 and signed My, about gross Cg.
        result=np.zeros(3);z,w=np.polynomial.legendre.leggauss(3)
        for i,lo,hi in independent['retained']:
            for u,weight in zip((lo+hi)/2+(hi-lo)*z/2,w*(hi-lo)/2):
                point=xy[i]+u*ds[i];stress=effort*(coeff[0]+(point-gross_cg)@coeff[1:])
                result+=t*ls[i]*weight*stress*np.array([1.,point[1]-gross_cg[1],-(point[0]-gross_cg[0])])
        assert result==pytest.approx([0.,0.,effort],rel=0.,abs=1e-7)
        assert c.build_component_sections(p)==cert
        return
    trial=web['Eq4_4_ULS_integral_trial']
    expected=math.sqrt(peak/web['sigma_cr_MPa'])
    assert trial['sigma_com_Ed_MPa']==pytest.approx(peak,abs=1e-12)
    assert trial['lambda_p_reduced']==pytest.approx(expected,rel=1e-14)
    assert trial['integral_trial']==(t>=2.)
    if t>=2.:
        assert v['effective_properties']==cert['gross_properties']
        assert v['centroid_shift_from_gross_mm']==[0.,0.]
        assert all(row['rho']==1. for row in v['local_panels'])
        assert all(row['integral_bound'] for row in v['outstand_flange_bounds'])
        coeff=np.asarray(v['sigma_coefficients_c0_cx_cy']);effort=v['ULS_pure_effort_signed']
        recomputed=effort*(coeff[0]+(xy-cg)@coeff[1:])
        assert max(abs(recomputed))==pytest.approx(250.,rel=1e-14)
        assert c.build_component_sections(p)==cert
    else:
        assert trial['rho_reduced_trial']<1 and web['rho']<1
        assert not v['eligible'] and v['effective_properties'] is None
