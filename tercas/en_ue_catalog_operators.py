"""Candidate EN normal operators for exact nominal Pierin Ue catalogue rows.

Isolated from the released seven pinned sections. An eligible component is a
local/distortional section proof in the declared panel model, not approval of
an EN design. Missing signed branches never fall back to gross coefficients.
The geometry is the SAME 32-chord rounded contour as catalog_torsion_section;
Pierin's sharp-corner critical values and catalogue A/I are never operands.
"""
from __future__ import annotations

import copy
import hashlib
import json
import math

from .catalogs import catalog_entry, entries
from .catalog_torsion_section import CONVENTION, nominal_channel_nodes
from .weak_pierin import reference_for_index
from .three_girt_en_normal.en1993_normal_components import (
    MATERIAL, PANEL_NAMES, PURE_ACTIONS, _internal_certificate, _lip_certificate,
)

SCHEMA = 'EN_Ue_Pierin_nominal_normal_operators_candidate_v1'
REVISION = 'uniform_axial_and_integral_pure_moments_20261106'
ARC_SEGMENTS = 32
EN13 = 'https://www.phd.eng.br/wp-content/uploads/2015/12/en.1993.1.3.2006.pdf'
EN15 = 'https://www.phd.eng.br/wp-content/uploads/2015/12/en.1993.1.5.2006.pdf'


def _sha(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'),
        ensure_ascii=False, allow_nan=False).encode()).hexdigest()


def available_indices():
    return [i for i, e in enumerate(entries()) if e['family'] == 'Ue'
            and reference_for_index(i)['status'] == 'tabulated_adopted_reference']


def _point(nodes, i, u):
    a, b = nodes[i:i+2]
    return [a[k] + u*(b[k]-a[k]) for k in (0, 1)]


def _properties(nodes, weighted):
    """Scalar exact polynomial line integrals. No BLAS reductions or inverse."""
    parts = []
    for i, lo, hi, t in weighted:
        a, b = _point(nodes, i, lo), _point(nodes, i, hi)
        area = t*math.dist(nodes[i], nodes[i+1])*(hi-lo)
        parts.append((area, a, b))
    A = math.fsum(p[0] for p in parts)
    if A <= 0.:
        raise ValueError('Nonpositive retained area')
    cg = [math.fsum(w*(a[k]+b[k])/2 for w,a,b in parts)/A for k in (0,1)]
    def inertia(j, k):
        return math.fsum(w*(2*(a[j]-cg[j])*(a[k]-cg[k])
            +(a[j]-cg[j])*(b[k]-cg[k])+(b[j]-cg[j])*(a[k]-cg[k])
            +2*(b[j]-cg[j])*(b[k]-cg[k]))/6 for w,a,b in parts)
    Ix, Iy, Ixy = inertia(1,1), inertia(0,0), inertia(0,1)
    if min(Ix, Iy) <= 0. or Ix*Iy-Ixy**2 <= 0.:
        raise ValueError('Degenerate retained inertia')
    return dict(A_mm2=A, Ix_strong_mm4=Ix, Iy_weak_mm4=Iy,
                Ixy_mm4=Ixy, centroid_xy_mm=cg)


def _geometry(index):
    entry = catalog_entry(index)
    if entry['family'] != 'Ue':
        raise ValueError('Only Ue is in this candidate extension; plain U is deferred')
    reference = reference_for_index(index)
    if reference['status'] != 'tabulated_adopted_reference':
        raise ValueError('Exact nominal Pierin row required; no interpolation')
    d = entry['dimensions_mm']; t = float(d['t']); ri = entry['published_properties']['ri_mm']
    identity = dict(catalog_id=entry['id'], dimensions_mm=d, inner_radius_mm=ri,
                    arc_segments=ARC_SEGMENTS, convention=CONVENTION)
    nodes = nominal_channel_nodes(h_mm=d['h'], bf_mm=d['bf'], lip_mm=d['lip'],
                                  t_mm=t, ri_mm=ri, arc_segments=ARC_SEGMENTS)
    # Four even chord sets put a real node at every corner midpoint.
    bounds = [0, 17, 50, 83, 116, 133]
    if len(nodes) != 134:
        raise ValueError('32-chord five-panel topology changed')
    normals = [d['bf']-t, 0., 0., d['h']-t, d['bf']-t]
    groups = []
    for j, (a,b) in enumerate(zip(bounds, bounds[1:])):
        axis = 1 if j % 2 == 0 else 0
        values = [p[axis] for p in nodes[a:b+1]]
        groups.append(dict(panel=PANEL_NAMES[j], ids=list(range(a,b)), axis=axis,
            lo=min(values), hi=max(values), b_mm=max(values)-min(values), normal_mm=normals[j]))
    full = [[i,0.,1.,t] for i in range(len(nodes)-1)]
    gross = _properties(nodes, full)
    mirror_error = max(abs(nodes[i][0]-nodes[-1-i][0]) for i in range(len(nodes)))
    mirror_error = max(mirror_error, max(abs(nodes[i][1]+nodes[-1-i][1]-(d['h']-t))
                                        for i in range(len(nodes))))
    if mirror_error > 1e-10 or abs(gross['Ixy_mm4']) > 1e-12*math.sqrt(
            gross['Ix_strong_mm4']*gross['Iy_weak_mm4']):
        raise ValueError('Horizontal nominal symmetry not demonstrated')
    # Conservative external dimensions bound the Table 5.1 slendernesses.
    guard = dict(external_b_over_t=d['bf']/t, external_c_over_t=d['lip']/t,
        external_h_over_t=d['h']/t, external_c_over_b=d['lip']/d['bf'],
        notional_c_over_b=groups[0]['b_mm']/groups[1]['b_mm'],
        inner_radius_mm=ri, radius_limit_mm=.04*t*MATERIAL['E_MPa']/MATERIAL['fyb_MPa'],
        lip_angle_degrees=90., mirror_max_error_mm=mirror_error,
        reference='EN13 5.1(6), 5.2/Table5.1/Eq5.2a, 5.5.3.2(1)',
        notional_ratio_extra_implementation_restriction='Inherited 0.2 <= bp,c/bp <= 0.6; distinct from external Eq5.2 ratio')
    guard['satisfied'] = (guard['external_b_over_t'] <= 60.
        and guard['external_c_over_t'] <= 50. and guard['external_h_over_t'] <= 500.
        and .2 <= guard['external_c_over_b'] <= .6
        and .2 <= guard['notional_c_over_b'] <= .6 and ri <= guard['radius_limit_mm'])
    return entry, reference, identity, nodes, t, groups, full, gross, guard


def _eval(coeff, point):
    return math.fsum((coeff[0], coeff[1]*point[0], coeff[2]*point[1]))


def _vertices(nodes, t, refs):
    for i,lo,hi in refs:
        dx,dy = (nodes[i+1][k]-nodes[i][k] for k in (0,1))
        length = math.hypot(dx,dy)
        normal = [-dy/length, dx/length]
        for u in (lo,hi):
            p = _point(nodes,i,u)
            for side in (-1,0,1):
                yield [p[k]+side*t/2*normal[k] for k in (0,1)]


def _domain(nodes, t, refs, compression):
    values = [_eval(compression,p) for p in _vertices(nodes,t,refs)]
    return dict(min_line_or_face_compression_MPa=min(values),
                max_line_or_face_compression_MPa=max(values))


def _ends(g, compression):
    result = []
    for value in (g['lo'],g['hi']):
        p=[0.,0.];p[g['axis']]=value;p[1-g['axis']]=g['normal_mm']
        result.append(_eval(compression,p))
    return result


def _bands(nodes, g, bands):
    refs=[]
    for i in g['ids']:
        u=(nodes[i][g['axis']]-g['lo'])/g['b_mm']
        v=(nodes[i+1][g['axis']]-g['lo'])/g['b_mm']
        for a,b in bands:
            if abs(v-u)<1e-14:
                if a <= u <= b: refs.append([i,0.,1.])
            else:
                lo,hi=sorted(((a-u)/(v-u),(b-u)/(v-u)))
                lo,hi=max(0.,lo),min(1.,hi)
                if hi>lo:refs.append([i,lo,hi])
    return refs


def _assembly(nodes,t,lip,flange,meta,compression):
    refs=[[i,0.,1.] for i in lip['ids']]
    refs += _bands(nodes,flange,[(meta['flange_lip_adjacent_start_fraction'],1.)])
    props=_properties(nodes,[[*r,t] for r in refs])
    audit=_domain(nodes,t,refs,compression)
    if audit['min_line_or_face_compression_MPa'] <= 0.:
        raise ValueError('Physical As not wholly compressed on line/offset faces')
    return dict(flange=flange['panel'], As_mm2=props['A_mm2'], Is_mm4=props['Ix_strong_mm4'],
        centroid_xy_mm=props['centroid_xy_mm'], b1_mm=props['centroid_xy_mm'][0],
        line_intervals=refs, stress_domain_audit=audit,
        sigma_com_Ed_MPa=_eval(compression,props['centroid_xy_mm']))


def _distortion(st,other,t,hw):
    b1=st['b1_mm'];b2=other['b1_mm'] if other else 0.
    kr=other['As_mm2']/st['As_mm2'] if other else 0.
    K=MATERIAL['E_MPa']*t**3/(4*(1-MATERIAL['nu']**2))/(b1*b1*hw+b1**3+.5*b1*b2*hw*kr)
    critical=2*math.sqrt(K*MATERIAL['E_MPa']*st['Is_mm4'])/st['As_mm2']
    ld=math.sqrt(MATERIAL['fyb_MPa']/critical)
    chi=1. if ld<=.65 else 1.47-.723*ld if ld<1.38 else .66/ld
    raw=chi*MATERIAL['fyb_MPa']/MATERIAL['gamma_M0']/st['sigma_com_Ed_MPa']
    st.update(kr_area=kr,hw_mm=hw,K_N_mm2=K,sigma_cr_MPa=critical,lambda_d=ld,
        chi_d=chi,Eq5_17_unclamped_As_ratio_at_ULS=raw,
        Eq5_17_As_red_over_As_at_ULS=min(1.,raw),step3_optional_refinement_used=False,
        source='EN13 Eq5.10b/5.12/5.15/5.17, physical As on own rounded contour')


def _weighted(refs,stiffeners,t):
    """Retained material partition; no As overlap or double thickness reduction."""
    by_segment={}
    for i,lo,hi in refs:
        if not 0.<=lo<hi<=1.:raise ValueError('Invalid retained interval')
        by_segment.setdefault(i,[]).append((lo,hi))
    for rows in by_segment.values():
        rows=sorted(rows)
        if any(a[1]>b[0] for a,b in zip(rows,rows[1:])):raise ValueError('Retained intervals overlap')
    assemblies={}
    for st in stiffeners:
        factor=st['Eq5_17_As_red_over_As_at_ULS']
        if not 0.<factor<=1.:raise ValueError('Invalid As thickness factor')
        for i,lo,hi in st['line_intervals']:
            if not any(a<=lo and hi<=b for a,b in by_segment.get(i,[])):
                raise ValueError('As is not a subset of the retained local material')
            assemblies.setdefault(i,[]).append((lo,hi,factor))
    for rows in assemblies.values():
        rows=sorted(rows)
        if any(a[1]>b[0] for a,b in zip(rows,rows[1:])):raise ValueError('Physical As overlap')
    out=[]
    for i,lo,hi in refs:
        cuts=sorted({lo,hi}|{v for a,b,_ in assemblies.get(i,[]) for v in (a,b) if lo<v<hi})
        for a,b in zip(cuts,cuts[1:]):
            factors=[f for aa,bb,f in assemblies.get(i,[]) if aa<(a+b)/2<bb]
            out.append([i,a,b,t*(factors[0] if factors else 1.)])
    return out


def _base(name):
    axis,sign=PURE_ACTIONS[name]
    return dict(action=name,physical_action_axis=('N_N','Mx_Nmm','My_Nmm')[axis],
        physical_action_sign=sign,eligible=False,blocking_reasons=[],
        sigma_coefficients_c0_cx_cy=None,effective_properties=None,
        section_status='blocked_no_effective_coefficients',first_yield_capacity_floor=None)


def _accept(base,coeff,props,weighted,gross,*,transport=False):
    ex,ey=[props['centroid_xy_mm'][k]-gross['centroid_xy_mm'][k] for k in (0,1)]
    base.update(eligible=True,sigma_coefficients_c0_cx_cy=coeff,effective_properties=props,
        effective_weighted_line_intervals=weighted,
        effective_centroid_relative_to_gross_mm=[ex,ey],centroid_shift_from_gross_mm=[ex,ey],
        moment_transport_required=transport,
        additional_Mx_per_N_mm=-ey if transport else 0.,additional_My_per_N_mm=ex if transport else 0.,
        coefficient_origin='Gross centroid of this rounded contour; multiply SIGNED action',
        moment_transport='Mx_corr=Mx-N*ey; My_corr=My+N*ex, once, before signed branch selection' if transport else None,
        favourable_centroid_shift_credit_permitted=False)
    return base


def _uniform_compression(nodes,t,groups,full,gross):
    base=_base('N_compression');fy=MATERIAL['fyb_MPa']/MATERIAL['gamma_M0']
    comp=[fy,0.,0.]
    meta={j:_internal_certificate(groups[j],t,[fy,fy]) for j in (1,2,3)}
    for l,f in ((0,1),(4,3)):meta[l]=_lip_certificate(groups[l],groups[f],t,[fy,fy])
    base['local_panels']=[meta[j] for j in range(5)]
    if any(meta[j]['rho']!=1. for j in (0,4)):
        raise ValueError('Reduced single lips need an independently qualified effective As construction')
    retained=[];bands=[]
    for j,g in enumerate(groups):
        rho=meta[j]['rho']
        band=[(0.,1.)] if rho==1. else [(0.,rho/2),(1-rho/2,1.)]
        rr=_bands(nodes,g,band);retained.extend(rr)
        bands.append(dict(panel=g['panel'],retained_fraction_bands=band,line_intervals=rr))
    stiff=[_assembly(nodes,t,groups[l],groups[f],meta[f],comp) for l,f in ((0,1),(4,3))]
    hw=max(p[1] for p in nodes)-min(p[1] for p in nodes)
    for st,other in zip(stiff,stiff[::-1]):
        _distortion(st,other,t,hw)
        if st['sigma_com_Ed_MPa']!=fy or st['Eq5_17_As_red_over_As_at_ULS']!=st['chi_d']:
            # Avoid assuming floating cancellation chi*fy/fy is exactly chi.
            if not math.isclose(st['Eq5_17_As_red_over_As_at_ULS'],st['chi_d'],rel_tol=0.,abs_tol=2e-16):
                raise ValueError('Uniform ULS does not recover As_red/As=chi_d')
        st['Eq5_17_As_red_over_As_at_ULS']=st['chi_d']
    weighted=_weighted(retained,stiff,t);props=_properties(nodes,weighted)
    if props['A_mm2']>gross['A_mm2']*(1+2e-13):raise ValueError('Effective area exceeds gross')
    # No assumption that ex must be positive: the actual transport is retained.
    # Near-zero ey is kept, not silently erased, and contributes to transport.
    base.update(local_panels=[meta[j] for j in range(5)],stiffeners=stiff,retained_bands=bands,
        section_status='effective_uniform_compression_steps1_2',
        ULS_pure_effort_signed=-fy*props['A_mm2'],
        uniform_unit_N_resultants_about_gross=[1.,props['centroid_xy_mm'][1]-gross['centroid_xy_mm'][1],
            -(props['centroid_xy_mm'][0]-gross['centroid_xy_mm'][0])],
        proof='EN13 6.1.3; 5.5.3.2 steps1-2; Eq5.17 uniform fyb => As_red/As=chi_d. Optional step3 omitted. EN15 Table4.1 psi=1 strips. Lips integral; physical As reduced once.',
        fixed_point_statement='Uniform reference ULS fixes widths and As factors independently of axial magnitude and centroid; no service stress law.',
        sigma_N_contract='Uniform N/Aeff,N; transport of N from original gross centroid is external and mandatory')
    return _accept(base,[1/props['A_mm2'],0.,0.],props,weighted,gross,transport=True)


def _outstand(nodes,t,lip,flange,comp):
    lip_audit=_domain(nodes,t,[[i,0.,1.] for i in lip['ids']],comp)
    margin=max(_eval(comp,p)-MATERIAL['fyb_MPa']*(1-(p[0]-flange['lo'])/flange['b_mm'])
               for p in _vertices(nodes,t,[[i,0.,1.] for i in flange['ids']]))
    critical=1.70*math.pi**2*MATERIAL['E_MPa']/(12*(1-MATERIAL['nu']**2))*(t/flange['b_mm'])**2
    lp=math.sqrt(MATERIAL['fyb_MPa']/critical)
    rho=1. if lp<=.748 else min(1.,(lp-.188)/lp**2)
    good=lip_audit['max_line_or_face_compression_MPa']<=0. and margin<=0. and rho==1.
    return dict(panel=flange['panel'],rho=rho,lambda_p=lp,k_sigma=1.70,
        maximum_actual_minus_bound_MPa=margin,lip_stress_domain_audit=lip_audit,
        integral_bound=good,reference='EN15 Table4.2 psi=0, supported web edge, free lip-side edge',
        lip_restraint_credited=False,translating_junction_modes_qualified=False)


def _integral_moment(name,nodes,t,groups,full,gross):
    base=_base(name);axis,sign=PURE_ACTIONS[name];cg=gross['centroid_xy_mm']
    # Complete scalar tensor inversion, retaining numerical Ixy and c0.
    Ix,Iy,Ixy=[gross[k] for k in ('Ix_strong_mm4','Iy_weak_mm4','Ixy_mm4')]
    det=Ix*Iy-Ixy*Ixy
    coeff=[0.,-Ixy/det,Iy/det] if axis==1 else [0.,-Ix/det,Ixy/det]
    absolute=[-coeff[1]*cg[0]-coeff[2]*cg[1],coeff[1],coeff[2]]
    refs=[r[:3] for r in full]
    maximum=max(abs(_eval(absolute,p)) for p in _vertices(nodes,t,refs))
    scale=MATERIAL['fyb_MPa']/MATERIAL['gamma_M0']/maximum
    comp=[-sign*scale*v for v in absolute]
    meta={j:_internal_certificate(groups[j],t,_ends(groups[j],comp)) for j in (1,2,3)}
    for l,f in ((0,1),(4,3)):meta[l]=_lip_certificate(groups[l],groups[f],t,_ends(groups[l],comp))
    # EN15 4.4(4) is allowed only as an integral pure-ULS fixed-point proof.
    if name=='My_negative' and meta[2]['rho']<1.:
        web=_domain(nodes,t,[[i,0.,1.] for i in groups[2]['ids']],comp)
        stress=web['max_line_or_face_compression_MPa']
        if not 0.<stress<=MATERIAL['fyb_MPa']:raise ValueError('Invalid web pure-ULS compression bound')
        lp=meta[2]['lambda_p']*math.sqrt(stress/MATERIAL['fyb_MPa'])
        rho=1. if lp<=meta[2]['lambda_p_integral_limit'] else min(1.,(lp-.055*(3+meta[2]['psi']))/lp**2)
        meta[2]['Eq4_4_integral_ULS_trial']=dict(sigma_com_Ed_MPa=stress,lambda_p_reduced=lp,rho=rho,
            rho_at_fyb=meta[2]['rho'],lambda_p_at_fyb=meta[2]['lambda_p'],
            reference='EN15 4.4(4)/Eq4.4 at the pure face-normalized ULS, not service stress',
            condition='Eligible only when all local widths and As thicknesses stay unchanged')
        if rho==1.:
            meta[2]['rho']=1.
            meta[2]['branch']='EN1993-1-5_Table4.1_Eq4.4_integral_pure_ULS_trial'
    base['local_panels']=[meta[j] for j in range(5)]
    if any(m['rho']!=1. for m in meta.values()):
        base['blocking_reasons'].append(dict(code='PURE_MOMENT_LOCAL_REDUCTION_NOT_QUALIFIED',
            panels=[dict(panel=m['panel'],rho=m['rho']) for m in meta.values() if m['rho']!=1.]))
        return base
    stiff=[];bounds=[];tension=[]
    for l,f in ((0,1),(4,3)):
        if meta[l]['branch']=='tension':
            audit=_domain(nodes,t,[[i,0.,1.] for i in groups[l]['ids']+groups[f]['ids']],comp)
            tension.append(dict(flange=groups[f]['panel'],**audit))
            if audit['max_line_or_face_compression_MPa']>0.:
                if name!='My_negative':raise ValueError('Unqualified mixed flange with a tensile lip')
                bound=_outstand(nodes,t,groups[l],groups[f],comp);bounds.append(bound)
                if not bound['integral_bound']:raise ValueError('Free-outstand integral majorant not demonstrated')
            stiff.append(None)
        else:
            stiff.append(_assembly(nodes,t,groups[l],groups[f],meta[f],comp))
    hw=max(p[1] for p in nodes)-min(p[1] for p in nodes)
    for st,other in zip(stiff,stiff[::-1]):
        if st is None:continue
        _distortion(st,other,t,hw)
        if st['Eq5_17_As_red_over_As_at_ULS']!=1.:
            base['blocking_reasons'].append(dict(code='PURE_MOMENT_DISTORTIONAL_REDUCTION_NOT_QUALIFIED',
                flange=st['flange'],As_red_over_As=st['Eq5_17_As_red_over_As_at_ULS']))
    base.update(stiffeners=[s for s in stiff if s],outstand_flange_bounds=bounds,tension_assemblies=tension,
        ULS_pure_effort_signed=sign*scale,pure_ULS_compression_coefficients_absolute=comp)
    if base['blocking_reasons']:return base
    base.update(section_status='integral_pure_moment_ULS_fixed_point',
        proof='EN13 5.5.2/5.5.3/6.1.4.1(4); EN15 Table4.1/4.2. Every local rho=1 and compressed physical As exact Eq5.17 cap=1. Tensile-lip mixed flanges require a separate free-outstand majorant.',
        fixed_point_statement='All widths and thicknesses unchanged at the pure-ULS reference; therefore same stress field on re-evaluation.',
        assembly_interpretation='Inherited EN stiffener-as-column model: wholly compressed physical As; kr=As2/As1 when both exist, kr=0 only for the wholly tensile opposite assembly. Not a coupled translating-junction eigenmode proof.')
    return _accept(base,coeff,copy.deepcopy(gross),copy.deepcopy(full),gross)


def _capacity_floor(nodes,t,cg,coeff):
    """Outward arithmetic for the exact supplied binary64 operator/contour.

    This encloses evaluation, not uncertainty in material or effective widths.
    It does not use a pure-ULS normalization as a resistance denominator.
    """
    from .torsion_vlasov.intervals import Interval as I, stack
    import numpy as np
    p=I(nodes);g=I(cg);c=I(coeff);d=p[1:]-p[:-1]
    length=(d[:,0].square()+d[:,1].square()).sqrt()
    normal=stack([-d[:,1]/length,d[:,0]/length],axis=-1)
    xy=stack([p[:-1]-g,p[1:]-g],axis=1);maximum=0.
    for side in (-1,0,1):
        face=xy+normal[:,None,:]*(side*t/2)
        sigma=c[0]+c[1]*face[:,:,0]+c[2]*face[:,:,1]
        maximum=max(maximum,float(np.max(sigma.abs().hi)))
    lower=float((I(MATERIAL['fya_MPa'])/I(MATERIAL['gamma_M0'])/I(maximum)).lo)
    floor=math.floor(lower)
    if floor<=0:raise ValueError('Nonpositive first-yield capacity floor')
    return dict(integer_floor=floor,first_yield_lower=lower,maximum_abs_unit_stress_upper=maximum,
        domain='ALL physical line/offset-face endpoints; contains the retained effective material',
        numerical_scope='Outward rounding for supplied binary64 operator/contour, not interval proof of effective-width derivation',
        reference='EN13 6.1.2/6.1.3/6.1.4.1; elastic first yield, no plastic/cold-work enhancement')


def build_catalog_component_sections(index, **material):
    """Return each signed branch separately; this does not enable app routing.

    Fixed E=210000, fyb=fya=250, nu=.3, gammaM0=1. A branch needing an
    unimplemented reduction is explicitly absent, even if its opposite works.
    """
    for key,value in material.items():
        if key not in MATERIAL or type(value) not in (int,float) or not math.isfinite(value) or value!=MATERIAL[key]:
            raise ValueError('Material outside the fixed reviewed EN domain: '+key)
    entry,reference,identity,nodes,t,groups,full,gross,guard=_geometry(index)
    components={}
    for name in PURE_ACTIONS:
        base=_base(name)
        if not guard['satisfied']:
            base['blocking_reasons']=[dict(code='EN_GEOMETRICAL_PROPORTIONS_NOT_QUALIFIED',audit=guard)]
        else:
            try:
                if name=='N_tension':
                    base.update(section_status='gross_uniform_tension_yielding_only',
                        proof='EN13 6.1.2 gross-area yielding; net fracture and connections not covered')
                    base=_accept(base,[1/gross['A_mm2'],0.,0.],copy.deepcopy(gross),copy.deepcopy(full),gross)
                elif name=='N_compression':base=_uniform_compression(nodes,t,groups,full,gross)
                else:base=_integral_moment(name,nodes,t,groups,full,gross)
            except ValueError as error:
                base=_base(name)
                base['blocking_reasons']=[dict(code='SIGNED_COMPONENT_DOMAIN_NOT_QUALIFIED',detail=str(error))]
        if base['eligible']:
            capacity=_capacity_floor(nodes,t,gross['centroid_xy_mm'],base['sigma_coefficients_c0_cx_cy'])
            base['first_yield_capacity_floor']=capacity['integer_floor'];base['capacity_audit']=capacity
        components[name]=base
    result=dict(schema=SCHEMA,method_revision=REVISION,catalog_index=index,catalog_id=entry['id'],
        nominal_identity=identity,nominal_identity_sha256=_sha(identity),nodes_sha256=_sha(nodes),
        profile_id='OWN_PIERIN_NOMINAL_'+entry['id']+'_'+_sha(identity)[:16],
        geometry_source_url=entry['source_url'],pierin_nominal_row_id=reference['id'],
        nodes_xy_mm=nodes,thickness_mm=t,material=copy.deepcopy(MATERIAL),gross_properties=gross,
        panels=groups,geometry_guard=guard,components=components,
        coordinate_system='R01, stress coefficients relative to this contour gross centroid',
        stress_convention='N tension positive, Mx=integral(y*sigma)dA, My=-integral(x*sigma)dA',
        all_normal_components_eligible=all(v['eligible'] for v in components.values()),
        signed_capacity_floor={k:v['first_yield_capacity_floor'] for k,v in components.items()},
        normal_yield_limit_MPa=MATERIAL['fya_MPa']/MATERIAL['gamma_M0'],
        review_status='candidate_pending_independent_review',runtime_release_approved=False,
        physical_geometry_verified=False,whole_member_approved=False,
        complete_EN_design_qualified=False,global_stability_qualified=False,
        pierin_criticals_transferred=False,NBR_capacities_used=False,AISI_capacities_used=False,
        source_basis=[dict(url=EN13,clauses='5.1,5.2,5.5.2,5.5.3.1-2,6.1.2-4,6.1.6'),
                      dict(url=EN15,clauses='4.4/Table4.1/Table4.2')],
        not_checked=['Reduced lips and nonintegral pure-moment branches',
            'shear resistance and EN6.27 interaction','EN6.1.6 warping and torsional stress interaction',
            'shear lag and flange curling applicability','member stability and second order',
            'coupled modes translating panel junctions','net fracture, fasteners and connections',
            'physical product, core thickness/coating tolerances and material certificate'],
        legacy_certificates_changed=False)
    result['content_sha256']=_sha(result)
    return result


def verify_catalog_component_sections(certificate):
    candidate=copy.deepcopy(certificate);digest=candidate.pop('content_sha256',None)
    if candidate.get('schema')!=SCHEMA or candidate.get('method_revision')!=REVISION or digest!=_sha(candidate):
        raise ValueError('Candidate EN operator certificate changed; rebuild from the nominal row')


def require_component(certificate, axis, value):
    """Zero needs no operator; never substitute another branch or gross data."""
    verify_catalog_component_sections(certificate)
    if axis not in ('N','Mx','My') or type(value) not in (int,float) or not math.isfinite(value):
        raise ValueError('Finite N, Mx or My signed action required')
    if value==0.:return None
    name=('N_tension' if value>0 else 'N_compression') if axis=='N' else axis+('_positive' if value>0 else '_negative')
    component=certificate['components'][name]
    if not component['eligible']:raise ValueError(name+': '+json.dumps(component['blocking_reasons']))
    return copy.deepcopy(component)
