"""Parametric EN13 local/distortional steps 1-2 for signed pure moments.

No catalogue critical stresses are used. Every interval refers to the original
rounded contour. The optional step-3 strength refinement is not used.
"""
from __future__ import annotations
import copy
import math
from .en_ue_catalog_operators import (_properties, _eval, _vertices, _domain,
    _ends, _bands, _weighted, _base, _accept)
from .three_girt_en_normal.en1993_normal_components import PURE_ACTIONS


def _operator(name, props, gross, nodes, t, full, fy):
    axis, sign = PURE_ACTIONS[name]
    Ix, Iy, Ixy = (props[k] for k in ('Ix_strong_mm4','Iy_weak_mm4','Ixy_mm4'))
    det = Ix*Iy-Ixy*Ixy
    cx, cy = (-Ixy/det, Iy/det) if axis == 1 else (-Ix/det, Ixy/det)
    x,y = props['centroid_xy_mm']
    absolute = [-cx*x-cy*y,cx,cy]
    maximum = max(abs(_eval(absolute,p)) for p in _vertices(nodes,t,[r[:3] for r in full]))
    scale = fy/maximum
    compression = [-sign*scale*c for c in absolute]
    gx,gy=gross['centroid_xy_mm']
    return [cx*(gx-x)+cy*(gy-y),cx,cy],compression,sign*scale


def _internal_bands(meta, stress):
    rho=meta['rho']
    if rho==1.:return [(0.,1.)]
    psi=meta['psi'];bc=1. if psi>=0. else 1./(1.-psi)
    first=rho*bc*(2./(5.-psi) if psi>=0. else .4)
    second=rho*bc-first
    if stress[0]>=stress[1]:
        return [(0.,first),(bc-second,1.)]
    return [(0.,1.-bc+second),(1.-first,1.)]


def _assembly(nodes,t,lip,flange,lip_refs,flange_meta,comp):
    refs=copy.deepcopy(lip_refs)+_bands(nodes,flange,[(flange_meta['flange_lip_adjacent_start_fraction'],1.)])
    props=_properties(nodes,[[*r,t] for r in refs])
    audit=_domain(nodes,t,refs,comp)
    if audit['min_line_or_face_compression_MPa']<=0:
        raise ValueError('Effective physical stiffener not wholly compressed')
    return dict(flange=flange['panel'],As_mm2=props['A_mm2'],Is_mm4=props['Ix_strong_mm4'],
        centroid_xy_mm=props['centroid_xy_mm'],b1_mm=props['centroid_xy_mm'][0],
        line_intervals=refs,stress_domain_audit=audit,
        sigma_com_Ed_MPa=_eval(comp,props['centroid_xy_mm']))


def reduced_moment(kernel,name,nodes,t,groups,full,gross):
    """Gross flange psi; iterated web psi; conservative fyb stiffener strength.

    t_red=chi_d*t is the uniform-fyb steps 1-2 reduction. The final pure-ULS
    stiffener stress must demonstrate chi_d <= the Eq5.17 permitted ratio.
    This forgoes the favourable stress-ratio enlargement of As, not reduction.
    """
    fy=kernel.material['fyb_MPa']; _,initial,_=_operator(name,gross,gross,nodes,t,full,fy)
    meta={j:kernel._internal_certificate(groups[j],t,_ends(groups[j],initial)) for j in (1,3)}
    for lip,flange in ((0,1),(4,3)):
        meta[lip]=kernel._lip_certificate(groups[lip],groups[flange],t,_ends(groups[lip],initial))
    refs_by_panel={};bands_by_panel={}
    for j in (0,1,3,4):
        if j in (1,3):bands=_internal_bands(meta[j],_ends(groups[j],initial))
        elif meta[j]['rho']==1.:bands=[(0.,1.)]
        else:bands=[(0.,meta[j]['rho'])] if j==0 else [(1.-meta[j]['rho'],1.)]
        bands_by_panel[j]=bands;refs_by_panel[j]=_bands(nodes,groups[j],bands)
    stiff=[]
    for lip,flange in ((0,1),(4,3)):
        if meta[lip]['branch']=='tension':stiff.append(None)
        else:stiff.append(_assembly(nodes,t,groups[lip],groups[flange],refs_by_panel[lip],meta[flange],initial))
    hw=max(p[1] for p in nodes)-min(p[1] for p in nodes)
    for st,other in zip(stiff,stiff[::-1]):
        if st is None:continue
        kernel._distortion(st,other,t,hw)
        st['Eq5_17_As_red_over_As_at_ULS']=st['chi_d']
        st['applied_As_red_over_As']=st['chi_d']
        st['t_red_mm']=t*st['chi_d']
    active=[s for s in stiff if s]
    # First web stress uses effective flanges, gross web, EN13 5.5.2(3).
    refs_by_panel[2]=[[i,0.,1.] for i in groups[2]['ids']]
    history=[]; previous=None
    for iteration in range(160):
        refs=[r for j in range(5) for r in refs_by_panel[j]]
        weighted=_weighted(refs,[dict(st,Eq5_17_As_red_over_As_at_ULS=st['applied_As_red_over_As']) for st in active],t)
        props=_properties(nodes,weighted)
        coeff,comp,effort=_operator(name,props,gross,nodes,t,full,fy)
        web_stress=_ends(groups[2],comp)
        web=kernel._internal_certificate(groups[2],t,web_stress)
        bands=_internal_bands(web,web_stress)
        vector=[v for band in bands for v in band]
        residual=max(abs(a-b) for a,b in zip(vector,previous)) if previous is not None and len(vector)==len(previous) else 1.
        history.append(dict(iteration=iteration,psi=web.get('psi'),rho=web['rho'],residual=residual))
        if iteration>=2 and residual<1e-13:break
        refs_by_panel[2]=_bands(nodes,groups[2],bands)
        previous=vector
    else:raise ValueError('Effective web stress-gradient iteration did not converge')
    meta[2]=web;bands_by_panel[2]=bands
    domains={g['panel']:_domain(nodes,t,[[i,0.,1.] for i in g['ids']],comp) for g in groups}
    for lip,flange in ((0,1),(4,3)):
        if meta[lip]['branch']=='tension':
            if max(domains[groups[j]['panel']]['max_line_or_face_compression_MPa'] for j in (lip,flange))>0.:
                raise ValueError('Opposite assembly not wholly tensile; kr=0 unavailable')
        elif domains[groups[lip]['panel']]['min_line_or_face_compression_MPa']<=0.:
            raise ValueError('Final lip no longer wholly compressed')
    for st in active:
        audit=_domain(nodes,t,st['line_intervals'],comp)
        sigma=_eval(comp,st['centroid_xy_mm'])
        permitted=min(1.,st['chi_d']*fy/sigma) if sigma>0 else 0.
        if audit['min_line_or_face_compression_MPa']<=0. or not st['chi_d']<=permitted:
            raise ValueError('Uniform-fyb stiffener reduction not conservative at final ULS')
        st.update(sigma_com_Ed_MPa=sigma,stress_domain_audit=audit,
            Eq5_17_unclamped_As_ratio_at_ULS=st['chi_d']*fy/sigma,
            Eq5_17_permitted_As_red_over_As_at_ULS=permitted,
            Eq5_17_As_red_over_As_at_ULS=permitted,
            application='Conservative chi_d thickness; favourable Eq5.17 stress-ratio enlargement omitted',
            applied_ratio_not_greater_than_Eq5_17=True)
    base=_accept(_base(name),coeff,props,weighted,gross)
    base.update(section_status='effective_local_distortional_steps1_2_pure_moment',
        local_panels=[meta[j] for j in range(5)],stiffeners=active,
        retained_bands=[dict(panel=groups[j]['panel'],retained_fraction_bands=bands_by_panel[j],
            line_intervals=refs_by_panel[j]) for j in range(5)],
        ULS_pure_effort_signed=effort,pure_ULS_compression_coefficients_absolute=comp,
        full_physical_panel_domain_audit=domains,
        web_iteration_audit=dict(history=history,iterations=len(history),residual=residual,
            tolerance=1e-13,final_recheck=True,uniqueness_proved=False),
        proof='EN13 5.5.2(3),5.5.3.2 steps1-2/Eq5.13-5.17,6.1.4.1; EN15 Table4.1. Gross flange psi, iterated effective web psi; physical local As reduced once by chi_d. Final Eq5.17 bound verified; favourable area enlargement and optional step3 omitted.',
        assembly_interpretation='Physical locally effective lip and adjacent flange strip on the own rounded contour; no transferred Pierin critical or coupled translating-junction eigenmode proof.',
        fixed_point_statement='Web stress-gradient widths rechecked after at least two iterations; flanges retain permitted gross psi. Numerical convergence, not interval uniqueness certificate.')
    return base


def adaptive_outstand(kernel,nodes,t,lip,flange,comp):
    """Signed Table4.2 majorants, supported edge compressed / free edge tensile.

    Every trial is constrained on ALL actual facet line/face vertices, including
    negative ordinates. A grid only selects a demonstrable majorant; failure is
    method noncoverage, never a normative rejection or an asserted capacity.
    """
    vertices=list(_vertices(nodes,t,[[i,0.,1.] for i in flange['ids']]))
    audit=_domain(nodes,t,[[i,0.,1.] for i in lip['ids']],comp)
    candidates=[]
    for n in range(21):
        psi=-n/20.
        pairs=[(_eval(comp,p),1.-(1.-psi)*(p[0]-flange['lo'])/flange['b_mm']) for p in vertices]
        lower=max([0.]+[s/q for s,q in pairs if q>0.])
        upper=min([math.inf]+[s/q for s,q in pairs if q<0.])
        amplitude=float(math.ceil(lower))
        if amplitude<=0. or amplitude>upper or any(s>0. for s,q in pairs if q==0.):continue
        margin=max(s-amplitude*q for s,q in pairs)
        if margin>0.:continue
        k=1.7-5*psi+17.1*psi*psi
        critical=kernel._critical(k,t,flange['b_mm'])
        lam=math.sqrt(amplitude/critical)
        rho=1. if lam<=.748 else min(1.,(lam-.188)/lam**2)
        candidates.append(dict(panel=flange['panel'],rho=rho,lambda_p=lam,k_sigma=k,
            bound_psi=psi,bound_stress_ends_MPa=[amplitude,psi*amplitude],
            sigma_cr_MPa=critical,slenderness_reference_stress_MPa=amplitude,
            maximum_actual_minus_bound_MPa=margin,minimum_amplitude_MPa=lower,
            maximum_amplitude_MPa=upper if math.isfinite(upper) else None,
            lip_stress_domain_audit=audit,integral_bound=rho==1. and audit['max_line_or_face_compression_MPa']<=0.,
            dominance_includes_negative_q=True,dominance_includes_line_and_both_faces=True,
            reference='EN15 Table4.2 [-1,0], supported web/free lip edge; 4.4(4)/Eq4.4 pure-ULS amplitude',
            lip_restraint_credited=False,translating_junction_modes_qualified=False))
    if not candidates:raise ValueError('No signed free-outstand majorant demonstrated')
    return min(candidates,key=lambda v:v['lambda_p'])


def audit_effective_state(kernel,name,nodes,t,groups,full,gross,weighted,*,stiffeners=()):
    """Recompute a supplied retained state, without granting qualification.

    Supplemental methods (e.g. shear lag) can compare required web bands and
    stiffener stress limits after modifying panel areas. They must close their
    own width/area iteration and establish the added method's domain. This
    function does not establish a shear-lag law or transfer an old approval.
    """
    segments={}
    for row in weighted:
        if not isinstance(row,(list,tuple)) or len(row)!=4:raise ValueError('Effective interval must contain i,lo,hi,t')
        i,lo,hi,te=row
        if (type(i) is not int or not 0<=i<len(nodes)-1
            or any(type(v) not in (int,float) or not math.isfinite(v) for v in (lo,hi,te))
            or not 0<=lo<hi<=1 or not 0<te<=t):raise ValueError('Invalid effective interval')
        segments.setdefault(i,[]).append((lo,hi))
    for rows in segments.values():
        rows=sorted(rows)
        if any(a[1]>b[0] for a,b in zip(rows,rows[1:])):raise ValueError('Effective intervals overlap')
    props=_properties(nodes,weighted)
    coefficients,compression,effort=_operator(name,props,gross,nodes,t,full,kernel.material['fyb_MPa'])
    stress=_ends(groups[2],compression)
    web=kernel._internal_certificate(groups[2],t,stress)
    panels={g['panel']:_domain(nodes,t,[[i,0.,1.] for i in g['ids']],compression) for g in groups}
    audits=[]
    for st in stiffeners:
        domain=_domain(nodes,t,st['line_intervals'],compression)
        sigma=_eval(compression,st['centroid_xy_mm'])
        allowed=min(1.,st['chi_d']*kernel.material['fyb_MPa']/kernel.material['gamma_M0']/sigma) if sigma>0. else None
        audits.append(dict(flange=st['flange'],sigma_com_Ed_MPa=sigma,
            physical_domain=domain,Eq5_17_permitted_As_red_over_As=allowed,
            whole_As_compressed=domain['min_line_or_face_compression_MPa']>0.))
    return dict(effective_properties=props,sigma_coefficients_c0_cx_cy=coefficients,
        pure_ULS_compression_coefficients_absolute=compression,ULS_pure_effort_signed=effort,
        web_certificate=web,required_web_bands=_internal_bands(web,stress),
        full_physical_panel_domain_audit=panels,stiffener_stress_audits=audits,
        qualification_inferred=False,whole_member_approved=False,
        scope='Arithmetic/domain re-audit of supplied effective intervals only; caller must establish and close supplemental normative model')
