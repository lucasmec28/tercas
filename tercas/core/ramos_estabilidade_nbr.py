"""Adapted from reviewed method protocols. See docs/METHOD.md."""
import math

def distortional(family,lip_mm,panel_tension_flange,W,fy,Mdist=None):
 if family=='U' and lip_mm==0 and panel_tension_flange is False:
  return {'status':'not_applicable','source':'NBR14762:2010 9.3 p32: plain U without tension-flange panel exception','MRd_Nmm':None}
 if Mdist is None:return {'status':'not_evaluated','reason':'Mdist required or documented Table14 exemption, not zero/infinity'}
 if not all(math.isfinite(v) and v>0 for v in (W,fy,Mdist)):raise ValueError('positive finite W fy Mdist required')
 lam=math.sqrt(W*fy/Mdist);chi=1 if lam<=.673 else (1-.22/lam)/lam
 return {'status':'computed','source':'NBR14762:2010 9.8.2.3','lambda_dist':lam,'chi_dist':chi,'MRd_Nmm':chi*W*fy/1.1}
