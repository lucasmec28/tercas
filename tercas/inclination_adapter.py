"""Explicit coordinate adapter. No inferred weak-axis capacities or restraints."""
import math
from .inclination import angle, area_actions, self_weight, combine, decompose, simply_supported_state, number
from .load_combinations import uniform_effects
from .mobile_point import same_direction_global_envelope

DEFAULT={'value':0.,'unit':'degrees','spacing_basis':'roof','permanent_basis':'roof','live_basis':'horizontal','wind_basis':'roof'}

def configuration(data):
 cfg=dict(DEFAULT);given=data.get('inclination',{})
 if not isinstance(given,dict) or set(given)-set(DEFAULT):raise ValueError('Configuração de inclinação inválida.')
 cfg.update(given);ang=angle(cfg['value'],cfg['unit'])
 for key in ('spacing_basis','permanent_basis','live_basis','wind_basis'):
  if cfg[key] not in ('roof','horizontal'):raise ValueError('Base de área/distância inválida.')
 return cfg,ang

def adapt_bundle(data,bundle):
 cfg,ang=configuration(data);theta=ang['radians'];a=data['area_inputs']
 cases={'PP':self_weight(data['properties']['mass_kg_m'],theta)}
 for case,key,basis,sgn in [('CP','permanent_kgf_m2','permanent_basis',1),('SC','live_kgf_m2','live_basis',1),('V_Cima','wind_up_kgf_m2','wind_basis',-1),('V_Baixo','wind_down_kgf_m2','wind_basis',1)]:
  cases[case]=area_actions(sgn*a[key],a['spacing_m'],theta,direction='normal' if case.startswith('V_') else 'vertical',spacing_basis=cfg['spacing_basis'],load_area_basis=cfg[basis])
 bundle['inclination']={'configuration':cfg,'angle':ang}
 bundle['case_vectors_N_mm']=cases
 bundle['case_q_N_mm']={k:v['normal'] for k,v in cases.items()}
 bundle['case_effects_at_midspan']={k:uniform_effects(v['normal'],data['L_mm']) for k,v in cases.items()}
 for c in bundle['combinations']:
  q=combine(cases,{k:v for k,v in c['coefficients'].items() if k!='P'})
  p=decompose(c['coefficients'].get('P',0.)*1000,0,theta)
  c.update(q_N_mm=q['normal'],q_kN_m=q['normal'],P_N=p['normal'],q_vector=q,P_vector=p,sign='descendente' if q['normal']>0 else 'ascendente' if q['normal']<0 else 'nulo')
  mid=simply_supported_state(data['L_mm'],data['L_mm']/2,q,p,data['L_mm']/2)['normal']
  c['effects_at_midspan']={'left_reaction_N':mid['Rleft_N'],'right_reaction_N':mid['Rright_N'],'V_N':mid['V_N'],'M_Nmm':mid['M_Nmm'],'midspan_moment_Nmm':mid['M_Nmm'],'max_abs_shear_N':max(abs(mid['Rleft_N']),abs(mid['Rright_N']))}
  if c.get('global_envelope') is not None:c['global_envelope']=same_direction_global_envelope(data['L_mm'],q['normal'],p['normal'])
 bundle['notes']+=['Alma perpendicular à cobertura; vento normal ao plano; PP, CP, SC e P verticais decompostos. Sem travamento da telha.', 'Flexão forte permanece calculável; resistência biaxial/flecha paralela não aprovadas sem dados e método aplicáveis ao eixo fraco.']
 return bundle

def evidence(data,q,p,a):
 cfg,ang=configuration(data);L=data['L_mm'];xs={0.,L,L/2,a}
 for axis in ('normal','parallel'):
  Q=q[axis];P=p[axis]
  if Q:
   ra=Q*L/2+P*(L-a)/L
   for x in (ra/Q,(ra-P)/Q):
    if 0<=x<=L:xs.add(x)
 states=[]
 for x in sorted(xs):
  for side in (('left','right') if x==a else ('right',)):
   states.append(dict(x_mm=x,side=side,**simply_supported_state(L,x,q,p,a,side)))
 demand=any(abs(v)>1e-12 for v in (q['parallel'],p['parallel']))
 return {'angle':ang,'configuration':cfg,'convention':'Eixos locais: normal à cobertura e paralelo ao caimento; alma normal; sem travamento da telha. M e V abaixo são concomitantes por seção/posição, não máximos independentes.', 'q_vector':q,'P_vector':p,'states':states,'parallel_demand':demand,'resistance_status':'Pendente: propriedades/críticos e resistências do eixo fraco por sentido não fornecidos; sem aprovação biaxial.' if demand else 'Sem demanda paralela neste caso; não equivale a aprovação global.', 'weak_property_provenance':None}

def direct_evidence(data):
 result={}
 for state,key in [('ELU','uls'),('ELS','sls')]:
  q={'normal':data['q_'+key],'parallel':number(data.get('q_parallel_'+key,0.),'q paralelo')}
  p={'normal':data['P_'+key],'parallel':number(data.get('P_parallel_'+key,0.),'P paralelo')}
  result[state]=evidence(data,q,p,data['x_'+key])
  result[state]['convention']+=' Modo direto: cargas já locais e combinadas; não há rotação nem PP automático.'
 return result

def pending_rows(ev,state):
 if not ev['parallel_demand']:return []
 names=[('Flexão biaxial','NBR 14762 §9.9'),('Cortante paralelo às mesas','Rota não implementada')] if state=='ELU' else [('Flecha paralela à cobertura','Rota não implementada')]
 return [{'Verificação':name,'Situação':'Pendente — componente paralela não verificada','Índice':None,'Demanda / valor':f"q paralelo={ev['q_vector']['parallel']:.6f} kN/m; P paralelo={ev['P_vector']['parallel']/1000:.6f} kN",'Resistência / limite':'Não definida para eixo/sentido','Referência':ref,'Observação':ev['resistance_status']+' Não reutiliza capacidades do eixo forte nem VRd da alma.'} for name,ref in names]
