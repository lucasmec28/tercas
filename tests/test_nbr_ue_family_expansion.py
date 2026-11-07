"""Independent arithmetic and source/version checks for parameterized R11 branches."""
import copy
from decimal import Decimal, localcontext
import json
import math
import pytest
from tercas import nbr_ue_family as f, nbr_ue_family_v1 as v1
from tercas import nbr_ue_family_expansion as ex
from tercas import nbr_ue_family_application as app, nbr_ue_family_application_v1 as app1
from test_nbr_ue_family_application import source


def geometry(index):
    r=f.registry.select_new_study(index,include_routes=False)
    return dict(r['dimensions_mm'],ri_mm=r['published_properties']['ri_mm']),f.prepare(index)['section']['properties']


@pytest.mark.parametrize('lam',[.673-1e-7,.673,.673+1e-7,.6731,.673205,.674,1.,2.])
def test_new_effective_width_never_creates_material(lam):
    assert 0<ex.rho(lam)<=1
    assert ex.rho(lam)<=v1.rho(lam)


def test_cbca_worked_edge_stiffener_example_independent_numbers():
    # CBCA2016 pp113-115: base thickness after coating deduction, in mm.
    edge=ex.edge_stiffener(36.344,10.172,11.964,.914,200000.,230.)
    assert edge['lambda_p0']==pytest.approx(2.164,rel=.001)
    assert edge['Is_mm4']==pytest.approx(80.2,rel=.003)
    assert edge['Ia_mm4']==pytest.approx(87.99,rel=.003)
    assert edge['k']==pytest.approx(3.51,rel=.003)
    assert edge['flange_effective_width_mm']==pytest.approx(34.03,rel=.003)
    assert edge['reduced_lip_width_mm']==pytest.approx(9.25,rel=.004)


@pytest.mark.parametrize('index',[79,80,81,82])
@pytest.mark.parametrize('fy',[250.,300.,345.,350.])
def test_strong_mle_missing_table12_rows(index,fy):
    p,props=geometry(index);m=dict(f.DEFAULT_MATERIAL,fy_MPa=fy)
    local=ex.strong_effective_modulus(p,props,m,fy)
    t=p['t'];h=p['h'];a=h-t;r=p['ri_mm']+t/2
    edge=local['edge_stiffener'];xlo=r+edge['flange_width_at_web_mm']
    xhi=p['bf']-t-r-edge['flange_width_at_lip_mm']
    liplo=a-(p['lip']-t/2);liphi=a-r-edge['reduced_lip_width_mm']
    # Independent trapezoid moment subtraction, without use of returned Ae/Ie.
    pieces=[(t*(xhi-xlo),a,a), (t*(liphi-liplo),liplo,liphi)]
    A=props['A_mm2'];cy=props['centroid_xy_mm'][1]
    Sy=A*cy;Q=props['Ix_strong_mm4']+A*cy*cy
    for area,y0,y1 in pieces:
        assert area>=-1e-12
        A-=area;Sy-=area*(y0+y1)/2;Q-=area*(y0*y0+y0*y1+y1*y1)/3
    assert local['Aef_mm2']==pytest.approx(A,rel=1e-13)
    assert local['centroid_y_mm']==pytest.approx(Sy/A,rel=1e-13)
    assert local['Ixef_mm4']==pytest.approx(Q-Sy*Sy/A,rel=1e-13)
    assert local['web_proof']['fully_effective']
    assert local['web_proof']['partition_overlap_mm']>0
    out=f.assess(index,L_mm=6000.,material=m)
    assert 'Ml_Nmm' not in out['strong']['local']
    assert out['strong']['local']['MRd_Nmm']==pytest.approx(local['Wfirst_mm3']*fy/m['gamma'])
    assert out['strong']['FLT_reference']['method']=='NBR9.8.2.2(a)_MLE'
    assert not local['tensor_stress_operator_qualified']


@pytest.mark.parametrize('index',[19,47,53,62])
@pytest.mark.parametrize('fy',[300.,350.])
def test_positive_flange_affine_majorant_is_sufficient_and_sign_specific(index,fy):
    p,props=geometry(index);m=dict(f.DEFAULT_MATERIAL,fy_MPa=fy)
    weak,_,_=ex.weak_positive_full_flange(p,props,m)
    proof=weak['proof'];al=proof['flange_outstand_majorant']
    assert al['fully_effective'] and al['lambda_flange']<=.673
    assert al['restraint_at_tensile_lip_released']
    assert al['no_reduced_AL_section_used']
    actual=al['actual_flat_endpoint_stresses_MPa'];upper=al['majorant_endpoint_stresses_MPa']
    assert actual[0]>0>actual[1]
    for u in (0.,.13,.5,.87,1.):
        assert (1-u)*upper[0]+u*upper[1]>=(1-u)*actual[0]+u*actual[1]-1e-12
    assert proof['centroid_upper_mm']<proof['connecting_bend_x_lower_mm']
    out=f.assess(index,L_mm=6000.,material=m)
    assert out['weak']['positive']['complete_reference_components']
    assert out['weak']['positive']['FLT_reference']['flange_proof']['fully_effective']


@pytest.mark.parametrize('index',[6,12,19])
def test_negative_uniform_lip_reduction_and_first_yield(index):
    p,props=geometry(index);m=dict(f.DEFAULT_MATERIAL,fy_MPa=350.)
    w=ex.weak_negative_full_flange(p,props,m,350.)
    sec=w['section'];proof=w['proof']
    assert sec['Aef_mm2']<=props['A_mm2']
    assert sec['Ixyef_mm4']==0 and proof['mirrored_lip_removal']
    assert proof['web_in_tension'] and proof['lips_and_connecting_bends_in_compression']
    assert proof['flange_proof']['edge_support_sufficient'] and proof['flange_proof']['fully_effective']
    assert sec['lip_effective_width_mm']<p['lip']-p['ri_mm']-p['t']
    assert proof['extreme_tension_magnitude_MPa']<=350.
    out=f.assess(index,L_mm=6000.,material=m)
    assert out['weak']['negative']['complete_reference_components']


@pytest.mark.parametrize('index',[40,47,53,79])
def test_partial_edge_stiffener_gradient_is_not_promoted(index):
    p,props=geometry(index);m=dict(f.DEFAULT_MATERIAL,fy_MPa=350.)
    with pytest.raises(ex.OutsideMethod,match='Is<Ia'):
        ex.weak_negative_full_flange(p,props,m,350.)
    out=f.assess(index,L_mm=6000.,material=m)['weak']['negative']
    assert out['distortional']['eligible']
    assert not out['local']['eligible'] and not out['complete_reference_components']
    assert out['pure_weak_reference_MRd_Nmm'] is None


@pytest.mark.parametrize('index',[19,26,53,79])
def test_weak_distortion_independent_decimal_formula(index):
    out=f.assess(index,L_mm=6000.)['weak']['negative']['distortional'];el=out['elastic']
    # Independently arranged equations, using only geometric/material inputs.
    p,g=geometry(index)
    with localcontext() as ctx:
        ctx.prec=50;D=lambda x:Decimal(str(x));pi=D(math.pi)
        t=D(p['t']);b=D(p['bf'])-t;d=D(p['lip'])-t/2;nu=D('.3');E=D(200000);G=D(77000)
        A=t*(b+d);J=(b+d)*t**3/3
        ix=t*(t*t*b*b+4*b*d**3+t*t*b*d+d**4)/(12*(b+d))
        iy=t*(b**4+4*d*b**3)/(12*(b+d));ixy=t*b*b*d*d/(4*(b+d))
        xo=b*b/(2*(b+d));xh=-(b*b+2*b*d)/(2*(b+d));yo=-d*d/(2*(b+d))
        H=ix*(xo-xh)**2*(1-ixy**2/(ix*iy));he=D('3.5')*(iy/A+xh*xh).sqrt()
        L=pi*he*(6*(1-nu*nu)*H/(t**3*he**3)+D(1)/120).sqrt().sqrt()
        q=pi/L;u=q*he;cg=D(g['centroid_xy_mm'][0]);ext=D(p['bf'])-t/2
        psi=(-xh-cg)/(ext-cg);xi=ext/(ext-cg)
        kg=q*q*((ix+iy+A*(xh*xh+yo*yo-2*yo*(xo-xh)*ixy/iy))*psi+iy*xi)
        ke=q**4*E*H+q*q*G*J+E*t**3/(6*(1-nu*nu)*he)*(1+u*u/6+u**4/120)
        stress=ke/kg;critical=D(g['Iy_weak_mm4'])/(ext-cg)*stress
    assert el['Lcrd_mm']==pytest.approx(float(L),rel=2e-14)
    assert el['Fcrd_MPa']==pytest.approx(float(stress),rel=2e-14)
    assert el['Mdist_Nmm']==pytest.approx(float(critical),rel=2e-14)
    assert not out['inherited_strong_or_Pierin_critical_used']
    assert out['correlation']['empirical_mean'] is None
    assert out['elastic_approximation'] and not out['guaranteed_lower_bound']


def test_distortion_elastic_independent_of_fy_lengths_and_physical_span():
    a=f.assess(26,L_mm=6000.)
    b=f.assess(26,L_mm=6000.,material=dict(f.DEFAULT_MATERIAL,fy_MPa=350.),
        lengths=dict(Lx_mm=3000.,Ly_mm=4000.,Lz_mm=5000.,origin='synthetic'))
    assert a['weak']['negative']['distortional']['elastic']==b['weak']['negative']['distortional']['elastic']
    assert a['weak']['negative']['distortional']['MRd_Nmm']!=b['weak']['negative']['distortional']['MRd_Nmm']
    short=f.assess(26,L_mm=10.)['weak']['negative']
    assert short['distortional']['eligible'] and short['complete_reference_components']
    assert short['distortional']['elastic']==a['weak']['negative']['distortional']['elastic']
    assert not short['distortional']['guaranteed_lower_bound']
    assert short['local']['eligible']


def test_replay_v1_stays_exact_and_never_uses_v2(monkeypatch):
    old=v1.assess(26,L_mm=6000.)
    saved=app1.attach(source())
    monkeypatch.setattr(f,'assess',lambda *a,**kw:pytest.fail('Historical replay promoted to v2'))
    assert f.validate_saved(old,index=26,L_mm=6000.)==old
    assert app.preserved(json.loads(json.dumps(saved)))==saved[app.FIELD]
    assert not old['weak']['negative']['complete_reference_components']
    assert not saved[app.FIELD]['records'][0]['weak_negative_complete']
    forged=copy.deepcopy(saved);forged[app.FIELD]['records'][0]['weak_negative_complete']=True
    with pytest.raises(ValueError):app.preserved(forged)


def test_v1_provider_and_consumer_sources_are_frozen():
    from pathlib import Path
    import hashlib
    root=Path(__file__).resolve().parents[1]
    # Exact R10 provider; consumer differs only in its import of this provider.
    raw=(root/'tercas/nbr_ue_family_v1.py').read_bytes()
    assert hashlib.sha256(raw).hexdigest()=='396dfd91b64f96ffd79f1743ae2a50629e36463ead78a74f878345f908b5edd5'


def test_flt_domain_failure_keeps_independent_local_and_distortion(monkeypatch):
    genuine=ex.positive_flange_majorant
    calls=[]
    def missing_only_flt(*args):
        calls.append(True)
        if len(calls)>1:raise ex.OutsideMethod('synthetic FLT-only method gap')
        return genuine(*args)
    monkeypatch.setattr(ex,'positive_flange_majorant',missing_only_flt)
    out=f.assess(19,L_mm=6000.,material=dict(f.DEFAULT_MATERIAL,fy_MPa=350.))['weak']['positive']
    assert out['local']['eligible'] and out['distortional']['eligible']
    assert not out['FLT_reference']['eligible'] and not out['complete_reference_components']
    assert out['pure_weak_reference_MRd_Nmm'] is None


def test_new_strong_capacity_caps_rounded_local_transition():
    p,props=geometry(26);W=props['Ix_strong_mm4']/(p['h']/2)
    crit=v1.local_critical('Ue',p['h'],p['bf'],p['t'],W,200000.,.3,p['lip'])['Ml_Nmm']
    fy=.6731**2*crit/W
    out=f.strong_capacity_at_me(26,material=dict(f.DEFAULT_MATERIAL,fy_MPa=fy),Me_Nmm=W*fy*10)
    assert out['Wc_effective_mm3']<=W
    assert not out['resistance_lower_bound_qualified']


@pytest.mark.parametrize('branch', ['local', 'distortional'])
def test_new_nominal_caps_rounded_transition_preserving_v1(branch):
    old=v1.tabulated_reference(26)
    values=old['strong'][branch]
    fy=.6731**2*values['elastic_critical_Nmm']/values['Wc_published_mm3']
    m=dict(f.DEFAULT_MATERIAL,fy_MPa=fy)
    new=f.tabulated_reference(26,material=m)
    historical=v1.tabulated_reference(26,material=m)
    assert new['strong'][branch]['rho']==1
    assert historical['strong'][branch]['rho']>1
    assert new['schema']=='nbr_ue_published_nominal_reference_v2'


@pytest.mark.parametrize('branch', ['local', 'distortional'])
def test_new_own_strong_caps_rounded_transition_preserving_v1(branch):
    old=v1.assess(26,L_mm=6000.)
    W=old['strong']['local']['Wc_mm3']
    critical=(old['strong']['local']['Ml_Nmm'] if branch=='local'
        else old['strong']['distortional']['elastic']['Mdist_Nmm'])
    fy=.6731**2*critical/W;m=dict(f.DEFAULT_MATERIAL,fy_MPa=fy)
    new=f.assess(26,L_mm=6000.,material=m)
    historical=v1.assess(26,L_mm=6000.,material=m)
    nominal=W*fy/m['gamma']
    assert new['strong'][branch]['MRd_Nmm']<=nominal
    assert historical['strong'][branch]['MRd_Nmm']>nominal


def test_current_base_caps_plate_width_at_rounded_transition():
    from tercas import nbr_ue_family_base as current
    p,props=geometry(26);m=f.DEFAULT_MATERIAL
    _,section,width=current.weak_kernel(p,props,m)
    B=p['h']-2*(p['ri_mm']+p['t'])
    stress=(.6731*.95*p['t']/B)**2*4*m['E_MPa']
    assert width(stress)<=B
    assert section(width(stress))['Aef_mm2']<=props['A_mm2']


@pytest.mark.parametrize('index',[6,19,26,40,47,53,79,82])
def test_weak_distortion_unrestricted_minimum_analytical(index):
    p,g=geometry(index);m=f.DEFAULT_MATERIAL
    flange=v1.elastic_distortion(dict(p,Ix_cm4=g['Ix_strong_mm4']/1e4),m)['flange_lip']
    out=ex.weak_negative_distortion(p,g,m,flange);el=out['elastic']
    pr=el['unrestricted_minimum_proof']
    a,b,c,C=(pr[k] for k in ('a_Nmm4','b_Nmm2','c_N','C_mm4'))
    assert min(a,b,c,C)>0
    assert pr['q_optimum_per_mm']==pytest.approx(math.pi/el['Lcrd_mm'],rel=1e-14)
    assert el['Fcrd_MPa']==pytest.approx((b+2*math.sqrt(a*c))/C,rel=1e-14)
    for ratio in (.001,.01,.1,.5,1.,2.,10.,100.,1000.):
        q=ratio*math.pi/el['Lcrd_mm']
        # Independently recompute the original Eqs9-11, not the stored
        # completed-square polynomial, for both shorter and longer halfwaves.
        H=flange['Cwf_mm6']+flange['Ixf_mm4']*(flange['xof_mm']-flange['xhf_mm'])**2*(
            1-flange['Ixyf_mm4']**2/(flange['Ixf_mm4']*flange['Iyf_mm4']))
        ke=q**4*m['E_MPa']*H+q*q*m['G_MPa']*flange['Jf_mm4']
        u=q*el['he_mm']
        ke+=m['E_MPa']*p['t']**3/(6*(1-m['nu']**2)*el['he_mm'])*(1+u*u/6+u**4/120)
        F=ke/(C*q*q)
        assert F>=el['Fcrd_MPa']*(1-2e-14)
        assert C*(F-pr['F_global_min_MPa'])==pytest.approx((math.sqrt(a)*q-math.sqrt(c)/q)**2,rel=2e-13,abs=1e-5)
    assert not pr['physical_member_lower_bound_proven']
