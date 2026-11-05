"""EN 1993-1-3 6.1.6(4),(5), concomitant faceted thin-wall stress bounds.

N/M use the caller's eligible effective-section coefficients; B, V, Tw and Tsv
use the same gross section. Each wall face has sigma affine and tau quadratic
in its contour coordinate u. Bernstein convex-hull bounds enclose every u.
Exact hyperbolic derivative partitions bound each Bernstein control function
throughout the longitudinal interval. Bounding sigma and tau independently is
used ONLY for an explicitly labelled upper bound, never as a physical witness.
Subdivision is needed only where the inequalities cannot yet be decided.
"""
from __future__ import annotations
import heapq
import math
import numpy as np
from . import field_envelope as f
from ..torsion_vlasov.section import verify_section

SCHEMA='EN_6_1_6_concomitant_shear_interaction_bounds_v1'


def _pad(values):
    out=np.zeros(3);out[:len(values)]=values
    return out


def _bernstein(c,lo,hi):
    """Power coefficients in global u -> quadratic Bernstein on [lo,hi]."""
    d=hi-lo
    p=c[0]+lo*c[1]+lo*lo*c[2]
    q=d*(c[1]+2*lo*c[2]);r=d*d*c[2]
    return np.asarray([p,p+q/2,p+q+r])


def section_fields(section,polynomials,coefficients,torsion,total_torque,L_mm):
    """Signed sigma/tau fields for every face, without independent action maxima.

    With tangent a->b and normal n=(-dy,dx)/length, positive St Venant
    torsion gives tau_tangent=-2 G phi' zeta. Therefore the +n face has
    -Tsv*t/J. The old midsurface diagnostic's interchangeable +/- label
    cannot be reused when exterior normal stresses differ between faces.
    """
    verify_section(section)
    if not math.isfinite(L_mm) or L_mm<=0:raise ValueError('Positive beam length required')
    p=section['properties'];th=section['thickness_mm'];J=p['J_mm4'];Cw=p['Cw_mm6']
    xy=np.asarray(section['nodes_xy_mm'])-p['centroid_xy_mm']
    omega=np.asarray(section['omega_nodes_mm2'])/Cw
    # Physical R01 identities Mx'=Vy and My'=-Vx, derivatives in x.
    vx=-np.polynomial.polynomial.polyder(polynomials['My'])/L_mm
    vy=np.polynomial.polynomial.polyder(polynomials['Mx'])/L_mm
    vx=_pad(vx);vy=_pad(vy);torque=_pad(total_torque)
    h=torsion['h']
    tw=dict(h=h,B0=torsion['V']/L_mm,U=h*h*torsion['V']/L_mm,V=torsion['U']/L_mm)
    rows=[]
    for i,(a,b) in enumerate(zip(xy[:-1],xy[1:])):
        d=b-a;normal=np.array([-d[1],d[0]])/np.linalg.norm(d)
        static=np.asarray(section['segment_static_coefficients'][i])
        for face in (-1,1):
            sigma=np.zeros((3,3));sigma_scale=0.;w=np.array([omega[i],omega[i+1]-omega[i],0.])
            for key,action in polynomials.items():
                if not any(action):continue
                c=np.asarray(coefficients[key])
                section_power=np.array([c[0]+c[1:]@(a+face*th/2*normal),c[1:]@d,0.])
                sigma+=section_power[:,None]*_pad(action)[None,:]
                sigma_scale+=float(sum(abs(section_power))*sum(abs(v) for v in action))
            tau=-(static[0,:,None]*vx[None,:]/p['Iy_weak_mm4']+
                  static[1,:,None]*vy[None,:]/p['Ix_strong_mm4'])/th
            tau_scale=float(np.sum(abs(static[0]))*sum(abs(vx))/p['Iy_weak_mm4']/th+
                np.sum(abs(static[1]))*sum(abs(vy))/p['Ix_strong_mm4']/th+th/J*sum(abs(torque)))
            tau[0]-=face*th/J*torque
            v=-static[2]/(Cw*th);v=v.copy();v[0]+=face*th/J
            rows.append(dict(segment_index=i,face=face,sigma=sigma,omega=w,
                tau=tau,tw_weight=v,normal_xy=normal.tolist(),
                sigma_roundoff_scale=sigma_scale,tau_roundoff_scale=tau_scale,
                tw_roundoff_scale=float(np.sum(abs(static[2]))/(Cw*th)+th/J),
                xy_start=a+face*th/2*normal,xy_delta=d))
    return rows,tw


def _evaluate(row,torsion,tw,x,u):
    xp=np.array([1.,x,x*x]);up=np.array([1.,u,u*u])
    sigma=float(up@row['sigma']@xp+(up@row['omega'])*f.bimoment(torsion,x))
    tau=float(up@row['tau']@xp+(up@row['tw_weight'])*f.bimoment(tw,x))
    return sigma,tau


def envelope(section,polynomials,coefficients,torsion,total_torque,L_mm,*,left=0.,right=1.,
             normal_limit_MPa=250.,max_refinements=2048,index_tolerance=1e-5):
    """Complete section/span bounds, refining only undecided inequalities.

    A within-limit verdict requires the upper bound <=1. An above-limit
    verdict requires an actual same-station/fiber witness >1. Budget or
    tolerance exhaustion is explicitly inconclusive, never a silent pass.
    This numerical budget is not a structural/code applicability condition.
    """
    if not 0<=left<right<=1:raise ValueError('Nonempty normalized interval required')
    if not math.isfinite(normal_limit_MPa) or normal_limit_MPa<=0:raise ValueError('Positive normal limit required')
    rows,tw=section_fields(section,polynomials,coefficients,torsion,total_torque,L_mm)
    limits={'shear':normal_limit_MPa/math.sqrt(3),'interaction':1.1*normal_limit_MPa}
    heaps={key:[] for key in limits};active={};counter=0
    best={key:None for key in limits}

    def roundoff_pad(p,w,field,polynomial_scale,weight_scale):
        h=field['h']
        c=.5 if h==0 else 2*(math.sinh(h/2)/h)**2
        d=1. if h==0 else math.sinh(h)/h
        scale=max(sum(abs(v) for v in p),polynomial_scale)+max(abs(w),weight_scale)*(abs(field['B0'])+abs(field['U'])*c+abs(field['V'])*d)
        return 128*np.finfo(float).eps*max(1.,scale)

    def add(row,x0,x1,u0,u1,depth):
        nonlocal counter
        sb=_bernstein(row['sigma'],u0,u1);wb=_bernstein(row['omega'],u0,u1)
        tb=_bernstein(row['tau'],u0,u1);vb=_bernstein(row['tw_weight'],u0,u1)
        upper={key:0. for key in limits};xs={x0,x1,(x0+x1)/2}
        for sp,ww,tp,vv in zip(sb,wb,tb,vb):
            se=f.stress_extrema(sp.tolist(),float(ww),torsion,x0,x1)
            te=f.stress_extrema(tp.tolist(),float(vv),tw,x0,x1)
            s=abs(se['maximum_absolute']['sigma_MPa'])+roundoff_pad(sp,ww,torsion,row['sigma_roundoff_scale'],sum(abs(row['omega'])))
            t=abs(te['maximum_absolute']['sigma_MPa'])+roundoff_pad(tp,vv,tw,row['tau_roundoff_scale'],row['tw_roundoff_scale'])
            upper['shear']=max(upper['shear'],t/limits['shear'])
            upper['interaction']=max(upper['interaction'],math.hypot(s,math.sqrt(3)*t)/limits['interaction'])
            xs.update((se['minimum']['t'],se['maximum']['t'],te['minimum']['t'],te['maximum']['t']))
        # Only actual points provide lower witnesses, including all initial
        # facet endpoints plus interior and analytic longitudinal candidates.
        for x in xs:
            for u in (u0,(u0+u1)/2,u1):
                sigma,tau=_evaluate(row,torsion,tw,x,u)
                for key,index in (('shear',abs(tau)/limits['shear']),
                                  ('interaction',math.hypot(sigma,math.sqrt(3)*tau)/limits['interaction'])):
                    if best[key] is None or index>best[key]['index']:
                        best[key]=dict(index=index,t=x,u=u,segment_index=row['segment_index'],
                            thickness_face_sign=row['face'],normal_xy=row['normal_xy'],
                            xy_relative_to_gross_CG_mm=(row['xy_start']+u*row['xy_delta']).tolist(),
                            sigma_MPa=sigma,tau_MPa=tau,
                            equivalent_MPa=math.hypot(sigma,math.sqrt(3)*tau))
        # Outward pad covers binary64 arithmetic, NOT model/physical error.
        upper={k:math.nextafter(v+64*np.finfo(float).eps*max(1.,v),math.inf) for k,v in upper.items()}
        counter+=1;active[counter]=(row,x0,x1,u0,u1,depth)
        for key in limits:heapq.heappush(heaps[key],(-upper[key],counter))

    def bounds():
        result={}
        for key in limits:
            while heaps[key][0][1] not in active:heapq.heappop(heaps[key])
            result[key]=-heaps[key][0][0]
        return result

    for row in rows:add(row,left,right,0.,1.,0)
    refined=0
    while True:
        upper=bounds()
        undecided=[k for k in limits if best[k]['index']<=1.<upper[k]]
        if not undecided or refined>=max_refinements:break
        if all(upper[k]-best[k]['index']<=index_tolerance for k in undecided):break
        key=max(undecided,key=lambda k:upper[k]-best[k]['index'])
        _,cell_id=heaps[key][0];row,x0,x1,u0,u1,depth=active.pop(cell_id)
        # Alternate x/u; every unresolved rectangle shrinks in both directions.
        if depth%2==0:
            mid=(x0+x1)/2
            if mid in (x0,x1):active[cell_id]=(row,x0,x1,u0,u1,depth);break
            add(row,x0,mid,u0,u1,depth+1);add(row,mid,x1,u0,u1,depth+1)
        else:
            mid=(u0+u1)/2
            if mid in (u0,u1):active[cell_id]=(row,x0,x1,u0,u1,depth);break
            add(row,x0,x1,u0,mid,depth+1);add(row,x0,x1,mid,u1,depth+1)
        refined+=1
    upper=bounds()
    result=dict(schema=SCHEMA,full_interval_covered=True,section_facets=len(rows)//2,
        faces_per_facet=2,refinements=refined,normal_limit_MPa=normal_limit_MPa,
        shear_limit_MPa=limits['shear'],equivalent_limit_MPa=limits['interaction'],
        upper_bound_method='Quadratic Bernstein convex hull across each wall face, analytical hyperbolic extrema per longitudinal interval; magnitude-scaled binary64 pad, not formal interval arithmetic',
        physical_witness_method='Concomitant sigma and tau at the same station, facet coordinate and face',
        model='Faceted thin-wall gross shear flow plus signed linear-through-thickness Saint Venant shear; not a curved-solid solution')
    for key in limits:
        low=best[key]['index'];hi=max(low,upper[key])
        result[key]=dict(witness=best[key],index_lower_witness=low,index_upper_bound=hi,
            bound_gap=hi-low,criterion='above_1_at_concomitant_state' if low>1 else
                'within_1_by_full_interval_upper_bound' if hi<=1 else 'unresolved_numerical_bound',
            bound_is_not_a_concomitant_state=True)
    return result


def aggregate(records,complete):
    """Aggregate interval bounds without turning a partial result into a pass."""
    records=[r for r in records if r is not None]
    out=dict(complete=bool(complete and records),checked_intervals=len(records))
    for key in ('shear','interaction'):
        if not records:
            out[key]=None
            continue
        w=max((r[key]['witness'] for r in records),key=lambda v:v['index'])
        hi=max(r[key]['index_upper_bound'] for r in records)
        out[key]=dict(witness=w,index_lower_witness=w['index'],
            index_upper_bound=hi if complete else None,
            partial_index_upper_bound=None if complete else hi,
            criterion=('above_1_at_concomitant_state' if w['index']>1 else
                       'within_1_by_full_interval_upper_bound' if hi<=1 else
                       'unresolved_numerical_bound') if complete else
                      ('above_1_at_checked_state_full_envelope_incomplete' if w['index']>1 else
                       'incomplete_section_branch_coverage'))
    return out
