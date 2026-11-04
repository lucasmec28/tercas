"""Static exact Vlasov element for constant GJ/ECw and uniform torque.
Rescaled {1,t,cosh(h t),sinh(h t)} basis, h=L*sqrt(GJ/ECw).
Series evaluate only hyperbolic functions, not a spatial discretization.
Restricted floating-point research domain: 0<=h<=10, ECw>0.
"""
import math
import numpy as np


def series(t,h,start,power_shift,derivative):
    # sum h^(2j-power_shift) t^(2j-derivative)/(2j-derivative)!
    terms=[]
    for j in range(start,70):
        power=2*j-derivative
        if power<0:continue
        term=(h**(2*j-power_shift))*(t**power)/math.factorial(power)
        terms.append(term)
        if len(terms)>3 and abs(term)<1e-18*max(1.,abs(math.fsum(terms))):break
    return math.fsum(terms)


def basis(t,L,S,D,derivative=0):
    h=L*math.sqrt(S/D)
    if not 0<=h<=10:raise ValueError('Exact-element floating-point qualification limited to 0<=kL<=10')
    # Columns [1,t,F2,F3], with F2=(cosh(ht)-1)/h² and
    # F3=(sinh(ht)-ht)/h³. Limits t²/2 and t³/6 are evaluated directly.
    if derivative==0:b0,b1=1.,t
    elif derivative==1:b0,b1=0.,1.
    else:b0=b1=0.
    F2=series(t,h,1,2,derivative)
    # F3 terms: sum h^(2j-2)t^(2j+1)/(2j+1)!.
    terms=[]
    for j in range(1,70):
        power=2*j+1-derivative
        if power<0:continue
        term=h**(2*j-2)*t**power/math.factorial(power);terms.append(term)
        if len(terms)>3 and abs(term)<1e-18*max(1.,abs(math.fsum(terms))):break
    F3=math.fsum(terms)
    return np.array([b0,b1,F2,F3])/L**derivative


def particular(t,L,S,D,m,derivative=0):
    # F4=(cosh(ht)-1-(ht)^2/2)/h^4; D*phi''''-S*phi''=m.
    h=L*math.sqrt(S/D)
    return m*L**(4-derivative)/D*series(t,h,2,4,derivative)


def constants(L,S,D,m,nodal):
    if L<=0 or S<0 or D<=0:raise ValueError('L,D positive and S nonnegative required')
    A=np.array([basis(0,L,S,D),L*basis(0,L,S,D,1),basis(1,L,S,D),L*basis(1,L,S,D,1)])
    rhs=np.array(nodal)*[1,L,1,L]-np.array([particular(0,L,S,D,m),L*particular(0,L,S,D,m,1),particular(1,L,S,D,m),L*particular(1,L,S,D,m,1)])
    return np.linalg.solve(A,rhs)


def state(L,S,D,m,nodal,t):
    c=constants(L,S,D,m,nodal)
    derivatives=[float(basis(t,L,S,D,j)@c+particular(t,L,S,D,m,j)) for j in range(5)]
    phi,psi,d2,d3,d4=derivatives;B=-D*d2;T=S*psi-D*d3
    return dict(phi=phi,psi=psi,B=B,T=T,Tsv=S*psi,Tw=-D*d3,d2=d2,d3=d3,d4=d4,
                differential_residual=D*d4-S*d2-m)


def end_actions(L,S,D,m,nodal):
    a=state(L,S,D,m,nodal,0.);b=state(L,S,D,m,nodal,1.)
    return np.array([-a['T'],a['B'],b['T'],-b['B']])


def matrices(L,S,D,m=0.):
    K=np.column_stack([end_actions(L,S,D,0.,e) for e in np.eye(4)])
    f=-end_actions(L,S,D,m,np.zeros(4))
    return K,f
