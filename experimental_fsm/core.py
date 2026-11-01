"""Fresh reconstruction R01, 2026-11-01. Research-only S-S classical FSM.
Independent Gaussian energy assembly; not a restoration of the lost artifact.
DOFs per node: transverse x,y, axial z, tangent-section rotation. N/mm/MPa.
"""
import numbers
import numpy as np
from scipy.linalg import eigh,LinAlgError
MAX_NODES=257
class NotEvaluated(RuntimeError):pass

def scalar(x,name,positive=False):
 if isinstance(x,(bool,np.bool_)) or not isinstance(x,numbers.Real) or not np.isfinite(x) or (positive and x<=0):raise ValueError(name+' invalid')
 return float(x)

def mesh(p):
 if len(p)>MAX_NODES:raise ValueError('operational node budget257 exceeded; not a physical limit')
 p=np.asarray(p,float)
 if p.ndim!=2 or p.shape[1]!=2 or len(p)<2 or not np.isfinite(p).all():raise ValueError('invalid mesh')
 q=p-p[0];span=np.max(abs(q))
 if not np.isfinite(span) or span<=0:raise ValueError('invalid span')
 q=q/span;d=np.diff(q,axis=0);tol=1e-12
 if min(np.linalg.norm(d,axis=1))<=tol:raise ValueError('duplicate nodes')
 def cross(a,b):return a[0]*b[1]-a[1]*b[0]
 for i in range(len(d)):
  if i+1<len(d) and abs(cross(d[i],d[i+1]))<tol and d[i]@d[i+1]<0:raise ValueError('backtrack')
  for j in range(i+2,len(d)):
   a,b,c,e=q[i],q[i+1],q[j],q[j+1]
   if np.any(np.maximum(np.minimum(a,b),np.minimum(c,e))>np.minimum(np.maximum(a,b),np.maximum(c,e))+tol):continue
   if cross(b-a,c-a)*cross(b-a,e-a)<=tol**2 and cross(e-c,a-c)*cross(e-c,b-c)<=tol**2:raise ValueError('self-intersecting/closed chain')
 return p

def strip(b,t,L,stress,E=200000.,nu=.3):
 b=scalar(b,'b',True);t=scalar(t,'t',True);L=scalar(L,'L',True);E=scalar(E,'E',True);nu=scalar(nu,'nu')
 stress=np.asarray(stress,float)
 if stress.shape!=(2,) or not np.isfinite(stress).all() or not -1<nu<.5:raise ValueError('invalid stress/material')
 try:
  with np.errstate(over='raise',invalid='raise',divide='raise'):
   k=np.pi/L;D=E/(1-nu**2)*np.array([[1,nu,0],[nu,1,0],[0,0,(1-nu)/2]])
   K=np.zeros((8,8));G=K.copy()
   for xi,wt in zip(*np.polynomial.legendre.leggauss(5)):
    r=(xi+1)/2;weight=wt*b*L/4;N=np.array([1-r,r]);dN=np.array([-1,1])/b
    H=np.array([1-3*r*r+2*r**3,b*(r-2*r*r+r**3),3*r*r-2*r**3,b*(-r*r+r**3)])
    Hs=np.array([-6*r+6*r*r,b*(1-4*r+3*r*r),6*r-6*r*r,b*(-2*r+3*r*r)])/b
    Hss=np.array([-6+12*r,b*(-4+6*r),6-12*r,b*(-2+6*r)])/b**2
    B=np.zeros((3,8));B[0,[0,4]]=dN;B[1,[2,6]]=-k*N;B[2,[0,4]]=k*N;B[2,[2,6]]=dN
    C=np.zeros((3,8));C[0,[1,3,5,7]]=-Hss;C[1,[1,3,5,7]]=k*k*H;C[2,[1,3,5,7]]=-2*k*Hs
    S=np.zeros((3,8));S[0,[0,4]]=N;S[1,[1,3,5,7]]=H;S[2,[2,6]]=N
    K+=weight*(t*B.T@D@B+t**3/12*C.T@D@C);G+=weight*t*k*k*(N@stress)*(S.T@S)
 except (OverflowError,FloatingPointError) as exc:raise NotEvaluated('unrepresentable element arithmetic') from exc
 return K,G

def matrices(nodes,t,L,stress,E=200000.,nu=.3):
 p=mesh(nodes);stress=np.asarray(stress,float)
 if stress.shape!=(len(p),) or not np.isfinite(stress).all():raise ValueError('invalid stress vector')
 K=np.zeros((4*len(p),4*len(p)));G=K.copy()
 for i,delta in enumerate(np.diff(p,axis=0)):
  b=np.linalg.norm(delta);c,s=delta/b;R=np.array([[c,s,0,0],[-s,c,0,0],[0,0,1,0],[0,0,0,1]])
  T=np.zeros((8,8));T[:4,:4]=R;T[4:,4:]=R;ke,ge=strip(b,t,L,stress[i:i+2],E,nu);ix=np.arange(4*i,4*i+8)
  K[np.ix_(ix,ix)]+=T.T@ke@T;G[np.ix_(ix,ix)]+=T.T@ge@T
 return K,G

def solve(nodes,t,L,stress,E=200000.,nu=.3,count=4):
 if isinstance(count,(bool,np.bool_)) or not isinstance(count,(int,np.integer)) or not 1<=count<=32:raise ValueError('count must be integer1..32, operational')
 K,G=matrices(nodes,t,L,stress,E,nu)
 if not np.isfinite(K).all() or not np.isfinite(G).all() or min(np.diag(K))<=0:raise NotEvaluated('invalid matrices')
 d=1/np.sqrt(np.diag(K))
 try:mu,v=eigh(d[:,None]*G*d,d[:,None]*K*d)
 except LinAlgError as e:raise NotEvaluated('elastic matrix not SPD') from e
 keep=np.flatnonzero(mu>max(abs(mu))*1e-12)[::-1][:count];f=1/mu[keep];v=d[:,None]*v[:,keep];res=[]
 for ff,q in zip(f,v.T):
  a=K@q;b=ff*(G@q);den=np.linalg.norm(a)+np.linalg.norm(b);res.append(np.linalg.norm(a-b)/den if den else np.inf)
 res=np.asarray(res)
 if not np.isfinite(res).all() or np.any(res>1e-6):raise NotEvaluated('eigenpair residual rejected')
 return f,v,res

def stresses(nodes,t,N=0.,Mx=0.,My=0.):
 p=mesh(nodes);t=scalar(t,'t',True);N=scalar(N,'N');Mx=scalar(Mx,'Mx');My=scalar(My,'My')
 a=np.linalg.norm(np.diff(p,axis=0),axis=1)*t;A=sum(a);centroid=np.sum(a[:,None]*(p[1:]+p[:-1])/2,axis=0)/A;q=p-centroid;J=np.zeros((2,2))
 for i,ar in enumerate(a):
  u,v=q[i:i+2];J+=ar*((np.outer(u,u)+np.outer(v,v))/3+(np.outer(u,v)+np.outer(v,u))/6)
 try:g=np.linalg.solve(J,[-My,Mx])
 except np.linalg.LinAlgError as e:raise NotEvaluated('singular section inertia') from e
 s=N/A+q@g
 if not np.isfinite(s).all():raise NotEvaluated('invalid stresses')
 return s,{'A':float(A),'centroid':centroid.tolist(),'Iy':float(J[0,0]),'Ix':float(J[1,1])}

def channel(h,b,lip,t,n=2):
 h=scalar(h,'h',True);b=scalar(b,'b',True);lip=scalar(lip,'lip');t=scalar(t,'t',True)
 if isinstance(n,bool) or not isinstance(n,(int,np.integer)) or n<1 or n*(12 if lip else 10)+1>MAX_NODES:raise ValueError('invalid/overbudget mesh')
 if h<=2*t or b<=t or lip<0 or (lip and not t/2<lip<h/2):raise ValueError('invalid geometry')
 a=h-t;bm=b-t if lip else b-t/2;c=lip-t/2
 p=np.array([[bm,c],[bm,0],[0,0],[0,a],[bm,a],[bm,a-c]]) if lip else np.array([[bm,0],[0,0],[0,a],[bm,a]])
 ns=[n,2*n,6*n,2*n,n] if lip else [2*n,6*n,2*n]
 return mesh([p[i]+(p[i+1]-p[i])*j/ns[i] for i in range(len(ns)) for j in range(ns[i])]+[p[-1]])
