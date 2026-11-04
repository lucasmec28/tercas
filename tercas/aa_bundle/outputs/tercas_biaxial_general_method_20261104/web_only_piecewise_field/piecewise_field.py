"""Mechanical q+P field and conditional scalar Green bounds. No section law.

Inputs are exact finite binary floats, integers or Fractions (never bool).
Two load components are ALREADY mapped to moment-equilibrium coordinates.
Tensor convention b=[1,y,-x], -d''=kappa. Units must be consistent.
"""
from dataclasses import dataclass
from fractions import Fraction as F
import math
if __package__:
    from .bounded_polynomial_source import _trim, _value, _divide, _sturm, _variations
else:
    from bounded_polynomial_source import _trim, _value, _divide, _sturm, _variations


class NumericalError(ArithmeticError):
    """No finite outward representation or isolation budget exhausted."""


def rational(x):
    if isinstance(x, bool) or not isinstance(x, (int, float, F)):
        raise ValueError('Expected finite int, float or Fraction, excluding bool')
    if isinstance(x, float) and not math.isfinite(x):
        raise ValueError('Nonfinite value')
    return F(x)


def vector(x):
    if not isinstance(x, (tuple, list)) or len(x) != 2:
        raise ValueError('Expected exactly two signed moment-coordinate components')
    return tuple(rational(v) for v in x)


def outward(x, upper=True):
    x = rational(x)
    try:
        y = float(x)
    except OverflowError as exc:
        raise NumericalError('Bound outside finite binary64 range') from exc
    if not math.isfinite(y):
        raise NumericalError('Bound outside finite binary64 range')
    if (upper and F(y) < x) or (not upper and F(y) > x):
        y = math.nextafter(y, math.inf if upper else -math.inf)
    if not math.isfinite(y):
        raise NumericalError('Outward bound outside finite binary64 range')
    return y


@dataclass(frozen=True)
class MomentPiece:
    left: F
    right: F
    controls: tuple  # three two-component vectors


@dataclass(frozen=True)
class MomentField:
    length: F
    q: tuple
    p: tuple
    position: object
    reaction_left: tuple
    reaction_right: tuple
    pieces: tuple

    def moment(self, z):
        z = rational(z)
        if not 0 <= z <= self.length:
            raise ValueError('Coordinate outside span')
        arm = max(F(0), z-self.position) if self.position is not None else F(0)
        return tuple(r*z-q*z*z/2-p*arm for r,q,p in zip(self.reaction_left,self.q,self.p))


def build_field(length, q, p=(0, 0), position=None):
    L, q, p = rational(length), vector(q), vector(p)
    if L <= 0:
        raise ValueError('Length must be positive')
    a = None if position is None else rational(position)
    if a is not None and not 0 < a < L:
        raise ValueError('Point position must be strictly interior, including zero P')
    if any(p) and a is None:
        raise ValueError('Nonzero P requires interior position')
    # Zero P is an identity: its optional valid position introduces no interface.
    if not any(p):
        a = None
    ra = tuple(qi*L/2 + (pi*(L-a)/L if a is not None else 0) for qi,pi in zip(q,p))
    rb = tuple(qi*L+pi-ri for qi,pi,ri in zip(q,p,ra))
    field = MomentField(L,q,p,a,ra,rb,())
    initial = [F(0),L] if a is None else [F(0),a,L]
    cuts = set(initial)
    for u,v in zip(initial,initial[1:]):
        for ri,qi,pi in zip(ra,q,p):
            if qi:
                root = (ri-(pi if a is not None and u >= a else 0))/qi
                if u < root < v:
                    cuts.add(root)
    cuts = sorted(cuts)
    pieces = []
    for u,v in zip(cuts,cuts[1:]):
        c0, c2 = field.moment(u), field.moment(v)
        slope = tuple(ri-qi*u-(pi if a is not None and u >= a else 0) for ri,qi,pi in zip(ra,q,p))
        c1 = tuple(c+(v-u)*s/2 for c,s in zip(c0,slope))
        pieces.append(MomentPiece(u,v,(c0,c1,c2)))
    return MomentField(L,q,p,a,ra,rb,tuple(pieces))


def roots_open_unit(coeff, bits=96, max_nodes=20000):
    """Rational enclosures of every DISTINCT interior root, Sturm proof.

    Exact right-end roots may yield singleton intervals. Other intervals have
    width <= 2**-bits and count exactly one; clustered roots are never merged.
    Resource exhaustion is explicit, never an incomplete extrema list.
    """
    if isinstance(bits,bool) or not isinstance(bits,int) or bits < 1:
        raise ValueError('bits must be positive integer')
    if isinstance(max_nodes,bool) or not isinstance(max_nodes,int) or max_nodes < 1:
        raise ValueError('max_nodes must be positive integer')
    p = _trim([rational(c) for c in coeff])
    if len(p) > 4:
        raise ValueError('Root isolator supports degree at most three')
    while len(p)>1 and p[0]==0:
        p=p[1:]
    while len(p)>1 and sum(p)==0:
        p, rem = _divide(p,[F(-1),F(1)])
        if rem != [0]:
            raise NumericalError('Endpoint division inconsistent')
    if len(p)<2:
        return ()
    seq = _sturm(p)
    if len(seq[-1])>1:
        p,rem = _divide(p,seq[-1])
        if rem != [0]:
            raise NumericalError('Square-free division inconsistent')
        seq = _sturm(p)
    if len(p)==2:
        root=-p[0]/p[1]
        return ((root,root),) if 0<root<1 else ()
    pending=[(F(0),F(1),_variations(seq,F(0)),_variations(seq,F(1)))]
    result=[]
    n=0
    while pending:
        n+=1
        if n>max_nodes:
            raise NumericalError('Exact root isolation budget exhausted')
        l,r,vl,vr=pending.pop()
        count=vl-vr
        if count<0:
            raise NumericalError('Inconsistent Sturm count')
        if count==0:
            continue
        if count==1 and _value(p,r)==0:
            result.append((r,r))
        elif count==1 and r-l<=F(1,2**bits) and _value(p,l)!=0:
            result.append((l,r))
        else:
            m=(l+r)/2
            vm=_variations(seq,m)
            pending.extend(((m,r,vm,vr),(l,m,vl,vm)))
    return tuple(sorted(result))


def interval_value(coeff, interval):
    """Exact interval Horner. Outward rational enclosure, not root sampling."""
    a,b=interval
    lo=hi=F(0)
    for c in reversed(coeff):
        products=(lo*a,lo*b,hi*a,hi*b)
        lo,hi=min(products)+c,max(products)+c
    return lo,hi


@dataclass(frozen=True)
class DisplacementPiece:
    left: F
    right: F
    coefficients: tuple  # ascending powers in t=(z-left)/(right-left)

    def value(self, t, derivative=0):
        t=rational(t)
        if not 0<=t<=1:
            raise ValueError('Local coordinate outside [0,1]')
        if isinstance(derivative,bool) or not isinstance(derivative,int) or derivative<0:
            raise ValueError('Derivative order must be nonnegative integer')
        c=list(self.coefficients)
        for _ in range(derivative):
            c=[i*c[i]/(self.right-self.left) for i in range(1,len(c))] or [F(0)]
        return _value(c,t)


@dataclass(frozen=True)
class ExtremaBound:
    minimum_lower: F
    maximum_upper: F
    critical_intervals: tuple  # (piece index, local rational interval, value interval)


def _partition(breaks):
    b=tuple(rational(x) for x in breaks)
    if len(b)<2 or b[0]!=0 or any(v<=u for u,v in zip(b,b[1:])):
        raise ValueError('Partition must start at 0 and be strictly increasing')
    return b


def _controls(controls, n):
    rows=tuple(tuple(rational(x) for x in row) for row in controls)
    if len(rows)!=n or any(len(row)!=3 for row in rows):
        raise ValueError('Three Bernstein controls required per interval')
    return rows


def integrate_green(breaks, controls):
    """Global Dirichlet Green integration of piecewise quadratic curvature.

    Discontinuous curvature is allowed: d and d' remain globally continuous.
    No statement that supplied curvature envelopes come from a valid section.
    """
    b=_partition(breaks)
    rows=_controls(controls,len(b)-1)
    polys=tuple((c0,2*(c1-c0),c0-2*c1+c2) for c0,c1,c2 in rows)
    A=F(0)
    for u,v,c in zip(b,b[1:],polys):
        h=v-u
        A+=sum((b[-1]-u)*h*ck/F(k+1)-h*h*ck/F(k+2) for k,ck in enumerate(c))/b[-1]
    d,s=F(0),A
    result=[]
    for u,v,c in zip(b,b[1:],polys):
        h=v-u
        p=(d,h*s)+tuple(-h*h*ck/F((k+1)*(k+2)) for k,ck in enumerate(c))
        piece=DisplacementPiece(u,v,p)
        result.append(piece)
        d,s=piece.value(1),piece.value(1,1)
    if d!=0:
        raise NumericalError('Exact global support condition failed')
    return tuple(result)


def extrema(pieces, bits=96, max_nodes=20000):
    values=[]
    evidence=[]
    if not pieces:
        raise ValueError('At least one displacement piece required')
    for i,piece in enumerate(pieces):
        c=piece.coefficients
        values.extend(((c[0],c[0]),(sum(c),sum(c))))
        for interval in roots_open_unit([k*c[k] for k in range(1,len(c))],bits,max_nodes):
            enclosure=interval_value(c,interval)
            values.append(enclosure)
            evidence.append((i,interval,enclosure))
    return ExtremaBound(min(v[0] for v in values),max(v[1] for v in values),tuple(evidence))


@dataclass(frozen=True)
class ComponentBound:
    lower_pieces: tuple
    upper_pieces: tuple
    lower_extrema: ExtremaBound
    upper_extrema: ExtremaBound
    absolute_upper: F

    def upper_float(self):
        return outward(self.absolute_upper)


def component_bound(breaks, lower_controls, upper_controls, bits=96, max_nodes=20000):
    """Conditional conservative magnitude bound for ONE fixed component.

    Caller must establish lower <= actual curvature <= upper over the span.
    This API additionally requires ordered corresponding controls, a sufficient
    algebraic ordering check only. It supplies neither physical approval nor
    a simultaneous vector resultant or resistance/serviceability index.
    """
    b=_partition(breaks)
    lower=_controls(lower_controls,len(b)-1)
    upper=_controls(upper_controls,len(b)-1)
    if any(l>u for lr,ur in zip(lower,upper) for l,u in zip(lr,ur)):
        raise ValueError('Lower controls must not exceed upper controls')
    lp,up=integrate_green(b,lower),integrate_green(b,upper)
    le,ue=extrema(lp,bits,max_nodes),extrema(up,bits,max_nodes)
    return ComponentBound(lp,up,le,ue,max(F(0),ue.maximum_upper,-le.minimum_lower))
