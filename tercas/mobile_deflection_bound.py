"""Conservative displacement bound, NOT a new resistance method.

Domain: straight simply supported beam; uniform E, Ig and fixed positive Ml;
full-span UDL and mobile P of concordant signs; existing capped Ief(M) model.
No credit for sheeting/bracing stiffness, no slope/axial/torsional component.
"""
import math

def _finite(value,name,positive=False):
 if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value):
  raise ValueError(f'{name}: número finito obrigatório')
 if positive and value<=0:raise ValueError(f'{name}: deve ser positivo')
 return float(value)

def mobile_deflection_bound(*,L_mm,E_N_mm2,Ig_mm4,Ml_Nmm,q_N_mm,P_N,limit_mm=None):
 L=_finite(L_mm,'L',True);E=_finite(E_N_mm2,'E',True)
 Ig=_finite(Ig_mm4,'Ig',True);Ml=_finite(Ml_Nmm,'Ml',True)
 q=_finite(q_N_mm,'q');P=_finite(P_N,'P')
 if q*P<0:raise ValueError('Envelope limitado a q e P de mesmo sentido')
 if limit_mm is not None:limit_mm=_finite(limit_mm,'Limite de flecha',True)
 try:
  M=abs(q)*L**2/8+abs(P)*L/4
  lam=math.sqrt(M/Ml)
  Imin=Ig if lam<=.673 else min(Ig,Ig*(1-.22/lam)/lam)
  bound=(5*abs(q)*L**4/384+abs(P)*L**3/48)/(E*Imin)
  ratio=bound/limit_mm if limit_mm is not None else None
 except (OverflowError,ZeroDivisionError):
  raise ValueError('Intervalo numérico excedido') from None
 if not all(math.isfinite(v) for v in [M,Imin,bound]) or Imin<=0 or (ratio is not None and not math.isfinite(ratio)):
  raise ValueError('Intervalo numérico excedido')
 return {'schema':'tercas_mobile_deflection_bound_v1','bound_abs_mm':bound,
         'global_Mmax_Nmm':M,'constant_Imin_mm4':Imin,
         'limit_mm':limit_mm,'upper_bound_ratio':ratio,
         'status':('envelope disponível' if ratio is None else
                   'atende pelo limite superior conservador' if ratio<=1 else
                   'limite superior excede: resultado inconclusivo, não reprovação física'),
         'actual_mobile_maximum_computed':False,
         'domain':'viga reta biapoiada, q uniforme e P concordantes, E/Ig/Ml constantes, modelo Ief limitado a Ig',
         'interpretation':'Substituição por Imin global: não é a flecha real calculada nem validação experimental.'}
