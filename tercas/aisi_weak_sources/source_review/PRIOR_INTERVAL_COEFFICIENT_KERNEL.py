"""Outward interval proof for a frozen discrete FSM model (not continuum).
Independent exact-polynomial integration; mpmath.iv endpoints, 180 decimal digits.
No external state changes. IEEE float inputs are interpreted exactly as stored.
"""
from pathlib import Path
from fractions import Fraction
import json,sys,time,hashlib,platform
import numpy as np
import mpmath
from mpmath import iv,mp
from certify import ROOT,R01,BW,sha,dense,assemble,poly,at
iv.dps=180;mp.dps=220
ZERO=iv.mpf(0);ONE=iv.mpf(1)

def point(x):
 if isinstance(x,(float,np.floating)):
  numerator,denominator=float(x).as_integer_ratio()
  return iv.mpf(numerator)/denominator
 return iv.mpf(x)

def low(x):return mp.mpf(x._mpi_[0])
def high(x):return mp.mpf(x._mpi_[1])
def show(x):
 return dict(decimal_approx=[mp.nstr(low(x),60),mp.nstr(high(x),60)],exact_binary_endpoints=[list(v) for v in x._mpi_],encoding='mpmath endpoint tuple (sign, integer mantissa, binary exponent, bit count)')
def midfloat(x):return float((low(x)+high(x))/2)
def rat(q):return iv.mpf(q.numerator)/q.denominator

def integ(a,b,sigma=False):
 r=Fraction(0)
 for i,x in enumerate(a):
  for j,y in enumerate(b):r+=Fraction(x*y,i+j+1+int(sigma))
 return r
# vector basis: local DOF -> (polynomial coefficients in r, power of strip b)
U={0:([1,-1],0),4:([0,1],0)}
DU={0:([-1],-1),4:([1],-1)}
W={2:([1,-1],0),6:([0,1],0)}
DW={2:([-1],-1),6:([1],-1)}
V={1:([1,0,-3,2],0),3:([0,1,-2,1],1),5:([0,0,3,-2],0),7:([0,0,-1,1],1)}
DV={1:([0,-6,6],-1),3:([1,-4,3],0),5:([0,6,-6],-1),7:([0,-2,3],0)}
DDV={1:([-6,12],-2),3:([-4,6],-1),5:([6,-12],-2),7:([-2,6],-1)}

def interval_coefficients(z):
 N=len(z['nodes']);n=4*N
 out=[[[ZERO for _ in range(n)] for _ in range(BW+1)] for _ in range(5)]
 t,E,nu=[point(z[k].item()) for k in ['t','E','nu']]
 C=E/(1-nu*nu);G=E/(2*(1+nu));F=t*t*t*C/12
 specs=[(0,t*C,DU,DU,False),(0,F,DDV,DDV,False),
 (1,-t*C*nu,DU,W,False),(1,-t*C*nu,W,DU,False),
 (1,t*G,U,U,False),(1,t*G,U,DW,False),(1,t*G,DW,U,False),(1,t*G,DW,DW,False),
 (1,-F*nu,DDV,V,False),(1,-F*nu,V,DDV,False),(1,2*F*(1-nu),DV,DV,False),
 (2,t*C,W,W,False),(2,F,V,V,False),
 (3,t,U,U,True),(3,t,V,V,True),(4,t,W,W,True)]
 # Compile exact rational polynomial integrals once.
 terms=[]
 for h,fac,va,vb,stress in specs:
  for i,(a,ea) in va.items():
   for j,(b,eb) in vb.items():
    q=integ(a,b);q1=integ(a,b,True) if stress else Fraction(0)
    if q or q1:terms.append((h,fac,i,j,1+ea+eb,rat(q),rat(q1),stress))
 lengths=[]
 for e in range(N-1):
  dx=point(z['nodes'][e+1,0])-point(z['nodes'][e,0]);dy=point(z['nodes'][e+1,1])-point(z['nodes'][e,1])
  b=iv.sqrt(dx*dx+dy*dy);lengths.append(b);c=dx/b;s=dy/b
  bp={j:b**j for j in range(-3,4)}
  sig0=point(z['stress'][e]);ds=point(z['stress'][e+1])-sig0
  loc=[[[ZERO for _ in range(8)] for _ in range(8)] for _ in range(5)]
  for h,fac,i,j,ex,q,q1,stress in terms:
   weight=q*sig0+q1*ds if stress else q
   loc[h][i][j]+=fac*bp[ex]*weight
  # Local->global congruence, explicitly sparse. Identity on uz/k and theta.
  T={0:[(0,c),(1,s)],1:[(0,-s),(1,c)],2:[(2,ONE)],3:[(3,ONE)],
     4:[(4,c),(5,s)],5:[(4,-s),(5,c)],6:[(6,ONE)],7:[(7,ONE)]}
  for h in range(5):
   for i in range(8):
    for j in range(8):
     if loc[h][i][j]==0:continue
     for gi,ci in T[i]:
      for gj,cj in T[j]:
       if gi>=gj:out[h][gi-gj][4*e+gj]+=ci*loc[h][i][j]*cj
 return out,lengths

def polynomial(c,load):
 lam=point(load)/1000000
 return [c[0],[[x-lam*y for x,y in zip(u,v)] for u,v in zip(c[1],c[3])],
                   [[x-lam*y for x,y in zip(u,v)] for u,v in zip(c[2],c[4])]]

def combine(a,s1,s2):
 return [[a[0][d][i]+s1*a[1][d][i]+s2*a[2][d][i] for i in range(len(a[0][0]))] for d in range(BW+1)]

def interval_ldlt(B):
 n=len(B[0]);L=[[ZERO for _ in range(n)] for _ in range(BW+1)];D=[ZERO]*n
 minratio=mp.inf;minp=mp.inf;maxrelwidth=mp.mpf(0);minindex=None
 for i in range(n):
  v=B[0][i]
  for k in range(max(0,i-BW),i):v-=L[i-k][k]*L[i-k][k]*D[k]
  D[i]=v
  if low(v)<=0:return dict(passed=False,failed_pivot=i,pivot_interval=show(v),reason='pivot lower endpoint is not strictly positive')
  if low(v)<minp:minp=low(v)
  ratio=low(v)/high(B[0][i])
  if ratio<minratio:minratio=ratio;minindex=i
  maxrelwidth=max(maxrelwidth,(high(v)-low(v))/low(v))
  for j in range(i+1,min(n,i+BW+1)):
   v=B[j-i][i]
   for k in range(max(0,j-BW),i):v-=L[i-k][k]*D[k]*L[j-k][k]
   L[j-i][i]=v/D[i]
 return dict(passed=True,pivots=n,min_pivot_lower=str(minp),min_pivot_over_diagonal_upper=str(minratio),
             min_ratio_pivot=minindex,min_pivot_lower_exact_binary=list(minp._mpf_),max_pivot_relative_interval_width=str(maxrelwidth))

def finite_certificate(c,load,bounds):
 if isinstance(load,bool) or not np.isfinite(load) or load<=0:raise ValueError('positive finite load required')
 if len(bounds)<2 or any(Fraction(x)<=0 for x in bounds) or any(Fraction(x)>=Fraction(y) for x,y in zip(bounds,bounds[1:])):raise ValueError('strictly increasing positive exact-decimal partition required')
 a=polynomial(c,load);rows=[]
 for lo,hi in zip(bounds,bounds[1:]):
  l,h=point(lo),point(hi)
  bs=[combine(a,l,l*l),combine(a,(l+h)/2,l*h),combine(a,h,h*h)]
  checks=[interval_ldlt(b) for b in bs]
  row=dict(p_lo_exact_decimal=lo,p_hi_exact_decimal=hi,bernstein=checks,passed=all(x['passed'] for x in checks))
  rows.append(row);print('interval',load,lo,hi,row['passed'],flush=True)
  if not row['passed']:break
 return dict(load_Nmm=load,passed=len(rows)==len(bounds)-1 and all(x['passed'] for x in rows),intervals=rows)

def tail_certificate(z,lengths,load,pstart='385'):
 t,E,nu=[point(z[k].item()) for k in ['t','E','nu']];lam=point(load)/1000000
 smax=point(float(np.max(z['stress'])))
 m=E/(1+abs(nu));G=E/(2*(1+nu))
 # Conservative exact-decimal endpoint bounds, independently checked below.
 bmin_lower=point('0.17664');stress_upper=point('171')
 valid_geometry=all(low(b)>=high(bmin_lower) for b in lengths) and low(stress_upper)>=high(smax)
 denom=m-lam*stress_upper;u=G/2-lam*stress_upper
 membrane_threshold=12*G/(bmin_lower*bmin_lower*denom)
 bending_threshold=12*lam*stress_upper/(m*t*t)
 p=point(pstart)
 return dict(p_tail_exact_decimal=pstart,bmin_lower_exact_decimal='0.17664',sigma_upper_exact_decimal='171',
  valid_input_bounds=bool(valid_geometry),membrane_threshold=show(membrane_threshold),bending_threshold=show(bending_threshold),
  u_coefficient_G_over_2_minus_lambda_sigma=show(u),w_coefficient_m_minus_lambda_sigma=show(denom),
  tail_w_coefficient_at_start=show(denom-12*G/(p*bmin_lower*bmin_lower)),
  tail_v_coefficient_at_start=show(m*t*t/12-lam*stress_upper/p),
  passed=bool(valid_geometry and low(denom)>0 and low(u)>0 and low(p)>high(membrane_threshold) and low(p)>high(bending_threshold)))

def interval_widths(c):
 maxabs=mp.mpf(0);maxrel=mp.mpf(0)
 for cc in c:
  for d in cc:
   for x in d:
    w=high(x)-low(x);maxabs=max(maxabs,w);den=max(abs(low(x)),abs(high(x)))
    if den>0:maxrel=max(maxrel,w/den)
 return dict(max_absolute_width=str(maxabs),max_relative_width=str(maxrel))

def main():
 start=time.time();src=R01/'modes/fine_rounded_n12_a16_web_local_historical_nu0p3.npz';z=np.load(src)
 assert sha(src)=='00a59a885924c8b6d25f99ac7b1d23b6a033085acf21643c68e80531161314d1','frozen NPZ hash mismatch'
 assert z['nodes'].shape==(209,2) and float(z['E'])==200000 and float(z['nu'])==.3 and float(z['t'])==1.2
 c,lengths=interval_coefficients(z);print('interval assembly',time.time()-start,flush=True)
 mid=np.array([[[midfloat(x) for x in d] for d in cc] for cc in c])
 np.savez_compressed(ROOT/'coefficients_interval_midpoints.npz',coefficients=mid)
 # Exact decimal partitions. Selection was exploratory; proof repeats every interval independently.
 bounds=['0.0000006','0.000008','0.0001','0.0012','0.0023','0.0044','0.016','0.2','2.5','31','385']
 finite=finite_certificate(c,850000,bounds);tail=tail_certificate(z,lengths,850000)
 out=dict(schema='discrete_FSM_outward_interval_lower_bound_v1',source=str(src),sha256=sha(src),verifier_source_sha256=sha(Path(__file__)),
 input_identity_matches_pinned_sha256=(sha(src)=='00a59a885924c8b6d25f99ac7b1d23b6a033085acf21643c68e80531161314d1'),
 model=dict(nodes=len(z['nodes']),dofs=4*len(z['nodes']),semi_bandwidth=BW,E_MPa=float(z['E']),nu=float(z['nu']),t_mm=float(z['t']),
            load='uniform pure My, positive, web compressed',N_N=0,Mref_Nmm=1000000,L_mm=4000,boundary='S-S classical single-harmonic FSM'),
 arithmetic=dict(library='mpmath.iv',version=mpmath.__version__,dps=iv.dps,intervals=True,
   integration='Exact rational integrals of polynomial shape functions; interval arithmetic for geometry/material/rotation and assembly',
   frozen_input_interpretation='Each saved IEEE float is its exact binary real value; no uncertainty in input measurement is claimed',
   algorithm='Symmetric band LDLT without pivoting; every interval pivot has lower endpoint > 0',
   distinction='Exploratory numpy.longdouble results are not interval arithmetic and are not the proof',
   platform=platform.platform(),coefficient_widths=interval_widths(c)),
 finite=finite,tail=tail,
 coverage=dict(p_min_exact_decimal=bounds[0],p_tail_exact_decimal=bounds[-1],
   argument='p_n=(n*pi/4000)^2 >= (pi/4000)^2 > 0.0000006; pi>3.14 suffices. Finite contiguous Bernstein intervals plus analytic tail cover all p>=0.0000006.',
   tail_infinite=True,all_positive_integer_harmonics=True),
 lower_bound_Nmm=850000 if finite['passed'] and tail['passed'] else None,
 passed=finite['passed'] and tail['passed'],
 physical_continuum_proof=False,whole_member_approved=False,published=False,
 elapsed_s=time.time()-start)
 (ROOT/'CERTIFICATE.json').write_text(json.dumps(out,indent=2))
 print('CERTIFICATE',out['passed'],time.time()-start,flush=True)

if __name__=='__main__':main()
