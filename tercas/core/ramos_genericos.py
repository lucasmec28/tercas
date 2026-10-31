"""Adapted from reviewed method protocols. See docs/METHOD.md."""
import math
from .flt_vrd import weff_ratio
from .ramos_estabilidade_nbr import distortional
from .ue_nbr import table14
from .envelope_mv import envelope
from .introducao_um_vao import support
from .anexo_d import frd

def calculate(spec,base):
 f=spec['selected_section']['fields'];v=lambda k:f[k]['value'];family=spec['selected_section']['family'];result={}
 W=v('Wx_cm3');fy=v('fy_MPa');critical=spec.get('Ml') if isinstance(spec.get('Ml'),dict) else {};Ml=critical.get('value')
 good=lambda a:isinstance(a,(int,float)) and not isinstance(a,bool) and math.isfinite(a) and a>0
 if good(W) and good(fy) and good(Ml) and isinstance(critical.get('origin'),str) and critical['origin'].strip():
  local=W*1000*fy*weff_ratio(math.sqrt(W*1000*fy/Ml))[0]/1.1
  result['local']={'status':'computed','MRd_Nmm':local,'property_convention_pending':spec['selected_section']['source_geometry_convention_unresolved']}
 else:local=None;result['local']={'status':'not_evaluated','missing':'W,fy,Ml and critical origin'}
 if family=='U' and v('lip')==0:result['distortional']=distortional('U',0,False,1,1)
 elif family=='Ue':
  try:
   gate=table14(v('h'),v('bf'),v('lip'),v('t'))
   if gate['exempt']:result['distortional']={'status':'exempt_Table14','table':gate}
   else:
    md=spec.get('Mdist',{});mdv=md.get('value') if isinstance(md,dict) else None
    if not good(W) or not good(fy) or not good(mdv) or not isinstance(md.get('origin'),str) or not md['origin'].strip():result['distortional']={'status':'not_evaluated','missing':'W,fy and Mdist with origin','table':gate}
    else:result['distortional']={**distortional('Ue',v('lip'),False,W*1000,fy,mdv),'Mdist_origin':md['origin']}
  except (ValueError,TypeError) as e:result['distortional']={'status':'invalid_inputs','reason':str(e)}
 else:result['distortional']={'status':'outside_implemented_family'}
 u=spec.get('ULS') if isinstance(spec.get('ULS'),dict) else {};L=spec.get('L_mm');vr=base.get('section_checks',{}).get('shear',{}).get('VRd_N')
 if local and vr and isinstance(u.get('origin'),str) and u['origin'].strip():
  try:
   best,_=envelope(L,u['q_Nmm'],u['P_N'],u['x_mm'],u['x_mm'],local,vr)
   result['MV']={'status':'computed_fixed_load_position','result':best,'source':'NBR9.8.4 same position and combination; local MRd denominator'}
  except (ValueError,TypeError,KeyError) as e:result['MV']={'status':'not_evaluated','reason':str(e)}
 else:result['MV']={'status':'not_evaluated','missing':'local MRd,VRd,ULS origin and actions'}
 bf0=v('bf')+(v('lip') if family=='Ue' else 0)
 result['shear_lag_domain']={'status':'not_triggered_by_length' if isinstance(L,(int,float)) and L>=30*bf0 else 'actual_free_flange_width_needed_to_decide_9_4','L_mm':L,'bf0_upper_bound_mm':bf0,'scope':'sufficient length screen using nominal width upper bound; failing bound is NOT proof shear lag required'}
 intro=spec.get('introduction') if isinstance(spec.get('introduction'),dict) else {};result['supports']={}
 for name in ['left','right']:
  s=intro.get(name) if isinstance(intro.get(name),dict) else {}
  result['supports'][name]=support(s.get('route'),s.get('origin'))
 patch=intro.get('point') if isinstance(intro.get('point'),dict) else {}
 try:
  if not patch or not isinstance(patch.get('origin'),str) or not patch['origin'].strip():raise ValueError('point patch geometry and origin missing')
  c=patch['c_mm'];x=u['x_mm'];h=v('h')-2*(v('ri_mm')+v('t'));dist=min(x-c/2,L-x-c/2)
  if not all(good(a) for a in [c,h,fy,u['P_N']]) or dist<=1.5*h:raise ValueError('outside isolated internal positive patch subset')
  if any(s['status']!='stiffener_exception_9_5_1' for s in result['supports'].values()):raise ValueError('current patch subset needs declared end-web connections; flange contacts need separate geometry')
  cap=frd(h=h,t=v('t'),ri=v('ri_mm'),c=c,fy=fy,end_distance=dist,opposite_clear_distance=dist,connected=False,lip=family=='Ue')
  result['point']={'status':'computed','FRd_N':cap,'force_N':u['P_N'],'index':u['P_N']/cap,'patch_mm':[x-c/2,x+c/2],'origin':patch['origin']}
 except (ValueError,TypeError,KeyError) as e:result['point']={'status':'not_evaluated','reason':str(e)}
 try:
  from .travamentos_nbr import segment_moments
  if not isinstance(u.get('origin'),str) or not u['origin'].strip():raise ValueError('ULS provenance missing')
  M=segment_moments(L,u['q_Nmm'],u['P_N'],u['x_mm'],0,L)['Mmax_Nmm']
  for name in ['local','distortional']:
   cap=result[name].get('MRd_Nmm')
   if cap:result[name].update(Msd_Nmm=M,index=M/cap,criterion_status='meets' if M<=cap else 'fails')
 except (ValueError,TypeError,KeyError):
  for name in ['local','distortional']:
   if result[name].get('MRd_Nmm'):result[name]['criterion_status']='not_evaluated_missing_valid_ULS'
 return result
