"""Analytical tests only: no member, eigenvalue or load-envelope solver."""
import copy
import math
from decimal import Decimal, localcontext

import pytest

from tercas import en_ue_catalog_operators as en
from tercas.catalogs import catalog_entry, entries


def _index(h=100,bf=50,lip=17,t=2.):
    return next(i for i,e in enumerate(entries())
                if e['family']=='Ue' and e['dimensions_mm']==dict(h=h,bf=bf,lip=lip,t=t))


def _gauss_properties(nodes,weighted):
    # Independent three-point quadrature: exact for polynomial degree <=5.
    x=(-math.sqrt(3/5),0.,math.sqrt(3/5));w=(5/9,8/9,5/9)
    samples=[]
    for i,lo,hi,t in weighted:
        a,b=nodes[i:i+2];length=math.dist(a,b)
        for q,weight in zip(x,w):
            u=(lo+hi)/2+q*(hi-lo)/2
            p=[a[k]+u*(b[k]-a[k]) for k in (0,1)]
            samples.append((t*length*(hi-lo)/2*weight,p))
    A=math.fsum(w for w,p in samples)
    cg=[math.fsum(w*p[k] for w,p in samples)/A for k in (0,1)]
    Ix=math.fsum(w*(p[1]-cg[1])**2 for w,p in samples)
    Iy=math.fsum(w*(p[0]-cg[0])**2 for w,p in samples)
    Ixy=math.fsum(w*(p[0]-cg[0])*(p[1]-cg[1]) for w,p in samples)
    return dict(A_mm2=A,centroid_xy_mm=cg,Ix_strong_mm4=Ix,Iy_weak_mm4=Iy,Ixy_mm4=Ixy)


def _decimal_yield(nodes,t,cg,coeff):
    # Independent 70-digit complete line/offset-face first-yield envelope.
    with localcontext() as context:
        context.prec=70
        D=Decimal.from_float
        points=[[D(float(x)),D(float(y))] for x,y in nodes]
        c=[D(v) for v in coeff];g=[D(v) for v in cg];th=D(t);maximum=Decimal(0)
        for a,b in zip(points,points[1:]):
            dx,dy=b[0]-a[0],b[1]-a[1];length=(dx*dx+dy*dy).sqrt()
            normal=[-dy/length,dx/length]
            for p in (a,b):
                for side in (-1,0,1):
                    xy=[p[k]-g[k]+side*th/2*normal[k] for k in (0,1)]
                    maximum=max(maximum,abs(c[0]+c[1]*xy[0]+c[2]*xy[1]))
        return Decimal(250)/maximum


def test_exact_ue_scope_and_reject_arbitrary_and_plain_u(monkeypatch):
    assert len(en.available_indices())==83
    assert all(catalog_entry(i)['family']=='Ue' for i in en.available_indices())
    u=next(i for i,e in enumerate(entries()) if e['family']=='U')
    for index in (u,True,-1,1.5,dict(h=100,bf=50,lip=17,t=2.)):
        with pytest.raises(ValueError):en.build_catalog_component_sections(index)
    monkeypatch.setattr(en,'reference_for_index',lambda i:dict(status='not_tabulated'))
    with pytest.raises(ValueError,match='Exact nominal'):en.build_catalog_component_sections(_index())


def test_geometry_agrees_with_common_torsion_contour_not_catalogue_scalars():
    from tercas.catalog_torsion_section import prepare
    for i in (en.available_indices()[0],_index(),en.available_indices()[-1]):
        cert=en.build_catalog_component_sections(i);geometry=prepare(i)
        assert cert['nodes_sha256']==geometry['section']['nodes_sha256']
        assert cert['nominal_identity_sha256']==geometry['nominal_identity_sha256']
        assert cert['profile_id']==geometry['section']['profile_id']
        assert cert['nodes_xy_mm']==geometry['section']['nodes_xy_mm']
        for key in ('A_mm2','Ix_strong_mm4','Iy_weak_mm4'):
            assert cert['gross_properties'][key]==pytest.approx(geometry['section']['properties'][key],rel=1e-13)
        assert cert['pierin_criticals_transferred'] is False
        assert cert['NBR_capacities_used'] is False and cert['AISI_capacities_used'] is False


def test_scalar_integrals_against_independent_gauss_quadrature():
    nodes=[[0.,-3.],[7.,1.],[4.,5.],[9.,9.]]
    weighted=[[0,.13,.8,1.2],[1,0.,.37,.9],[1,.7,1.,1.8],[2,.2,.88,2.1]]
    actual=en._properties(nodes,weighted);expected=_gauss_properties(nodes,weighted)
    for key in actual:assert actual[key]==pytest.approx(expected[key],rel=2e-13,abs=2e-12)


def test_partition_applies_reduction_once_and_rejects_overlap_or_missing_material():
    refs=[[0,0.,.4],[0,.6,1.],[1,0.,1.]]
    stiff=[dict(line_intervals=[[0,.7,1.],[1,0.,.5]],Eq5_17_As_red_over_As_at_ULS=.8)]
    weighted=en._weighted(refs,stiff,2.)
    assert weighted==[[0,0.,.4,2.],[0,.6,.7,2.],[0,.7,1.,1.6],[1,0.,.5,1.6],[1,.5,1.,2.]]
    with pytest.raises(ValueError,match='overlap'):en._weighted(refs,stiff+stiff,2.)
    wrong=copy.deepcopy(stiff);wrong[0]['line_intervals']=[[0,.3,.7]]
    with pytest.raises(ValueError,match='subset'):en._weighted(refs,wrong,2.)


@pytest.mark.parametrize('t',[1.2,1.5,2.,2.25,2.65,3.,3.35])
def test_same_named_family_is_recomputed_not_legacy_substitution(t):
    cert=en.build_catalog_component_sections(_index(t=t))
    assert cert['schema']!= 'en1993_1_3_2006_normal_component_sections_effective_v5'
    assert len(cert['nodes_xy_mm'])==134
    assert cert['runtime_release_approved'] is False
    assert cert['whole_member_approved'] is False
    assert cert['review_status']=='candidate_pending_independent_review'
    assert cert['legacy_certificates_changed'] is False
    for name,component in cert['components'].items():
        if not component['eligible']:
            assert component['sigma_coefficients_c0_cx_cy'] is None
            assert component['effective_properties'] is None
            assert component['first_yield_capacity_floor'] is None
            assert component['blocking_reasons']
            continue
        props=_gauss_properties(cert['nodes_xy_mm'],component['effective_weighted_line_intervals'])
        for key in props:assert props[key]==pytest.approx(component['effective_properties'][key],rel=2e-12,abs=1e-8)
        exact=_decimal_yield(cert['nodes_xy_mm'],t,cert['gross_properties']['centroid_xy_mm'],
                             component['sigma_coefficients_c0_cx_cy'])
        assert Decimal(component['first_yield_capacity_floor'])<=exact
        assert Decimal.from_float(component['capacity_audit']['first_yield_lower'])<=exact


def test_axial_local_distortional_equations_and_transport_are_independent_of_ex_sign():
    cert=en.build_catalog_component_sections(_index(t=1.2));c=cert['components']['N_compression']
    assert c['eligible']
    t=cert['thickness_mm'];fy=250.;E=210000.;nu=.3
    for p in c['local_panels']:
        if p['panel'] in ('lower_flange','web','upper_flange'):
            critical=4*math.pi**2*E/(12*(1-nu**2))*(t/p['b_mm'])**2
            lp=math.sqrt(fy/critical)
            rho=1 if lp<=.5+math.sqrt(.03) else (lp-.22)/lp**2
            assert p['rho']==pytest.approx(rho,rel=1e-14)
    for st in c['stiffeners']:
        other=next(s for s in c['stiffeners'] if s is not st)
        b1,b2=st['b1_mm'],other['b1_mm'];hw=st['hw_mm'];kr=other['As_mm2']/st['As_mm2']
        K=E*t**3/(4*(1-nu**2)*(b1*b1*hw+b1**3+.5*b1*b2*hw*kr))
        critical=2*math.sqrt(K*E*st['Is_mm4'])/st['As_mm2'];ld=math.sqrt(fy/critical)
        chi=1 if ld<=.65 else 1.47-.723*ld if ld<1.38 else .66/ld
        assert st['chi_d']==pytest.approx(chi,rel=1e-14)
        assert st['Eq5_17_As_red_over_As_at_ULS']==st['chi_d']
    ex,ey=c['effective_centroid_relative_to_gross_mm']
    assert c['uniform_unit_N_resultants_about_gross']==[1.,ey,-ex]
    assert c['additional_Mx_per_N_mm']==-ey and c['additional_My_per_N_mm']==ex
    assert c['favourable_centroid_shift_credit_permitted'] is False
    assert c['sigma_coefficients_c0_cx_cy']==[1/c['effective_properties']['A_mm2'],0.,0.]


def test_zero_needs_no_branch_but_nonzero_absent_branch_fails_closed():
    cert=en.build_catalog_component_sections(_index(t=1.2))
    assert en.require_component(cert,'N',0) is None
    assert en.require_component(cert,'N',1)['eligible']
    assert not cert['components']['Mx_positive']['eligible']
    with pytest.raises(ValueError,match='Mx_positive'):en.require_component(cert,'Mx',1)
    with pytest.raises(ValueError):en.require_component(cert,'Mx',float('nan'))
    with pytest.raises(ValueError):en.require_component(cert,'N',True)
    changed=copy.deepcopy(cert);changed['components']['Mx_positive']['eligible']=True
    with pytest.raises(ValueError,match='changed'):en.require_component(changed,'Mx',1)


def test_fixed_material_and_no_kernel_dependent_operations(monkeypatch):
    import numpy as np
    def forbidden(*args,**kwargs):raise AssertionError('BLAS/LAPACK prohibited in normal generator')
    monkeypatch.setattr(np.linalg,'solve',forbidden)
    monkeypatch.setattr(np.linalg,'inv',forbidden)
    cert=en.build_catalog_component_sections(_index())
    en.verify_catalog_component_sections(cert)
    for values in (dict(E_MPa=200000.),dict(fyb_MPa=300.),dict(gamma_M0=True),dict(nu=float('nan')),dict(unknown=1)):
        with pytest.raises(ValueError,match='Material'):en.build_catalog_component_sections(_index(),**values)


def test_geometric_guard_withholds_every_branch_not_a_gross_fallback(monkeypatch):
    original=en.catalog_entry
    def changed(i):
        e=original(i);e['published_properties']['ri_mm']=100.
        return e
    # Impossible radius fails at geometry creation before any stress operator.
    monkeypatch.setattr(en,'catalog_entry',changed)
    with pytest.raises(ValueError):en.build_catalog_component_sections(_index())


def test_integral_moment_unit_resultants_have_no_axial_or_cross_moment():
    cert=en.build_catalog_component_sections(_index(t=3.35));cg=cert['gross_properties']['centroid_xy_mm']
    nodes=cert['nodes_xy_mm'];z=(-math.sqrt(3/5),0.,math.sqrt(3/5));weights=(5/9,8/9,5/9)
    for name,c in cert['components'].items():
        if not name.startswith('M') or not c['eligible']:continue
        result=[[],[],[]];coeff=c['sigma_coefficients_c0_cx_cy']
        for i,lo,hi,t in c['effective_weighted_line_intervals']:
            a,b=nodes[i:i+2]
            for q,w in zip(z,weights):
                u=(lo+hi)/2+q*(hi-lo)/2;p=[a[k]+u*(b[k]-a[k])-cg[k] for k in (0,1)]
                sigma=coeff[0]+coeff[1]*p[0]+coeff[2]*p[1]
                dA=t*math.dist(a,b)*(hi-lo)/2*w
                for k,value in enumerate((1.,p[1],-p[0])):result[k].append(dA*sigma*value)
        actual=[math.fsum(r) for r in result]
        expected=[0.,1.,0.] if name.startswith('Mx') else [0.,0.,1.]
        assert actual==pytest.approx(expected,rel=0.,abs=2e-12)
        for st in c['stiffeners']:assert st['Eq5_17_As_red_over_As_at_ULS']==1.
