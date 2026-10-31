"""User-supplied area combinations: each state is evaluated independently."""
import copy,math
from .application import calculate,rows,fingerprint,VERSION,build_spec,finite
from .load_combinations import combine_area_actions,COMBINATION_TYPES
from .point_combinations import point_combinations
from .envelope_mv import envelope

def area_bundle(data):
 if data.get('load_mode')!='area':raise ValueError('Modo de área não selecionado.')
 area=data.get('area_inputs')
 if not isinstance(area,dict):raise ValueError('Entradas de área ausentes.')
 if set(area)!={'spacing_m','permanent_kgf_m2','live_kgf_m2','wind_up_kgf_m2','wind_down_kgf_m2'}:raise ValueError('Conjunto de ações de área inválido.')
 types=data.get('selected_types')
 if not types:raise ValueError('Selecione pelo menos um tipo de combinação.')
 for key in ['ELS_down_denominator','ELS_up_denominator']:
  v=data.get(key)
  if not finite(v) or v<=0:raise ValueError('Informe denominador positivo para o limite ELS.')
 bundle=combine_area_actions(L_mm=data['L_mm'],selected_types=types,mass_kg_m=data['properties']['mass_kg_m'],**area)
 # Contact is a local-resistance input, not a prerequisite or restriction for
 # the normative mathematical point-load global envelope.
 bundle['combinations']+=point_combinations(L_mm=data['L_mm'],case_q_N_mm=bundle['case_q_N_mm'],selected_types=types)
 bundle['notes']+=['P = 1 kN de manutenção, isolada de SC e vento: quatro ELU e uma ELS rara conforme seleção; NBR 6120 §6.4 / NBR 14762.', 'Sem comprimento de contato obrigatório: apenas a resistência local pode ficar pendente.']
 from .inclination_adapter import adapt_bundle
 return adapt_bundle(data,bundle)

def case_inputs(data,combo):
 d=copy.deepcopy(data);q=combo['q_N_mm'];L=d['L_mm']
 # Internal adapter evaluates q in both states; only the requested state below
 # is retained, reported and exported. There is no fictitious zero combination.
 d.update(q_parallel_uls=combo.get('q_vector',{}).get('parallel',0.),q_parallel_sls=combo.get('q_vector',{}).get('parallel',0.),P_parallel_uls=combo.get('P_vector',{}).get('parallel',0.),P_parallel_sls=combo.get('P_vector',{}).get('parallel',0.))
 d.update(load_mode='direct',q_uls=q,q_sls=q,P_uls=combo.get('P_N',0.),P_sls=combo.get('P_N',0.),x_uls=L/2,x_sls=L/2,actions_origin=f"{combo['id']} — {combo['type']} — {combo['expression']} — {combo.get('origin','matriz fornecida por Lucas')}")
 if combo['limit_state']=='ELS':
  denom=d['ELS_down_denominator'] if q>=0 else d['ELS_up_denominator']
  d.update(ELS_limit_mm=L/denom,ELS_origin=f"L/{denom:g} informado para {'descendente' if q>=0 else 'ascendente'}; {combo['type']}")
 return d

def calculate_batch(data):
 bundle=area_bundle(data);cases=[]
 # Direct-mode actions are inactive here, including point-load coordinates.
 build_spec(case_inputs(data,bundle['combinations'][0]))
 for combo in bundle['combinations']:
  d=case_inputs(data,combo);result=calculate(d)
  rs=[r for r in rows(result) if (r['Verificação'] in ('Flecha — flexão','Flecha paralela à cobertura'))==(combo['limit_state']=='ELS')]
  mobile={}
  if combo.get('P_N',0):mobile=mobile_rows(rs,result,combo)
  evidence=({'ELS':result['ELS']} if combo['limit_state']=='ELS' else {k:result[k] for k in ['NBR_branches','FLT_segments','section_checks']})
  if mobile:evidence['mobile_point']=mobile
  from .inclination_adapter import pending_rows
  from .inclination_adapter import evidence as inclination_evidence
  ev=inclination_evidence(data,combo['q_vector'],combo['P_vector'],data['L_mm']/2)
  if mobile:ev['convention']+=' P móvel: estados exibidos para candidato central, não envelope biaxial móvel.'
  evidence['inclination']=ev
  # Core rows already contain ELU pending rows, but ELS filtering excludes its parallel component.
  # All rows filtered by limit state above.
  cases.append({'combination':combo,'rows':rs,'evidence':evidence,'warnings':result['coverage_warnings']+result['numerical_warnings']})
 return {'schema':'tercas_batch_results_v1','version':VERSION,'project':data['project'],'synthetic':data['synthetic'],'input_fingerprint':fingerprint(data),'input_data':copy.deepcopy(data),'load_bundle':bundle,'cases':cases,'whole_member_approved':False,'summary':governing(cases)}

def governing(cases):
 groups={}
 for case in cases:
  for row in case['rows']:
   groups.setdefault(row['Verificação'],[]).append((case['combination'],row))
 out=[]
 for name,items in groups.items():
  numeric=[(c,r) for c,r in items if finite(r.get('Índice'))]
  c,r=max(numeric,key=lambda x:x[1]['Índice']) if numeric else items[0]
  entry=copy.deepcopy(r);entry['Combinação']=f"{c['id']} — {c['type']}";entry['q [kN/m]']=c['q_kN_m'];entry['Casos avaliados']=len(numeric)
  pending=sum(1 for _,rr in items if not finite(rr.get('Índice')) and rr['Situação'] not in ('Não aplicável','Dispensado pela Tabela 14','Não acionado pelo comprimento'))
  entry['Casos pendentes']=pending
  if pending:
   entry['Situação']='Parcial — '+entry['Situação'];entry['Observação']+=f' {pending} combinação(ões) sem índice; o máximo numérico não cobre essas pendências.'
  out.append(entry)
 return out


def mobile_rows(rs,result,combo):
 """Exact global same-direction envelopes; partial routes remain pending."""
 env=combo['global_envelope'];L=result['input_data']['L_mm']
 b=result['NBR_branches'];vr=result['section_checks'].get('shear',{}).get('VRd_N')
 mr=b['local'].get('MRd_Nmm');ev={'global_envelope':env,'method':'Biapoiada; permanentes uniformes e P móvel; máximos M/V não simultâneos.'}
 best=None
 if mr and vr:
  best,_=envelope(L,combo['q_N_mm'],combo['P_N'],0.,L,mr,vr)
  ev['MV_concomitant']=best
 for row in rs:
  name=row['Verificação'];idx=None
  if name=='Cortante' and vr:
   idx=env['V_abs_N']/vr;row['Demanda / valor']=f"{env['V_abs_N']/1000:.6f} kN"
   row['Observação']='Envelope global: limite com P aproximando-se do apoio, não P aplicada exatamente no apoio.'
  elif name=='Flexão e cortante concomitantes' and best:
   idx=best['index_squared'];row['Observação']=f"Envelope concomitante: posição P={best['a_mm']:.3f} mm; seção x={best['x_mm']:.3f} mm; limite de apoio={best['support_limit']}. Não soma máximos M/V independentes."
  elif name in ('Flexão local','Distorcional'):
   row['Observação']+=' Máximo global de momento com P no centro (permanentes e P no mesmo sentido).'
  elif name.startswith('FLT —') or name=='Flecha — flexão' or name=='Carga concentrada':
   ev[name]={'central_candidate_index':row.get('Índice'),'central_candidate_value':row['Demanda / valor']}
   central_index=row.get('Índice')
   known_failure=finite(central_index) and central_index>1
   row['Índice']=central_index if known_failure else None
   row['Situação']='Não atende já no candidato central — envelope parcial' if known_failure else 'Pendente — envelope móvel parcial'
   row['Observação']+=' P avaliada no centro somente; valor exibido é candidato, não envelope móvel qualificado desta rota.'
   if name=='Carga concentrada' and result['input_data'].get('patch_mm') is None:row['Observação']+=' Sem contato físico informado, resistência local permanece pendente; cálculos globais continuam.'
  if idx is not None:
   row['Índice']=idx;row['Situação']='Não atende' if idx>1 else 'Atende ao critério calculado'
 return ev
