"""Unintegrated reference: pure-My shear lag with integral subyield local/D.

A new candidate, not an extension/replay of saved v1/v2/v3 authorities.  It does
not read any previously accepted signed-component certificate.  Retained areas
are unknown nonnegative measures on the nominal contour, paired by horizontal
reflection.  Straight web/lip x moments depend only on lost area; ALL corner
area may be lost.  No beta*t geometry or corner loss placement is fabricated.

The sufficient stress ceiling is recomputed at the new centroid enclosure.
Only when the actual pure-My demand is below that ceiling may Ac,eff be gross.
An overrun means noncoverage, never a physical failure.  No member solver.
"""
from __future__ import annotations
import copy
import hashlib
import math
from fractions import Fraction as F
from pathlib import Path

from .en_ue_catalog_operators import _sha
from .en_ue_family_applicability import _zones, _ratio
from .en_ue_family_shear_lag import _beta_lower, _decimal, _pair, PRIMARY_SOURCE
from .en_signed_partial_interaction import _outward
from .torsion_vlasov.intervals import Interval as I

SCHEMA = 'EN_Ue_pure_My_shear_lag_subyield_candidate_v1'
REVISION = 'unknown_corner_loss_integral_local_D_ceiling_20261107_v1'
SOURCE = ('EN1993-1-5:2006 3.3 Note2 Eq3.3/3.4, Table3.1, 4.3(1),(2),(4),(5), '
          '4.4(4)/Eq4.4; EN1993-1-3:2006 5.4,5.5.3.2/Eq5.10b,5.12,5.15,5.17,6.1.6(3),(5)')
STRAIGHT_IDS = (0, 33, 66, 99, 132)
ARC_IDS = tuple(i for i in range(133) if i not in STRAIGHT_IDS)


def _constant(s):
    return _decimal(s)


def _source_binding():
    root = Path(__file__).parent
    names = ('en_ue_my_shear_lag_candidate.py', 'en_ue_family_shear_lag.py',
             'en_ue_family_applicability.py', 'en_ue_catalog_operators.py',
             'en_signed_partial_interaction.py', 'isolated_en_ue_catalog_application.py',
             'torsion_vlasov/intervals.py')
    return _sha({name: hashlib.sha256((root/name).read_bytes()).hexdigest() for name in names})


def _chi_lower(lambda_upper):
    """Infimum of every EN13 Eq5.12 branch below the supplied upper bound.

    Rounded branch transitions at .65 and 1.38 must not be treated as globally
    monotone.  In particular the left limit at 1.38 is below its right value.
    """
    lam = F(lambda_upper)
    if lam <= 0:
        raise ValueError('Positive lambda_d upper bound required')
    values = [1.]
    if lam > F('.65'):
        end = min(lam, F('1.38'))
        values.append(float((_constant('1.47')-_constant('.723')*_decimal(end)).lo))
    if lam >= F('1.38'):
        values.append(float((_constant('.66')/_decimal(lam)).lo))
    lower = min(values)
    if not 0 < lower <= 1:
        raise ValueError('Nonpositive distortional strength lower bound')
    return lower


def _segments(n):
    nodes = n['nodes_xy_mm']; t = I(n['thickness_mm'])
    if len(nodes) != 134 or n['nominal_identity']['arc_segments'] != 32:
        raise ValueError('Only the declared 32-chord Ue topology is implemented')
    if not n['geometry_guard']['satisfied']:
        raise ValueError('Own EN geometrical-proportion guard is not satisfied')
    if not n['geometry_guard']['mirror_max_error_mm'] <= 1e-10:
        raise ValueError('Nominal horizontal reflection guard failed')
    d = n['nominal_identity']['dimensions_mm']; w = float(d['bf']-n['thickness_mm'])
    for i in (0, 132):
        if nodes[i][0] != w or nodes[i+1][0] != w:
            raise ValueError('Lip straight segment is not at constant x=w')
    if nodes[66][0] != 0. or nodes[67][0] != 0.:
        raise ValueError('Web straight segment is not at constant x=0')
    if any(nodes[i][1] != nodes[i+1][1] for i in (33, 99)):
        raise ValueError('Flange straight segment is not horizontal')
    output = []
    for i, (a, b) in enumerate(zip(nodes, nodes[1:])):
        x0,y0,x1,y1 = map(I, (*a,*b))
        length = ((x1-x0).square()+(y1-y0).square()).sqrt()
        output.append(dict(id=i, a=a, b=b, length=length, area=t*length))
    return output


def _area(rows, ids):
    result = I(0.)
    for i in ids:
        result = result+rows[i]['area']
    return result


def _beta_groups(demand, n, rows):
    zone = _zones(demand, 0)
    if not zone['active'] or not zone['zones']:
        raise ValueError('Active My with supported physical moment-zero zones required')
    dims = n['nominal_identity']['dimensions_mm']; t = n['thickness_mm']
    # The full adjacent arcs are counted, not just the usual half-arc partition.
    # These are upper areas for any notional web/lip panel on this contour.
    specs = (
        ('web', (F(dims['h'])-F(t))/2, _area(rows, range(34,99))/I(2)),
        ('lower_lip', F(dims['lip'])-F(t)/2, _area(rows, range(0,33))),
        ('upper_lip', F(dims['lip'])-F(t)/2, _area(rows, range(100,133))),
    )
    output = {}
    for name, b0, area in specs:
        records = []
        for a,b in zone['zones']:
            le = b-a
            kappa = (area*_decimal(b0)/I(t)).sqrt()/_decimal(le)
            records.append(dict(start_exact=[a.numerator,a.denominator],
                end_exact=[b.numerator,b.denominator],Le_exact=[le.numerator,le.denominator],
                b0_upper_mm=_outward(b0,1),gross_half_panel_area_upper_mm2=float(area.hi),
                **_beta_lower(float(kappa.hi))))
        output[name] = dict(beta_lower=min(z['beta_lower'] for z in records), zones=records,
            gross_area_upper_mm2=float(area.hi),
            Ac_eff_basis='Gross only conditional on the new integral local/D stress ceiling; no prior effective-area input',
            longitudinal_interior_stiffeners=0)
    return output


def _moments(n, rows, beta):
    """Outward moment bounds on the actual binary64 contour.

    Nominal paired losses are contained in a larger independent-loss superset.
    The latter also encloses coordinate roundoff without assuming exact Ixy=0.
    No physical corner loss position or common biaxial tensor is reconstructed.
    """
    xg,yg = n['gross_properties']['centroid_xy_mm']
    A0,Sx0,Sy0,Qx0,Qy0,Qxy0 = (I(0.) for _ in range(6))
    for row in rows:
        ux,vx = (I(row[k][0])-I(xg) for k in ('a','b'))
        uy,vy = (I(row[k][1])-I(yg) for k in ('a','b'))
        area = row['area']
        A0 = A0+area
        Sx0 = Sx0+area*(ux+vx)/I(2.); Sy0 = Sy0+area*(uy+vy)/I(2.)
        Qx0 = Qx0+area*(ux.square()+ux*vx+vx.square())/I(3.)
        Qy0 = Qy0+area*(uy.square()+uy*vy+vy.square())/I(3.)
        Qxy0 = Qxy0+area*(I(2.)*ux*uy+ux*vy+vx*uy+I(2.)*vx*vy)/I(6.)
    losses = []
    for name, ids, multiplicity in (('web',(66,),2),('lower_lip',(0,),1),('upper_lip',(132,),1)):
        b = beta[name]
        cap = I(multiplicity)*(I(1.)-I(b['beta_lower']))*I(b['gross_area_upper_mm2'])
        cap = min(float(cap.hi),float(_area(rows,ids).hi))
        row = rows[ids[0]]; x = row['a'][0]
        losses.append(dict(name=name,ids=list(ids),area_loss_upper_mm2=cap,
            x_interval_mm=[x,x],y_interval_mm=sorted([row['a'][1],row['b'][1]]),corner=False))
    for i in ARC_IDS:
        row = rows[i]
        losses.append(dict(name='corner_'+str(i),ids=[i],
            area_loss_upper_mm2=float(row['area'].hi),
            x_interval_mm=sorted([row['a'][0],row['b'][0]]),
            y_interval_mm=sorted([row['a'][1],row['b'][1]]),corner=True))
    D,Sxl,Syl,Jxl,Jyl,Jxyl = (I(0.) for _ in range(6))
    for row in losses:
        cap = I(row['area_loss_upper_mm2']); mass = I(0.,float(cap.hi))
        qx = I(*row['x_interval_mm'])-I(xg); qy = I(*row['y_interval_mm'])-I(yg)
        D = D+cap; Sxl = Sxl+mass*qx; Syl = Syl+mass*qy
        Jxl = Jxl+cap*qx.square(); Jyl = Jyl+cap*qy.square(); Jxyl = Jxyl+mass*qx*qy
    amin = float((A0-D).lo)
    if amin<=0.:
        raise ValueError('Nonpositive retained-area lower bound')
    retained_A = I(amin,float(A0.hi)); Sx = Sx0-Sxl; Sy = Sy0-Syl
    shiftx,shifty = Sx/retained_A,Sy/retained_A
    iy_lower = float((Qx0-I(float(Jxl.hi))-Sx.square()/retained_A).lo)
    ix_lower = float((Qy0-I(float(Jyl.hi))-Sy.square()/retained_A).lo)
    if min(ix_lower,iy_lower)<=0.:
        raise ValueError('Nonpositive retained-inertia lower bound')
    cross = Qxy0-Jxyl-Sx*Sy/retained_A
    cross_max = float(cross.abs().hi)
    schur = float((I(iy_lower)-I(cross_max).square()/I(ix_lower)).lo)
    if schur<=0.:
        raise ValueError('Nonpositive Schur-complement inertia lower bound')
    t = I(n['thickness_mm']); radii = []
    for axis,cg in ((0,xg),(1,yg)):
        lo,hi = min(p[axis] for p in n['nodes_xy_mm']),max(p[axis] for p in n['nodes_xy_mm'])
        radii.append(max(float((I(cg)-I(lo)+t/I(2)).hi),float((I(hi)-I(cg)+t/I(2)).hi)))
    xarm = I(radii[0])+shiftx.abs(); yarm = I(radii[1])+shifty.abs()
    cross_ratio = I(cross_max)/I(ix_lower)
    na_excursion = cross_ratio*yarm
    maximum_arm = float((xarm+na_excursion).hi)
    inverse = I(1.)/I(schur,float(Qx0.hi))
    cx = -inverse
    cy = cross/(I(ix_lower,float(Qy0.hi))*I(schur,float(Qx0.hi)))
    c0 = shiftx*inverse-shifty*cy
    coefficients = [[min(0.,float(v.lo)),max(0.,float(v.hi))] for v in (c0,cx,cy)]
    return dict(A_gross_interval_mm2=_pair(A0),Sx_about_reference_interval_mm3=_pair(Sx0),
        Sy_about_reference_interval_mm3=_pair(Sy0),Qx_about_reference_interval_mm4=_pair(Qx0),
        Qy_about_reference_interval_mm4=_pair(Qy0),Qxy_about_reference_interval_mm4=_pair(Qxy0),
        area_loss_upper_mm2=float(D.hi),A_retained_lower_mm2=amin,
        centroid_shift_x_interval_mm=_pair(shiftx),centroid_shift_y_interval_mm=_pair(shifty),
        centroid_x_interval_mm=_pair(I(xg)+shiftx),centroid_y_interval_mm=_pair(I(yg)+shifty),
        Iy_lower_mm4=iy_lower,Ix_lower_mm4=ix_lower,Ixy_interval_mm4=_pair(cross),
        Ixy_absolute_upper_mm4=cross_max,My_schur_inertia_lower_mm4=schur,
        physical_reference_radii_upper_mm=radii,maximum_fibre_arm_upper_mm=maximum_arm,
        neutral_axis_x_excursion_upper_mm=float(na_excursion.hi),
        operator_intervals_c0_cx_cy=coefficients,loss_groups=losses,
        corner_rule='All 128 arc facets may lose their whole area; no beta*t or retained arc band is asserted',
        symmetry_rule='Physical nominal losses are paired under horizontal reflection. Bounds deliberately include the wider independent-loss set on the actual binary64 contour, so no exact Cy or Ixy=0 is assumed from a tolerance.',
        nominal_mirror_error_mm=n['geometry_guard']['mirror_max_error_mm'],
        proof='A=A0-d; Sx=Sx0-Sxl; Sy=Sy0-Syl; Iy=Qx0-Jxl-Sx^2/A; Ix=Qy0-Jyl-Sy^2/A; Ixy=Qxy0-Jxyl-Sx*Sy/A. My denominator Iy-Ixy^2/Ix has a positive lower bound.')


def _stress_ceiling(n, rows):
    """No accepted old local/D data are read; all bounds are reconstructed."""
    m = n['material']; t = I(n['thickness_mm']); E = I(m['E_MPa']); nu = I(m['nu'])
    fy,gamma = I(m['fyb_MPa']),I(m['gamma_M0'])
    pi = _constant('3.14159265358979323846264338327950288419716939937510582097494459230781640628620899')
    elastic = pi.square()*E/(I(12.)*(I(1.)-nu.square()))
    internal_limit = _constant('.5')+_constant('.03').sqrt()
    outstand_limit = _constant('.748')
    local = []; initial_lips = []
    for j,g in enumerate(n['panels']):
        # Free-outstand flanges are deliberately used for BOTH signs, including
        # the tensile-lip My sign. No lip restraint is needed for this local cap.
        k,limit = (I(4.),internal_limit) if j==2 else ((_constant('.43'),outstand_limit) if j in (1,3) else (_constant('.5'),outstand_limit))
        critical = k*elastic*(t/I(g['b_mm'])).square()
        if j in (0,4):
            initial_lambda = (fy/critical).sqrt()
            if float(initial_lambda.hi)>float(limit.lo):
                raise ValueError('Initial fyb-uniform lip is not proved integral; full-lip Is bound unavailable')
            initial_lips.append(dict(panel=g['panel'],k_sigma_lower=float(k.lo),
                sigma_cr_lower_MPa=float(critical.lo),lambda_at_fyb_upper=float(initial_lambda.hi),
                lambda_integral_limit_lower=float(limit.lo),rho_initial_proved=1.,
                source='Fresh EN13 5.5.3.2 steps1-2/Eq5.13 uniform-fyb majorant; not a saved certificate'))
        cap = critical*limit.square()/gamma
        local.append(dict(panel=g['panel'],k_sigma_lower=float(k.lo),
            sigma_cr_lower_MPa=float(critical.lo),lambda_integral_limit_lower=float(limit.lo),
            allowable_design_compression_lower_MPa=float(cap.lo),
            model='Uniform compression majorant; EN15 Table4.1 web, Table4.2 free-outstand flange, EN13 Eq5.13 lip lower k=.5; Eq4.4'))
    width = I(max(p[0] for p in n['nodes_xy_mm']))
    H = I(max(p[1] for p in n['nodes_xy_mm']))-I(min(p[1] for p in n['nodes_xy_mm']))
    lip_length = I(min(float(rows[i]['length'].lo) for i in (0,132)))
    Is_min = t*lip_length*lip_length*lip_length/I(12.)
    As_max = I(max(float(_area(rows,n['panels'][lip]['ids']+n['panels'][flange]['ids']).hi)
                  for lip,flange in ((0,1),(4,3))))
    As_min = t*lip_length
    kr_max = As_max/As_min
    denominator = width.square()*H+width*width*width+I(.5)*width.square()*H*kr_max
    K_min = E*t*t*t/(I(4.)*(I(1.)-nu.square())*denominator)
    critical = I(2.)*(K_min*E*Is_min).sqrt()/As_max
    lam_upper = float((fy/critical).sqrt().hi)
    chi = _chi_lower(lam_upper)
    d_cap = I(chi)*fy/gamma
    # Strict arithmetic margin, not a material factor or an experimental fit.
    safe = min([float(d_cap.lo),float((fy/gamma).lo)]+
               [row['allowable_design_compression_lower_MPa'] for row in local])
    cap = float((I(safe)*_constant('.999999999999')).lo)
    if not cap > 0.:
        raise ValueError('Nonpositive integral local/distortional stress ceiling')
    for row in local:
        lam = (I(cap)*gamma/I(row['sigma_cr_lower_MPa'])).sqrt()
        row['lambda_reduced_upper_at_ceiling'] = float(lam.hi)
        row['integral_proved'] = float(lam.hi)<=row['lambda_integral_limit_lower']
        if not row['integral_proved']:
            raise ValueError('Directed local integral recheck failed')
    if float((I(cap)*gamma).hi)>float((I(chi)*fy).lo):
        raise ValueError('Directed Eq5.17 integral As recheck failed')
    return dict(design_compression_ceiling_MPa=cap,local_panels=local,
        initial_fyb_lip_integral_certificates=initial_lips,
        gamma_M0=m['gamma_M0'],fyb_MPa=m['fyb_MPa'],
        uniform_compression_is_pointwise_majorant=True,
        distortion=dict(As_upper_mm2=float(As_max.hi),Is_lower_mm4=float(Is_min.lo),
            b1_b2_upper_mm=float(width.hi),hw_upper_mm=float(H.hi),kr_upper=float(kr_max.hi),As_lower_mm2=float(As_min.lo),
            K_lower_N_mm2=float(K_min.lo),sigma_cr_lower_MPa=float(critical.lo),
            lambda_d_upper=lam_upper,chi_d_lower=chi,
            allowable_design_compression_lower_MPa=float(d_cap.lo),
            As_red_over_As_proved=1.,
            proof='Each initial fyb lip is independently proved integral; every admissible initial/refined As therefore contains its full straight lip, hence Is>=t*l_lip^3/12 by the parallel-axis identity; As<=full lip+flange area; 0<b1,b2<=w; As_opposite/As<=As_max/(t*l_lip_min), without assuming binary64 equality of mirrored areas; a tensile opposite gives kr=0. These bound Eq5.10b/5.15. Actual average compression<=ceiling<=chi_lower*fy/gamma, so Eq5.17 permits full As.',
            shear_lag_area_not_used_as_physical_stiffener_stiffness=True),
        no_old_local_or_distortional_certificate_copied=True,
        basis='Design stress at the supplied pure-My moment, not yield-normalized resistance and not a member-buckling effective area',
        Ac_eff_fixed_point='For every centroid in the new enclosure, all physical compression<=ceiling. Uniform local majorants and the full As bounds prove local/D integral. Therefore Ac,eff=gross used in beta is self-consistent without iteration.')


def _demand_bound(demand):
    from . import isolated_en_ue_catalog_application as arithmetic
    from . import en_signed_partial_interaction as core
    bound = F(0); mx_active = False
    pieces = arithmetic._source_pieces(demand)
    if not pieces:
        raise ValueError('Source equilibrium pieces required')
    for p in pieces:
        fields = arithmetic._fields(demand,p)
        if any(fields['N']):
            raise ValueError('This pure-component supplement requires N=0')
        mx_active |= any(fields['Mx'])
        for pair in core._bernstein([(v,v) for v in fields['My']]):
            bound = max(bound,*(abs(v) for v in pair))
    b_active = False
    elements = demand.get('elements')
    if not isinstance(elements,list) or not elements:
        raise ValueError('Explicit element B polynomials required to prove pure My')
    for element in elements:
        values = element.get('coefficients',{}).get('B_Nmm2')
        if (not isinstance(values,list) or not 1<=len(values)<=4
                or any(type(v) not in (int,float) or not math.isfinite(v) for v in values)):
            raise ValueError('Every source element requires an explicit finite B polynomial; missing B is not zero')
        b_active |= any(values)
    states = demand.get('support_limit_states',[])
    declared_limit = any(load.get('existing_point_position')=='support_limit' for load in demand['loads'])
    declared_limit |= demand.get('analysis_domain',{}).get('point_position_scope','').startswith('Prescribed a->0+')
    if not isinstance(states,list) or (declared_limit and not states):
        raise ValueError('Declared support-limit source requires explicit states and finite B')
    for state in states:
        value = state.get('B_Nmm2')
        if type(value) not in (int,float) or not math.isfinite(value):
            raise ValueError('Every source support-limit state requires explicit finite B; missing B is not zero')
        b_active |= value!=0.
    return bound,not(mx_active or b_active),dict(Mx=bool(mx_active),B=bool(b_active))


def build(demand,n):
    """Build a candidate only. No consumers or old schemas are modified."""
    out = dict(schema=SCHEMA,method_revision=REVISION,source=SOURCE,
        primary_source=copy.deepcopy(PRIMARY_SOURCE),technical_source_sha256=_source_binding(),
        normal_source_sha256=n['content_sha256'],source_demand_sha256=_sha(demand),
        eligible=False,consumer_integrated=False,whole_member_approved=False,
        exact_effective_tensor_claimed=False,physical_exceedance_witness_permitted=False,
        old_signed_components_requalified=False,blocking_reasons=[])
    try:
        if n['method_revision']=='explicit_material_integral_and_reduced_web_20261106_v1':
            raise ValueError('Historical R10 normal authority is not extended')
        rows = _segments(n)
        beta = _beta_groups(demand,n,rows)
        geometry = _moments(n,rows,beta)
        lip_ids = n['panels'][0]['ids']+n['panels'][4]['ids']
        lip_xmin = min(n['nodes_xy_mm'][j][0] for i in lip_ids for j in (i,i+1))
        lip_arm = I(lip_xmin)-I(n['thickness_mm'])/I(2.)-I(geometry['centroid_x_interval_mm'][1])-I(geometry['neutral_axis_x_excursion_upper_mm'])
        if float(lip_arm.lo)<=0.:
            raise ValueError('Entire physical lips not proved on one side of every admissible pure-My neutral axis')
        geometry['whole_lip_same_pure_My_stress_sign_arm_lower_mm'] = float(lip_arm.lo)
        ceiling = _stress_ceiling(n,rows)
        safe = ceiling['design_compression_ceiling_MPa']
        capacity = I(safe)*I(geometry['My_schur_inertia_lower_mm4'])/I(geometry['maximum_fibre_arm_upper_mm'])
        floor = math.floor(float(capacity.lo))
        if floor<=0:
            raise ValueError('No positive integer My capacity floor')
        demand_bound,pure_only,companions = _demand_bound(demand)
        actual_stress = _decimal(demand_bound)*I(geometry['maximum_fibre_arm_upper_mm'])/I(geometry['My_schur_inertia_lower_mm4'])
        adequate = demand_bound<=floor
        dims = n['nominal_identity']['dimensions_mm']; t = n['thickness_mm']
        w = I(dims['bf'])-I(t); r = I(n['nominal_identity']['inner_radius_mm'])+I(t)/I(2.)
        delta = r*(I(1.)-I(1.)/I(2.).sqrt())
        center = I(*geometry['centroid_x_interval_mm'])
        # Mean stress on gross area is bounded by its pointwise peak because
        # retained-area weights are nonnegative and at most one (EN13 5.4(2)).
        excursion = I(geometry['neutral_axis_x_excursion_upper_mm'])
        curling = dict(weak_web=_ratio(actual_stress,dims['h']/2,center-delta-excursion,t,dims['bf']),
                       weak_lip=_ratio(actual_stress,dims['lip'],w-center-delta-excursion,t,dims['bf']))
        qualified_curling = all(v is not None and v['ratio_upper']<1. for v in curling.values())
        out.update(eligible=adequate and pure_only,
            status=('sufficient_pure_My_subyield_shear_lag_envelope' if pure_only else 'pending_simultaneous_action_guard') if adequate else 'pending_demand_above_integral_ceiling',
            pure_component_capacity_qualified=True,simultaneous_normal_actions_absent=pure_only,
            concomitant_normal_actions=companions,simultaneous_action_local_D_qualified=False,
            beta_groups=beta,geometry_audit=geometry,local_distortional_audit=ceiling,
            moment_capacity_floor_Nmm=floor,signed_capacity_floor={k:floor for k in ('My_positive','My_negative')},
            operator_intervals={k:copy.deepcopy(geometry['operator_intervals_c0_cx_cy']) for k in ('My_positive','My_negative')},
            pure_My_demand_upper_exact=[demand_bound.numerator,demand_bound.denominator],
            pure_My_demand_upper_Nmm=_outward(demand_bound,1),
            actual_compression_upper_MPa=float(actual_stress.hi),
            pure_demand_within_integral_ceiling=adequate,curling_panels=curling,
            curling_qualified=qualified_curling,applicability_qualified=adequate and pure_only and qualified_curling,
            applicability_requirement='Never activate solely because a field is below fy. This subyield local/D proof requires the source-derived absolute pure-My bound <= its own moment floor AND absence of Mx/B. A concomitant state requires a new guard on all simultaneous normal actions under EN15 Eq4.4.',
            capacity_proof='floor(s_ceiling*My_Schur_lower/maximum_equivalent_fibre_arm_upper), recomputed from own nominal geometry; no scaling of a stored capacity',
            stress_scope='Pure-My effective normal-section coefficient intervals only; B/V/Tsv/Tw remain on the unchanged gross source; no shared biaxial effective tensor',
            numerical_scope='Outward area/moment/strength arithmetic on supplied binary64 contour and material; full centroid and coupling enclosures; no exact symmetry inferred from tolerance, not measured physical geometry or FE error')
        if not pure_only:
            out['blocking_reasons'].append(dict(code='SIMULTANEOUS_NORMAL_ACTIONS_NOT_QUALIFIED_AT_SUBYIELD_CEILING',actions=companions,normative_rejection_inferred=False))
        if not adequate:
            out['blocking_reasons'].append(dict(code='MY_DEMAND_ABOVE_SUFFICIENT_INTEGRAL_CEILING',normative_rejection_inferred=False))
    except (ValueError,KeyError,TypeError,ZeroDivisionError,OverflowError) as error:
        out.update(status='pending_method_domain',blocking_reasons=[dict(
            code='MY_SHEAR_LAG_CANDIDATE_DOMAIN_NOT_QUALIFIED',detail=str(error),normative_rejection_inferred=False)])
    out['content_sha256'] = _sha(out)
    return out
