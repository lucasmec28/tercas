import copy
import math
import subprocess
import sys
from decimal import Decimal, localcontext
from pathlib import Path
import pytest
from tercas import en_ue125_300_builder as b
from tercas import en_ue125_300_authority as a


def quadrature(nodes, weighted):
    # Independent Gauss-3 integration of raw moments, no production integrals.
    totals=[0.]*6
    for i,lo,hi,t in weighted:
        p,q=nodes[i:i+2]; L=math.dist(p,q)
        for z,w in ((-math.sqrt(3/5),5/9),(0,8/9),(math.sqrt(3/5),5/9)):
            u=(hi+lo)/2+z*(hi-lo)/2
            x,y=[p[k]+u*(q[k]-p[k]) for k in (0,1)]
            da=t*L*(hi-lo)*w/2
            for k,f in enumerate((1,x,y,x*x,y*y,x*y)):totals[k]+=da*f
    return totals


def test_four_branches_and_independent_properties():
    v=a.read();assert b.build()==v
    cg=v['gross_properties']['centroid_xy_mm']
    for name,c in v['components'].items():
        A,Sx,Sy,Sxx,Syy,Sxy=quadrature(v['nodes_xy_mm'],c['effective_weighted_line_intervals'])
        e=c['effective_properties']
        assert A==pytest.approx(e['A_mm2'],abs=1e-9)
        assert [Sx/A,Sy/A]==pytest.approx(e['centroid_xy_mm'],abs=1e-10)
        assert Sxx-Sx*Sx/A==pytest.approx(e['Iy_weak_mm4'],abs=1e-8)
        assert Syy-Sy*Sy/A==pytest.approx(e['Ix_strong_mm4'],abs=1e-7)
        c0,cx,cy=c['sigma_coefficients_c0_cx_cy']; k=c0-cx*cg[0]-cy*cg[1]
        N=k*A+cx*Sx+cy*Sy
        Mx=k*Sy+cx*Sxy+cy*Syy-cg[1]*N
        My=-(k*Sx+cx*Sxx+cy*Sxy-cg[0]*N)
        assert [N,Mx,My]==pytest.approx([0,1,0] if name.startswith('Mx') else [0,0,1],abs=2e-12)
        assert c0==pytest.approx(-cx*(e['centroid_xy_mm'][0]-cg[0])-cy*(e['centroid_xy_mm'][1]-cg[1]),abs=1e-17)


def test_fixed_point_starts_domain_and_monotonicity():
    _,_,_,nodes,t,groups,_,gross,_=b._geometry(26)
    states=[b._reduced_state(r,nodes,t,groups,gross) for r in (.2,.4,.6,.8,1.)]
    assert all(x['target']<y['target'] for x,y in zip(states,states[1:]))
    for r in (.2,.5,.85,1.):
        v=b._negative_my(nodes,t,groups,gross,r)
        assert v['rho_web']==pytest.approx(.85502078461695,abs=2e-13)
        assert abs(v['fixed_point_audit']['residual'])<1e-13
    for r in (0,-1,1.1,float('nan'),True):
        with pytest.raises(ValueError):b._reduced_state(r,nodes,t,groups,gross)


def test_decimal_first_yield_all_faces_and_curves():
    v=a.read()
    with localcontext() as ctx:
        ctx.prec=65
        D=Decimal; nodes=[[D(x) for x in p] for p in v['nodes_xy_mm']];cg=list(map(D,v['gross_properties']['centroid_xy_mm']))
        for c in v['components'].values():
            co=list(map(D,c['sigma_coefficients_c0_cx_cy']));maximum=D(0)
            for p,q in zip(nodes,nodes[1:]):
                dx,dy=q[0]-p[0],q[1]-p[1];L=(dx*dx+dy*dy).sqrt()
                for point in (p,q):
                    for side in (-1,0,1):
                        x=point[0]-D(side)*dy/L-cg[0];y=point[1]+D(side)*dx/L-cg[1]
                        maximum=max(maximum,abs(co[0]+co[1]*x+co[2]*y))
            assert D(c['capacity_audit']['maximum_abs_unit_stress_upper'])>=maximum
            assert D(c['first_yield_capacity_floor'])<=D(300)/maximum
            assert D(c['first_yield_capacity_floor'])+1>D(300)/maximum


@pytest.mark.parametrize('change', ['material','node','coefficient','flag'])
def test_rehashed_mutations_fail(change):
    v=a.read()
    if change=='material':v['material']['fyb_MPa']=250
    elif change=='node':v['nodes_xy_mm'][0][0]+=.001
    elif change=='coefficient':v['components']['My_negative']['sigma_coefficients_c0_cx_cy'][0]=0
    else:v['torsion_qualified']=True
    v.pop('content_sha256');v['content_sha256']=a._sha(v)
    with pytest.raises(ValueError):a.validate(v)


def test_reader_without_builder_or_numpy():
    code="import sys; sys.modules['tercas.en_ue125_300_builder']=None; sys.modules['numpy']=None; from tercas.en_ue125_300_authority import read; assert len(read()['components'])==4"
    subprocess.run([sys.executable,'-c',code],check=True)
    with pytest.raises(ValueError):a.require_component(a.read(),'My',1,N=1)
    with pytest.raises(ValueError):a.require_component(a.read(),'N',1)


def test_retained_partition_symmetry_and_uls():
    v=a.read();nodes=v['nodes_xy_mm'];t=v['thickness_mm']
    for c in v['components'].values():
        rows=c['effective_weighted_line_intervals'];ordered=sorted(rows)
        assert all(0<=lo<hi<=1 and tt==t for i,lo,hi,tt in rows)
        assert all(x[0]!=y[0] or x[2]<=y[1] for x,y in zip(ordered,ordered[1:]))
        mirror=sorted([len(nodes)-2-i,1-hi,1-lo,tt] for i,lo,hi,tt in rows)
        for x,y in zip(ordered,mirror):assert x==pytest.approx(y,abs=1e-13)
        comp=c['pure_ULS_compression_coefficients_absolute']
        maximum=max(abs(b._eval(comp,p)) for p in b._vertices(nodes,t,[r[:3] for r in rows]))
        assert maximum==pytest.approx(300,abs=1e-10)


def test_source_mutation_rejected(tmp_path,monkeypatch):
    v=a.read(); altered=tmp_path/'altered.py';altered.write_text('changed')
    monkeypatch.setattr(a,'SOURCE_PINS',{str(altered):'0'*64})
    with pytest.raises(ValueError,match='snapshot'):a.validate(v)


def test_legacy_sources_unchanged():
    import hashlib
    # Inherited authorities stay byte-identical to 9a55de7; no broad regeneration.
    pins = {'tercas/en_ue_qualified_library.py': 'b53375fc4110e3ec9092cef329639e353ca9b689caae04d8868e14541b0c8cfb', 'tercas/data/en_ue_qualified_operator_inventory_20261106.json': '455f8aa52886d620ec54255c332d39ccbac55212870bc046dd3ff4fbe1429353', 'tercas/en_ue_catalog_operators.py': '86f8c5d6fb78b344f89d1f4e8adce789cf2a9790d3461d965a1fad83e3e62222', 'tercas/three_girt_en_normal/en1993_normal_components.py': '2f407a8d96ff24ed5541efe7a1507cacde9a21d3729db83a8f627e54b6efc745'}
    for name,digest in pins.items():
        assert hashlib.sha256(Path(name).read_bytes()).hexdigest()==digest


def test_independent_closed_form_fixed_point_and_contraction():
    v=a.read();nodes=v['nodes_xy_mm'];gross=v['gross_properties']
    # In this bracket removed material is ONLY the straight x=0 web.
    # Reconstruct panel width directly from its corner-midpoint nodes.
    width=nodes[83][1]-nodes[50][1]
    A0=gross['A_mm2']; S=A0*gross['centroid_xy_mm'][0]
    critical=4*math.pi**2*210000/(12*(1-.3**2))*(2/width)**2
    def target(r):
        A=A0-2*width*(1-r);cx=S/A
        stress=300*(cx+1)/(49-cx)
        lam=math.sqrt(stress/critical)
        return (lam-.22)/lam**2
    lo,hi=.8,.9
    assert target(lo)>lo and target(hi)<hi
    for _ in range(50):
        mid=(lo+hi)/2
        if target(mid)>mid:lo=mid
        else:hi=mid
    assert v['components']['My_negative']['rho_web']==pytest.approx((lo+hi)/2,abs=2e-13)
    # Conservative analytical derivative bound on the entire invariant bracket:
    # d rho_target/d lambda = (.44-lambda)/lambda**3;
    # |dcx/dr| <= S*2*b/A_min**2; ds/dcx = 15000/(49-cx)**2.
    amin=A0-2*width*.2;cxmax=S/amin
    lammin=math.sqrt(300*((S/(A0-2*width*.1))+1)/(49-S/(A0-2*width*.1))/critical)
    assert lammin > .44  # fixes derivative sign throughout the bracket
    # |(.44-lambda)/lambda**3| <= 1/lambda**2.
    bound=(1/lammin**2)*(1/(2*critical*lammin))*15000/(49-cxmax)**2*S*2*width/amin**2
    assert bound<1


def test_builder_rejects_other_material_and_contour(monkeypatch):
    with monkeypatch.context() as m:
        m.setattr(b,'MATERIAL',dict(b.MATERIAL,E_MPa=200000))
        with pytest.raises(ValueError,match='material'):b.build()
    original=b._geometry
    def altered(index):
        result=list(original(index));result[3]=copy.deepcopy(result[3]);result[3][0][0]+=.001
        return result
    monkeypatch.setattr(b,'_geometry',altered)
    with pytest.raises(ValueError,match='geometry'):b.build()


def test_integral_local_and_physical_stiffener_recalculation():
    v=a.read();nodes=v['nodes_xy_mm'];t=v['thickness_mm']
    for name in ('Mx_positive','Mx_negative','My_positive'):
        c=v['components'][name]
        for p in c['local_panels']:
            if p['branch']=='tension':continue
            critical=p['k_sigma']*math.pi**2*210000/(12*(1-.3**2))*(t/p['b_mm'])**2
            assert p['sigma_cr_MPa']==pytest.approx(critical,rel=1e-14)
            assert p['lambda_p']==pytest.approx(math.sqrt(300/critical),rel=1e-14)
            assert p['rho']==1
        for j,s in enumerate(c['stiffeners']):
            A,Sx,Sy,Sxx,Syy,Sxy=quadrature(nodes,[[*r,t] for r in s['line_intervals']])
            assert A==pytest.approx(s['As_mm2'],abs=1e-10)
            assert Syy-Sy*Sy/A==pytest.approx(s['Is_mm4'],abs=1e-8)
            b1=Sx/A;other=c['stiffeners'][1-j] if len(c['stiffeners'])==2 else None
            b2=other['b1_mm'] if other else 0;kr=other['As_mm2']/A if other else 0
            K=210000*t**3/(4*(1-.3**2))/(b1*b1*123+b1**3+.5*b1*b2*123*kr)
            critical=2*math.sqrt(K*210000*(Syy-Sy*Sy/A))/A
            lam=math.sqrt(300/critical);chi=1 if lam<=.65 else 1.47-.723*lam if lam<1.38 else .66/lam
            assert s['chi_d']==pytest.approx(chi,abs=1e-12)
            comp=c['pure_ULS_compression_coefficients_absolute']
            values=[b._eval(comp,p) for p in b._vertices(nodes,t,s['line_intervals'])]
            assert min(values)>0
            sig=comp[0]+comp[1]*Sx/A+comp[2]*Sy/A
            assert chi*300/sig>1 and s['Eq5_17_As_red_over_As_at_ULS']==1


def test_qualification_is_only_normal_components():
    v=a.read()
    assert v['review_status']=='independently_reviewed_normal_components_only'
    assert v['normal_section_qualified'] is True
    assert set(v['components'])==set(b.ACTIONS)
    for key in ('runtime_release_approved','whole_member_approved',
                'complete_EN_design_qualified','first_order_analysis_qualified',
                'global_stability_qualified','torsion_qualified','physical_geometry_verified'):
        assert v[key] is False
    assert v['geometry_guard']['radius_limit_mm']==56
