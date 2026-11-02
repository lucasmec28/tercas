"""User-supplied area combinations: each state is evaluated independently."""
import copy,math
from .application import calculate,rows,fingerprint,VERSION,build_spec,finite
from .load_combinations import combine_area_actions,COMBINATION_TYPES
from .point_combinations import point_combinations


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
 bundle['notes']+=['P = 1 kN de manutenção, isolada de SC e vento: quatro ELU e uma ELS rara conforme seleção; NBR 6120 §6.4 / NBR 14762.', 'P avaliada em duas posições prescritas: centro e limite junto ao apoio; sem varredura de posições intermediárias.']
 from .inclination_adapter import adapt_bundle
 bundle=adapt_bundle(data,bundle)
 expanded=[]
 for c in bundle['combinations']:
  if not c.get('P_N'):expanded.append(c);continue
  for position,suffix in [('center','CENTRO'),('support_limit','APOIO')]:
   cc=copy.deepcopy(c);cc.update(id=c['id']+'_'+suffix,point_position=position,x_mm=data['L_mm']/2 if position=='center' else 0.)
   if position=='support_limit':
    q=cc['q_N_mm'];P=cc['P_N'];L=data['L_mm']
    cc['effects_at_midspan']={'left_reaction_N':q*L/2+P,'right_reaction_N':q*L/2,'V_N':0.,'M_Nmm':q*L*L/8,'midspan_moment_Nmm':q*L*L/8,'max_abs_shear_N':abs(q*L/2+P),'support_limit':True}
   for key in ('global_envelope','position_plan','mobile_resistance_status','local_contact_status','ELS_position_status'):cc.pop(key,None)
   expanded.append(cc)
 bundle['combinations']=expanded
 return bundle

def case_inputs(data,combo):
 d=copy.deepcopy(data);q=combo['q_N_mm'];L=d['L_mm']
 # Internal adapter evaluates q in both states; only the requested state below
 # is retained, reported and exported. There is no fictitious zero combination.
 d.update(q_parallel_uls=combo.get('q_vector',{}).get('parallel',0.),q_parallel_sls=combo.get('q_vector',{}).get('parallel',0.),P_parallel_uls=combo.get('P_vector',{}).get('parallel',0.),P_parallel_sls=combo.get('P_vector',{}).get('parallel',0.))
 d.update(load_mode='direct',q_uls=q,q_sls=q,P_uls=combo.get('P_N',0.),P_sls=combo.get('P_N',0.),x_uls=L/2,x_sls=L/2,actions_origin=f"{combo['id']} — {combo['type']} — {combo['expression']} — {combo.get('origin','matriz fornecida por Lucas')}")
 if combo.get('point_position')=='support_limit':
  # Analytical limit: P has zero bending/displacement away from the support.
  # Its limiting internal shear is evaluated explicitly, not by applying P at x=0.
  d.update(P_uls=0.,P_sls=0.,P_parallel_uls=0.,P_parallel_sls=0.)
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
  if mobile:evidence['prescribed_point']=mobile
  from .inclination_adapter import pending_rows
  from .inclination_adapter import evidence as inclination_evidence
  ev=copy.deepcopy(result['inclination_evidence'][combo['limit_state']])
  if mobile:
   ev['convention']+=' '+mobile['method']
   if combo.get('point_position')=='support_limit':
    # Reactions include the limiting point load, although interior M/V
    # away from the vanishing support layer are those of q alone.
    for state in ev['states']:
     if state['x_mm']==0.:state['position_limit']='interior após P no limite'
     for axis in ('normal','parallel'):state[axis]['Rleft_N']+=combo['P_vector'][axis]
    boundary=copy.deepcopy(ev['states'][0]);boundary.update(x_mm=0.,side='right',position_limit='x→0+, seção antes de P')
    for axis in ('normal','parallel'):
     boundary[axis]['M_Nmm']=0.;boundary[axis]['V_N']=combo['q_vector'][axis]*data['L_mm']/2+combo['P_vector'][axis]
    ev['states'].insert(0,boundary);ev['P_vector']=copy.deepcopy(combo['P_vector'])
  evidence['inclination']=ev
  evidence['strong_critical_qualification']=copy.deepcopy(result['strong_critical_qualification'])
  # Core rows already contain ELU pending rows, but ELS filtering excludes its parallel component.
  # All rows filtered by limit state above.
  cases.append({'combination':combo,'rows':rs,'evidence':evidence,'warnings':result['coverage_warnings']+result.get('critical_warnings',[])+result['numerical_warnings'],'scope_notes':[mobile['scope']] if mobile else []})
 from .weak_pierin import reference_for_inputs
 from .strong_pierin import qualify
 return {'strong_critical_reference':qualify(data)[1],'weak_critical_reference':reference_for_inputs(data),'schema':'tercas_batch_results_v1','version':VERSION,'project':data['project'],'synthetic':data['synthetic'],'input_fingerprint':fingerprint(data),'input_data':copy.deepcopy(data),'load_bundle':bundle,'cases':cases,'whole_member_approved':False,'summary':governing(cases)}

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
  pending=sum(1 for _,rr in items if any(tag in str(rr.get('Situação','')).lower() for tag in ('parcial','pendente','hipótese','provisóri')) or (not finite(rr.get('Índice')) and rr['Situação'] not in ('Não aplicável','Dispensado pela Tabela 14','Não acionado pelo comprimento')))
  entry['Casos pendentes']=pending
  if pending:
   entry['Situação']='Parcial — '+entry['Situação'];entry['Observação']+=f' {pending} combinação(ões) com índice ausente, resultado parcial ou hipótese; o máximo numérico não cobre essas pendências.'
  out.append(entry)
 return out


def mobile_rows(rs,result,combo):
 """Two prescribed positions only; no sweep or continuous-position envelope."""
 position=combo.get('point_position','center');L=result['input_data']['L_mm']
 ev={'position':position,'method':'P no centro.' if position=='center' else 'P no limite junto ao apoio esquerdo: x→0+, sem distância fictícia. M e flecha de P tendem a zero; V limite inclui P.'}
 b=result['NBR_branches'];vr=result['section_checks'].get('shear',{}).get('VRd_N')
 if position=='support_limit':
  v=abs(combo['q_N_mm']*L/2+combo['P_N']);ev['V_support_limit_N']=v
  for row in rs:
   if row['Verificação']=='Cortante' and vr:
    row['Índice']=v/vr;row['Demanda / valor']=f'{v/1000:.6f} kN'
    row['Situação']='Não atende' if row['Índice']>1 else 'Atende ao critério calculado'
   elif row['Verificação']=='Flexão e cortante concomitantes' and vr and row.get('Índice') is not None:
    # Away from the support: q-only interaction. At the boundary layer:
    # M→0 and V→qL/2+P. Max of these distinct concomitant states.
    ev['MV_limit_states']={'interior_q_only_index_squared':row['Índice'],'support_layer_index_squared':(v/vr)**2,'method':'máximo entre estados concomitantes distintos'}
    row['Índice']=max(row['Índice'],(v/vr)**2)
    ev['MV_limit_states']['governing_index_squared']=row['Índice']
    row['Situação']='Não atende' if row['Índice']>1 else 'Atende ao critério calculado'
   row['Observação']+=' '+ev['method']
 else:
  for row in rs:row['Observação']+=' P na posição central prescrita.'
 ev['scope']='Resultados das duas posições prescritas; não certificam máximo da interação ou FLT para outras posições de P.'
 return ev
