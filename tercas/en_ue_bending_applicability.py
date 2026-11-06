"""Arithmetic applicability guards for the actual isolated bending diagram.

EN1993-1-5:2006 3.1(1),3.2.1(2): shear lag may be ignored only when
b0 < Le/50. Le is a physical moment-zero zone, never a mesh element or an
arbitrary split at P. EN1993-1-3:2006 5.4: conservative panel curling bounds.
No legacy seven-profile proof, NBR length criterion, solver or section builder.
"""
from fractions import Fraction as F
import math
from .torsion_vlasov.intervals import Interval as I
from .en_signed_partial_interaction import _outward

SCHEMA='EN_Ue_actual_bending_applicability_v1'
SOURCE='EN1993-1-5:2006 3.1(1),3.2.1(2); EN1993-1-3:2006 5.4,6.1.4.1(4),6.1.4.3'


def _centroid_interval(dims,ri):
    # Rational enclosure of sin(pi/128) by alternating Taylor sums. This is
    # the exact nominal 32-chord formula, not a geometry/normal-section build.
    pi_lo=F('3.14159265358979323846264338327950288419716939937510582097494459230781640628620899862803')
    pi_hi=pi_lo+F(1,10**80)
    def sine(x,n):return sum(((-1)**k*x**(2*k+1)/math.factorial(2*k+1) for k in range(n+1)),F(0))
    sin_lo=sine(pi_lo/128,13);sin_hi=sine(pi_hi/128,12)
    r=F(ri)+F(dims['t'])/2
    slo,shi=64*r*sin_lo,64*r*sin_hi
    s=I(_outward(slo,-1),_outward(shi,1));h,b,c,t=(I(dims[k]) for k in ('h','bf','lip','t'))
    H=h-t;w=b-t;e=c-t/2;radius=I(ri)+t/2
    return w*(w+2*e-4*radius+2*s)/(H+2*w+2*e-8*radius+4*s)


def _zones(summary,axis):
    L=F(summary['length_mm'])
    q=sum((F(x['q_xy_N_mm'][axis]) for x in summary['loads'] if x['kind']=='uniform'),F(0))
    points={}
    for load in summary['loads']:
        if load['kind']=='point':points[F(load['s_mm'])]=points.get(F(load['s_mm']),F(0))+F(load['force_xy_N'][axis])
    points={x:p for x,p in points.items() if p!=0 and 0<x<L}
    if len(points)>1:return dict(active=True,qualified=False,reason='Guarda implementada para q uniforme e até uma posição P por eixo.',zones=[])
    if not q and not points:return dict(active=False,qualified=True,reason='Momento físico deste eixo identicamente zero por equilíbrio exato.',zones=[])
    zeros={F(0),L}
    if q and points:
        a,P=next(iter(points.items()))
        left=L+2*P*(L-a)/(q*L);right=-2*P*a/(q*L)
        if 0<left<=a:zeros.add(left)
        if a<=right<L:zeros.add(right)
    ordered=sorted(zeros)
    return dict(active=True,qualified=None,reason=None,zones=[(a,b) for a,b in zip(ordered,ordered[1:])])


def _ratio(stress,bs,z,t,depth):
    if float(z.lo)<=0:return None
    upper=2*stress.square()*I(bs).square().square()/(I(210000.).square()*I(t).square()*z)
    return dict(stress_upper_MPa=float(stress.hi),width_upper_mm=bs,z_lower_mm=float(z.lo),
        curling_upper_mm=float(upper.hi),depth_mm=depth,ratio_upper=float((upper/(I(.05)*depth)).hi))


def assess(summary,normal_source_binding):
    n=normal_source_binding;dims=n['nominal_identity']['dimensions_mm']
    h,b,c,t=(dims[k] for k in ('h','bf','lip','t'));ri=n['nominal_identity']['inner_radius_mm']
    if summary['section']['nodes_sha256']!=n['nodes_sha256']:raise ValueError('Guarda flexional usa outro contorno.')
    xg=_centroid_interval(dims,ri)
    saved_xg=summary['section']['properties']['centroid_xy_mm'][0]
    if type(saved_xg) not in (int,float) or not math.isfinite(saved_xg) or not math.isclose(saved_xg,float(xg.lo),rel_tol=2e-12,abs_tol=1e-9):
        raise ValueError('Centróide salvo diverge da identidade nominal facetada de 32 cordas.')
    H=I(h)-t;w=I(b)-t;r=I(ri)+I(t)/2;delta=r*(I(1.)-I(1.)/I(2.).sqrt())
    zg=H/2-delta;zw=xg-delta;zl=w-xg-delta
    da=xg+I(t)/2;db=w-xg+I(t)/2
    D=I(max(float(da.lo),float(db.lo)),max(float(da.hi),float(db.hi)))
    panels=dict(strong=_ratio(I(250.),b,zg,t,h),
        weak_web=_ratio(I(250.)*xg/D,h/2,zw,t,b),
        weak_lip=_ratio(I(250.)*(w-xg)/D,c,zl,t,b))
    rows={};reasons=[]
    for name,axis,b0,panel_names in [('Mx',1,F(b)-F(t)/2,('strong',)),
                                    ('My',0,max((F(h)-F(t))/2,F(c)-F(t)/2),('weak_web','weak_lip'))]:
        row=_zones(summary,axis);zones=row.pop('zones');required=row['active']
        zone_rows=[dict(a_mm=_outward(a,-1),b_mm=_outward(z,1),Le_lower_mm=_outward(z-a,-1),
            threshold_upper_mm=_outward(50*b0,1),qualified=_outward(z-a,-1)>_outward(50*b0,1)) for a,z in zones]
        lag=not required or bool(zone_rows) and all(z['qualified'] for z in zone_rows)
        curl=not required or all(panels[k] is not None and panels[k]['ratio_upper']<1 for k in panel_names)
        reason=row['reason'] if not required else '; '.join(([row['reason']] if row['reason'] else [])+
            ([] if lag else ['shear lag: Le deve exceder estritamente 50·b0 em toda zona entre zeros'])+
            ([] if curl else ['curling: teto de deslocamento do painel não inferior a 5% da altura associada']))
        rows[name]=dict(active=required,b0_upper_mm=_outward(b0,1),zero_zones=zone_rows,
            shear_lag_qualified=lag,curling_qualified=curl,qualified=lag and curl,reason=reason)
        if required and not (lag and curl):reasons.append(name+': '+reason)
    return dict(schema=SCHEMA,source=SOURCE,nodes_sha256=n['nodes_sha256'],
        nominal_identity_sha256=n['nominal_identity_sha256'],centroid_x_interval_mm=[float(xg.lo),float(xg.hi)],axes=rows,curling_panels=panels,
        scope='Curling applicability of pure bending resistance components; not combined N/M/B flange displacement.',
        curling_model='Initially straight prismatic nominal member; no credit for transverse stiffeners; gross-panel stress and minimum-z upper bounds at fy.',
        shear_lag_method='Exact rational q/P zeros; strict Le>50b0; no subdivision at P without moment reversal.',
        qualified=all(r['qualified'] for r in rows.values()),reason='; '.join(reasons) if reasons else 'Shear lag e curling dispensados por guardas explícitas nos eixos ativos.',
        physical_geometry_verified=False,whole_member_approved=False)
