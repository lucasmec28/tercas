"""Current family base arithmetic, separated from immutable R10 replay.

The effective-width reduction is capped by the gross width at the rounded
0.673 transition. New expanded methods are composed in nbr_ue_family.
"""
from __future__ import annotations
import copy
import math
from . import pierin_ue_registry as registry
from .catalog_torsion_section import prepare
from .core.local_table12 import local_critical
from .core.ue_nbr import table14
from .core.flt_vrd import chi_flt
from .ue_catalog_reference import digest
from .ue_catalog_nbr_distortional import SOURCE_DOCUMENTS
SCHEMA='nbr_ue_family_components_v2_base'
FIELD='nbr_ue_family_reference_components'
DEFAULT_MATERIAL=dict(E_MPa=200000.,G_MPa=77000.,fy_MPa=300.,nu=.3,gamma=1.1)

class OutsideMethod(ValueError):
    """A legitimate method gap, not a corrupt source or numerical failure."""

def positive(value,name):
    if type(value) not in (int,float) or not math.isfinite(value) or value<=0:
        raise ValueError(name+': positive finite number required')
    return float(value)

def material_values(material):
    if set(material)!=set(DEFAULT_MATERIAL):
        raise ValueError('Explicit E, G, fy, nu and gamma required; no implicit material mixing')
    m={k:positive(v,k) for k,v in material.items() if k!='nu'}
    nu=material['nu']
    if type(nu) not in (int,float) or not math.isfinite(nu) or not -1<nu<.5:
        raise ValueError('Invalid explicit Poisson ratio')
    return dict(m,nu=float(nu))

def rho(lam):
    return 1. if lam<=.673 else min(1.,(1-.22/lam)/lam)

def elastic_distortion(p,material):
    """S100-2024 general elastic simple 90-degree lip, pure strong bending.
    Sharp midline flange substructure plus own rounded global Sfc is explicit.
    """
    E,G,nu=material['E_MPa'],material['G_MPa'],material['nu']
    ho,t,b,d=float(p['h']),float(p['t']),p['bf']-p['t'],p['lip']-p['t']/2.
    A=(b+d)*t; J=(b+d)*t**3/3.
    Ix=t*(t*t*b*b+4*b*d**3+t*t*b*d+d**4)/(12*(b+d))
    Iy=t*(b**4+4*d*b**3)/(12*(b+d)); Ixy=t*b*b*d*d/(4*(b+d))
    Cw,xo,xh,yo=0.,b*b/(2*(b+d)),-(b*b+2*d*b)/(2*(b+d)),-d*d/(2*(b+d))
    H=Cw+Ix*(xo-xh)**2*(1-Ixy*Ixy/(Ix*Iy))
    Lcr=math.pi*ho*(4*(1-nu*nu)*H/(t**3*ho**3)+1/720)**.25
    q,u=math.pi/Lcr,math.pi/Lcr*ho
    kfe=q**4*E*H+q*q*G*J
    kwe=E*t**3/(12*(1-nu*nu))*(3/ho)*(1+2*u*u/15+u**4/720)
    kfg=q*q*(Ix+Iy+A*(xh*xh+yo*yo-2*yo*(xo-xh)*Ixy/Iy))
    kwg=q*q*(t*ho**3/240)*(300+8*u*u+u**4)/(420+28*u*u+u**4)
    Fcrd=(kfe+kwe)/(kfg+kwg); Sfc=p['Ix_cm4']*1e4/(ho/2.)
    return dict(Mdist_Nmm=Sfc*Fcrd,Fcrd_MPa=Fcrd,Lcrd_mm=Lcr,Ld_mm=Lcr,
        k_phi_fe_N=kfe,k_phi_we_N=kwe,k_phi_fg_mm2=kfg,k_phi_wg_mm2=kwg,
        ho_mm=ho,t_mm=t,Sfc_mm3=Sfc,exterior_fibre_distance_mm=ho/2.,
        global_Ix_mm4=p['Ix_cm4']*1e4,global_inner_radius_mm=p['ri_mm'],
        Sfc_basis='Ix do contorno arredondado / (h externo / 2), na junção mesa-alma comprimida.',
        flange_lip=dict(b_mm=b,d_mm=d,t_mm=t,Af_mm2=A,Jf_mm4=J,Ixf_mm4=Ix,Iyf_mm4=Iy,
            Ixyf_mm4=Ixy,Cwf_mm6=Cw,xof_mm=xo,xhf_mm=xh,yof_mm=yo,yhf_mm=yo,
            lip_angle_degrees=90.,corner_radius_included=False,
            geometry_basis='Tabela 2.3.3-1, coluna esquerda; linhas médias sem raio, não larguras planas.',
            axes='Origem no CG mesa-enrijecedor; x para o lábio; y para baixo.'),
        E_MPa=E,G_MPa=G,formula_nu=nu,
        formula_nu_origin='Parâmetro explícito da fórmula; não inferido do G arredondado.',
        beta=1.,xi_web=2.,k_phi_N=0.,Lm_mm=None,
        length_policy='Ld=Lcrd irrestrito; sem crédito de vão finito, contenção intermediária ou telha.',
        moment_gradient_credit_used=False,panel_restraint_credit_used=False,
        ho_over_Ld=ho/Lcr,preliminary_commentary_formula_used=False)

def weak_kernel(p,props,m):
    """Uniform-AA-web MLE, with all sufficient proofs rechecked per geometry."""
    t,ri=p['t'],p['ri_mm'];fy,E=m['fy_MPa'],m['E_MPa']
    B=p['h']-2*(ri+t);b=p['bf']-2*(ri+t);d=p['lip']-ri-t
    A=props['A_mm2'];cg=props['centroid_xy_mm'][0]
    S=A*cg;Q=props['Iy_weak_mm4']+A*cg*cg;a=t/2;c=p['bf']-t/2
    l0=b/t/.623*math.sqrt(fy/E);Is=t*d**3/12
    Ia=min(399*t**4*(.487*max(0.,l0-.673))**3,t**4*(56*l0+5))
    ratio=p['lip']/b
    # CBCA pp64–65 equations4.8–4.20. Stocky flange needs no stiffener.
    if l0<=.673:
        k=None;lf=l0
    else:
        if ratio>.8:raise OutsideMethod('D/b exceeds .8 in required edge-stiffener MLE branch')
        k=4. if ratio<=.25 else min(4.,4.82-5*ratio+.43)
        lf=b/t/.95*math.sqrt(fy/(E*k))
    ll=d/t/.95*math.sqrt(fy/(E*.43))
    if not ((l0<=.673 or Is>=Ia) and lf<=.673 and ll<=.673):
        raise OutsideMethod('Flanges/lips need local reduction; uniform-web-only MLE not applicable')
    def width(stress):
        return B*rho(B/t/.95*math.sqrt(stress/(4*E)))
    def section(w):
        ae=A-t*(B-w);ce=S/ae;iy=Q-S*S/ae
        if min(ae,iy,ce+a,c-ce)<=0:raise OutsideMethod('Invalid effective-section interval')
        return dict(Aef_mm2=ae,centroid_x_mm=ce,Iyef_mm4=iy,Wfirst_mm3=iy/max(ce+a,c-ce),
            Wc_web_mm3=iy/(ce+a),Wc_lips_mm3=iy/(c-ce),web_effective_width_mm=w)
    lower=width(fy);secmin=section(lower);amin=secmin['Aef_mm2']
    sigma_min=fy*(cg+a)/(c-cg);dsmax=(c+a)*fy*t*S/(c*amin-S)**2
    contraction=B*(.5/.88-.22/.88**2)/sigma_min*dsmax
    if not (secmin['centroid_x_mm']<(c-a)/2 and contraction<1 and Q<c*S):
        raise OutsideMethod('Tension-first-yield, monotonicity or contraction proof unavailable')
    def residual(w):
        ce=section(w)['centroid_x_mm'];return w-width(fy*(ce+a)/(c-ce))
    lo,hi=lower,B
    if residual(lo)>1e-10 or residual(hi)<-1e-10:raise OutsideMethod('MLE root not bracketed')
    for _ in range(64):
        mid=(lo+hi)/2
        if residual(mid)<0:lo=mid
        else:hi=mid
    if abs(residual(lo))>1e-8:raise ValueError('MLE numerical failure')
    bend_min=p['bf']-2*t-ri;lip_min=p['bf']-1.5*t
    tension=secmin['centroid_x_mm']<bend_min<=lip_min
    proof=dict(flange_lambda=lf,lip_lambda=ll,Is_mm4=Is,Ia_mm4=Ia,
        contraction_upper_bound=contraction,root_residual_mm=residual(lo),
        centroid_upper_mm=secmin['centroid_x_mm'],connecting_bend_x_lower_mm=bend_min,
        lips_in_tension_for_positive_pure_weak=tension)
    return dict(positive=section(lo),negative=section(B),proof=proof),section,width

def section_constants(section):
    """Exact cubic moments via two-point Gauss on each straight/faceted segment."""
    p=section['properties'];cx,cy=p['centroid_xy_mm'];t=section['thickness_mm'];x3=[];xy2=[]
    for a,b in zip(section['nodes_xy_mm'][:-1],section['nodes_xy_mm'][1:]):
        ds=math.dist(a,b)*t
        for u in (.5-.5/math.sqrt(3),.5+.5/math.sqrt(3)):
            x=a[0]+u*(b[0]-a[0])-cx;y=a[1]+u*(b[1]-a[1])-cy
            x3.append(ds*x**3/2);xy2.append(ds*x*y*y/2)
    x0=cx-p['shear_center_xy_mm'][0]
    j=(math.fsum(x3)+math.fsum(xy2))/(2*p['Iy_weak_mm4'])+x0
    r2=(p['Ix_strong_mm4']+p['Iy_weak_mm4'])/p['A_mm2']+x0*x0
    return dict(j_mm=j,r0_squared_mm2=r2,x0_mm=x0,integral_x3_mm5=math.fsum(x3),integral_xy2_mm5=math.fsum(xy2))

def _missing(reason):
    return dict(eligible=False,status='outside_method_domain',reason=reason,MRd_Nmm=None)

def assess(index,*,L_mm,material=None,lengths=None,load_position='unknown'):
    """Explicit new reference calculation; effective lengths never change span.
    Load position must describe all actual actions. Unknown/destabilizing leaves
    classical Me as a reference only; no height benefit or actual-load approval.
    """
    record=registry.select_new_study(index,include_routes=False)
    m=material_values(DEFAULT_MATERIAL if material is None else material);L=positive(L_mm,'physical span')
    if load_position not in ('shear_center','stabilizing','destabilizing','unknown'):
        raise ValueError('Explicit supported load position required')
    if lengths is None:lens=dict(Lx_mm=L,Ly_mm=L,Lz_mm=L,origin='whole_span_fork_free_warping_reference')
    else:
        if not isinstance(lengths.get('origin'),str) or not lengths['origin'].strip():
            raise ValueError('Declared effective lengths require provenance')
        lens={k:positive(lengths.get(k),k) for k in ('Lx_mm','Ly_mm','Lz_mm')};lens['origin']=lengths['origin']
    geometry=prepare(index);sec=geometry['section'];props=sec['properties']
    p=dict(record['dimensions_mm'],ri_mm=record['published_properties']['ri_mm'],Ix_cm4=props['Ix_strong_mm4']/1e4)
    W=props['Ix_strong_mm4']/(p['h']/2);fy=m['fy_MPa'];gamma=m['gamma']
    out=dict(schema=SCHEMA,catalog_index=index,catalog_id=record['catalog_id'],
        source_binding=dict(nominal_identity=geometry['nominal_identity'],nominal_identity_sha256=geometry['nominal_identity_sha256'],nodes_sha256=sec['nodes_sha256'],material=m),
        physical_span_mm=L,effective_lengths=lens,load_position=load_position,
        sign_convention='Positive My_app compresses web; negative compresses lips; strong signs symmetric',
        published_Pierin_reference=record['pierin_reference'],published_critical_values=record['workbook_critical_values'],
        pierin_criticals_transferred=False,source_documents=copy.deepcopy(SOURCE_DOCUMENTS),strong={},weak={},
        actual_load_capacity_qualified=False,whole_member_approved=False)
    try:
        local=local_critical('Ue',p['h'],p['bf'],p['t'],W,m['E_MPa'],m['nu'],p['lip'])
        lam=math.sqrt(W*fy/local['Ml_Nmm'])
        out['strong']['local']=dict(local,eligible=True,status='computed',Wc_mm3=W,lambda_local=lam,MRd_Nmm=rho(lam)*W*fy/gamma)
    except ValueError as exc:out['strong']['local']=_missing(str(exc))
    t14=table14(p['h'],p['bf'],p['lip'],p['t']);el=elastic_distortion(p,m)
    ratios=dict(h_t=p['h']/p['t'],b_t=(p['bf']-p['t'])/p['t'],d_t=(p['lip']-p['t']/2)/p['t'])
    envelope=50<=ratios['h_t']<=200 and 25<=ratios['b_t']<=100 and 6.25<=ratios['d_t']<=50
    correlation=dict(source='Glauz2018 Tables2/4 set4',channel_count=60,prediction_to_FSM_mean=.966,
        prediction_to_FSM_standard_deviation=.096,sample_thickness_mm=1.,sample_lip_angles_degrees=[45,90],
        dimensionless_coordinates=ratios,inside_sample_coordinate_envelope=envelope,same_contour_FSM_claimed=False,
        rounded_corner_correlation_proven=False,
        scope='General simple-lip channel approximation; sample envelope is descriptive, not a normative limit or pointwise guarantee')
    if t14['exempt']:distortion=dict(eligible=True,status='not_required_table14',MRd_Nmm=None,table14=t14)
    elif L<el['Lcrd_mm']:
        distortion=_missing('Physical span below unrestricted Lcrd; finite-length distortion not implemented')
        distortion.update(elastic_reference=el,table14=t14,correlation=correlation)
    else:
        lam=math.sqrt(W*fy/el['Mdist_Nmm'])
        distortion=dict(eligible=True,status='computed_approximate_reference',elastic=el,lambda_dist=lam,
            MRd_Nmm=rho(lam)*W*fy/gamma,table14=t14,correlation=correlation,guaranteed_lower_bound=False,elastic_approximation=True)
    out['strong']['distortional']=distortion
    me=math.pi/lens['Ly_mm']*math.sqrt(m['E_MPa']*props['Iy_weak_mm4']*(m['G_MPa']*props['J_mm4']+math.pi**2*m['E_MPa']*props['Cw_mm6']/lens['Lz_mm']**2))
    flt=dict(eligible=False,status='classical_reference_only',Me_reference_Nmm=me,
        actual_position_supported=load_position in ('shear_center','stabilizing'),Cb=1.,height_effect_included=False,
        reason='NBR 9.8.2.2: destabilizing/unknown positions require specialized treatment; lengths do not resolve height')
    if out['strong']['local']['eligible']:
        chi,branch=chi_flt(math.sqrt(W*fy/me));ml=out['strong']['local']['Ml_Nmm']
        flt.update(eligible=True,chi=chi,curve_branch=branch,MRd_Nmm=chi*rho(math.sqrt(chi*W*fy/ml))*W*fy/gamma)
    out['strong']['FLT_reference']=flt
    constants=section_constants(sec);out['section_constants']=constants
    nex=m['E_MPa']*props['Ix_strong_mm4']*(math.pi/lens['Lx_mm'])**2
    nez=(m['G_MPa']*props['J_mm4']+m['E_MPa']*props['Cw_mm6']*(math.pi/lens['Lz_mm'])**2)/constants['r0_squared_mm2']
    j=constants['j_mm'];r2=constants['r0_squared_mm2'];root=math.hypot(j,math.sqrt(r2*nez/nex))
    mes=dict(positive=nex*(root+j),negative=r2*nez/(root+j))
    try:weak,section,width=weak_kernel(p,props,m)
    except OutsideMethod as exc:
        for sign in mes:
            out['weak'][sign]=dict(local=_missing(str(exc)),
                FLT_reference=dict(Me_reference_Nmm=mes[sign],eligible=False,reason='Admissible Wcef method unavailable'),
                distortional=dict(eligible=False,status='susceptibility_not_resolved',MRd_Nmm=None),
                pure_weak_reference_MRd_Nmm=None,complete_reference_components=False)
    else:
        gross=weak['negative']
        for sign in mes:
            wc=gross['Wc_web_mm3' if sign=='positive' else 'Wc_lips_mm3']
            chi,branch=chi_flt(math.sqrt(wc*fy/mes[sign]))
            eff=section(width(chi*fy) if sign=='positive' else gross['web_effective_width_mm'])
            local=weak[sign]['Wfirst_mm3']*fy/gamma
            fltval=chi*fy*eff['Wc_web_mm3' if sign=='positive' else 'Wc_lips_mm3']/gamma
            d_na=sign=='positive' and weak['proof']['lips_in_tension_for_positive_pure_weak']
            out['weak'][sign]=dict(local=dict(eligible=True,MRd_Nmm=local,section=weak[sign],proof=weak['proof']),
                FLT_reference=dict(eligible=True,Me_reference_Nmm=mes[sign],Nex_N=nex,Nez_N=nez,chi=chi,curve_branch=branch,MRd_Nmm=fltval),
                distortional=dict(status='not_applicable_lips_in_tension' if d_na else 'susceptibility_not_resolved',eligible=d_na,MRd_Nmm=None),
                pure_weak_reference_MRd_Nmm=min(local,fltval) if d_na else None,complete_reference_components=d_na)
    out['snapshot_sha256']=digest(out);return out

def validate_saved(evidence,**inputs):
    expected=assess(**inputs)
    if evidence!=expected:raise ValueError('Changed family components or inputs; recalculate explicitly')
    return copy.deepcopy(expected)

def coverage(*,L_mm,material=None,lengths=None,load_position='unknown'):
    records=[assess(i,L_mm=L_mm,material=material,lengths=lengths,load_position=load_position) for i in registry.new_study_indices()]
    counts={k:0 for k in ('strong_local','strong_distortional','strong_FLT_reference','weak_positive_local','weak_negative_local','weak_positive_reference')};rows=[]
    for r in records:
        branches={**{'strong_'+k:v for k,v in r['strong'].items()},**{'weak_'+s+'_local':v['local'] for s,v in r['weak'].items()}}
        row=dict(catalog_index=r['catalog_index'],catalog_id=r['catalog_id'],branches={})
        for name,b in branches.items():
            row['branches'][name]=dict(eligible=b['eligible'],reason=b.get('reason'),status=b.get('status'))
            if b['eligible']:counts[name]+=1
        counts['weak_positive_reference']+=r['weak']['positive'].get('complete_reference_components',False);rows.append(row)
    return dict(schema=SCHEMA,total=len(records),counts=counts,rows=rows,
        material=material_values(DEFAULT_MATERIAL if material is None else material),physical_span_mm=L_mm,whole_member_approved=False)

def tabulated_reference(index,*,material=None):
    """Separate adopted nominal published-scalar section reference.
    NBR§9.8.2.1(b) permits the elastic local critical Ml; §9.3 concerns
    distortional elastic criticals. Table12 is not mandatory for that local route.
    Wx catalogue and Pierin criticals correspond by nominal row, NOT demonstrated
    identical corner/centerline conventions. No source G/nu or weak sign invented.
    """
    record=registry.select_new_study(index,include_routes=False)
    m=material_values(DEFAULT_MATERIAL if material is None else material);source=record['pierin_reference'];compatibility=[]
    if m['E_MPa']!=source['E_MPa']:compatibility.append('E differs from published Pierin E; no elastic rescaling authorized')
    if m['G_MPa']!=77000. or m['nu']!=.3:
        compatibility.append('App reference G/nu changed; Pierin G/nu are unknown and cannot be silently reassigned')
    W=record['published_properties']['Wx_cm3']*1000;critical=record['workbook_critical_values']
    result=dict(schema='nbr_ue_published_nominal_reference_v2',catalog_index=index,catalog_id=record['catalog_id'],
        material=m,dimensions_mm=record['dimensions_mm'],published_properties=record['published_properties'],source=record['source'],
        published_criticals=critical,
        reference_hypothesis='Published Wx and Pierin elastic criticals correspond by exact external nominal row; geometric contour identity is NOT established',
        property_source='Published catalogue geometry source, not a property derivation from Pierin INSTAB',
        source_G_MPa=source['G_MPa'],source_nu=source['nu'],source_corners=source['corners'],source_geometry_to_mean_line=source['source_geometry_to_mean_line'],
        eligibility_scope='Adopted nominal section-reference arithmetic only; no actual member or contour qualification',
        compatibility_reasons=compatibility,elastic_values_rescaled=False,own_contour_used=False,strong={},
        weak=dict(eligible=False,reason='Mly source sign not explicit; neither weak sign resistance is inferred'),whole_member_approved=False,actual_load_capacity_qualified=False)
    for branch,key in (('local','Ml_Nmm'),('distortional','Mdist_Nmm')):
        if compatibility:result['strong'][branch]=_missing('; '.join(compatibility))
        else:
            lam=math.sqrt(W*m['fy_MPa']/critical[key])
            result['strong'][branch]=dict(eligible=True,status='computed_adopted_nominal_reference',elastic_critical_Nmm=critical[key],
                Wc_published_mm3=W,lambda_bar=lam,rho=rho(lam),MRd_Nmm=rho(lam)*W*m['fy_MPa']/m['gamma'],
                source='NBR14762:2010 §§9.3,9.8.2.1(b),9.8.2.3; adopted Pierin criticals',signs=['positive','negative'],
                sign_basis='Strong-axis symmetry of nominal Ue',identical_geometric_models_proven=False)
    result['local_distortional_reference_min_Nmm']=min(b['MRd_Nmm'] for b in result['strong'].values()) if not compatibility else None
    result['FLT_included']=False;result['snapshot_sha256']=digest(result);return result

def attach(result,*,fresh_calculation=False,lengths=None,load_position='unknown',formula_nu=.3):
    """Fresh-result opt-in only; no historical migration or denominator rewrite."""
    if fresh_calculation is not True:return result
    data=result['input_data'];index=data['catalog_index'];row=registry.select_new_study(index,include_routes=False);p=data['properties']
    if any(p.get(k)!=v for k,v in row['dimensions_mm'].items()):raise ValueError('Current nominal dimensions differ from selected complete Pierin row')
    m=dict(E_MPa=p['E_MPa'],G_MPa=p['G_MPa'],fy_MPa=p['fy_MPa'],nu=formula_nu,gamma=1.1)
    packet=dict(schema='nbr_ue_family_reference_attachment_v2',
        own_rounded_contour=assess(index,L_mm=data['L_mm'],material=m,lengths=lengths,load_position=load_position),
        published_nominal_reference=tabulated_reference(index,material=m),routes_must_not_be_mixed=True,
        legacy_denominators_replaced=False,roof_height_effect_qualified=False,whole_member_approved=False)
    packet['snapshot_sha256']=digest(packet);out=copy.deepcopy(result);out[FIELD]=packet;return out
