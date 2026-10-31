"""Restricted Annex E / 9.9 integration. No unqualified catalogue criticals."""
import math
from .inclination import annex_e_critical, weak_resistance, biaxial_interaction, number
from .core.travamentos_nbr import moment

FIELDS=('W_mm3','Wc_mm3','Ml_Nmm','Mdist_Nmm','Nex_N','Nez_N','r0_mm','j_mm','Cm')
def validate(data):
 cfg=data.get('weak_axis',{})
 if not isinstance(cfg,dict) or set(cfg)-{'positive','negative'}:raise ValueError('Eixo fraco: configuração inválida.')
 for sign,s in cfg.items():
  if not isinstance(s,dict) or set(s)-set(FIELDS)-{'Cs','provenance','plain_u_no_distortion','provisional_hypothesis'}:raise ValueError('Eixo fraco: campos inválidos.')
  for k in FIELDS:
   if s.get(k) is not None:number(s[k],k,positive=k not in ('j_mm',))
  if s.get('Cm') is not None and s['Cm']!=1:raise ValueError('Nesta rota simplificada, Cm = 1,0. Redução requer enquadramento do diagrama e não é aceita automaticamente.')
  if s.get('Cs') is not None and (s['Cs'] not in (-1,1) or isinstance(s['Cs'],bool)):raise ValueError('Cs deve ser +1 ou −1.')
  if not isinstance(s.get('provenance',''),str):raise ValueError('Origem do eixo fraco deve ser texto.')
  if not isinstance(s.get('provisional_hypothesis',False),bool):raise ValueError('Marcador de hipótese provisória inválido.')
  if not isinstance(s.get('plain_u_no_distortion',False),bool):raise ValueError('Dispensa distorcional inválida.')
 return cfg

def capacities(data,family):
 cfg=validate(data);out={}
 auto=None
 if data.get('weak_catalog') is not None:
  from .weak_catalog import automatic_inputs
  try:auto=automatic_inputs(data)
  except (ValueError,TypeError,KeyError) as exc:auto={'status':'not_evaluated','missing':['Dados do catálogo/linha média: '+str(exc)],'signs':{}}
 for sign in ('positive','negative'):
  s=dict(cfg.get(sign,{}))
  if auto is not None:
   if auto['status']!='computed_catalog_inputs':
    out[sign]={'status':'not_evaluated','missing':auto['missing'],'automatic_inputs':auto};continue
   critical_origin=s.get('provenance','')
   s.update(auto['signs'][sign]);s['provenance']+='; críticos: '+critical_origin
   if not critical_origin.strip():
    out[sign]={'status':'not_evaluated','missing':['origem dos críticos para este sentido'],'automatic_inputs':auto};continue
  missing=[k for k in ('W_mm3','Wc_mm3','Ml_Nmm','Nex_N','Nez_N','r0_mm','j_mm','Cm','Cs') if s.get(k) is None]
  if not s.get('provenance','').strip():missing.append('origem da seção, eixo, sentido, vínculos e críticos')
  if missing:out[sign]={'status':'not_evaluated','missing':missing};continue
  me=annex_e_critical(**{k:s[k] for k in ('Nex_N','Nez_N','r0_mm','j_mm','Cs','Cm')},provenance=s['provenance'])
  out[sign]=weak_resistance(W_mm3=s['W_mm3'],Wc_mm3=s['Wc_mm3'],fy_MPa=data['properties']['fy_MPa'],Me_Nmm=me['Me_Nmm'],Ml_Nmm=s['Ml_Nmm'],Mdist_Nmm=s.get('Mdist_Nmm'),distortional_not_applicable=s.get('plain_u_no_distortion',False),family=family,provenance=s['provenance'])
  if auto is not None:out[sign]['automatic_inputs']=auto
  out[sign]['annex_e']=dict(me,Cm_adopted=1.0,Cm_policy='Rota simplificada: Cm=1 em todas as combinações, sem redução automática.')
 return out

def strong_capacity(result):
 """Whole-span conservative minimum; require all demanded strong branches."""
 caps=[];b=result['NBR_branches']
 for name in ('local','distortional'):
  r=b[name]
  if r.get('status') in ('not_applicable','exempt_Table14'):continue
  if not r.get('MRd_Nmm'):return None
  caps.append(r['MRd_Nmm'])
 if result['coverage_warnings']:return None
 for r in result['FLT_segments']:
  if r.get('status')=='not_applicable':continue
  branches=r.get('flange_results') or [r]
  for branch in branches:
   v=branch.get('FLT',{}).get('MRd_flt_Nmm')
   if not v:return None
   caps.append(v)
 return min(caps) if caps else None

def interaction_envelope(L,qx,px,qy,py,a,mrx,caps):
 """Exact maximum of |Mx|/Rx+|My|/Ry for FIXED P and constant capacities.
 Sign boundaries and stationary points in every polynomial interval; no grid.
 """
 pts={0.,a,L}
 def coefficients(q,p,side):return (-q/2,q*L/2+p*(L-a)/L-(p if side else 0),p*a if side else 0)
 for lo,hi,side in ((0,a,False),(a,L,True)):
  for q,p in ((qx,px),(qy,py)):
   A,B,C=coefficients(q,p,side)
   if A:
    disc=B*B-4*A*C
    if disc>=0:
     for x in ((-B-math.sqrt(disc))/(2*A),(-B+math.sqrt(disc))/(2*A)):
      if lo<x<hi:pts.add(x)
   elif B:
    x=-C/B
    if lo<x<hi:pts.add(x)
 base=sorted(pts);missing=set()
 for lo,hi in zip(base,base[1:]):
  mid=(lo+hi)/2;mx=moment(mid,L,qx,px,a);my=moment(mid,L,qy,py,a)
  sy='positive' if my>=0 else 'negative';ry=caps.get(sy,{}).get('MRd_Nmm')
  if abs(my)>1e-10 and not ry:missing.add(sy);continue
  if abs(mx)>1e-10 and mrx is None:missing.add('strong');continue
  ax,bx,_=coefficients(qx,px,mid>a);ay,by,_=coefficients(qy,py,mid>a)
  sx=1 if mx>=0 else -1;sgny=1 if my>=0 else -1
  A=(sx*ax/mrx if mrx else 0)+(sgny*ay/ry if ry else 0)
  B=(sx*bx/mrx if mrx else 0)+(sgny*by/ry if ry else 0)
  if A:
   x=-B/(2*A)
   if lo<x<hi:pts.add(x)
 samples=[]
 for x in sorted(pts):
  mx=moment(x,L,qx,px,a);my=moment(x,L,qy,py,a);ry=caps.get('positive' if my>=0 else 'negative',{}).get('MRd_Nmm')
  if (abs(mx)>1e-10 and not mrx) or (abs(my)>1e-10 and not ry):continue
  idx=(abs(mx)/mrx if mrx else 0)+(abs(my)/ry if ry else 0)
  samples.append(dict(x_mm=x,Mx_Nmm=mx,My_Nmm=my,index=idx))
 best=max(samples,key=lambda s:s['index']) if samples else None
 return dict(status='not_evaluated' if missing else 'computed_fixed_position',missing=sorted(missing),governing=best,candidate_count=len(pts),whole_member_approved=False)

def integrate(result):
 d=result['input_data'];ev=result['inclination_evidence']['ELU']
 if not ev['parallel_demand']:return
 fam=result['input_snapshot']['selected_section']['family'];caps=capacities(d,fam);rx=strong_capacity(result)
 z=interaction_envelope(d['L_mm'],d['q_uls'],d['P_uls'],d.get('q_parallel_uls',0),d.get('P_parallel_uls',0),d['x_uls'],rx,caps)
 ev['provisional_hypothesis']=any(s.get('provisional_hypothesis',False) or 'HIPÓTESE PROVISÓRIA' in s.get('provenance','').upper() for s in d.get('weak_axis',{}).values())
 ev['weak_axis_capacities']=caps;ev['biaxial']=z;ev['strong_capacity_Nmm']=rx
 ev['resistance_status']='Interação §9.9 calculada na posição fixa de P; resistências condicionadas aos dados rastreados. Sem aprovação global.' if z['status']=='computed_fixed_position' else 'Interação §9.9 pendente: '+', '.join({'positive':'resistência para My positivo','negative':'resistência para My negativo','strong':'resistência completa do eixo forte'}.get(k,k) for k in z['missing'])

def rows(ev):
 z=ev.get('biaxial',{});g=z.get('governing') or {};complete=z.get('status')=='computed_fixed_position';idx=g.get('index') if complete or g.get('index',0)>1 else None
 status=('Não atende' if idx>1 else 'Atende ao critério calculado') if complete and idx is not None else 'Parcial — faltam resistências por eixo/sentido'
 if ev.get('provisional_hypothesis'):status+=' — hipótese provisória, a conferir'
 return {'Verificação':'Flexão biaxial','Situação':status,'Índice':idx,'Demanda / valor':f"Seção x={g.get('x_mm','—')} mm; Mx={g.get('Mx_Nmm','—')} Nmm; My={g.get('My_Nmm','—')} Nmm",'Resistência / limite':'|Mx|/MxRd + |My|/MyRd ≤ 1; N=0','Referência':'NBR 14762 §9.9; Anexo E; §9.8.2','Observação':ev['resistance_status']+' Menor resistência forte dos trechos, conservadora. Momentos concomitantes; não soma máximos independentes. Dados fracos nunca importados bilateralmente de Pierin.'}
