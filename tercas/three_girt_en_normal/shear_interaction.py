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
import copy
import math
import numpy as np
from . import field_envelope as f
from ..torsion_vlasov.section import verify_section

SCHEMA='EN_6_1_6_concomitant_normal_shear_interaction_bounds_v2'


def _pad(values):
    out=np.zeros(3);out[:len(values)]=values
    return out


def _bernstein(c,lo,hi):
    """Power coefficients in global u -> quadratic Bernstein on [lo,hi]."""
    d=hi-lo
    p=c[0]+lo*c[1]+lo*lo*c[2]
    q=d*(c[1]+2*lo*c[2]);r=d*d*c[2]
    return np.asarray([p,p+q/2,p+q+r])


def section_field_builder(section):
    """Own and validate one immutable section for a calculation-local builder.

    Geometry-only operations retain their original ordering. Each call returns
    fresh mutable field arrays; callers cannot modify the captured geometry.
    No trust is cached by an object's identity or by a declared source hash.
    """
    section=copy.deepcopy(section);verify_section(section)
    p=section['properties'];th=section['thickness_mm'];J=p['J_mm4'];Cw=p['Cw_mm6']
    xy=np.asarray(section['nodes_xy_mm'])-p['centroid_xy_mm']
    omega=np.asarray(section['omega_nodes_mm2'])/Cw
    geometry=[]
    for i,(a,b) in enumerate(zip(xy[:-1],xy[1:])):
        d=b-a;normal=np.array([-d[1],d[0]])/np.linalg.norm(d)
        static=np.asarray(section['segment_static_coefficients'][i])
        for face in (-1,1):
            w=np.array([omega[i],omega[i+1]-omega[i],0.])
            pos=a+face*th/2*normal
            v=-static[2]/(Cw*th);v=v.copy();v[0]+=face*th/J
            geometry.append((i,face,d,normal,static,w,pos,v,
                float(np.sum(abs(static[2]))/(Cw*th)+th/J)))
    def build(polynomials,coefficients,torsion,total_torque,L_mm):
        if not math.isfinite(L_mm) or L_mm<=0:raise ValueError('Positive beam length required')
        # Physical R01 identities Mx'=Vy and My'=-Vx, derivatives in x.
        vx=-np.polynomial.polynomial.polyder(polynomials['My'])/L_mm
        vy=np.polynomial.polynomial.polyder(polynomials['Mx'])/L_mm
        vx=_pad(vx);vy=_pad(vy);torque=_pad(total_torque)
        h=torsion['h']
        tw=dict(h=h,B0=torsion['V']/L_mm,U=h*h*torsion['V']/L_mm,V=torsion['U']/L_mm)
        rows=[]
        for i,face,d,normal,static,w,pos,v,tw_scale in geometry:
            sigma=np.zeros((3,3));sigma_scale=0.
            for key,action in polynomials.items():
                if not any(action):continue
                c=np.asarray(coefficients[key])
                section_power=np.array([c[0]+c[1:]@pos,c[1:]@d,0.])
                sigma+=section_power[:,None]*_pad(action)[None,:]
                section_scale=abs(c[0])+sum(abs(c[1:]*pos))+sum(abs(c[1:]*d))
                sigma_scale+=float(section_scale*sum(abs(v) for v in action))
            tau=-(static[0,:,None]*vx[None,:]/p['Iy_weak_mm4']+
                  static[1,:,None]*vy[None,:]/p['Ix_strong_mm4'])/th
            tau_scale=float(np.sum(abs(static[0]))*sum(abs(vx))/p['Iy_weak_mm4']/th+
                np.sum(abs(static[1]))*sum(abs(vy))/p['Ix_strong_mm4']/th+th/J*sum(abs(torque)))
            tau[0]-=face*th/J*torque
            rows.append(dict(segment_index=i,face=face,sigma=sigma,omega=w.copy(),
                tau=tau,tw_weight=v.copy(),normal_xy=normal.tolist(),
                sigma_roundoff_scale=sigma_scale,tau_roundoff_scale=tau_scale,
                tw_roundoff_scale=tw_scale,xy_start=pos.copy(),xy_delta=d.copy()))
        return rows,tw
    return build


def section_fields(section,polynomials,coefficients,torsion,total_torque,L_mm):
    """Signed full-face fields, retaining the stateless validated public path.

    Saint Venant signs, exterior coordinates, arithmetic and outputs are
    unchanged. Calculation-local callers may reuse section_field_builder.
    """
    return section_field_builder(section)(polynomials,coefficients,torsion,total_torque,L_mm)


def _evaluate(row,torsion,tw,x,u):
    xp=np.array([1.,x,x*x]);up=np.array([1.,u,u*u])
    sigma=float(up@row['sigma']@xp+(up@row['omega'])*f.bimoment(torsion,x))
    tau=float(up@row['tau']@xp+(up@row['tw_weight'])*f.bimoment(tw,x))
    return sigma,tau


def _tiny_interval_magnitude(polynomial,weight,field,left,right):
    """Center value + global [0,1] derivative bound; caller adds roundoff pad.

    No root isolation is needed for sub-ulp sign brackets. This remains a
    binary64 numerical enclosure, not formal directed interval arithmetic.
    """
    mid=(left+right)/2
    radius=max(mid-left,right-mid)
    h=field['h']
    ds=1. if h==0 else math.sinh(h)/h
    dc=1. if h==0 else math.cosh(h)
    derivative=abs(polynomial[1])+2*abs(polynomial[2])+abs(weight)*(abs(field['U'])*ds+abs(field['V'])*dc)
    return abs(f.sigma_value(polynomial,float(weight),field,mid))+radius*derivative


def envelope(section,polynomials,coefficients,torsion,total_torque,L_mm,*,left=0.,right=1.,
             normal_limit_MPa=250.,max_refinements=2048,index_tolerance=1e-5,witness_evaluator=None,bounds_only_tiny=False,prepared_fields=None,certify_bounds=False):
    """Complete section/span bounds, refining only undecided inequalities.

    A within-limit verdict requires the upper bound <=1. An above-limit
    verdict requires an actual same-station/fiber witness >1. Budget or
    tolerance exhaustion is explicitly inconclusive, never a silent pass.
    This numerical budget is not a structural/code applicability condition.

    witness_evaluator receives a same-location face point before selection
    and returns its physical signed-section stresses plus optional absolute
    witness_error_MPa (scalar, or sigma/tau mapping). Returning None rejects
    that point as evidence. Its errors cannot reduce this engine's scaled
    binary64 guard. The guard is numerical, not formal interval arithmetic.
    A callback point from a different section can explicitly enlarge the
    local upper bound; the caller must still union every required branch.
    """
    if not 0<=left<right<=1:raise ValueError('Nonempty normalized interval required')
    if not math.isfinite(L_mm) or L_mm<=0:raise ValueError('Positive beam length required')
    if isinstance(max_refinements,bool) or not isinstance(max_refinements,int) or max_refinements<0:
        raise ValueError('Nonnegative integer refinement budget required')
    if not math.isfinite(index_tolerance) or index_tolerance<0:raise ValueError('Finite nonnegative numerical tolerance required')
    numerical=list(total_torque)+list(torsion.values())
    numerical.extend(v for values in polynomials.values() for v in values)
    numerical.extend(v for values in coefficients.values() for v in values)
    if not all(math.isfinite(v) for v in numerical):raise ValueError('Finite stress field coefficients required')
    if not math.isfinite(normal_limit_MPa) or normal_limit_MPa<=0:raise ValueError('Positive normal limit required')
    rows,tw=prepared_fields if prepared_fields is not None else section_fields(section,polynomials,coefficients,torsion,total_torque,L_mm)
    limits={'normal':normal_limit_MPa,'shear':normal_limit_MPa/math.sqrt(3),'interaction':1.1*normal_limit_MPa}
    heaps={key:[] for key in limits};active={};counter=0;leaf_paths={}
    best={key:None for key in limits}
    witnessed_upper={key:0. for key in limits}
    discarded_witnesses=0

    def lower(key):
        return 0. if best[key] is None else best[key]['index_lower_witness']

    def roundoff_padding(field):
        # These field-only factors are identical for every rectangle/fiber.
        # Hoist their original operations, without changing association or eps.
        h=field['h']
        c=.5 if h==0 else 2*(math.sinh(h/2)/h)**2
        d=1. if h==0 else math.sinh(h)/h
        magnitude=abs(field['B0'])+abs(field['U'])*c+abs(field['V'])*d
        eps128=128*np.finfo(float).eps
        def pad(p,w,polynomial_scale,weight_scale):
            scale=max(sum(abs(v) for v in p),polynomial_scale)+max(abs(w),weight_scale)*magnitude
            return eps128*max(1.,scale)
        return pad
    sigma_pad=roundoff_padding(torsion);tau_pad=roundoff_padding(tw)

    def certify(result,paths):
        if not certify_bounds:return result
        from . import bound_certificate as bc
        proof=dict(schema=bc.SCHEMA,faces=[dict(segment_index=r['segment_index'],face=r['face'],
            paths=sorted(paths.get((r['segment_index'],r['face']),['']))) for r in rows])
        upper=bc.verify(proof,rows,tw,torsion,left,right,normal_limit_MPa)
        result['bound_certificate']=proof
        for key in limits:
            record=result[key];hi=max(record['index_upper_bound'],upper[key]);low=record['index_lower_witness']
            record.update(index_upper_bound=hi,bound_gap=None if low is None else hi-low,
                criterion='above_1_at_concomitant_state' if low is not None and low>1 else
                    'within_1_by_full_interval_upper_bound' if hi<=1 else 'unresolved_numerical_bound')
        return result

    if bounds_only_tiny and right-left<=32*math.ulp(1.):
        # Vectorized full-face Bernstein controls. No fabricated lower state:
        # this branch deliberately carries only a complete numerical upper.
        mid=(left+right)/2;radius=max(mid-left,right-mid)
        def all_upper(polynomial_key,weight_key,field,scale_key,weight_scales):
            raw=np.asarray([r[polynomial_key] for r in rows])
            weights=np.asarray([r[weight_key] for r in rows])
            controls=np.stack((raw[:,0],raw[:,0]+raw[:,1]/2,raw[:,0]+raw[:,1]+raw[:,2]),axis=1)
            wc=np.stack((weights[:,0],weights[:,0]+weights[:,1]/2,weights[:,0]+weights[:,1]+weights[:,2]),axis=1)
            scale=np.asarray([r[scale_key] for r in rows])[:,None]
            ws=np.asarray(weight_scales)[:,None]
            h=field['h'];ds=1. if h==0 else math.sinh(h)/h
            dc=1. if h==0 else math.cosh(h)
            c=.5 if h==0 else 2*(math.sinh(h/2)/h)**2
            if not all(np.all(np.isfinite(a)) for a in (controls,wc,scale,ws)):
                raise ValueError('Finite prepared field bounds required')
            center=np.sum(controls*np.array([1.,mid,mid*mid]),axis=2)+wc*f.bimoment(field,mid)
            derivative=abs(controls[:,:,1])+2*abs(controls[:,:,2])+abs(wc)*(abs(field['U'])*ds+abs(field['V'])*dc)
            magnitude=np.maximum(np.sum(abs(controls),axis=2),scale)+np.maximum(abs(wc),ws)*(abs(field['B0'])+abs(field['U'])*c+abs(field['V'])*ds)
            pad=128*np.finfo(float).eps*np.maximum(1.,magnitude)
            answer=abs(center)+radius*derivative+pad
            if not np.all(np.isfinite(answer)):raise ArithmeticError('Nonfinite vectorized upper bound')
            return answer
        su=all_upper('sigma','omega',torsion,'sigma_roundoff_scale',[sum(abs(r['omega'])) for r in rows])
        tu=all_upper('tau','tw_weight',tw,'tau_roundoff_scale',[r['tw_roundoff_scale'] for r in rows])
        upper=dict(normal=float(np.max(su))/limits['normal'],shear=float(np.max(tu))/limits['shear'],
            interaction=float(np.max(np.hypot(su,math.sqrt(3)*tu)))/limits['interaction'])
        result=dict(schema=SCHEMA,full_interval_covered=True,section_facets=len(rows)//2,faces_per_facet=2,
            refinements=0,normal_limit_MPa=normal_limit_MPa,shear_limit_MPa=limits['shear'],
            equivalent_limit_MPa=limits['interaction'],discarded_witness_count=0,bounds_only_tiny=True,
            upper_bound_method='Quadratic Bernstein full-face controls; tiny-interval center plus global derivative bound; magnitude-scaled binary64 padding, not formal interval arithmetic',
            physical_witness_method='No physical witness proposed in bounds-only tiny interval',
            model='Faceted thin-wall gross shear flow plus signed linear-through-thickness Saint Venant shear; not a curved-solid solution')
        for key,value in upper.items():
            hi=math.nextafter(value+64*np.finfo(float).eps*max(1.,value),math.inf)
            if not math.isfinite(hi) or hi<0:raise ArithmeticError('Nonfinite vectorized upper index')
            result[key]=dict(witness=None,index_lower_witness=None,index_upper_bound=hi,
                partial_index_upper_bound=None,bound_gap=None,physical_witness_upper_adjustment=0.,
                criterion='within_1_by_full_interval_upper_bound' if hi<=1 else 'unresolved_numerical_bound',
                bound_is_not_a_concomitant_state=True)
        return certify(result,{})

    extrema_cache={}
    def cached_extrema(polynomial,weight,field,left,right):
        # Exact argument memoization only: no rounding, approximation or
        # coordinate quantization. Results are read-only in this module.
        key=(tuple(polynomial),float(weight),tuple(field[k] for k in ('h','B0','U','V')),left,right)
        if key not in extrema_cache:
            extrema_cache[key]=f.stress_extrema(list(polynomial),float(weight),field,left,right)
        return extrema_cache[key]

    def add(row,x0,x1,u0,u1,depth,path=""):
        nonlocal counter,discarded_witnesses
        sb=_bernstein(row['sigma'],u0,u1);wb=_bernstein(row['omega'],u0,u1)
        omega_scale=sum(abs(row['omega']))
        tb=_bernstein(row['tau'],u0,u1);vb=_bernstein(row['tw_weight'],u0,u1)
        upper={key:0. for key in limits};xs={x0,x1,(x0+x1)/2}
        for sp,ww,tp,vv in zip(sb,wb,tb,vb):
            if x1-x0<=32*math.ulp(1.):
                s=_tiny_interval_magnitude(sp,ww,torsion,x0,x1)
                t=_tiny_interval_magnitude(tp,vv,tw,x0,x1)
            else:
                se=cached_extrema(sp.tolist(),float(ww),torsion,x0,x1)
                te=cached_extrema(tp.tolist(),float(vv),tw,x0,x1)
                s=abs(se['maximum_absolute']['sigma_MPa'])
                t=abs(te['maximum_absolute']['sigma_MPa'])
                xs.update((se['minimum']['t'],se['maximum']['t'],te['minimum']['t'],te['maximum']['t']))
            s+=sigma_pad(sp,ww,row['sigma_roundoff_scale'],omega_scale)
            t+=tau_pad(tp,vv,row['tau_roundoff_scale'],row['tw_roundoff_scale'])
            if not all(math.isfinite(v) for v in (s,t)):raise ArithmeticError('Nonfinite stress bound')
            upper['normal']=max(upper['normal'],s/limits['normal'])
            upper['shear']=max(upper['shear'],t/limits['shear'])
            upper['interaction']=max(upper['interaction'],math.hypot(s,math.sqrt(3)*t)/limits['interaction'])
        # Only actual points provide lower witnesses, including all initial
        # facet endpoints plus interior and analytic longitudinal candidates.
        # These full-face scales dominate every u in [0,1], so the witness
        # arithmetic guard is computed once per rectangle, not per candidate.
        default_error=dict(
            sigma=sigma_pad(np.sum(abs(row['sigma']),axis=0),0.,
                row['sigma_roundoff_scale'],omega_scale),
            tau=tau_pad(np.sum(abs(row['tau']),axis=0),0.,
                row['tau_roundoff_scale'],row['tw_roundoff_scale']))
        # Same left-associated products as _evaluate, cached only where their
        # arguments repeat. No candidate, root or operation order is changed.
        section_values=[]
        for u in (u0,(u0+u1)/2,u1):
            up=np.array([1.,u,u*u])
            section_values.append((u,up@row['sigma'],up@row['omega'],
                                   up@row['tau'],up@row['tw_weight']))
        es0=default_error['sigma'];et0=default_error['tau']
        ee0=math.hypot(es0,math.sqrt(3)*et0)
        for x in xs:
            xp=np.array([1.,x,x*x]);bm=f.bimoment(torsion,x);twm=f.bimoment(tw,x)
            for u,sp,ww,tp,vv in section_values:
                sigma=float(sp@xp+ww*bm);tau=float(tp@xp+vv*twm)
                if not math.isfinite(sigma) or not math.isfinite(tau):
                    raise ValueError('Finite physical witness and nonnegative errors required')
                if witness_evaluator is None:
                    # Without a callback the physical lower candidates are
                    # already known. Skip dictionary materialization only when
                    # even their pre-nextafter lower values cannot improve L.
                    values=(abs(sigma),abs(tau),math.hypot(sigma,math.sqrt(3)*tau))
                    if all((key=='normal' and u not in (0.,1.)) or
                           (best[key] is not None and (value-error)/limits[key]<=best[key]['index_lower_witness'])
                           for key,value,error in zip(('normal','shear','interaction'),values,(es0,et0,ee0))):
                        continue
                w=dict(t=x,u=u,segment_index=row['segment_index'],
                    thickness_face_sign=row['face'],normal_xy=row['normal_xy'],
                    xy_relative_to_gross_CG_mm=(row['xy_start']+u*row['xy_delta']).tolist(),
                    sigma_MPa=sigma,tau_MPa=tau,
                    equivalent_MPa=math.hypot(sigma,math.sqrt(3)*tau))
                # The callback must select the physical section before ANY
                # witness can drive refinement or an above-limit verdict.
                if witness_evaluator is not None:
                    w=witness_evaluator(w)
                    if w is None:
                        discarded_witnesses+=1
                        continue
                    if w['t']!=x or w['u']!=u or w['segment_index']!=row['segment_index'] or w['thickness_face_sign']!=row['face']:
                        raise ValueError('Physical witness evaluator must preserve the candidate location')
                sigma=w['sigma_MPa'];tau=w['tau_MPa']
                error=w.get('witness_error_MPa',default_error)
                es,et=(error['sigma'],error['tau']) if isinstance(error,dict) else (error,error)
                if not all(math.isfinite(v) for v in (sigma,tau,es,et)) or min(es,et)<0:
                    raise ValueError('Finite physical witness and nonnegative errors required')
                es=max(es,default_error['sigma']);et=max(et,default_error['tau'])
                w['equivalent_MPa']=math.hypot(sigma,math.sqrt(3)*tau)
                w['witness_error_MPa']=dict(sigma=es,tau=et)
                for key,value,err in (
                        ('normal',abs(sigma),es),('shear',abs(tau),et),
                        ('interaction',w['equivalent_MPa'],math.hypot(es,math.sqrt(3)*et))):
                    # Normal stress is affine along each straight wall face;
                    # physical exterior vertices suffice for its lower witness.
                    if key=='normal' and u not in (0.,1.):continue
                    index=value/limits[key]
                    lo=max(0.,math.nextafter((value-err)/limits[key],-math.inf))
                    hi=math.nextafter((value+err)/limits[key],math.inf)
                    if not all(math.isfinite(v) for v in (index,lo,hi)):
                        raise ArithmeticError('Nonfinite witness index')
                    if best[key] is None or lo>best[key]['index_lower_witness']:
                        best[key]=dict(w,index=index,index_lower_witness=lo,index_upper_witness=hi)
                    witnessed_upper[key]=max(witnessed_upper[key],hi)
        # Outward pad covers binary64 arithmetic, NOT model/physical error.
        upper={k:math.nextafter(v+64*np.finfo(float).eps*max(1.,v),math.inf) for k,v in upper.items()}
        if not all(math.isfinite(v) and v>=0 for v in upper.values()):raise ArithmeticError('Nonfinite upper bound')
        counter+=1;active[counter]=(row,x0,x1,u0,u1,depth);leaf_paths[counter]=path
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
        undecided=[k for k in limits if lower(k)<=1.<upper[k]]
        if not undecided or refined>=max_refinements:break
        if all(upper[k]-lower(k)<=index_tolerance for k in undecided):break
        key=max(undecided,key=lambda k:upper[k]-lower(k))
        _,cell_id=heaps[key][0];row,x0,x1,u0,u1,depth=active.pop(cell_id);path=leaf_paths[cell_id]
        # Alternate x/u; every unresolved rectangle shrinks in both directions.
        if depth%2==0:
            mid=(x0+x1)/2
            if mid in (x0,x1):active[cell_id]=(row,x0,x1,u0,u1,depth);break
            add(row,x0,mid,u0,u1,depth+1,path+"0");add(row,mid,x1,u0,u1,depth+1,path+"1")
        else:
            mid=(u0+u1)/2
            if mid in (u0,u1):active[cell_id]=(row,x0,x1,u0,u1,depth);break
            add(row,x0,x1,u0,mid,depth+1,path+"0");add(row,x0,x1,mid,u1,depth+1,path+"1")
        refined+=1
    upper=bounds()
    result=dict(schema=SCHEMA,full_interval_covered=True,section_facets=len(rows)//2,
        faces_per_facet=2,refinements=refined,normal_limit_MPa=normal_limit_MPa,
        shear_limit_MPa=limits['shear'],equivalent_limit_MPa=limits['interaction'],
        upper_bound_method='Quadratic Bernstein convex hull across each wall face, analytical hyperbolic extrema or center plus global derivative bound for intervals <=32 ulp(1); magnitude-scaled binary64 pad, not formal interval arithmetic',
        physical_witness_method='Concomitant sigma and tau at the same station, facet coordinate and face; lower index excludes declared binary64 evaluation error',
        discarded_witness_count=discarded_witnesses,
        model='Faceted thin-wall gross shear flow plus signed linear-through-thickness Saint Venant shear; not a curved-solid solution')
    for key in limits:
        low=None if best[key] is None else best[key]['index_lower_witness']
        hi=upper[key];adjustment=0.
        # A callback can select another eligible section than the artificial
        # branch whose field supplies this U. Include the physical point's
        # error enclosure explicitly; the eventual union covers all branches.
        if witness_evaluator is not None and witnessed_upper[key]>hi:
            adjustment=witnessed_upper[key]-hi
            hi=witnessed_upper[key]
        if not math.isfinite(hi) or (low is not None and hi<low):
            raise ArithmeticError('Upper bound below physical lower witness')
        result[key]=dict(witness=best[key],index_lower_witness=low,index_upper_bound=hi,
            partial_index_upper_bound=None,bound_gap=None if low is None else hi-low,
            physical_witness_upper_adjustment=adjustment,
            criterion='above_1_at_concomitant_state' if low is not None and low>1 else
                'within_1_by_full_interval_upper_bound' if hi<=1 else 'unresolved_numerical_bound',
            bound_is_not_a_concomitant_state=True)
    paths={}
    for cell_id,(row,*_) in active.items():
        paths.setdefault((row['segment_index'],row['face']),[]).append(leaf_paths[cell_id])
    return certify(result,paths)


def aggregate(records,complete):
    """Aggregate physical lower witnesses and upper bounds; never pass gaps."""
    original=list(records)
    records=[r for r in original if r is not None]
    complete=bool(complete and records and len(records)==len(original))
    out=dict(complete=complete,checked_intervals=len(records))
    keys=('normal','shear','interaction') if all('normal' in r for r in records) else ('shear','interaction')
    for key in keys:
        if not records:
            out[key]=None
            continue
        values=[r[key] for r in records]
        for value in values:
            low=value['index_lower_witness'];high=value['index_upper_bound']
            if (value['witness'] is None)!=(low is None):
                raise ValueError('Lower witness and physical state must both be present or absent')
            if low is not None and (not math.isfinite(low) or low<0):
                raise ValueError('Finite nonnegative lower witness required')
            if low is not None and high is not None and high<low:
                raise ArithmeticError('Aggregate upper bound below physical lower witness')
        witnessed=[r for r in values if r['witness'] is not None and r['index_lower_witness'] is not None]
        best=max(witnessed,key=lambda r:r['index_lower_witness']) if witnessed else None
        w=None if best is None else best['witness']
        lo=None if best is None else best['index_lower_witness']
        uppers=[r['index_upper_bound'] for r in values]
        if any(v is None or not math.isfinite(v) or v<0 for v in uppers):
            raise ValueError('Finite complete interval upper bounds required')
        hi=max(uppers)
        if lo is not None and (not math.isfinite(lo) or lo<0 or hi<lo):
            raise ArithmeticError('Aggregate upper bound below physical lower witness')
        exceeded=lo is not None and lo>1
        out[key]=dict(witness=w,index_lower_witness=lo,
            index_upper_bound=hi if complete else None,
            partial_index_upper_bound=None if complete else hi,
            bound_gap=None if lo is None else hi-lo,bound_is_not_a_concomitant_state=True,
            criterion=('above_1_at_concomitant_state' if exceeded else
                       'within_1_by_full_interval_upper_bound' if hi<=1 else
                       'unresolved_numerical_bound') if complete else
                      ('above_1_at_checked_state_full_envelope_incomplete' if exceeded else
                       'incomplete_section_branch_coverage'))
    return out
