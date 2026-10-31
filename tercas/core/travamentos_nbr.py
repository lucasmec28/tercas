"""Adapted from reviewed method protocols. See docs/METHOD.md."""
import math
from .flt_vrd import flt_mse

def moment(x,L,q,P,a):return q*x*(L-x)/2+P*((L-a)*x/L if x<=a else a*(L-x)/L)

def segment_moments(L,q,P,a,start,end):
 if not all(math.isfinite(v) for v in [L,q,P,a,start,end]) or not 0<=start<end<=L or not 0<=a<=L:raise ValueError('invalid segment/action geometry')
 pts=[start,end]
 if start<a<end:pts.append(a)
 Ra=q*L/2+P*(L-a)/L
 if q:
  for lo,hi,offset in [(start,min(a,end),0),(max(start,a),end,P)]:
   root=(Ra-offset)/q
   if lo<root<hi:pts.append(root)
 vals=[abs(moment(x,L,q,P,a)) for x in pts];M=max(vals)
 quarters=[abs(moment(start+(end-start)*f,L,q,P,a)) for f in [.25,.5,.75]]
 cb=1 if M==0 else 12.5*M/(2.5*M+3*quarters[0]+4*quarters[1]+3*quarters[2])
 return {'Mmax_Nmm':M,'quarter_moments_Nmm':quarters,'Cb_from_moments':cb}

def evaluate_segment(section,actions,segment):
 if section.get('route_domain')!='strong_symmetry_CT_no_primary_torsion':return {'status':'route_domain_not_declared','other_checks_may_continue':True,'reason':'subroutine requires declared NBR strong-axis expression domain; not generic any-profile stability'}
 moments=segment_moments(**actions,start=segment['start_mm'],end=segment['end_mm'])
 required=['Ly_effective_mm','Lz_effective_mm','restraint_provenance']
 missing=[k for k in required if segment.get(k) is None or (k=='restraint_provenance' and (not isinstance(segment[k],str) or not segment[k].strip()))]
 if missing:return {'moments':moments,'status':'FLT_not_evaluated','missing':missing,'other_checks_may_continue':True}
 ly,lz=segment['Ly_effective_mm'],segment['Lz_effective_mm']
 if not all(isinstance(v,(int,float)) and not isinstance(v,bool) and math.isfinite(v) and v>0 for v in [ly,lz]):raise ValueError('positive effective lengths required')
 mode=segment.get('Cb_mode','one')
 if mode not in ['one','quarter_formula']:raise ValueError('unsupported Cb mode')
 cb=1 if mode=='one' else moments['Cb_from_moments']
 E,G,Iy,J,Cw=[section[k] for k in ['E','G','Iy','J','Cw']]
 if not all(math.isfinite(v) and v>0 for v in [E,G,Iy,J,Cw]):raise ValueError('positive finite properties required')
 Me=cb*math.pi/ly*math.sqrt(E*Iy*(G*J+math.pi**2*E*Cw/lz**2))
 f=flt_mse(section['W'],section['fy'],section['Ml'],Me)
 return {'status':'computed_from_supplied_effective_lengths','moments':moments,'Cb_used':cb,'Me_Nmm':Me,'FLT':f,'index':moments['Mmax_Nmm']/f['MRd_flt_Nmm'],'restraint_provenance':segment['restraint_provenance'],'whole_member_approved':False,'condition':'NBR expression domain and effective lengths supplied; physical stiffness/strength not established by coordinates alone'}
