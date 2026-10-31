"""Adapted from reviewed method protocols. See docs/METHOD.md."""
import math
from scipy.integrate import quad
from scipy.optimize import brentq

def positive(*values):
    if any(not math.isfinite(v) or v <= 0 for v in values):
        raise ValueError('Propriedades/comprimento devem ser positivos e finitos')

def ief_literal(Ig, M, Ml):
    positive(Ig, Ml)
    if not math.isfinite(M): raise ValueError('Momento não finito')
    lam=math.sqrt(abs(M)/Ml)
    return Ig if lam<=.673 else Ig*(1-.22/lam)/lam

def ief(Ig, M, Ml):
    # Envelope de implementação conservador e divulgado; não altera a fórmula citada.
    return min(Ig, ief_literal(Ig,M,Ml))

def moment(x,L,q,P,a):
    return q*x*(L-x)/2 + (P*(L-a)*x/L if x<=a else P*a*(L-x)/L)

def model(L,E,Ig,Ml,q=0.,P=0.,a=None):
    positive(L,E,Ig,Ml)
    a=L/2 if a is None else a
    if not all(math.isfinite(v) for v in (q,P,a)) or not 0<=a<=L:
        raise ValueError('Ação ou posição inválida')
    if q*P<0: raise ValueError('Protocolo de máximo único limitado a ações de mesmo sentido')
    return L,E,Ig,Ml,q,P,a

def max_moment(args):
    L,E,Ig,Ml,q,P,a=args
    cands=[0.,L,a]
    if q:
        for lo,hi,ra in [(0,a,q*L/2+P*(L-a)/L),(a,L,q*L/2+P*(L-a)/L-P)]:
            x=ra/q
            if lo<=x<=hi:cands.append(x)
    return max(abs(moment(x,L,q,P,a)) for x in cands)

def deflection(args,z,constant_min=False):
    L,E,Ig,Ml,q,P,a=args
    if not 0<=z<=L:raise ValueError('Ponto fora do vão')
    if z in (0.,L):return 0.
    imin=ief(Ig,max_moment(args),Ml)
    def f(x):
        m=moment(x,L,q,P,a)
        mu=(L-z)*x/L if x<=z else z*(L-x)/L
        return m*mu/(E*(imin if constant_min else ief(Ig,m,Ml)))
    points=sorted(set([0.,a,z,L]))
    return sum(quad(f,lo,hi,epsabs=1e-9,epsrel=1e-9,limit=200)[0] for lo,hi in zip(points,points[1:]) if hi>lo)

def slope(args,z,constant_min=False):
    L,E,Ig,Ml,q,P,a=args
    imin=ief(Ig,max_moment(args),Ml)
    def f(x):
        m=moment(x,L,q,P,a)
        dmu=-x/L if x<=z else (L-x)/L
        return m*dmu/(E*(imin if constant_min else ief(Ig,m,Ml)))
    points=sorted(set([0.,a,z,L]))
    return sum(quad(f,lo,hi,epsabs=1e-11,epsrel=1e-9,limit=200)[0] for lo,hi in zip(points,points[1:]) if hi>lo)

def peak(args,constant_min=False):
    L,E,Ig,Ml,q,P,a=args
    if max_moment(args)==0:return 0.,0.
    x=brentq(lambda z:slope(args,z,constant_min),0.,L,xtol=1e-8)
    return x,deflection(args,x,constant_min)
