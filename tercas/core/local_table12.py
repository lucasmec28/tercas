"""NBR 14762:2010 §9.8.2.1(b), Table12 cases a/b (printed45/46; PDF51/52).
Nominal dimensions, strong-axis bending only. Elastic critical, not resistance.
"""
import math
SOURCE='ABNT NBR 14762:2010 §9.8.2.1(b), Tabela 12; pp.45–46 (PDF51–52)'

def local_critical(family,bw_mm,bf_mm,t_mm,Wc_mm3,E_MPa=200000.,nu=.3,D_mm=0.):
 for value in (bw_mm,bf_mm,t_mm,Wc_mm3,E_MPa):
  if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value) or value<=0:raise ValueError('Dimensões, Wc e E devem ser positivos e finitos.')
 if isinstance(nu,bool) or not isinstance(nu,(int,float)) or not math.isfinite(nu) or not -1<nu<.5:raise ValueError('Coeficiente de Poisson inválido.')
 if isinstance(D_mm,bool) or not isinstance(D_mm,(int,float)) or not math.isfinite(D_mm) or D_mm<0:raise ValueError('Enrijecedor inválido.')
 eta=bf_mm/bw_mm;mu=D_mm/bw_mm
 if family=='U':
  if D_mm!=0 or not .1<=eta<=1:raise ValueError('Tabela12(a): U simples, D=0 e 0,1≤bf/bw≤1,0.')
  k=eta**-1.843;case='a'
 elif family=='Ue':
  if not .2<=eta<=1 or not .1<=mu<=.3:raise ValueError('Tabela12(b): 0,2≤bf/bw≤1,0 e 0,1≤D/bw≤0,3.')
  a=81-730*eta+4261*eta**2-12304*eta**3+17919*eta**4-12796*eta**5+3574*eta**6
  b=0 if mu<=.2 or eta>.6 else 320-2788*eta+13458*eta**2-27667*eta**3+19167*eta**4
  k=a-b*(mu-.2);case='b'
 else:raise ValueError('Família fora das duas rotas implementadas.')
 if k<=0:raise ValueError('Coeficiente local não positivo; conferir domínio.')
 Ml=k*math.pi**2*E_MPa/(12*(1-nu**2))*(t_mm/bw_mm)**2*Wc_mm3
 return {'Ml_Nmm':Ml,'kl':k,'eta':eta,'mu':mu,'case':case,'origin':SOURCE,'whole_member_approved':False}
