"""Sufficient shear-lag bounds for a symmetric pure strong-bending component.

EN1993-1-5:2006 3.3 Note2, Eq3.3/3.4 and Table3.1. No arbitrary spatial
placement of the combined effective area: lost second moment is bounded by
lost area times the squared outer fibre distance. This is NOT a reconstructed
effective tensor or an exact physical stress distribution. A concomitant My
uses its own unmodified effective section only when independently applicable.
"""
from __future__ import annotations
from fractions import Fraction as F
from pathlib import Path
import copy
import hashlib
import math
from .en_ue_catalog_operators import _sha, _assembly
from .en_ue_family_kernel import _Kernel, material
from .en_ue_family_applicability import _zones, assess
from .en_signed_partial_interaction import _outward
from .torsion_vlasov.intervals import Interval as I

SCHEMA='EN_Ue_pure_Mx_shear_lag_inertia_envelope_v1'
REVISION='symmetric_integral_area_loss_bound_independent_My_20261107_v2'
PRIMARY_SOURCE=dict(url='https://people.fsv.cvut.cz/machacek/PomuckyE/Plated%20structural%20elements%20%281993-1-5%29.pdf',
    sha256='1f1c2639f1d03520ccf2ef3d438f6c8cf0a02875ab0fece2ff4410882e0fa7a6',
    standard='EN1993-1-5:2006 (E)',printed_pages='10-13',bytes=448378)
SOURCE='EN1993-1-5:2006 3.1,3.2.1,Table3.1,3.3 Note2 Eq3.3/3.4; EN1993-1-3:2006 5.5/6.1.4.1'


def _companion_axis(demand,n):
    """Qualify the actual My source, never a caller-provided applicability flag.

    EN13 6.1.6(3),(5) uses the respective pure effective cross sections. This
    does not extend the Mx area-loss construction to My or to a common tensor.
    The enclosing engine authenticates n; both My operators remain unchanged.
    """
    from . import isolated_en_ue_catalog_application as arithmetic
    fields=[arithmetic._fields(demand,p) for p in arithmetic._source_pieces(demand)]
    if any(any(row['N']) for row in fields):
        raise ValueError('Pure-Mx shear-lag component requires N=0')
    if not any(any(row['My']) for row in fields):return None
    if any(not n['components'][key]['eligible'] for key in ('My_positive','My_negative')):
        raise ValueError('Concomitant My requires eligible unchanged signed My operators')
    row=assess(demand,n)['axes'].get('My',{})
    if not (row.get('active') is True and row.get('shear_lag_qualified') is True
            and row.get('curling_qualified') is True and row.get('qualified') is True):
        raise ValueError('Pure-Mx supplement requires independent My shear-lag dispensation and curling qualification; otherwise demand N=My=0 is required')
    return dict(axis='My',source='EN1993-1-3:2006 6.1.4.1(4),(7),6.1.6(3),(5)',
        applicability=copy.deepcopy(row),applicability_sha256=_sha(row),
        normal_source_sha256=n['content_sha256'],
        unchanged_operator_sha256={key:_sha(n['components'][key]) for key in ('My_positive','My_negative')},
        shared_effective_tensor_claimed=False,
        interpretation='Independent pure-My effective sections with source-derived shear-lag dispensation and curling qualification; no My supplement or capacity override')


def source_binding():
    root=Path(__file__).parent
    return _sha({name:hashlib.sha256((root/name).read_bytes()).hexdigest() for name in (
        'en_ue_family_shear_lag.py','en_ue_family_applicability.py',
        'isolated_en_ue_family.py','en_ue_family_field_controls.py')})


def _pair(v):return [float(v.lo),float(v.hi)]

def _decimal(value):
    q=F(value)
    return I(_outward(q,-1),_outward(q,1))


def _beta_lower(kappa_upper):
    """Lower bound for every Table3.1 location curve, not a sign-name rule."""
    k=I(kappa_upper)
    if F(kappa_upper)<=F('.02'):return dict(beta_lower=1.,kappa_upper=kappa_upper,curves={'integral':1.})
    if F(kappa_upper)<=F('.7'):
        b1=I(1)/(I(1)+_decimal('6.4')*k.square())
        b2=I(1)/(I(1)+I(6)*(k-I(1)/(I(2500)*k))+_decimal('1.6')*k.square())
    else:
        b1=I(1)/(_decimal('5.9')*k);b2=I(1)/(_decimal('8.6')*k)
    b0=(_decimal('.55')+_decimal('.025')/k)*b1
    lower=min(1.,float(b1.lo),float(b2.lo),float(b0.lo))
    # The rounded Table3.1 formulae are not continuous at kappa=.7.
    # Kappa_actual may lie anywhere below its conservative upper bound.
    # Preserve the left-limit minimum rather than assuming global monotonicity.
    boundary=None
    if F(kappa_upper)>F('.7'):
        q=_decimal('.7')
        left1=I(1)/(I(1)+_decimal('6.4')*q.square())
        left2=I(1)/(I(1)+I(6)*(q-I(1)/(I(2500)*q))+_decimal('1.6')*q.square())
        left0=(_decimal('.55')+_decimal('.025')/q)*left1
        boundary=min(float(v.lo) for v in (left1,left2,left0))
        lower=min(lower,boundary)
    if not 0<lower<=1:raise ValueError('Invalid Table3.1 lower bound')
    return dict(beta_lower=lower,kappa_upper=kappa_upper,
        kappa_point_seven_left_limit_lower=boundary,
        curves={'span_beta1_lower':float(b1.lo),'support_beta2_lower':float(b2.lo),
                'end_beta0_lower':min(float(b0.lo),float(b1.lo))},
        interpretation='Minimum of span, support and end-support curves; reflection of load sign does not select a different curve')


def _inertia_and_area(n):
    nodes=n['nodes_xy_mm'];t=I(n['thickness_mm']);d=n['nominal_identity']['dimensions_mm']
    center=(I(d['h'])-t)/I(2);ix=I(0);areas=[I(0),I(0)];selected=[[],[]]
    for i,(a,b) in enumerate(zip(nodes,nodes[1:])):
        x0,y0=I(a[0]),I(a[1]);x1,y1=I(b[0]),I(b[1])
        length=((x1-x0).square()+(y1-y0).square()).sqrt();area=t*length
        u,v=y0-center,y1-center
        ix=ix+area*(u.square()+u*v+v.square())/I(3)
        # Only the straight mid-plane web is excluded. Every lip, flange and
        # rounded junction is in the possible-loss superset, including corners
        # which a finer idealization might assign partly to the web.
        if a[0]==0. and b[0]==0.:continue
        side=0 if (a[1]+b[1])/2<float(center.lo) else 1
        areas[side]=areas[side]+area;selected[side].append(i)
    amax=max(float(v.hi) for v in areas)
    return ix,I(amax),center,dict(Ix_gross_interval_mm4=_pair(ix),
        flange_area_intervals_mm2=[_pair(v) for v in areas],
        flange_area_upper_mm2=amax,possible_loss_segments=selected,
        possible_loss_scope='Each flange, lip and all rounded junctions; only the straight web at x=0 is excluded. Upper area per side is used twice.',
        area_loss_localization='Unknown mirrored subsets; no fabricated centroid_x, Ixy or retained-band placement')


def _local_distortional_audit(n,ymax):
    kernel=_Kernel(material(n['material']['fyb_MPa'],n['material']['gamma_M0']))
    nodes=n['nodes_xy_mm'];t=n['thickness_mm'];groups=n['panels'];fy=n['normal_yield_limit_MPa']
    center=(n['nominal_identity']['dimensions_mm']['h']-t)/2
    output={}
    for sign,label in ((1,'Mx_positive'),(-1,'Mx_negative')):
        comp=[sign*fy*center/ymax,0.,-sign*fy/ymax]
        # Uniform fy is a majorant of the entire compressed flange/lip. The
        # mirrored straight web retains its antisymmetric pure bending field.
        from .en_ue_catalog_operators import _ends, _domain
        local={j:kernel._internal_certificate(groups[j],t,_ends(groups[j],comp)) for j in (1,2,3)}
        for lip,flange in ((0,1),(4,3)):
            local[lip]=kernel._lip_certificate(groups[lip],groups[flange],t,_ends(groups[lip],comp))
        if any(row['rho']!=1. for row in local.values()):
            raise ValueError('Pure-Mx shear-lag envelope requires independently integral local panels')
        lip,flange=(0,1) if sign==1 else (4,3)
        other=(4,3) if sign==1 else (0,1)
        opposite=_domain(nodes,t,[[i,0.,1.] for j in other for i in groups[j]['ids']],comp)
        if opposite['max_line_or_face_compression_MPa']>=0:
            raise ValueError('Opposite flange is not tensile under the pure-Mx majorant')
        st=_assembly(nodes,t,groups[lip],groups[flange],local[flange],comp)
        kernel._distortion(st,None,t,n['nominal_identity']['dimensions_mm']['h']-t)
        # Integrate the majorant average on the physical original local As.
        A=I(0);S=I(0)
        for i,lo,hi in st['line_intervals']:
            a,b=nodes[i:i+2];dx,dy=I(b[0])-I(a[0]),I(b[1])-I(a[1])
            area=I(t)*(dx.square()+dy.square()).sqrt()*(I(hi)-I(lo))
            ya=I(a[1])+I(lo)*dy;yb=I(a[1])+I(hi)*dy
            mean_y=(ya+yb)/I(2)
            stress=I(sign)*I(fy)*(I(center)-mean_y)/I(ymax)
            A=A+area;S=S+area*stress
        sigma=S/A;strength=I(st['chi_d'])*I(fy)
        if not float(sigma.hi)<=float(strength.lo):
            raise ValueError('Eq5.17 integral As not proved under the pure-Mx stress majorant')
        output[label]=dict(local_panels=[local[j] for j in range(5)],
            stiffener=dict(As_mm2=st['As_mm2'],Is_mm4=st['Is_mm4'],K_N_mm2=st['K_N_mm2'],
                chi_d=st['chi_d'],sigma_As_upper_MPa=float(sigma.hi),
                chi_d_fyb_lower_MPa=float(strength.lo),As_red_over_As_proved=1.,
                line_intervals=st['line_intervals']),
            proof='Every actual retained/redistributed nonnegative flange stress is bounded by fy*abs(y-y0)/ymax; its physical As average is below chi_d*fy. No distortion reduction is waived by a status label.')
    return output


def build(demand,n,applicability):
    base=dict(schema=SCHEMA,method_revision=REVISION,source=SOURCE,primary_source=copy.deepcopy(PRIMARY_SOURCE),
        technical_source_sha256=source_binding(),normal_source_sha256=n['content_sha256'],
        source_demand_sha256=_sha(demand),eligible=False,blocking_reasons=[],
        exact_effective_tensor_claimed=False,exact_physical_stress_distribution_claimed=False,
        physical_exceedance_witness_permitted=False,whole_member_approved=False)
    if applicability['axes'].get('Mx',{}).get('shear_lag_qualified',False):
        base['status']='not_required';base['content_sha256']=_sha(base);return base
    try:
        if n['method_revision']=='explicit_material_integral_and_reduced_web_20261106_v1':
            raise ValueError('Historical R10 source is not extended or requalified')
        companion=_companion_axis(demand,n)
        for name in ('Mx_positive','Mx_negative'):
            c=n['components'][name]
            if not c['eligible'] or c['effective_properties']!=n['gross_properties']:
                raise ValueError('Shear-lag inertia envelope requires integral pure-Mx source in both signs')
        if not n['geometry_guard']['mirror_max_error_mm']<=1e-10:
            raise ValueError('Horizontal mirror geometry not demonstrated')
        zone_info=_zones(demand,1)
        if not zone_info['active'] or not zone_info['zones']:
            raise ValueError('No supported physical moment-zero zones')
        d=n['nominal_identity']['dimensions_mm'];t=n['thickness_mm'];b0=F(d['bf'])-F(t)/2
        ix,area,center,geometry=_inertia_and_area(n)
        zone_rows=[]
        for a,b in zone_info['zones']:
            Le=b-a
            # Eq3.4: kappa = sqrt(Ac,eff*b0/t)/Le. Both area and b0 are
            # upper bounds, so kappa is bounded upwards and beta downwards.
            kappa=(area*I(_outward(b0,1))/I(t)).sqrt()/I(_outward(Le,-1))
            beta=_beta_lower(float(kappa.hi))
            zone_rows.append(dict(start_exact=[a.numerator,a.denominator],end_exact=[b.numerator,b.denominator],
                Le_exact=[Le.numerator,Le.denominator],Le_mm=float(Le),Le_lower_mm=_outward(Le,-1),b0_upper_mm=_outward(b0,1),**beta))
        beta=min(z['beta_lower'] for z in zone_rows)
        ymax=float(d['h'])/2
        loss=I(2)*(I(1)-I(beta))*area*I(ymax).square()
        lower=float((ix-loss).lo)
        if not lower>0:raise ValueError('Area-loss inertia lower bound is nonpositive; no resistance inferred')
        capacity=(I(n['normal_yield_limit_MPa'])*I(lower)/I(ymax))
        floor=math.floor(float(capacity.lo))
        if floor<=0:raise ValueError('No positive integer moment capacity lower bound')
        audit=_local_distortional_audit(n,ymax)
        inverse=I(1)/I(lower);cy=I(0,float(inverse.hi))
        shift=I(n['gross_properties']['centroid_xy_mm'][1])-center
        c0=shift*cy
        coeff=[_pair(c0),[0.,0.],_pair(cy)]
        base.update(eligible=True,status='sufficient_pure_Mx_area_loss_envelope',
            physical_zero_zones=zone_rows,beta_global_lower=beta,geometry_audit=geometry,
            Ix_lower_mm4=lower,Ix_loss_upper_mm4=float(loss.hi),outer_fibre_distance_mm=ymax,
            moment_capacity_floor_Nmm=floor,
            signed_capacity_floor={name:floor for name in ('Mx_positive','Mx_negative')},
            operator_intervals={name:copy.deepcopy(coeff) for name in ('Mx_positive','Mx_negative')},
            local_distortional_audit=audit,
            symmetry_statement='Paired mirrored area losses: centroid_y=(h-t)/2 and Ixy=0. Centroid_x is deliberately unspecified. Source geometric symmetry is numerical, not a physical-product certificate.',
            inertia_proof='For each of two mirrored flanges, integral_removed(y^2 dA) <= (1-beta_lower)*A_flange_upper*ymax^2. No location of the retained area is assumed.',
            stress_envelope='Signed Mx times coefficient interval [0,1/Ix_lower] times y about the symmetry axis. The zero end covers unknown shear-lag redistribution and prevents favourable cancellation with the unchanged B field.',
            capacity_proof='Integer floor of fy/gammaM0 * Ix_lower / ymax; derived from the area-loss inertia inequality, not beta times a stored capacity.',
            numerical_scope='Outward intervals of supplied binary64 nominal contour/material and rational load-zero lengths; no eigenmode, FE-error or physical-geometry certificate')
        if companion is not None:base['independent_My_companion']=companion
    except (ValueError,KeyError,TypeError,ZeroDivisionError) as error:
        base.update(status='pending_method_domain',blocking_reasons=[dict(code='SHEAR_LAG_ENVELOPE_DOMAIN_NOT_QUALIFIED',detail=str(error),normative_rejection_inferred=False)])
    base['content_sha256']=_sha(base)
    return base


def apply_applicability(original,proof):
    if not proof.get('eligible'):return original
    out=copy.deepcopy(original);row=out['axes']['Mx']
    row.update(shear_lag_dispensation_qualified=row['shear_lag_qualified'],shear_lag_qualified=True,
        shear_lag_explicit_method=SCHEMA,qualified=row['curling_qualified'],
        reason='' if row['curling_qualified'] else row['reason'])
    out['qualified']=all(r['qualified'] for r in out['axes'].values())
    out['shear_lag_method']='Physical moment-zero zones and explicit pure-Mx symmetric area-loss envelope; original strict dispensation remains recorded.'
    out['reason']='Shear lag considerado por envoltória suficiente de inércia e tensões; curling mantém suas guardas.' if out['qualified'] else original['reason']
    out['shear_lag_supplement_sha256']=proof['content_sha256']
    return out
