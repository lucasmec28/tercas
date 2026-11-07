"""Offline EN derivation restricted to the own index-26 contour and fy=300.

Separate implementation snapshot: never mutates the fy250 modules or admits
its own output to the frozen reader. Pure moments only, N=0.
"""
from __future__ import annotations
import copy
import math
from .en_ue_catalog_operators import (_geometry, _sha, _properties, _eval,
    _vertices, _domain, _ends, _bands, _base, _accept, _assembly)
from .three_girt_en_normal.en1993_normal_components import PURE_ACTIONS
MATERIAL = dict(E_MPa=210000., nu=.3, fyb_MPa=300., fya_MPa=300., gamma_M0=1.)
NODES_PIN = '3814f4cd9fcfa474b6e3fcbd21eedb3fdee38818eca0440abb4408fd506143e2'
ACTIONS = ('Mx_positive','Mx_negative','My_positive','My_negative')
def _critical(k, t, b):
    return k*math.pi**2*MATERIAL["E_MPa"]/(12*(1-MATERIAL["nu"]**2))*(t/b)**2

def _internal_certificate(g, t, stress):
    """EN 1993-1-5 Table 4.1, Eq.4.2 at fyb, NOT at service stress."""
    s0, s1 = stress
    if max(stress) <= 1e-10:
        return {"panel": g["panel"], "branch": "tension", "rho": 1.0,
                "b_mm": g["b_mm"], "compression_stress_ends_MPa": stress}
    psi = min(stress)/max(stress)
    if psi < -3.0-1e-12 or psi > 1.0+1e-12:
        raise ValueError("Table4.1 stress ratio outside [-3,1]")
    psi = max(-3., min(1., psi))
    # Snap only numerical representations of the tabulated endpoints; this
    # prevents mirrored pure bending from selecting different k at psi=-1.
    if abs(psi-1.) <= 1e-12: k = 4.0
    elif abs(psi+1.) <= 1e-12: k = 23.9
    elif psi > 0.: k = 8.2/(1.05+psi)
    elif psi > -1.: k = 7.81-6.29*psi+9.78*psi**2
    else: k = 5.98*(1-psi)**2
    critical = _critical(k, t, g["b_mm"])
    slenderness = math.sqrt(MATERIAL["fyb_MPa"]/critical)
    limit = .5+math.sqrt(.085-.055*psi)
    rho = 1. if slenderness <= limit else min(1., (slenderness-.055*(3+psi))/slenderness**2)
    bc = 1. if psi >= 0. else 1./(1.-psi)
    first = rho*bc*(2./(5.-psi) if psi >= 0. else .4)
    second = rho*bc-first
    lip_start = 1.-first if s1 > s0 else 1.-second
    return {"panel": g["panel"], "branch": "EN1993-1-5_Table4.1_ULS_fyb",
            "b_mm": g["b_mm"], "compression_stress_ends_MPa": stress, "psi": psi,
            "k_sigma": k, "sigma_cr_MPa": critical, "lambda_p": slenderness,
            "lambda_p_integral_limit": limit, "rho": rho,
            "flange_lip_adjacent_start_fraction": lip_start,
            "slenderness_reference_stress_MPa": MATERIAL["fyb_MPa"]}

def _lip_certificate(g, flange, t, stress):
    if max(stress) <= 1e-10:
        return {"panel": g["panel"], "branch": "tension", "rho": 1.0,
                "b_mm": g["b_mm"], "compression_stress_ends_MPa": stress}
    if min(stress) < -1e-10:
        raise ValueError("Mixed-sign lip outside the implemented pure-component domain")
    ratio = g["b_mm"]/flange["b_mm"]
    if not .2 <= ratio <= .6:
        raise ValueError("Lip/flange ratio outside EN1993-1-3 Eq.5.2")
    k = .5 if ratio <= .35 else .5+.83*(ratio-.35)**(2./3.)
    critical = _critical(k, t, g["b_mm"])
    slenderness = math.sqrt(MATERIAL["fyb_MPa"]/critical)
    rho = 1. if slenderness <= .748 else min(1., (slenderness-.188)/slenderness**2)
    return {"panel": g["panel"], "branch": "EN1993-1-3_Eq5.13_ULS_fyb",
            "b_mm": g["b_mm"], "compression_stress_ends_MPa": stress,
            "bpc_over_bp": ratio, "k_sigma": k, "sigma_cr_MPa": critical,
            "lambda_p": slenderness, "lambda_p_integral_limit": .748, "rho": rho,
            "slenderness_reference_stress_MPa": MATERIAL["fyb_MPa"]}

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

def _reduced_state(rho, nodes, t, groups, gross):
    if type(rho) not in (int,float) or not math.isfinite(rho) or not 0 < rho <= 1:
        raise ValueError('rho outside (0,1]')
    refs=[]
    for j,g in enumerate(groups):
        refs.extend(_bands(nodes,g,[(0.,rho/2),(1-rho/2,1.)] if j==2 else [(0.,1.)]))
    weighted=[[*r,t] for r in refs]; eff=_properties(nodes,weighted)
    cx,cy=eff['centroid_xy_mm']; iy=eff['Iy_weak_mm4']
    if abs(cy-gross['centroid_xy_mm'][1])>1e-10 or abs(eff['Ixy_mm4'])>1e-7:
        raise ValueError('Effective geometry lost symmetry')
    pts=list(_vertices(nodes,t,refs)); scale=300/max(abs(p[0]-cx) for p in pts)
    comp=[scale*cx,-scale,0.]
    web=_domain(nodes,t,[[i,0.,1.] for i in groups[2]['ids']],comp)
    stress=web['max_line_or_face_compression_MPa']
    lam=math.sqrt(stress/_critical(4,t,groups[2]['b_mm']))
    target=1. if lam<=.5+math.sqrt(.03) else (lam-.22)/lam**2
    bounds=[_outstand(nodes,t,groups[l],groups[f],comp) for l,f in ((0,1),(4,3))]
    if not all(b['integral_bound'] for b in bounds) or not 0<target<=1 or not 0<stress<=300:
        raise ValueError('Unqualified reduced field or flange majorant')
    coeff=[(cx-gross['centroid_xy_mm'][0])/iy,-1/iy,0.]
    return dict(rho=rho,target=target,residual=target-rho,lambda_red=lam,
        web_bound_MPa=stress,props=eff,weighted=weighted,comp=comp,
        coefficients=coeff,effort=-scale*iy,bounds=bounds)


def _negative_my(nodes,t,groups,gross,initial_rho=1.):
    rho=initial_rho;history=[]
    for n in range(150):
        state=_reduced_state(rho,nodes,t,groups,gross)
        history.append({k:state[k] for k in ('rho','target','residual','lambda_red','web_bound_MPa')})
        if abs(state['residual'])<1e-13:break
        rho=state['target']
    else:raise ValueError('No fixed point convergence')
    state=_reduced_state(rho,nodes,t,groups,gross)
    if abs(state['residual'])>=1e-13 or not 0<rho<1:raise ValueError('Final recheck failed')
    base=_accept(_base('My_negative'),state['coefficients'],state['props'],state['weighted'],gross)
    base.update(section_status='effective_web_reduced_negative_My_ULS',
        rho_web=rho,ULS_pure_effort_signed=state['effort'],
        pure_ULS_compression_coefficients_absolute=state['comp'],
        outstand_flange_bounds=state['bounds'],
        fixed_point_audit=dict(initial_rho=initial_rho,iterations=len(history),history=history,
            residual=state['residual'],final_recheck=True,tolerance=1e-13),
        proof='EN15 4.4(4), Eq4.4 Note1; uniform web bound k=4; free-outstand flanges Table4.2 psi=0 k=1.70; EN13 6.1.4.1(4).',
        lip_restraint_credited=False,translating_junction_modes_qualified=False)
    return base


def build():
    if MATERIAL != dict(E_MPa=210000.,nu=.3,fyb_MPa=300.,fya_MPa=300.,gamma_M0=1.):
        raise ValueError('Only the fixed EN resistance material is supported')
    entry,reference,identity,nodes,t,groups,full,gross,guard=_geometry(26)
    guard['radius_limit_mm']=.04*t*MATERIAL['E_MPa']/MATERIAL['fyb_MPa']
    guard['satisfied'] = guard['satisfied'] and identity['inner_radius_mm']<=guard['radius_limit_mm']
    if (not guard['satisfied'] or _sha(nodes)!=NODES_PIN or t!=2.
            or identity['inner_radius_mm']!=2.
            or identity['dimensions_mm']!=dict(h=125.,bf=50.,lip=17.,t=2.)):
        raise ValueError('Exact index26 geometry required')
    components={}
    for name in ACTIONS:
        result=(_negative_my(nodes,t,groups,gross) if name=='My_negative'
                else _integral_moment(name,nodes,t,groups,full,gross))
        if not result['eligible']:raise ValueError('Signed branch failed: '+name)
        result['capacity_audit']=_capacity_floor(nodes,t,gross['centroid_xy_mm'],result['sigma_coefficients_c0_cx_cy'])
        result['first_yield_capacity_floor']=result['capacity_audit']['integer_floor']
        components[name]=result
    output=dict(schema='EN_own_Ue125x50x17x2_fy300_normal_N0_v1',
        revision='20261106_r1',catalog_index=26,catalog_id=entry['id'],nominal_identity=identity,
        nominal_identity_sha256=_sha(identity),
        profile_id='OWN_PIERIN_NOMINAL_'+entry['id']+'_'+_sha(identity)[:16],
        nodes_xy_mm=nodes,nodes_sha256=_sha(nodes),material=copy.deepcopy(MATERIAL),
        material_origin=dict(fyb_fya='Explicit requested nominal yield, no enhancement or product verification',
            elastic_constants='EN1993-1-3 3.2.1(5) referring to EN1993-1-1 3.2.6: E=210000 MPa, nu=0.3',
            analysis_E_G='External analysis inputs, not read or converted by this authority'),
        thickness_mm=t,gross_properties=gross,geometry_guard=guard,components=components,
        stress_convention='N tension positive, Mx=integral(y*sigma)dA, My=-integral(x*sigma)dA',
        coordinate_origin='Own contour gross centroid; c0 includes effective centroid shift',
        action_scope='N=0; four signed normal moment operators only; EN My is opposite to app NBR My',
        sources=[dict(url='https://www.gfos.unios.hr/download/en-1993-1-1-2005.pdf',clauses='3.2.6'),
                 dict(url='https://www.phd.eng.br/wp-content/uploads/2015/12/en.1993.1.3.2006.pdf',clauses='3.2.1(5), 5.5, 6.1.4, 6.1.6'),
                 dict(url='https://www.phd.eng.br/wp-content/uploads/2015/12/en.1993.1.5.2006.pdf',clauses='4.4 Eq4.4 Note1, Tables4.1/4.2')],
        normal_section_qualified=True,whole_member_approved=False,
        runtime_release_approved=False,complete_EN_design_qualified=False,
        first_order_analysis_qualified=False,global_stability_qualified=False,
        torsion_qualified=False,physical_geometry_verified=False,
        not_checked=['axial force','shear and EN6.27','EN6.1.6 torsion/warping interaction',
                     'curling/shear lag applicability','member stability/second order',
                     'connections/net section','physical product and material certificate'],
        review_status='independently_reviewed_normal_components_only')
    output['content_sha256']=_sha(output)
    return output
