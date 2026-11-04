"""Analytical full-span extrema of quadratic N/M stress plus exact Vlasov B.

On each interval all pure-section stress coefficients are constant. The third
stress derivative is a single hyperbolic pair, with at most one zero. Rolle
partitioning then finds all second/first derivative roots. No longitudinal grid
or independently maximized actions enters the resistance objective.

The section model is the source faceted thin wall. Normal bending uses the
exterior coordinates at both faces of every segment; omega is constant through
the thickness at each corresponding midsurface station. The field is affine
on each rectangle, so four vertices suffice. This is not an exact curved solid.
"""
import math
import numpy as np
from scipy.optimize import brentq
from ..three_girt_warping.exact_torsion import state as exact_state


def _finite(value, name):
    if type(value) not in (int, float) or not math.isfinite(value):
        raise ValueError(name + ' must be a finite real number')
    return float(value)


def torsion_field(parameters):
    """B(t)=B0+U*(cosh(ht)-1)/h²+V*sinh(ht)/h, including the h=0 limit."""
    names=('L_mm','GJ_Nmm2','ECw_Nmm4','m_SC_N')
    L,S,D,m=(_finite(parameters[k],k) for k in names)
    nodal=parameters['nodal_phi_psi']
    if L<=0 or S<0 or D<=0 or not isinstance(nodal,(list,tuple)) or len(nodal)!=4:
        raise ValueError('Invalid exact torsion parameters')
    nodal=[_finite(v,'nodal value') for v in nodal]
    h=L*math.sqrt(S/D)
    if h>10:raise ValueError('Exact demand domain requires kL<=10')
    first=exact_state(L,S,D,m,nodal,0.)
    B0=first['B'];U=h*h*B0-m*L*L;V=L*first['Tw']
    result=dict(h=h,B0=B0,U=U,V=V)
    # Independently cross-check the ODE representation against the existing
    # series basis. No network solve or changed stiffness is involved.
    for t in (0.,.37,1.):
        exact=exact_state(L,S,D,m,nodal,t)['B']
        value=bimoment(result,t)
        if not math.isclose(value,exact,rel_tol=2e-10,abs_tol=1e-6):
            raise ArithmeticError('Equivalent torsion field failed its source comparison')
    return result


def bimoment(field,t,derivative=0):
    """Derivative is with respect to normalized t, not x."""
    h,B0,U,V=(field[k] for k in ('h','B0','U','V'))
    t=float(t)
    if h==0:
        return (B0+V*t+U*t*t/2 if derivative==0 else
                V+U*t if derivative==1 else U if derivative==2 else 0.)
    z=h*t;sh=math.sinh(z);ch=math.cosh(z)
    if derivative==0:
        return math.fsum((B0,U*2*(math.sinh(z/2)/h)**2,V*sh/h))
    if derivative==1:return math.fsum((U*sh/h,V*ch))
    if derivative==2:return math.fsum((U*ch,V*h*sh))
    if derivative==3:return math.fsum((U*h*sh,V*h*h*ch))
    raise ValueError('Only derivatives 0 to 3 are needed')


def sigma_value(polynomial,omega_over_Cw,field,t,derivative=0):
    p=polynomial
    normal=(math.fsum((p[0],p[1]*t,p[2]*t*t)) if derivative==0 else
            p[1]+2*p[2]*t if derivative==1 else 2*p[2] if derivative==2 else 0.)
    return math.fsum((normal,omega_over_Cw*bimoment(field,t,derivative)))


def _distinct(values):
    # Do not snap an interior physical root to an endpoint. Exact duplicates
    # only are removed; very close roots are harmless to the maximum.
    return sorted(set(float(v) for v in values))


def _monotone_roots(fn,knots):
    roots=[]
    for a,b in zip(knots[:-1],knots[1:]):
        fa,fb=fn(a),fn(b)
        if not math.isfinite(fa) or not math.isfinite(fb):
            raise ArithmeticError('Nonfinite analytical derivative')
        if fa==0:roots.append(a)
        if fb==0:roots.append(b)
        if (fa<0<fb) or (fb<0<fa):
            roots.append(brentq(fn,a,b,xtol=5e-15,rtol=1e-14,maxiter=100))
    return _distinct(roots)


def stress_extrema(polynomial,omega_over_Cw,field,left=0.,right=1.):
    """All candidate extrema for one fiber on one sign-constant interval."""
    p=[_finite(v,'normal coefficient') for v in polynomial]
    if len(p)!=3:raise ValueError('Three ascending quadratic coefficients required')
    w=_finite(omega_over_Cw,'omega/Cw')
    left=_finite(left,'left');right=_finite(right,'right')
    if not 0<=left<right<=1:raise ValueError('Nonempty normalized interval required')
    for k in ('h','B0','U','V'):_finite(field[k],k)
    if field['h']<0 or field['h']>10:raise ValueError('Hyperbolic domain outside [0,10]')
    if w==0 or field['h']==0:
        c=p[2]+(w*field['U']/2 if field['h']==0 else 0.)
        b=p[1]+(w*field['V'] if field['h']==0 else 0.)
        root=-b/(2*c) if c else None
        knots=_distinct([left,right]+([root] if root is not None and left<root<right else []))
    else:
        # B''' is proportional to U*sinh(ht)+V*h*cosh(ht), so tanh(ht)
        # gives at most one zero. Endpoint signs locate it without division
        # by a possibly vanishing U or catastrophic Q/C cancellation.
        third=lambda t:sigma_value(p,w,field,t,3)
        second=lambda t:sigma_value(p,w,field,t,2)
        first=lambda t:sigma_value(p,w,field,t,1)
        k3=_distinct([left,right]+_monotone_roots(third,[left,right]))
        k2=_distinct([left,right]+_monotone_roots(second,k3))
        knots=_distinct([left,right]+_monotone_roots(first,k2))
    points=[dict(t=t,sigma_MPa=sigma_value(p,w,field,t)) for t in knots]
    if any(not math.isfinite(v['sigma_MPa']) for v in points):
        raise ArithmeticError('Nonfinite analytical stress')
    return dict(minimum=min(points,key=lambda v:v['sigma_MPa']),
                maximum=max(points,key=lambda v:v['sigma_MPa']),
                maximum_absolute=max(points,key=lambda v:abs(v['sigma_MPa'])),
                candidate_count=len(points))


def sign_intervals(polynomials):
    """Exact sign coverage, including unresolved sub-ulp root neighborhoods.

    The discriminant is rational in the original binary64 inputs. Decimal
    roots merely locate bracketing float knots; every interval's possible
    signs are independently established from exact endpoints and vertex.
    A nonrepresentable narrow opposite-sign interval is never erased.
    """
    from fractions import Fraction
    from decimal import Decimal,localcontext
    if set(polynomials)!={'N','Mx','My'}:raise ValueError('N/Mx/My fields required')
    out={};knots=[0.,1.]
    def evaluate(coef,t):return sum(c*t**i for i,c in enumerate(coef))
    def bracket(coef,root):
        # Include rounded boundary roots. Exact residual/vertex tests below
        # decide whether a tiny interior sign actually exists.
        r=float(root)
        if not math.isfinite(r) or not 0<=r<=1:return
        if evaluate(coef,Fraction(r))==0:
            if 0<r<1:knots.append(r)
        else:
            knots.extend((max(0.,math.nextafter(r,-math.inf)),
                          min(1.,math.nextafter(r,math.inf))))
    with localcontext() as ctx:
        ctx.prec=100
        def dec(v):return Decimal(v.numerator)/Decimal(v.denominator)
        for name,coef in polynomials.items():
            if not isinstance(coef,(list,tuple)) or not 1<=len(coef)<=(1 if name=='N' else 3):
                raise ValueError('Unexpected action polynomial degree')
            c=[Fraction(_finite(v,name)) for v in coef]
            while len(c)>1 and c[-1]==0:c.pop()
            out[name]=c
            if len(c)==2:bracket(c,dec(-c[0]/c[1]))
            elif len(c)==3:
                aa,bb,cc=c[2],c[1],c[0];disc=bb*bb-4*aa*cc
                if disc==0:bracket(c,dec(-bb/(2*aa)))
                elif disc>0:
                    root_disc=dec(disc).sqrt()
                    q=-(dec(bb)+(root_disc if bb>=0 else -root_disc))/2
                    if q==0:raise ArithmeticError('Unresolved exact positive discriminant')
                    bracket(c,q/dec(aa));bracket(c,dec(cc)/q)
    knots=_distinct(knots);rows=[]
    for left,right in zip(knots[:-1],knots[1:]):
        lo,hi=Fraction(left),Fraction(right);mid=(lo+hi)/2;signs={};required={}
        for key,c in out.items():
            values=[evaluate(c,lo),evaluate(c,hi)]
            if len(c)==3:
                vertex=-c[1]/(2*c[2])
                if lo<vertex<hi:values.append(evaluate(c,vertex))
            low,high=min(values),max(values)
            req=([-1] if low<0 else [])+([1] if high>0 else [])
            required[key]=req or [0]
            value=evaluate(c,mid)
            signs[key]=1 if value>0 else -1 if value<0 else required[key][0]
        rows.append(dict(left=left,right=right,signs=signs,required_signs=required,
            sign_root_neighborhood=any(len(v)>1 for v in required.values())))
    return rows


def envelope(polynomials,coefficients_by_action,nodes_relative_to_gross_CG,
             omega_over_Cw,torsion,left=0.,right=1.):
    """Coefficients are stress/unit physical action, with actual signed actions."""
    xy=np.asarray(nodes_relative_to_gross_CG,dtype=float);omega=np.asarray(omega_over_Cw,dtype=float)
    if xy.ndim!=2 or xy.shape[1]!=2 or len(xy)<2 or omega.shape!=(len(xy),) or not np.isfinite(xy).all() or not np.isfinite(omega).all():
        raise ValueError('Finite matching contour nodes and omega/Cw required')
    matrix=np.c_[np.ones(len(xy)),xy];P=np.zeros((len(xy),3))
    for name,coef in polynomials.items():
        if name not in ('N','Mx','My'):raise ValueError('Unknown normal action')
        if all(v==0 for v in coef):continue
        factors=coefficients_by_action.get(name)
        if factors is None:raise ValueError('Missing eligible pure-section coefficients: '+name)
        factors=np.asarray(factors,dtype=float)
        if factors.shape!=(3,) or not np.isfinite(factors).all():raise ValueError('Three finite section stress coefficients required')
        action=np.zeros(3);action[:len(coef)]=coef
        P+=(matrix@factors)[:,None]*action[None,:]
    records=[]
    for i,(p,w) in enumerate(zip(P,omega)):
        extrema=stress_extrema(p.tolist(),float(w),torsion,left,right)
        for kind in ('minimum','maximum','maximum_absolute'):
            extrema[kind].update(section_fiber_index=i,xy_relative_to_gross_CG_mm=xy[i].tolist(),
                omega_over_Cw_per_mm4=float(w))
        records.append(extrema)
    return dict(minimum=min((r['minimum'] for r in records),key=lambda v:v['sigma_MPa']),
        maximum=max((r['maximum'] for r in records),key=lambda v:v['sigma_MPa']),
        maximum_absolute=max((r['maximum_absolute'] for r in records),key=lambda v:abs(v['sigma_MPa'])),
        section_fibers_checked=len(xy),analytical_candidates_checked=sum(r['candidate_count'] for r in records),
        coordinate='t=(x-x_start)/length',method='Rolle partition of hyperbolic third/second/first stress derivatives; all exterior thin-wall facet vertices')


def exterior_fibers(section):
    """Both faces of every source facet, with the endpoint's own omega.

    Coordinates refer to the gross centroid. All four rectangular vertices are
    retained, including both adjacent facet normals at a source corner node.
    """
    nodes=np.asarray(section['nodes_xy_mm'],dtype=float)
    omega=np.asarray(section['omega_nodes_mm2'],dtype=float)
    cg=np.asarray(section['properties']['centroid_xy_mm'],dtype=float)
    thickness=_finite(section['thickness_mm'],'thickness')
    Cw=_finite(section['properties']['Cw_mm6'],'Cw')
    if thickness<=0 or Cw<=0 or omega.shape!=(len(nodes),):raise ValueError('Invalid section fibers')
    xy=[];weights=[];identities=[]
    for i,(a,b) in enumerate(zip(nodes[:-1],nodes[1:])):
        delta=b-a;length=float(np.linalg.norm(delta))
        if length<=0:raise ValueError('Zero contour facet')
        normal=np.array([-delta[1],delta[0]])/length
        for endpoint,node in enumerate((a,b)):
            for face in (-1,1):
                xy.append((node-cg+face*thickness/2*normal).tolist())
                weights.append(float(omega[i+endpoint]/Cw))
                identities.append(dict(segment_index=i,endpoint=endpoint,midsurface_node_index=i+endpoint,
                    thickness_face_sign=face,normal_xy=normal.tolist(),
                    fiber_xy_relative_to_gross_CG_mm=xy[-1],omega_mm2=float(omega[i+endpoint])))
    return dict(xy_mm=xy,omega_over_Cw=weights,identities=identities,
        scope='Both faces of every faceted R01 wall rectangle; omega constant through thickness; not an exact curved solid')
