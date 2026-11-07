"""Parameterized NBR scalar extensions; no catalogue identities or borrowed criticals.

The conventional strong-axis MLE is not a two-dimensional stress operator.
The weak elastic distortion is an approximation explicitly admitted as such.
"""
from __future__ import annotations
import math

SOURCE_MLE = 'NBR14762:2010 §§9.2.2,9.2.3,9.8.2.1(a),9.8.2.2(a); CBCA2016 §§4.3,6.3.1.1'
SOURCE_D = 'Elastic: S100-2024 Appendix2 §2.3.3.2(b), Eqs8–11; adoption NBR14762:2010 §9.3; resistance only §9.8.2.3'
SOURCE_DOCUMENTS = [dict(title='CBCA Steel Framing: Engenharia, 2016',
    url='https://www.skylightestruturas.com.br/downloads/101497_manual_lsf_engenharia_2016.pdf',
    sha256='3fc032153cd5afdfa2710d402499a3ebde5353d0a167fdc220e18bdb0fa457b6',
    pages_printed=[61,62,63,64,65,112,113,114,115,116,117,118,119],
    role='NBR effective-width equations and conventional strong-axis scalar example.'),
    dict(title='ANSI/SDI/AISI S100-2024 and Commentary',
    url='https://sdi.org/wp-content/uploads/2025/01/ANSI-SDI-AISI-S100-2024-SDI-AISI-S100-2024-C.pdf',
    pages_PDF_one_based=[217,219,220,221,502],
    clauses=['Table2.3.3-1','2.3.3.2(b)','2.3.3.2-8/9/10/11','C-2.3.3.2'],
    role='Elastic weak-axis flange-gradient approximation only; no AISI strength curve or resistance factor.'),
    dict(title='AISI S100-16 (R2020) with Supplement3, 2022',
    url='https://buildusingsteel-media.s3.amazonaws.com/wp-content/uploads/2023/06/23212327/AISI-S100-16-2020-wS3-22.pdf',
    sha256='706a4bfaf030768d6382324a8d1916acdb749a0e739ef20fa0d7638ba8a9f03a',
    pages_PDF_one_based=[233],clauses=['2.3.3.2-8/9/10/11'],
    role='Independent visual verification of the same elastic equations read in the 2024 source; not a second resistance standard.')]



class OutsideMethod(ValueError):
    """Method assumptions unproved, not a prohibition of the nominal section."""


def rho(lam):
    return 1. if lam <= .673 else min(1., (1-.22/lam)/lam)


def edge_stiffener(b, d, D, t, E, sigma):
    """NBR9.2.3, simple 90 degree lip, uniform compression envelope.

    The exact printed .328 is used, rather than .487*.673. Existing v1
    certificates retain their own slightly more conservative expression.
    """
    if min(b,d,D,t,E) <= 0 or sigma < 0 or not all(map(math.isfinite,(b,d,D,t,E,sigma))):
        raise ValueError('Invalid element/material/stress parameters')
    l0 = b/t/.623*math.sqrt(sigma/E)
    ll = d/t/.95*math.sqrt(sigma/(.43*E))
    de = d*rho(ll)
    Is = t*d**3/12
    Ia = min(399*t**4*max(0., .487*l0-.328)**3, t**4*(56*l0+5))
    if l0 <= .673:
        k, lf, ratio, be, ds = None, l0, 1., b, de
    else:
        if D/b > .8:
            raise OutsideMethod('NBR9.2.3 requires D/b<=0.8 when the edge stiffener is necessary')
        ratio = min(1., Is/Ia) if Ia else 1.
        n = max(1/3, .582-.122*l0)
        k = min(4., (3.57 if D/b <= .25 else 4.82-5*D/b)*ratio**n+.43)
        lf = b/t/.95*math.sqrt(sigma/(E*k))
        be, ds = b*rho(lf), ratio*de
    return dict(flange_flat_mm=b,lip_flat_mm=d,nominal_lip_mm=D,
        uniform_compression_envelope_MPa=sigma,lambda_p0=l0,Is_mm4=Is,Ia_mm4=Ia,
        Is_over_Ia_capped=ratio,k=k,flange_lambda=lf,lip_lambda=ll,
        flange_effective_width_mm=be,lip_effective_width_mm=de,
        reduced_lip_width_mm=ds,flange_width_at_lip_mm=ratio*be/2,
        flange_width_at_web_mm=be-ratio*be/2,
        corners_in_stiffener_inertia=False,source=SOURCE_MLE)


def strong_effective_modulus(p, props, m, stress):
    """Conventional scalar MLE with reduced flange/lip and proved full web.

    CBCA6.3.1.1 explicitly integrates y/Ix, preserving corner material. This
    helper follows that engineering convention, not an exact tensor operator.
    It does NOT infer a local elastic critical moment or modify gross rigidity.
    """
    if not 0 < stress <= m['fy_MPa'] or not math.isfinite(stress):
        raise ValueError('Effective-section stress must satisfy 0<sigma<=fy')
    t,ri,h = p['t'],p['ri_mm'],p['h']
    b,d,B = p['bf']-2*(ri+t),p['lip']-ri-t,h-2*(ri+t)
    if min(b,d,B) <= 0 or b/t>60 or B/t>200 or d/t>60:
        raise OutsideMethod('Flat geometry or NBR Table4 unreinforced-beam width/thickness domain unavailable')
    edge = edge_stiffener(b,d,p['lip'],t,m['E_MPa'],stress)
    a,r = h-t,ri+t/2
    removed_flange = b-edge['flange_effective_width_mm']
    lip_lo,lip_hi = a-(p['lip']-t/2),a-r-edge['reduced_lip_width_mm']
    # Coordinates refer to the unchanged rounded midsurface. Only flat parts
    # are removed; the four corner arcs retain their original line integrals.
    A = props['A_mm2']; cy = props['centroid_xy_mm'][1]
    Ae = A-t*removed_flange-t*(lip_hi-lip_lo)
    Sy = A*cy-t*removed_flange*a-t*(lip_hi**2-lip_lo**2)/2
    Qy = props['Ix_strong_mm4']+A*cy*cy-t*removed_flange*a*a-t*(lip_hi**3-lip_lo**3)/3
    ce = Sy/Ae; Ie=Qy-Sy*Sy/Ae
    ctop,cbottom = a+t/2-ce,ce+t/2
    if min(Ae,Ie,ctop,cbottom)>0:
        sigma1=stress*(a-r-ce)/ctop; sigma2=stress*(r-ce)/ctop
    else:
        raise OutsideMethod('Conventional strong MLE compression-first-yield geometry not proved')
    if not sigma1>0>sigma2:
        raise OutsideMethod('Required strong web stress-reversal branch unavailable')
    psi=sigma2/sigma1; k=4+2*(1-psi)+2*(1-psi)**3
    lam=B/t/.95*math.sqrt(sigma1/(m['E_MPa']*k)); be=B*rho(lam)
    bc=a-r-ce; b1=be/(3-psi); b2=.5*be if psi<=-.236 else be-b1
    # The formula caps b1+b2 at bc. Overlap means the compressed web is full.
    # No tolerance turns an actually insufficient width into full effectiveness.
    full=lam<=.673 or b1+b2>=bc
    if not full:
        raise OutsideMethod('Strong MLE requires iterative reduced web; this full-web branch is insufficient')
    return dict(status='computed_conventional_strong_MLE',method='NBR_MLE_reduced_flange_lip_full_web',
        source=SOURCE_MLE,stress_MPa=stress,Aef_mm2=Ae,centroid_y_mm=ce,Ixef_mm4=Ie,
        Wc_mm3=Ie/ctop,Wt_mm3=Ie/cbottom,Wfirst_mm3=Ie/max(ctop,cbottom),
        edge_stiffener=edge,web_proof=dict(sigma1_MPa=sigma1,sigma2_MPa=sigma2,psi=psi,
            k=k,lambda_web=lam,bef_unpartitioned_mm=be,bef1_mm=b1,bef2_mm=b2,
            compressed_width_mm=bc,partition_overlap_mm=b1+b2-bc,fully_effective=full),
        removed_flange_width_mm=removed_flange,removed_lip_y_interval_mm=[lip_lo,lip_hi],
        section_convention='Conventional NBR/CBCA scalar strong bending about the original horizontal direction; NOT an exact 2D effective-section stress operator.',
        tensor_stress_operator_qualified=False,corners_preserved=True,gross_properties_changed=False,
        compression_envelope_used=True,local_elastic_critical_inferred=False)


def positive_flange_majorant(p,m,ce,gradient):
    """Sufficient full-effectiveness check only, not reduced-width AL design."""
    t,ri=p['t'],p['ri_mm'];b=p['bf']-2*(ri+t)
    xstart,xend=ri+t/2,p['bf']-t-(ri+t/2)
    if not (gradient>0 and ce<p['bf']-2*t-ri):
        raise OutsideMethod('Positive weak tensile lip/connecting bend is not proved')
    actual_psi=(ce-xend)/(ce-xstart) if ce>xstart else None
    actual=[gradient*(ce-xstart),gradient*(ce-xend)]
    proof=dict(restraint_at_tensile_lip_released=True,actual_psi=actual_psi,
        actual_flat_endpoint_stresses_MPa=actual,flat_x_interval_mm=[xstart,xend],
        normalized_comparison_interval=[0.,1.],
        two_face_stress_equal=True,flange_normal_x_component=0.,
        no_reduced_AL_section_used=True,moving_junction_stability_claimed=False,
        method='NBR Table6(c) full-effectiveness sufficient affine majorant; no reduced AL section')
    if actual_psi is not None and actual_psi<0:
        psi=max(-1.,actual_psi);k=1.7-5*psi+17.1*psi*psi
        lam=b/t/.95*math.sqrt(actual[0]/(m['E_MPa']*k))
        proof.update(majorant_psi=psi,k=k,lambda_flange=lam,
            majorant_endpoint_stresses_MPa=[actual[0],actual[0]*psi],
            fully_effective=lam<=.673,majorant_dominates_actual=psi>=actual_psi,
            domination_proof='Affine difference is nonnegative at both flat endpoints, hence throughout [0,1] and on both faces.')
    else:
        proof.update(fully_effective=ce<=xstart,entire_flat_in_tension=ce<=xstart)
    return proof


def weak_positive_full_flange(p,props,m):
    """Same uniform-web MLE as v1 with sign-specific sufficient flange proof.

    No reduced flange is invented. Lip and corner tension and fully effective
    compressed flange are rechecked on the final bracketed solution.
    """
    t,ri=p['t'],p['ri_mm'];fy,E=m['fy_MPa'],m['E_MPa']
    B=p['h']-2*(ri+t);b=p['bf']-2*(ri+t);d=p['lip']-ri-t
    A=props['A_mm2'];cg=props['centroid_xy_mm'][0];S=A*cg
    Q=props['Iy_weak_mm4']+A*cg*cg;a=t/2;c=p['bf']-t/2
    if min(B,b,d)<=0 or b/t>60 or B/t>200 or d/t>60:
        raise OutsideMethod('Weak positive geometry or NBR Table4 width/thickness condition unavailable')
    def width(sigma):
        return B*rho(B/t/.95*math.sqrt(sigma/(4*E)))
    def section(w):
        ae=A-t*(B-w);ce=S/ae;iy=Q-S*S/ae
        if min(ae,iy,ce+a,c-ce)<=0:raise OutsideMethod('Invalid positive weak MLE effective section')
        return dict(Aef_mm2=ae,centroid_x_mm=ce,Iyef_mm4=iy,
            Wfirst_mm3=iy/max(ce+a,c-ce),Wc_web_mm3=iy/(ce+a),Wc_lips_mm3=iy/(c-ce),
            web_effective_width_mm=w)
    lower=width(fy);secmin=section(lower);amin=secmin['Aef_mm2']
    sigma_min=fy*(cg+a)/(c-cg);dsmax=(c+a)*fy*t*S/(c*amin-S)**2
    contraction=B*(.5/.88-.22/.88**2)/sigma_min*dsmax
    if not(secmin['centroid_x_mm']<(c-a)/2 and contraction<1 and Q<c*S):
        raise OutsideMethod('Positive weak tension-first-yield/contraction/monotonicity not proved')
    def residual(w):
        ce=section(w)['centroid_x_mm'];return w-width(fy*(ce+a)/(c-ce))
    lo,hi=lower,B
    if residual(lo)>1e-10 or residual(hi)<-1e-10:raise OutsideMethod('Positive MLE root not bracketed')
    for _ in range(64):
        mid=(lo+hi)/2
        if residual(mid)<0:lo=mid
        else:hi=mid
    if abs(residual(lo))>1e-8:raise ValueError('Positive MLE scalar root failed')
    sec=section(lo);ce=sec['centroid_x_mm'];bend_min=p['bf']-2*t-ri
    if not ce<bend_min:
        raise OutsideMethod('Positive weak lip/connecting-bend tension not proved')
    # x=ri+t/2 is the web end of the straight flange. Its normal is vertical:
    # no favourable midsurface correction is used in the weak stress direction.
    sigma_flange=fy*max(0.,ce-(ri+t/2))/(c-ce)
    edge=edge_stiffener(b,d,p['lip'],t,E,sigma_flange)
    full_edge=(edge['lambda_p0']<=.673 or
        (edge['Is_over_Ia_capped']==1. and edge['flange_lambda']<=.673))
    # Independent sufficient check: release the tensile lip's restraint and
    # treat the flange as an AL outstand supported only at the compressed web
    # end. No AL reduced section is used. A less-tensile affine majorant stays
    # in Table6(c)'s -1<=psi<0 interval and can only increase geometric work.
    # If it is fully effective, the actual flange with its extra edge restraint
    # is fully effective too. The lip and bend themselves are proved tensile.
    al_proof=positive_flange_majorant(p,m,ce,fy/(c-ce))
    if not(full_edge or al_proof['fully_effective']):
        raise OutsideMethod('Positive weak flange still needs reduction; no qualified gradient edge-stiffened MLE')
    return dict(section=sec,proof=dict(source=SOURCE_MLE,
        flange_uniform_envelope_MPa=sigma_flange,edge_stiffener=edge,
        sufficient_edge_stiffener_proof=full_edge,flange_outstand_majorant=al_proof,
        lips_in_tension_for_positive_pure_weak=True,
        centroid_upper_mm=ce,connecting_bend_x_lower_mm=bend_min,
        lip_compression_reduction_not_used=True,flanges_fully_effective=True,
        contraction_upper_bound=contraction,root_residual_mm=residual(lo),
        root_bracket_mm=[lo,hi],section_modulus_monotonicity='Q<c*S',
        compression_stress_at_first_yield_MPa=fy*(ce+a)/(c-ce),
        first_yield_side='tension_lips')),section,width


def weak_negative_full_flange(p,props,m,stress):
    """Uniform-lip MLE, with independent proof that both flanges stay full.

    Lip reductions are mirrored, so the horizontal symmetry and Ixy=0 survive.
    No partially supported/locally reduced flange under gradient is admitted.
    """
    if not 0<stress<=m['fy_MPa'] or not math.isfinite(stress):
        raise ValueError('Negative weak MLE requires 0<sigma<=fy')
    t,ri=p['t'],p['ri_mm'];E=m['E_MPa']
    b,d,B=p['bf']-2*(ri+t),p['lip']-ri-t,p['h']-2*(ri+t)
    if min(b,d,B)<=0 or b/t>60 or d/t>60 or B/t>200:
        raise OutsideMethod('Negative weak flat geometry or Table4 width/thickness domain unavailable')
    lip_lambda=d/t/.95*math.sqrt(stress/(.43*E));de=d*rho(lip_lambda)
    A=props['A_mm2'];cg=props['centroid_xy_mm'][0];S=A*cg
    Q=props['Iy_weak_mm4']+A*cg*cg;xmid=p['bf']-t;xext=p['bf']-t/2
    removed=2*t*(d-de);ae=A-removed;se=S-removed*xmid;ce=se/ae
    iy=Q-removed*xmid*xmid-se*se/ae
    if not (min(ae,iy)>0 and t/2<ce<p['bf']-2*t-ri and ce+t/2<=xext-ce):
        raise OutsideMethod('Negative weak compression-first-yield, web tension or lip/bend compression not proved')
    xstart,xend=ri+t/2,p['bf']-ri-1.5*t
    gradient=stress/(xext-ce);s1=gradient*(xend-ce);s2=gradient*(xstart-ce)
    if not s1>0>s2:
        raise OutsideMethod('Negative weak flange stress reversal not proved')
    psi=s2/s1;k=4+2*(1-psi)+2*(1-psi)**3
    lam=b/t/.95*math.sqrt(s1/(E*k));be=b*rho(lam)
    bc=b/(1-psi);b1=be/(3-psi);b2=.5*be if psi<=-.236 else be-b1
    edge=edge_stiffener(b,d,p['lip'],t,E,s1)
    support=edge['lambda_p0']<=.673 or edge['Is_over_Ia_capped']==1.
    full=lam<=.673 or b1+b2>=bc
    if not support:
        raise OutsideMethod('Negative weak Is<Ia under final flange envelope: partially supported flange under gradient needs a qualified reduced-section/local-elastic method')
    if not full:
        raise OutsideMethod('Negative weak flange requires local width reduction under gradient; current full-flange MLE branch does not cover it')
    return dict(section=dict(Aef_mm2=ae,centroid_x_mm=ce,Iyef_mm4=iy,Ixyef_mm4=0.,
        Wfirst_mm3=iy/(xext-ce),Wc_lips_mm3=iy/(xext-ce),Wc_web_mm3=iy/(ce+t/2),
        web_effective_width_mm=B,lip_effective_width_mm=de,
        removed_lip_area_mm2=removed,corners_preserved=True,gross_properties_changed=False),
        proof=dict(source=SOURCE_MLE,method='NBR_MLE_uniform_lips_proved_full_flange',
            compression_stress_MPa=stress,lip_lambda=lip_lambda,lip_effective_width_mm=de,
            mirrored_lip_removal=True,Ixy_zero_by_horizontal_symmetry=True,
            exterior_x_interval_mm=[-t/2,xext],extreme_compression_x_mm=xext,
            entire_contour_absolute_stress_max_MPa=stress,
            extreme_tension_magnitude_MPa=gradient*(ce+t/2),web_in_tension=True,
            lips_and_connecting_bends_in_compression=True,edge_stiffener=edge,
            flange_proof=dict(sigma1_MPa=s1,sigma2_MPa=s2,psi=psi,k=k,lambda_flange=lam,
                bef1_mm=b1,bef2_mm=b2,compressed_width_mm=bc,
                fully_effective=full,edge_support_sufficient=support,
                stress_majorant_basis='Maximum compression of actual flat flange; same on both faces under pure weak bending.'),
            reduced_flange_method_used=False,distortion_qualification_implied=False))


def weak_negative_distortion(p,props,m,flange):
    """S100 general elastic §2.3.3.2(b), web tension / compressed lip.

    Sharp midline flange properties follow Table2.3.3-1; the gross stress field
    and global Iy use the own rounded contour. This is an explicit approximate
    substructure idealization, not an identical-contour FSM certificate.
    """
    f=flange;t=p['t'];E,G,nu=m['E_MPa'],m['G_MPa'],m['nu']
    A,Ix,Iy,Ixy=f['Af_mm2'],f['Ixf_mm4'],f['Iyf_mm4'],f['Ixyf_mm4']
    xo,xh,yo,Cw=f['xof_mm'],f['xhf_mm'],f['yof_mm'],f['Cwf_mm6']
    cg=props['centroid_xy_mm'][0];xext=p['bf']-t/2
    f1=xext-cg;f2=-cg;fcg=-xh-cg
    if not f1>0>f2 or not p['bf']-2*t-p['ri_mm']>cg:
        raise OutsideMethod('Weak distortion requires web in tension and the entire lip/bend in compression')
    xi,psi=(f1-f2)/f1,fcg/f1
    H=Cw+Ix*(xo-xh)**2*(1-Ixy*Ixy/(Ix*Iy))
    he=3.5*math.sqrt(Iy/A+xh*xh)
    Lcr=math.pi*he*(6*(1-nu*nu)*H/(t**3*he**3)+1/120)**.25
    q=math.pi/Lcr;u=q*he
    kfe=q**4*E*H+q*q*G*f['Jf_mm4']
    kwe=E*t**3/(12*(1-nu*nu))*2/he*(1+u*u/6+u**4/120)
    base=Ix+Iy+A*(xh*xh+yo*yo-2*yo*(xo-xh)*Ixy/Iy)
    kfg=q*q*(base*psi+Iy*xi)
    if min(H,he,Lcr,kfe,kwe,kfg)<=0:raise OutsideMethod('Weak distortion elastic coefficients are not positive')
    F=(kfe+kwe)/kfg;Sfc=props['Iy_weak_mm4']/f1
    # For q>0, divide numerator and denominator by q². Completing the
    # square gives a*q²+c/q²-2*sqrt(a*c)=(sqrt(a)*q-sqrt(c)/q)²>=0.
    # Thus Eq8 minimizes this unrestricted approximation globally; using
    # that minimum never takes finite-span/brace credit within THIS model.
    K=E*t**3/(6*(1-nu*nu)*he)
    a=E*H+K*he**4/120;b=G*f['Jf_mm4']+K*he**2/6;c=K
    C=base*psi+Iy*xi
    Fmin=(b+2*math.sqrt(a*c))/C
    minimum_proof=dict(a_Nmm4=a,b_Nmm2=b,c_N=c,C_mm4=C,
        q_optimum_per_mm=(c/a)**.25,q_used_per_mm=q,
        F_global_min_MPa=Fmin,F_formula_MPa=F,
        domain='q>0; a>0,c>0,C>0; same approximate flange-web operator',
        squared_residual_identity='C*(F(q)-Fmin)=(sqrt(a)*q-sqrt(c)/q)^2',
        finite_span_credit_used=False,finite_span_exact_critical_computed=False,
        physical_member_lower_bound_proven=False,
        longitudinal_mode_basis='Sinusoidal half-wave of the cited approximate elastic formula',
        end_restraint_credit_used=False,actual_member_boundary_conditions_qualified=False)
    W=props['Iy_weak_mm4']/max(cg+t/2,f1)
    lam=math.sqrt(W*m['fy_MPa']/(Sfc*F))
    return dict(eligible=True,status='computed_approximate_reference',source=SOURCE_D,
        elastic=dict(Mdist_Nmm=Sfc*F,Fcrd_MPa=F,Lcrd_mm=Lcr,Ld_mm=Lcr,he_mm=he,
            Sfc_mm3=Sfc,compression_fibre_x_mm=xext,global_Iy_mm4=props['Iy_weak_mm4'],
            xi_flange=xi,psi_flange=psi,stress_coordinates=dict(extreme_x_mm=xext,
            flange_web_juncture_x_mm=0.,flange_lip_centroid_x_mm=-xh,gross_centroid_x_mm=cg),
            stress_ratios=dict(f1=1.,f2=f2/f1,fcg=psi),flange_lip=dict(f),
            k_phi_fe_N=kfe,k_phi_we_N=kwe,k_phi_fg_mm2=kfg,k_phi_wg_mm2=0.,
            k_phi_N=0.,beta=1.,E_MPa=E,G_MPa=G,formula_nu=nu,
            length_policy='Ld=Lcrd gives the global minimum of this approximate q>0 formula, including when physical span is shorter; no finite-span credit or effective-length substitution',
            unrestricted_minimum_proof=minimum_proof,
            moment_gradient_credit_used=False,panel_restraint_credit_used=False),
        Wfirst_gross_mm3=W,lambda_dist=lam,rho=rho(lam),
        MRd_Nmm=rho(lam)*W*m['fy_MPa']/m['gamma'],
        sign='negative',web_in_tension=True,lips_in_compression=True,
        geometric_domain=dict(single_web=True,open_cross_section=True,flanges_one_side_of_web=True,
            simple_lip_angle_degrees=90.,holes_present=False),
        strength_standard='NBR14762:2010 §9.8.2.3; gamma='+str(m['gamma']),
        elastic_approximation=True,guaranteed_lower_bound=False,
        same_contour_FSM_claimed=False,rounded_corner_correlation_proven=False,
        correlation=dict(source='S100-2024 Commentary C-2.3.3.2, PDF502; Glauz2018',
            scope='Published derivation for flange stress gradient and web tension. Strong-axis sample statistics are NOT assigned to weak bending.',
            empirical_mean=None,empirical_standard_deviation=None),
        inherited_strong_or_Pierin_critical_used=False)
