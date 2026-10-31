"""User-supplied area combinations: each state is evaluated independently."""
import copy,math
from .application import calculate,rows,fingerprint,VERSION,build_spec,finite
from .load_combinations import combine_area_actions,COMBINATION_TYPES

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
 return combine_area_actions(L_mm=data['L_mm'],selected_types=types,mass_kg_m=data['properties']['mass_kg_m'],**area)

def case_inputs(data,combo):
 d=copy.deepcopy(data);q=combo['q_N_mm'];L=d['L_mm']
 # Internal adapter evaluates q in both states; only the requested state below
 # is retained, reported and exported. There is no fictitious zero combination.
 d.update(load_mode='direct',q_uls=q,q_sls=q,P_uls=0.,P_sls=0.,x_uls=L/2,x_sls=L/2,actions_origin=f"{combo['id']} — {combo['type']} — {combo['expression']} — matriz fornecida por Lucas")
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
  rs=[r for r in rows(result) if (r['Verificação']=='Flecha — flexão')==(combo['limit_state']=='ELS')]
  evidence=({'ELS':result['ELS']} if combo['limit_state']=='ELS' else {k:result[k] for k in ['NBR_branches','FLT_segments','section_checks']})
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
