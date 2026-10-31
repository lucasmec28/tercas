"""Adapted from reviewed method protocols. See docs/METHOD.md."""
import math
from numpy.polynomial import Polynomial as Poly

def envelope(L,q,P,amin,amax,MR,VR):
 if not all(math.isfinite(v) for v in [L,q,P,amin,amax,MR,VR]) or L<=0 or MR<=0 or VR<=0 or not 0<amin<=amax<L:raise ValueError('invalid input')
 out=[]
 def add(m,v,lo,hi,tag,apos):
  u=(m/MR)**2+(v/VR)**2
  xx=[lo,hi]+[float(z.real) for z in u.deriv().roots() if abs(z.imag)<1e-7 and lo<z.real<hi]
  for x in xx:out.append({'x_mm':x,'a_mm':x if apos is None else apos,'branch':tag,'index_squared':float(u(x))})
 for a in [amin,amax]:
  ra=q*L/2+P*(1-a/L)
  add(Poly([0,ra,-q/2]),Poly([ra,-q]),0,a,'a_bound_left',a)
  add(Poly([P*a,ra-P,-q/2]),Poly([ra-P,-q]),a,L,'a_bound_right',a)
 m=Poly([0,q*L/2+P,-q/2-P/L])
 add(m,Poly([q*L/2+P,-q-P/L]),amin,amax,'a_equals_x_left',None)
 add(m,Poly([q*L/2,-q-P/L]),amin,amax,'a_equals_x_right',None)
 return max(out,key=lambda t:t['index_squared']),out
