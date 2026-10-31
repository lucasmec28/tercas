"""Adapted from reviewed method protocols. See docs/METHOD.md."""
import math

def pos(*args):
 if any(not math.isfinite(x) or x<=0 for x in args):raise ValueError('positive finite inputs required')

def chi_flt(lam):
 if not math.isfinite(lam) or lam<0:raise ValueError('finite nonnegative slenderness required')
 if lam<=.6:return 1.,'stocky'
 if lam<1.336:return 1.11*(1-.278*lam**2),'intermediate'
 return 1/lam**2,'elastic'

def weff_ratio(lam):
 if not math.isfinite(lam) or lam<0:raise ValueError('finite nonnegative slenderness required')
 return (1.,'gross') if lam<=.673 else ((1-.22/lam)/lam,'effective')

def flt_mse(Wc_mm3,Fy_MPa,Ml_Nmm,Me_Nmm):
 pos(Wc_mm3,Fy_MPa,Ml_Nmm,Me_Nmm)
 lam0=math.sqrt(Wc_mm3*Fy_MPa/Me_Nmm);chi,branch=chi_flt(lam0)
 lamp=math.sqrt(chi*Wc_mm3*Fy_MPa/Ml_Nmm);rho,localbranch=weff_ratio(lamp)
 return dict(lambda0=lam0,chi_flt=chi,flt_branch=branch,lambda_p_reduced_stress=lamp,local_branch=localbranch,Wceff_mm3=Wc_mm3*rho,MRd_flt_Nmm=chi*Wc_mm3*rho*Fy_MPa/1.1,gamma=1.1,scope='MSE 9.8.2.2 only; Me/Ml supplied and qualified externally; not total capacity')

def vrd(h_mm,t_mm,Fy_MPa,E_MPa):
 pos(h_mm,t_mm,Fy_MPa,E_MPa)
 kv=5.;ratio=h_mm/t_mm;s=math.sqrt(E_MPa*kv/Fy_MPa);lo=1.08*s;hi=1.4*s
 if ratio<=lo:v=.6*Fy_MPa*h_mm*t_mm/1.1;b='yield'
 elif ratio<=hi:v=.65*t_mm**2*math.sqrt(kv*Fy_MPa*E_MPa)/1.1;b='intermediate'
 else:v=.905*E_MPa*kv*t_mm**3/h_mm/1.1;b='elastic'
 return dict(VRd_N=v,branch=b,h_over_t=ratio,lower=lo,upper=hi,kv=kv,gamma=1.1,scope='9.8.3 single flat web without transverse shear stiffeners; no concentrated-force check')
