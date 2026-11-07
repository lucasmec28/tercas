"""Isolated simultaneous-stress audit for the pure-My shear-lag candidate.

This is not a production consumer and does not change saved authorities. Each pure
bending axis has its own shear-lag area/moment enclosure, while B retains the
original gross omega/Cw field. The complete normal field closes local/D.
No member analysis is run. Source authentication and consumer activation are separate from this arithmetic
audit. The adverse uniform reference closes local/D for the complete field.
"""
from __future__ import annotations
import copy
import hashlib
import math
from fractions import Fraction as F
from pathlib import Path
import numpy as np

from .en_ue_catalog_operators import _sha
from .en_ue_family_applicability import assess, _zones, _ratio
from .en_ue_family_shear_lag import _beta_lower, _decimal, _pair
from .en_ue_my_shear_lag_candidate import build as build_my, _segments
from .en_signed_partial_interaction import _outward
from .torsion_vlasov.intervals import Interval as I, stack

SCHEMA='EN_Ue_concurrent_shear_lag_subyield_candidate_v1'
REVISION='simultaneous_normal_field_triangle_bound_20261107_v1'


def _source_binding():
    root=Path(__file__).parent
    names=('en_ue_concurrent_shear_lag_candidate.py','en_ue_my_shear_lag_candidate.py',
        'en_ue_family_shear_lag.py','en_ue_family_applicability.py',
        'isolated_en_ue_catalog_application.py','en_signed_partial_interaction.py',
        'en_ue_family_kernel.py','en_ue_catalog_operators.py',
        'torsion_vlasov/intervals.py')
    return _sha({p:hashlib.sha256((root/p).read_bytes()).hexdigest() for p in names})


def _moment_bounds(demand):
    from . import isolated_en_ue_catalog_application as arithmetic
    from . import en_signed_partial_interaction as core
    result={'Mx':F(0),'My':F(0)};required={'Mx':set(),'My':set()}
    pieces=arithmetic._source_pieces(demand)
    if not pieces:raise ValueError('Original source equilibrium pieces required')
    for piece in pieces:
        fields=arithmetic._fields(demand,piece)
        if any(fields['N']):raise ValueError('Only N=0 is supported')
        for axis in result:
            for pair in core._bernstein([(v,v) for v in fields[axis]]):
                result[axis]=max(result[axis],*(abs(v) for v in pair))
                required[axis].update(core._required(axis,pair))
    return result,{k:sorted(v) for k,v in required.items()}


def _power_bernstein(values):
    if (not isinstance(values,list) or not 1<=len(values)<=4
            or any(type(v) not in (int,float) or not math.isfinite(v) for v in values)):
        raise ValueError('Explicit finite B polynomial of degree at most3 required')
    a=list(map(F,values));degree=len(a)-1
    return [sum((a[k]*F(math.comb(i,k),math.comb(degree,k)) for k in range(i+1)),F(0))
            for i in range(degree+1)]


def _b_bound(demand):
    maximum=F(0);rows=[]
    for element in demand['elements']:
        values=_power_bernstein(element.get('coefficients',{}).get('B_Nmm2'))
        lo,hi=min(values),max(values);maximum=max(maximum,abs(lo),abs(hi))
        rows.append(dict(element_id=element['element_id'],
            B_interval_Nmm2=[_outward(lo,-1),_outward(hi,1)]))
    for state in demand.get('support_limit_states',[]):
        value=state.get('B_Nmm2')
        _power_bernstein([value]);maximum=max(maximum,abs(F(value)))
        rows.append(dict(element_id=state['element_id'],B_interval_Nmm2=[value,value]))
    return maximum,rows


def _unit_stress_bound(n,pairs,*,reference_cg=None):
    points=I(n['nodes_xy_mm']);cg=I(n['gross_properties']['centroid_xy_mm'] if reference_cg is None else reference_cg)
    delta=points[1:]-points[:-1]
    length=(delta[:,0].square()+delta[:,1].square()).sqrt()
    normal=stack([-delta[:,1]/length,delta[:,0]/length],axis=-1)
    c=I([p[0] for p in pairs],[p[1] for p in pairs]);maximum=0.
    for endpoint in (points[:-1],points[1:]):
        for side in (-1,0,1):
            position=endpoint-cg+normal*(I(side)*I(n['thickness_mm'])/I(2.))
            sigma=c[0]+c[1]*position[:,0]+c[2]*position[:,1]
            maximum=max(maximum,float(np.max(sigma.abs().hi)))
    return maximum


def _transport_operator_origin(operators,normal_cg,source_cg):
    """Exact N=0 coordinate transport with outward arithmetic, not tolerance.

    c0s + cx*(x-gs) + cy*(y-gs) equals c0n + cx*(x-gn) + cy*(y-gn).
    Both CGs are independently authenticated by the consumer. No gross B,
    omega/Cw, shear-flow, torque or source geometry is changed.
    """
    for cg in (normal_cg,source_cg):
        if (not isinstance(cg,list) or len(cg)!=2
                or any(type(v) not in (int,float) or not math.isfinite(v) for v in cg)):
            raise ValueError('Two explicit finite CG coordinate references required')
    same=normal_cg==source_cg;result=copy.deepcopy(operators)
    shift=I([0.,0.]) if same else I(source_cg)-I(normal_cg)
    if not same:
        for key,pairs in result.items():
            c0,cx,cy=[I(*pair) for pair in pairs]
            pairs[0]=_pair(c0+cx*shift[0]+cy*shift[1])
    return result,dict(normal_operator_CG_xy_mm=copy.deepcopy(normal_cg),
        original_source_CG_xy_mm=copy.deepcopy(source_cg),
        source_minus_normal_CG_intervals_mm=[_pair(shift[j]) for j in (0,1)],
        translation_applied=not same,identical_coordinates_proved_by_exact_values=same,
        N_identically_zero_proved=True,Mx_My_invariant_under_translation=True,
        original_B_omega_Cw_shear_torque_and_demand_unchanged=True,
        coefficient_rule='c0_source=c0_normal+cx*(CGsource_x-CGnormal_x)+cy*(CGsource_y-CGnormal_y); cx/cy unchanged')


def _mx_component(demand,n,active,my):
    """Own strong-axis area loss with the same simultaneous subyield closure.

    This never scales a previously reduced strong-axis certificate. The pure
    axes share only their gross input contour and uniform local/D upper bound;
    each has its own beta, lost-area set, centroids and Schur denominator.
    """
    if not active:return dict(status='exactly_zero',eligible=True,operator_intervals={})
    if any(not n['components'][name]['eligible'] for name in ('Mx_positive','Mx_negative')):
        raise ValueError('Own qualified signed Mx source components required')
    rows=_segments(n);d=n['nominal_identity']['dimensions_mm'];t=n['thickness_mm']
    areas=[]
    for ids in (range(0,66),range(67,133)):
        area=I(0.)
        for i in ids:area=area+rows[i]['area']
        areas.append(area)
    area_upper=max(float(a.hi) for a in areas);b0=F(d['bf'])-F(t)/2
    zone=_zones(demand,1)
    if not zone['active'] or not zone['zones']:
        raise ValueError('Supported nonzero Mx moment-zero zones required')
    zones=[]
    for a,b in zone['zones']:
        le=b-a;kappa=(I(area_upper)*_decimal(b0)/I(t)).sqrt()/_decimal(le)
        zones.append(dict(start_exact=[a.numerator,a.denominator],end_exact=[b.numerator,b.denominator],
            Le_exact=[le.numerator,le.denominator],b0_upper_mm=_outward(b0,1),
            **_beta_lower(float(kappa.hi))))
    beta=min(z['beta_lower'] for z in zones)
    losses=[]
    for label,ids in (('lower_flange_and_lip',(0,33)),('upper_flange_and_lip',(99,132))):
        straight=I(0.)
        for i in ids:straight=straight+rows[i]['area']
        cap=min(float(((I(1.)-I(beta))*I(area_upper)).hi),float(straight.hi))
        points=[n['nodes_xy_mm'][j] for i in ids for j in (i,i+1)]
        losses.append(dict(name=label,ids=list(ids),area_loss_upper_mm2=cap,
            x_interval_mm=[min(p[0] for p in points),max(p[0] for p in points)],
            y_interval_mm=[min(p[1] for p in points),max(p[1] for p in points)],corner=False))
    # Deliberately allow every rounded corner to disappear, independently of
    # the straight-part budgets; no placement or uniform beta*t is assumed.
    losses += [copy.deepcopy(r) for r in my['geometry_audit']['loss_groups'] if r['corner']]
    g=my['geometry_audit'];xg,yg=n['gross_properties']['centroid_xy_mm']
    A0=I(*g['A_gross_interval_mm2']);Sx0=I(*g['Sx_about_reference_interval_mm3']);Sy0=I(*g['Sy_about_reference_interval_mm3'])
    Qx0=I(*g['Qx_about_reference_interval_mm4']);Qy0=I(*g['Qy_about_reference_interval_mm4']);Qxy0=I(*g['Qxy_about_reference_interval_mm4'])
    D,Sxl,Syl,Jxl,Jyl,Jxyl=(I(0.) for _ in range(6))
    for row in losses:
        cap=I(row['area_loss_upper_mm2']);mass=I(0.,float(cap.hi))
        qx=I(*row['x_interval_mm'])-I(xg);qy=I(*row['y_interval_mm'])-I(yg)
        D=D+cap;Sxl=Sxl+mass*qx;Syl=Syl+mass*qy
        Jxl=Jxl+cap*qx.square();Jyl=Jyl+cap*qy.square();Jxyl=Jxyl+mass*qx*qy
    amin=float((A0-D).lo)
    if amin<=0.:raise ValueError('Nonpositive strong-component retained area lower bound')
    A=I(amin,float(A0.hi));Sx=Sx0-Sxl;Sy=Sy0-Syl;dx,dy=Sx/A,Sy/A
    iy=float((Qx0-I(float(Jxl.hi))-Sx.square()/A).lo)
    ix=float((Qy0-I(float(Jyl.hi))-Sy.square()/A).lo)
    if min(ix,iy)<=0.:raise ValueError('Nonpositive strong-component inertia lower bound')
    cross=Qxy0-Jxyl-Sx*Sy/A;maximum=float(cross.abs().hi)
    schur=float((I(ix)-I(maximum).square()/I(iy)).lo)
    if schur<=0.:raise ValueError('Nonpositive strong Schur inertia lower bound')
    inverse=I(1.)/I(schur,float(Qy0.hi));cy=inverse
    cx=-cross/(I(iy,float(Qx0.hi))*I(schur,float(Qy0.hi)))
    c0=-cx*dx-cy*dy
    coefficients=[[min(0.,float(v.lo)),max(0.,float(v.hi))] for v in (c0,cx,cy)]
    rx,ry=g['physical_reference_radii_upper_mm']
    na_excursion=I(maximum)/I(iy)*(I(rx)+dx.abs())
    arm=float((I(ry)+dy.abs()+na_excursion).hi)
    ceiling=my['local_distortional_audit']['design_compression_ceiling_MPa']
    floor=math.floor(float((I(ceiling)*I(schur)/I(arm)).lo))
    if floor<=0:raise ValueError('No positive pure-Mx subyield capacity floor')
    return dict(status='own_pure_Mx_subyield_area_enclosure',eligible=True,
        conditional_on_simultaneous_local_D_ceiling=True,beta_global_lower=beta,physical_zero_zones=zones,
        flange_group_gross_area_upper_mm2=area_upper,loss_groups=losses,
        A_retained_lower_mm2=amin,centroid_x_interval_mm=_pair(I(xg)+dx),centroid_y_interval_mm=_pair(I(yg)+dy),
        centroid_shift_x_interval_mm=_pair(dx),centroid_shift_y_interval_mm=_pair(dy),
        Ix_lower_mm4=ix,Iy_lower_mm4=iy,Ixy_interval_mm4=_pair(cross),Ixy_absolute_upper_mm4=maximum,
        Mx_schur_inertia_lower_mm4=schur,maximum_equivalent_fibre_arm_upper_mm=arm,
        neutral_axis_y_excursion_upper_mm=float(na_excursion.hi),
        operator_intervals={name:copy.deepcopy(coefficients) for name in ('Mx_positive','Mx_negative')},
        moment_capacity_floor_Nmm=floor,signed_capacity_floor={name:floor for name in ('Mx_positive','Mx_negative')},
        old_reduced_operator_scaled_or_requalified=False,
        corner_rule='Every arc facet may be fully lost, in addition to the bounded straight flange/lip losses',
        geometric_proof='Six gross moments are reused from the same freshly integrated contour, not from an old effective certificate. Strong-axis losses have their own beta and coordinate groups; full centroid/Ixy intervals give Ix_schur>=Ix_min-|Ixy|max^2/Iy_min.',
        local_D_closure='Ac,eff is gross only after the complete simultaneous normal field proves the same uniform local/D ceiling. Initial lips at fyb are separately proved integral.')


def _uniform_reference_audit(n,ceiling,total_upper):
    """Geometric As from adverse uniform compression; no tensile-area credit.

    Both the fyb initial local widths and the locally integral refined widths
    are shown. Bounds cover every intervening adjacent flange strip because
    the full lip is retained, the strip stays inside its own flange, and no
    real tensile subset is removed from As or credited in its stress demand.
    """
    from .en_ue_family_kernel import _Kernel,material
    from .en_ue_catalog_operators import _assembly
    kernel=_Kernel(material(n['material']['fyb_MPa'],n['material']['gamma_M0']))
    if any(kernel.material[k]!=n['material'][k] for k in ('E_MPa','nu','fyb_MPa','gamma_M0')):
        raise ValueError('Uniform reference material differs from the own section material')
    nodes=n['nodes_xy_mm'];t=n['thickness_mm'];groups=n['panels'];fy=n['material']['fyb_MPa']
    gamma=n['material']['gamma_M0'];bounds=ceiling['distortion'];reference_stress=[fy,0.,0.]
    initials={j:kernel._internal_certificate(groups[j],t,[fy,fy]) for j in (1,3)}
    lips={lip:kernel._lip_certificate(groups[lip],groups[flange],t,[fy,fy])
          for lip,flange in ((0,1),(4,3))}
    if any(v['rho']!=1. for v in lips.values()):
        raise ValueError('Both initial lips must independently remain integral in the uniform-fyb reference')
    stages=[]
    for stage in ('initial_uniform_fyb','locally_integral_uniform_reference'):
        assemblies=[]
        for lip,flange in ((0,1),(4,3)):
            meta=copy.deepcopy(initials[flange])
            if stage=='locally_integral_uniform_reference':
                meta.update(rho=1.,flange_lip_adjacent_start_fraction=.5)
            assemblies.append(_assembly(nodes,t,groups[lip],groups[flange],meta,reference_stress))
        records=[]
        hw=max(p[1] for p in nodes)-min(p[1] for p in nodes)
        for st,other in zip(assemblies,assemblies[::-1]):
            kernel._distortion(st,other,t,hw)
            if not (bounds['As_lower_mm2']<=st['As_mm2']<=bounds['As_upper_mm2']
                    and st['Is_mm4']>=bounds['Is_lower_mm4']
                    and 0.<st['b1_mm']<=bounds['b1_b2_upper_mm']
                    and st['kr_area']<=bounds['kr_upper']
                    and st['K_N_mm2']>=bounds['K_lower_N_mm2']
                    and st['sigma_cr_MPa']>=bounds['sigma_cr_lower_MPa']
                    and st['chi_d']>=bounds['chi_d_lower']):
                raise ValueError('A constructed uniform-reference As is not enclosed by the physical bounds')
            records.append({k:copy.deepcopy(st[k]) for k in ('flange','As_mm2','Is_mm4',
                'b1_mm','kr_area','K_N_mm2','sigma_cr_MPa','lambda_d','chi_d','line_intervals')})
        stages.append(dict(stage=stage,assemblies=records))
    local=[]
    for panel in ceiling['local_panels']:
        lam=(I(total_upper)*I(gamma)/I(panel['sigma_cr_lower_MPa'])).sqrt()
        local.append(dict(panel=panel['panel'],lambda_reduced_upper=float(lam.hi),
            lambda_integral_limit_lower=panel['lambda_integral_limit_lower'],
            integral_proved=float(lam.hi)<=panel['lambda_integral_limit_lower']))
    strength=I(bounds['chi_d_lower'])*I(fy)/I(gamma)
    ratio=1. if total_upper==0. else min(1.,float((strength/I(total_upper)).lo))
    passed=all(p['integral_proved'] for p in local) and ratio==1.
    return dict(qualified=passed,reference_stages=stages,
        initial_uniform_lip_certificates=[lips[j] for j in (0,4)],
        simultaneous_local_panel_audits=local,As_red_over_As_lower_proved=ratio,
        full_field_absolute_compression_upper_MPa=total_upper,
        chi_min_fyb_over_gamma_lower_MPa=float(strength.lo),
        real_tensile_subsets_removed_from_As=False,favourable_tensile_stress_credit=False,
        As_geometry_basis='Own physical lip plus adjacent flange strip under adverse uniform compression; initial fyb widths and integral refinement, never cut by the real tension/compression sign',
        bound_scope='All adjacent strips between zero and the full own flange with the initial full lip retained; A/K/Is/b/kr bounds cover the entire family, not only the two displayed reference endpoints',
        proof='Every relevant compression is <= sum of absolute Mx/My/B contributions. The same nonnegative majorant applies to the full reference As, including any physically tensile portion. It is <=chi_min*fyb/gamma, so Eq5.17 permits the full reference As. Eq4.4 uses the simultaneous full-field bound, not the My contribution alone.',
        sources='EN1993-1-5 4.4(4)/Eq4.4; EN1993-1-3 5.5.3.2 steps1-2/Eq5.10b,5.12,5.13,5.15,5.17')


def _curling_components(demand,n,my,mx,contributions):
    """Pure resistance-component curling only; no common biaxial neutral axis."""
    result={'My':dict(qualified=my['curling_qualified'],panels=copy.deepcopy(my['curling_panels']))}
    if mx['status']=='exactly_zero':
        result['Mx']=dict(qualified=True,active=False,panels={})
    else:
        d=n['nominal_identity']['dimensions_mm'];t=n['thickness_mm']
        H=I(d['h'])-I(t);r=I(n['nominal_identity']['inner_radius_mm'])+I(t)/I(2.)
        delta=r*(I(1.)-I(1.)/I(2.).sqrt())
        center=I(*mx['centroid_y_interval_mm']);excursion=I(mx['neutral_axis_y_excursion_upper_mm'])
        distance=I(min(float((center-delta-excursion).lo),float((H-center-delta-excursion).lo)))
        panel=_ratio(contributions['Mx'],d['bf'],distance,t,d['h'])
        result['Mx']=dict(qualified=panel is not None and panel['ratio_upper']<1.,active=True,
            panels={'strong':panel})
    return dict(qualified=all(r['qualified'] for r in result.values()),axes=result,
        scope='Curling of the respective pure bending resistance components under EN13 5.4/6.1.4.1; not simultaneous physical flange displacement from N/M/B',
        common_neutral_axis_assumed=False)


def audit(demand,n):
    """Arithmetic audit only. It cannot silently activate the old consumer."""
    out=dict(schema=SCHEMA,method_revision=REVISION,technical_source_sha256=_source_binding(),
        source_demand_sha256=_sha(demand),normal_source_sha256=n['content_sha256'],
        eligible=False,construction_qualified=False,source_authenticated=False,
        consumer_integrated=False,simultaneous_local_D_qualified=False,
        whole_member_approved=False,physical_exceedance_witness_permitted=False,
        exact_common_effective_tensor_claimed=False,blocking_reasons=[])
    try:
        section=demand['section']
        if (section.get('nodes_sha256')!=n['nodes_sha256']
                or _sha(section.get('nodes_xy_mm'))!=n['nodes_sha256']
                or section.get('thickness_mm')!=n['thickness_mm']):
            raise ValueError('Normal operators and simultaneous field must use the same own contour/thickness')
        my=build_my(demand,n)
        if not my.get('pure_component_capacity_qualified'):
            raise ValueError('Own My area/local/D construction unavailable: '+str(my['blocking_reasons']))
        moments,required=_moment_bounds(demand)
        mx=_mx_component(demand,n,moments['Mx']!=0,my)
        operators=copy.deepcopy(my['operator_intervals']);operators.update(mx['operator_intervals'])
        source_cg=section.get('properties',{}).get('centroid_xy_mm')
        operators,origin_transport=_transport_operator_origin(operators,n['gross_properties']['centroid_xy_mm'],source_cg)
        contributions={};unit_bounds={}
        for axis in ('Mx','My'):
            unit=max([0.]+[_unit_stress_bound(n,operators[name],reference_cg=source_cg) for name in required[axis]])
            unit_bounds[axis]=unit
            contributions[axis]=_decimal(moments[axis])*I(unit)
        b,bernstein_rows=_b_bound(demand)
        section=demand['section'];omega=section['omega_nodes_mm2'];cw=section['properties']['Cw_mm6']
        if (not isinstance(omega,list) or len(omega)!=len(n['nodes_xy_mm'])
                or any(type(v) not in (int,float) or not math.isfinite(v) for v in omega)
                or type(cw) not in (int,float) or not math.isfinite(cw) or cw<=0):
            raise ValueError('Explicit finite own gross omega/Cw required')
        omega_max=max(abs(v) for v in omega)
        contributions['B']=_decimal(b)*I(omega_max)/I(cw)
        total=contributions['Mx']+contributions['My']+contributions['B']
        ceiling=my['local_distortional_audit']['design_compression_ceiling_MPa']
        sufficient=float(total.hi)<=ceiling
        uniform_reference=_uniform_reference_audit(n,my['local_distortional_audit'],float(total.hi))
        curling=_curling_components(demand,n,my,mx,contributions)
        ready=sufficient and uniform_reference['qualified'] and curling['qualified']
        if not sufficient:
            out['blocking_reasons'].append(dict(code='SIMULTANEOUS_LOCAL_D_CEILING_NOT_PROVED',
                detail='The absolute simultaneous field bound exceeds the sufficient local/D design ceiling.',
                stress_upper_MPa=float(total.hi),ceiling_MPa=ceiling,normative_rejection_inferred=False))
        if not uniform_reference['qualified']:
            out['blocking_reasons'].append(dict(code='UNIFORM_LOCAL_D_REFERENCE_NOT_QUALIFIED',
                detail='The adverse uniform As/local/D reference is not qualified for the complete simultaneous field.',
                stress_upper_MPa=float(total.hi),ceiling_MPa=ceiling,normative_rejection_inferred=False))
        if not curling['qualified']:
            out['blocking_reasons'].append(dict(code='PURE_COMPONENT_CURLING_NOT_QUALIFIED',
                detail='Own pure-component curling guards are not all qualified.',
                axes=[axis for axis,row in curling['axes'].items() if not row['qualified']],
                normative_rejection_inferred=False))
        out.update(status='arithmetic_simultaneous_ceiling_audited',construction_qualified=ready,
            source_authenticated=False,
            pure_My_construction=my,pure_Mx_construction=mx,operator_intervals=operators,
            operator_reference_transport=origin_transport,
            moment_upper_Nmm={k:_outward(v,1) for k,v in moments.items()},
            required_signed_branches=required,unit_bending_stress_upper_per_Nmm=unit_bounds,
            B_upper_Nmm2=_outward(b,1),B_bernstein_piece_bounds=bernstein_rows,
            gross_omega_absolute_upper_mm2=omega_max,gross_Cw_mm6=cw,
            absolute_stress_contributions_upper_MPa={k:float(v.hi) for k,v in contributions.items()},
            simultaneous_normal_stress_upper_MPa=float(total.hi),
            integral_local_D_design_ceiling_MPa=ceiling,
            simultaneous_field_below_ceiling=sufficient,
            simultaneous_uniform_reference=uniform_reference,curling_components=curling,
            arithmetic_proof='Triangle bound: sup|sigma_total|<=sum sup|M_axis|*sup|unit_effective_operator_axis| + sup|B|*max|omega|/Cw. Rational Bernstein bounds cover original source pieces, signs and support states; both physical faces are enclosed. No favourable cancellation.',
            activation_contract='Construction alone cannot activate a consumer. It additionally requires authenticated own normal/contour/omega/Cw, original dense-field replay and exact reaction equilibrium, with a new schema; old results are not requalified.')
    except (ValueError,KeyError,TypeError,ZeroDivisionError,OverflowError) as error:
        out.update(status='pending_method_domain',blocking_reasons=[dict(
            code='CONCURRENT_SHEAR_LAG_REFERENCE_NOT_QUALIFIED',detail=str(error),normative_rejection_inferred=False)])
    out['content_sha256']=_sha(out)
    return out
