"""Recovered synthetic family QA; no private project data."""
import math
from decimal import Decimal,localcontext
import pytest
from tercas import en_ue_family_kernel as k
from tercas import en_ue_family_provider as p
from tercas.catalogs import STEELS
from tercas.pierin_ue_registry import new_study_indices,inventory

@pytest.fixture(scope='module')
def matrix():
    return [k.build(i,fyb_MPa=fy) for fy in sorted({s['fy_MPa'] for s in STEELS.values()}) for i in new_study_indices()]


def quadrature(v,c):
    cg=v['gross_properties']['centroid_xy_mm']; c0,cx,cy=c['sigma_coefficients_c0_cx_cy']; result=[0.,0.,0.]
    for i,lo,hi,t in c['effective_weighted_line_intervals']:
        a,b=v['nodes_xy_mm'][i:i+2]; L=math.dist(a,b)
        for z,w in ((-math.sqrt(3/5),5/9),(0,8/9),(math.sqrt(3/5),5/9)):
            u=(lo+hi)/2+z*(hi-lo)/2
            x,y=[a[j]+u*(b[j]-a[j])-cg[j] for j in (0,1)]
            sigma=c0+cx*x+cy*y; da=t*L*(hi-lo)*w/2
            for j,value in enumerate((sigma,y*sigma,-x*sigma)):result[j]+=da*value
    return result


def test_full_matrix_signed_scope_and_resultants(matrix):
    assert len(matrix)==66*len(STEELS)
    assert {v['catalog_index'] for v in matrix}==set(new_study_indices())
    failures=reduced=0
    for v in matrix:
        assert tuple(v['components'])==k.ACTIONS
        assert v['material']['E_MPa']==210000 and v['material']['nu']==.3
        assert not v['pierin_criticals_transferred'] and not v['whole_member_approved']
        pos,neg=[v['components'][a] for a in k.ACTIONS[:2]]
        assert pos['eligible']==neg['eligible']
        assert pos['first_yield_capacity_floor']==neg['first_yield_capacity_floor']
        for name,c in v['components'].items():
            if not c['eligible']:
                failures+=1
                assert c['blocking_reasons'] and c['sigma_coefficients_c0_cx_cy'] is None
                assert c['first_yield_capacity_floor'] is None
                continue
            assert c['first_yield_capacity_floor']>0
            assert quadrature(v,c)==pytest.approx([0,1,0] if name.startswith('Mx') else [0,0,1],abs=5e-12)
            if 'rho_web' in c:
                reduced+=1; audit=c['fixed_point_audit']
                assert abs(audit['residual'])<1e-13
                assert audit['contraction_certificate']['derivative_absolute_upper']<1
                assert len(audit['independent_seeds'])==3
    assert failures==0 and reduced>0


def test_125_300_exact_regression():
    from tercas.en_ue125_300_builder import build
    from tercas.en_ue125_shear300 import _derive
    old,new=build(),k.build(26,fyb_MPa=300)
    for action in k.ACTIONS:
        a,b=old['components'][action],new['components'][action]
        for key in ('sigma_coefficients_c0_cx_cy','effective_properties','first_yield_capacity_floor','capacity_audit'):
            assert a[key]==b[key]
    assert new['shear']['shear_capacity_geometry']==_derive(26)['shear_capacity_geometry']


def test_250_regression_with_endpoint_correction(matrix):
    from tercas.en_ue_catalog_operators import build_catalog_component_sections
    for new in (v for v in matrix if v['material']['fyb_MPa']==250):
        old=build_catalog_component_sections(new['catalog_index'])
        for name in k.ACTIONS:
            a,b=old['components'][name],new['components'][name]
            if a['eligible']:
                assert b['eligible']
                assert a['first_yield_capacity_floor']==b['first_yield_capacity_floor']
                assert a['sigma_coefficients_c0_cx_cy']==b['sigma_coefficients_c0_cx_cy']


def test_decimal_shear_all_rows_and_materials(matrix):
    with localcontext() as ctx:
        ctx.prec=70; D=Decimal
        for v in matrix:
            if not v['shear']['eligible']:
                assert v['shear']['blocking_reasons'];continue
            fy=D(str(v['material']['fyb_MPa']))
            for wall in v['shear']['shear_capacity_geometry'].values():
                h,t=D(str(wall['hw_mm'])),D(str(v['thickness_mm']))
                lam=D('.346')*h/t*(fy/D(210000)).sqrt()
                fbv=D('.58')*fy if lam<=D('.83') else D('.48')*fy/lam if lam<D('1.4') else D('.67')*fy/lam**2
                raw=D(wall['walls'])*h*t*fbv
                assert D(wall['capacity_floor_N'])<=raw<D(wall['capacity_floor_N'])+1
                assert D(wall['lambda_upper'])>=lam and D(wall['fbv_lower_MPa'])<=fbv


@pytest.mark.parametrize('field',['material','node','capacity','action','revision','flag','index','bool'])
def test_resealed_tampering_rejected(field):
    v=p.section(26,fyb_MPa=300)
    if field=='material':v['material']['E_MPa']=200000
    elif field=='node':v['nodes_xy_mm'][0][0]+=.001
    elif field=='capacity':v['components']['Mx_positive']['first_yield_capacity_floor']+=1
    elif field=='action':v['components']['Mx_positive']['physical_action_sign']=-1
    elif field=='revision':v['method_revision']='other'
    elif field=='flag':v['whole_member_approved']=True
    elif field=='index':v['catalog_index']+=1
    else:v['material']['gamma_M0']=True
    v.pop('content_sha256');v['content_sha256']=k._sha(v)
    with pytest.raises(ValueError):p.verify(v)


def test_cache_isolation_and_cold_verification():
    a=p.section(26,fyb_MPa=300);assert p.verify(a)
    a['nodes_xy_mm'][0][0]+=1
    assert p.section(26,fyb_MPa=300)['nodes_xy_mm']!=a['nodes_xy_mm']
    p._cached.cache_clear()
    with pytest.raises(ValueError):p.verify(a)
    assert p.verify(p.section(26,fyb_MPa=300))
    with pytest.raises(ValueError):p.require_component(p.section(26,fyb_MPa=300),'N',1)


@pytest.mark.parametrize('value',[True,0,-1,float('nan'),float('inf')])
def test_invalid_material(value):
    with pytest.raises(ValueError):k.build(26,fyb_MPa=value)


def test_incomplete_and_partial_factor_scope():
    for row in inventory()['incomplete']:
        with pytest.raises(ValueError,match='Incomplete'):k.build(row['catalog_index'],fyb_MPa=300)
    with pytest.raises(ValueError,match='normalization'):k.build(26,fyb_MPa=300,gamma_M0=1.1)


def test_material_declaration_and_custom_are_not_conformity_claims():
    for name,steel in STEELS.items():
        v=k.build(26,fyb_MPa=steel['fy_MPa'])
        assert v['material_declaration']['name']==name
        assert v['material_declaration']['fu_MPa']==steel['fu_MPa']
        assert v['material_declaration']['source']==steel['source']
        assert not v['material_normative_conformance_verified']
    v=p.section(26,fyb_MPa=310,material_declaration=dict(name='Declared custom',fu_MPa=450,source='Synthetic test'))
    assert p.verify(v) and v['material_declaration']['fu_MPa']==450
    assert not v['material_declaration']['fu_used_in_N0_equations']
    assert not v['material_normative_conformance_verified']
    assert k.build(26,fyb_MPa=310)['material_declaration']['conformance_status']=='not_verified'
    with pytest.raises(ValueError):k.build(26,fyb_MPa=310,material_declaration={'fu_MPa':300})


def test_failure_categories_are_implementation_not_blanket_normative_rejection(matrix):
    reasons=[r for v in matrix for c in v['components'].values() for r in c['blocking_reasons']]
    assert not reasons  # All four standard materials now have signed section methods.
    for reason in reasons:
        assert reason['category'] in ('implementation_method_not_covered','outside_normative_geometric_domain','numerical_failure','integrity_failure')
        if reason['code'] in ('PURE_MOMENT_LOCAL_REDUCTION_NOT_QUALIFIED','PURE_MOMENT_DISTORTIONAL_REDUCTION_NOT_QUALIFIED'):
            assert reason['category']=='implementation_method_not_covered'
            assert not reason['normative_rejection_inferred']


@pytest.mark.parametrize('fy',[250,300,345,350,310])
def test_table61_endpoint_branches(fy):
    assert k.table61_unstiffened_fbv(.83,fyb_MPa=fy)==.58*fy
    x=math.nextafter(.83,math.inf);assert k.table61_unstiffened_fbv(x,fyb_MPa=fy)==.48*fy/x
    x=math.nextafter(1.4,-math.inf);assert k.table61_unstiffened_fbv(x,fyb_MPa=fy)==.48*fy/x
    assert k.table61_unstiffened_fbv(1.4,fyb_MPa=fy)==.67*fy/1.4/1.4
    for x in (-1,True,float('inf'),float('nan')):
        with pytest.raises(ValueError):k.table61_unstiffened_fbv(x,fyb_MPa=fy)


def test_reduced_closed_form_root_independently_for_every_admitted_branch(matrix):
    for v in matrix:
        c=v['components']['My_negative']
        if not c['eligible'] or 'rho_web' not in c:continue
        nodes=v['nodes_xy_mm']; t=v['thickness_mm']; fy=v['material']['fyb_MPa']
        width=abs(nodes[83][1]-nodes[50][1])
        area=sum(t*math.dist(a,b) for a,b in zip(nodes,nodes[1:]))
        first=sum(t*math.dist(a,b)*(a[0]+b[0])/2 for a,b in zip(nodes,nodes[1:]))
        xs=[]
        for a,b in zip(nodes,nodes[1:]):
            L=math.dist(a,b)
            for q in (a,b):xs.extend(q[0]+side*t/2*(-(b[1]-a[1])/L) for side in (-1,0,1))
        xmin,xmax=min(xs),max(xs)
        critical=4*math.pi**2*210000/(12*(1-.3**2))*(t/width)**2
        def target(r):
            cx=first/(area-t*width*(1-r));lam=math.sqrt(fy*(cx-xmin)/(xmax-cx)/critical)
            return (lam-.22)/lam**2
        lo,hi=c['fixed_point_audit']['contraction_certificate']['bracket']
        assert target(lo)>lo and target(hi)<hi
        for _ in range(45):
            mid=(lo+hi)/2
            if target(mid)>mid:lo=mid
            else:hi=mid
        assert c['rho_web']==pytest.approx((lo+hi)/2,abs=5e-12)


def test_reduced_steps12_independent_geometry_equations_and_resultants(matrix):
    count=0
    for v in matrix:
        for name,c in v['components'].items():
            if c['section_status']!='effective_local_distortional_steps1_2_pure_moment':continue
            count+=1;fy=v['material']['fyb_MPa'];t=v['thickness_mm'];nodes=v['nodes_xy_mm']
            coeff=c['pure_ULS_compression_coefficients_absolute']
            assert c['web_iteration_audit']['iterations']>=3
            assert c['web_iteration_audit']['residual']<1e-13
            assert c['effective_properties']['A_mm2']<v['gross_properties']['A_mm2']
            for st in c['stiffeners']:
                # Independent two-point Gauss integration, not _properties().
                A=Sx=Sy=Sy2=0.
                for i,lo,hi in st['line_intervals']:
                    a,b=nodes[i:i+2];weight=t*math.dist(a,b)*(hi-lo)/2
                    for z in (-1/math.sqrt(3),1/math.sqrt(3)):
                        u=(lo+hi)/2+z*(hi-lo)/2
                        x,y=[a[j]+u*(b[j]-a[j]) for j in (0,1)]
                        A+=weight;Sx+=weight*x;Sy+=weight*y;Sy2+=weight*y*y
                Is=Sy2-Sy*Sy/A
                assert A==pytest.approx(st['As_mm2'],rel=3e-14)
                assert Is==pytest.approx(st['Is_mm4'],rel=2e-10)
                other=next((q for q in c['stiffeners'] if q is not st),None)
                b1=Sx/A;b2=other['b1_mm'] if other else 0.;kr=other['As_mm2']/A if other else 0.
                h=max(p[1] for p in nodes)-min(p[1] for p in nodes)
                spring=210000*t**3/(4*(1-.3**2)*(b1*b1*h+b1**3+.5*b1*b2*h*kr))
                critical=2*math.sqrt(spring*210000*Is)/A
                ld=math.sqrt(fy/critical)
                chi=1. if ld<=.65 else 1.47-.723*ld if ld<1.38 else .66/ld
                sigma=coeff[0]+coeff[1]*Sx/A+coeff[2]*Sy/A
                assert st['chi_d']==pytest.approx(chi,rel=1e-10)
                assert 0<sigma<=fy
                assert st['applied_As_red_over_As']==st['chi_d']
                assert st['applied_As_red_over_As']<=min(1,chi*fy/sigma)+1e-10
                assert st['stress_domain_audit']['min_line_or_face_compression_MPa']>0
            # Effective intervals must never double-count physical material.
            by_segment={}
            for i,lo,hi,te in c['effective_weighted_line_intervals']:
                assert 0<=lo<hi<=1 and 0<te<=t
                by_segment.setdefault(i,[]).append((lo,hi))
            assert all(all(a[1]<=b[0] for a,b in zip(sorted(rows),sorted(rows)[1:])) for rows in by_segment.values())
    assert count>100


def test_adaptive_outstand_signed_dominance_independent(matrix):
    count=0
    for v in matrix:
        c=v['components']['My_negative']
        for bound in c.get('outstand_flange_bounds',[]):
            if 'bound_psi' not in bound:continue
            count+=1
            g=next(g for g in v['panels'] if g['panel']==bound['panel'])
            psi=bound['bound_psi'];amplitude=bound['bound_stress_ends_MPa'][0]
            comp=c['pure_ULS_compression_coefficients_absolute'];t=v['thickness_mm'];nodes=v['nodes_xy_mm']
            assert -1<=psi<=0 and bound['integral_bound'] and bound['rho']==1
            critical=(1.7-5*psi+17.1*psi**2)*math.pi**2*210000/(12*(1-.3**2))*(t/g['b_mm'])**2
            assert math.sqrt(amplitude/critical)<=.748
            for i in g['ids']:
                a,b=nodes[i:i+2];L=math.dist(a,b);nx=-(b[1]-a[1])/L;ny=(b[0]-a[0])/L
                for p in (a,b):
                    for side in (-1,0,1):
                        x,y=p[0]+side*t*nx/2,p[1]+side*t*ny/2
                        actual=comp[0]+comp[1]*x+comp[2]*y
                        majorant=amplitude*(1-(1-psi)*(x-g['lo'])/g['b_mm'])
                        assert actual<=majorant+2e-12
    assert count>100


def test_r10_historical_snapshot_preserves_exact_content_and_blocked_branches():
    from tercas._en_ue_family_r10 import en_ue_family_provider as old
    v=old.section(19,fyb_MPa=300)
    saved=__import__('copy').deepcopy(v)
    assert not v['components']['Mx_positive']['eligible']
    assert p.verify(v) and v==saved
    assert p.section(19,fyb_MPa=300)['components']['Mx_positive']['eligible']
    v['components']['Mx_positive']['eligible']=True
    v.pop('content_sha256');v['content_sha256']=k._sha(v)
    with pytest.raises(ValueError):p.verify(v)


def test_new_operator_source_is_in_technical_binding():
    assert 'en_ue_family_reductions.py' in p.TECHNICAL_SOURCES


def test_extension_nonconvergence_is_numerical_failure(monkeypatch):
    from tercas import en_ue_family_reductions as reductions
    def fail(*args,**kwargs):raise ValueError('Effective web stress-gradient iteration did not converge')
    monkeypatch.setattr(reductions,'reduced_moment',fail)
    c=k.build(19,fyb_MPa=300)['components']['Mx_positive']
    assert not c['eligible'] and c['sigma_coefficients_c0_cx_cy'] is None
    assert c['blocking_reasons'][0]['category']=='numerical_failure'
    assert not c['blocking_reasons'][0]['normative_rejection_inferred']


def test_supplemental_reaudit_recomputes_tensor_without_qualification():
    from tercas.en_ue_family_reductions import audit_effective_state
    v=k.build(19,fyb_MPa=350);c=v['components']['Mx_positive']
    args=k._geometry(19,k.material(350));_,_,_,nodes,t,groups,full,gross,_=args
    weighted=[row[:] for row in c['effective_weighted_line_intervals']]
    for row in weighted:
        if row[0] in groups[1]['ids']:row[3]*=.9
    audit=audit_effective_state(k._Kernel(k.material(350)),'Mx_positive',nodes,t,groups,full,gross,weighted,stiffeners=c['stiffeners'])
    assert not audit['qualification_inferred'] and not audit['whole_member_approved']
    assert audit['effective_properties']['A_mm2']<c['effective_properties']['A_mm2']
    assert audit['sigma_coefficients_c0_cx_cy']!=c['sigma_coefficients_c0_cx_cy']
    synthetic=dict(audit,effective_weighted_line_intervals=weighted)
    assert quadrature(v,synthetic)==pytest.approx([0,1,0],abs=5e-12)
    assert audit['required_web_bands'] and audit['stiffener_stress_audits']
    with pytest.raises(ValueError,match='overlap'):
        audit_effective_state(k._Kernel(k.material(350)),'Mx_positive',nodes,t,groups,full,gross,weighted+[weighted[0]])
    invalid=[row[:] for row in weighted];invalid[0][3]=-1.
    with pytest.raises(ValueError,match='Invalid effective interval'):
        audit_effective_state(k._Kernel(k.material(350)),'Mx_positive',nodes,t,groups,full,gross,invalid)



def test_notional_lip_formula_has_no_artificial_point_two_lower_guard():
    kernel=k._Kernel(k.material(300))
    cert=kernel._lip_certificate({'panel':'synthetic_lip','b_mm':10.}, {'b_mm':60.},2.,[300.,300.])
    assert cert['bpc_over_bp']==pytest.approx(1/6)
    assert cert['k_sigma']==.5 and cert['rho']==1.
    # External c/b is separately tested in _geometry, as required by EN13 5.2.
