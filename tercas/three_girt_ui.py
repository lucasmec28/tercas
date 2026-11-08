from .direct_self_weight import active as direct_PP_active, input_text as direct_PP_text
"""UI for an explicitly separate 3D diagnostic; never renders legacy pass rows."""
import copy
import html
import json
import pandas as pd
from .three_girt_application import defaults,configuration,SCHEMA
from .three_girt_frame import topology,element_response
from .presentation import display_frame,fmt

LEVEL_LABEL={'upper':'Superior','middle':'Central','lower':'Inferior'}


def render_configuration(st,d,b,revision,num,txt):
 from .load_application_policy import active as loads_at_CT
 c=defaults();c.update(copy.deepcopy(b.get('three_girt_model',{})));c['enabled']=True
 ct=loads_at_CT(d)
 st.subheader('Sistema 3D — três travessas contínuas e barras axiais')
 st.warning('Diagnóstico de solicitações e deslocamentos brutos, sem aprovação resistente ou ELS. O sistema 3D substitui a análise de vão isolado nesta seleção; a resistência N=0 e o estudo de molas não serão executados nem misturados.')
 st.caption('Seis extremos: três translações e torção impedidas; rotações de flexão livres. Não se presume restrição de empenamento. Barras lineares em tração/compressão, primeira ordem, sem resistência de tirantes/cantoneiras. Sem crédito da telha.')
 if d['load_mode']=='direct':
  d['area_inputs']['spacing_m']=num('Distância entre travessas','spacing_m',b['area_inputs']['spacing_m'],'m')
 st.caption('Reutiliza o vão e a distância entre travessas já informados. As três travessas têm a mesma seção; distâncias superior–central e central–inferior iguais ao campo acima. Não são dimensões medidas do croqui.')
 c['tie_count']=st.number_input('Quantidade de linhas interiores de tirantes',min_value=0,max_value=20,value=c['tie_count'],step=1,key=f'three_count_{revision}')
 mode=st.selectbox('Posições das linhas', ['uniform','custom'],index=0 if c['position_mode']=='uniform' else 1,
  format_func=lambda x:'Uniformes — padrão editável' if x=='uniform' else 'Coordenadas informadas',key=f'three_positions_mode_{revision}')
 c['position_mode']=mode
 if mode=='custom':
  previous=c['positions_mm']
  if len(previous)!=c['tie_count']:previous=[d['L_mm']*j/(c['tie_count']+1) for j in range(1,c['tie_count']+1)]
  positions=[]
  for i,v in enumerate(previous):positions.append(num(f'Posição da linha {i+1} a partir de A','three_x_'+str(i),v,'mm'))
  c['positions_mm']=positions
 st.caption('No croqui há duas linhas. Para outras quantidades: verticais em todas as linhas; diagonais dos extremos superiores à primeira/última linha central. Uma linha recebe ambas as diagonais; zero desliga as barras. Confira a topologia, não apenas o número.')
 c['geometry_declared']=st.checkbox('Declaro a geometria acima e a equivalência entre distância geométrica e largura tributária',value=c['geometry_declared'],key=f'three_geometry_{revision}')
 with st.expander('Perfis Gerdau das barras — dados nominais e hipótese axial',expanded=True):
  st.caption('Defaults: azul = barra redonda ASTM A36 Ø3/8; verde = cantoneira ASTM A36 L3×3×3/16. Disponibilidade de classe não certifica o lote. Alterações manuais exigem origem própria. A redonda usa área calculada com d exato nominal 9.525 mm; catálogo exibe 9.53 mm.')
  for color,title in [('blue','Azuis — redondas'),('green','Verdes — cantoneiras')]:
   st.markdown('**'+title+'**');m=c[color]
   m['label']=txt('Rótulo do perfil — '+title,'three_'+color+'_label',m['label'])
   cols=st.columns(3)
   for col,(key,label,unit) in zip(cols,[('A_mm2','Área axial bruta','mm²'),('E_MPa','E declarado','MPa'),('mass_kg_m','Massa linear','kg/m')]):
    with col:m[key]=num(label+' — '+title,'three_'+color+'_'+key,m[key],unit)
   m['origin']=txt('Origem do perfil / E — '+title,'three_'+color+'_origin',m['origin'])
  c['axial_bars_declared']=st.checkbox('Adoto barras redondas e cantoneiras articuladas axiais, tração e compressão, sem rigidez de flexão',value=c['axial_bars_declared'],key=f'three_axial_{revision}')
  st.caption('Essa declaração é uma hipótese, não valida flambagem, rigidez real ou ligações. Barras comprimidas serão mostradas, sem resistência verificada.')
 with st.expander('Centro de cisalhamento e ligações — obrigatórios' if ct else 'Centro de cisalhamento, linha de carga e ligações — obrigatórios',expanded=True):
  st.caption('Referência global: X de A para B; Y para cima; Z para a direita na vista A→B. Todas as excentricidades são medidas a partir do centroide. x0 bruto do catálogo não é transferido com sinal presumido.')
  cols=st.columns(2)
  with cols[0]:c['sc_y_mm']=num('CG → centro de cisalhamento: componente Y','three_sc_y',c['sc_y_mm'],'mm')
  with cols[1]:c['sc_z_mm']=num('CG → centro de cisalhamento: componente Z','three_sc_z',c['sc_z_mm'],'mm')
  c['sc_origin']=txt('Origem e convenção do centro de cisalhamento','three_sc_origin',c['sc_origin'])
  if not ct:
   cols=st.columns(2)
   with cols[0]:c['load_y_from_CG_mm']=num('Linha das ações externas: Y a partir do CG','three_load_y',c['load_y_from_CG_mm'],'mm')
   with cols[1]:c['load_z_from_CG_mm']=num('Linha das ações externas: Z a partir do CG','three_load_z',c['load_z_from_CG_mm'],'mm')
   st.caption('Nesta fase, vento e permanente externo compartilham a linha acima; se forem diferentes, o modelo não representa o caso sem uma redução equivalente documentada. PP da travessa atua sempre no CG, separado do torque externo.')
   c['load_line_declared']=st.checkbox('Declaro a linha das cargas externas e a separação do PP no centroide',value=c['load_line_declared'],key=f'three_load_line_{revision}')
  labels={'concentric':'Conexões concêntricas ao CG — idealização explícita','common_arm':'Mesmo braço rígido em todas as extremidades das barras','individual':'Braços individuais por barra — avançado'}
  c['connection_mode']=st.selectbox('Pontos das ligações',list(labels),format_func=labels.get,index=list(labels).index(c['connection_mode']),key=f'three_connection_mode_{revision}')
  if c['connection_mode']=='common_arm':
   cols=st.columns(3);arms=[]
   for i,axis in enumerate('XYZ'):
    with cols[i]:arms.append(num('Braço rígido '+axis,'three_arm_'+axis,c['connection_arm_mm'][i],'mm'))
   c['connection_arm_mm']=arms
  elif c['connection_mode']=='individual':
   records=[]
   for name,_,_,_ in topology(c['tie_count']):
    arms=c['connection_offsets'].get(name,[[0.,0.,0.],[0.,0.,0.]])
    for end,arm in enumerate(arms):records.append(dict(barra=name,extremidade=end+1,x_mm=arm[0],y_mm=arm[1],z_mm=arm[2]))
   table=st.data_editor(pd.DataFrame(records,columns=['barra','extremidade','x_mm','y_mm','z_mm']),hide_index=True,disabled=['barra','extremidade'],key=f'three_arms_{revision}_{c["tie_count"]}',width='stretch')
   offsets={}
   for row in table.to_dict('records'):offsets.setdefault(row['barra'],[]).append([row['x_mm'],row['y_mm'],row['z_mm']])
   c['connection_offsets']=offsets
  c['connections_declared']=st.checkbox('Declaro os braços/idealização das conexões e os seis apoios descritos',value=c['connections_declared'],key=f'three_connections_{revision}')
  st.caption('Braços rígidos transferem força e momento, mas não tornam ligação real rígida nem representam empenamento. O núcleo contém GJ, não ECw; nenhuma declaração remove esse limite.')
 c['brace_self_weight']=st.checkbox('Incluir PP das barras e cantoneiras, inteiro, aplicado metade em cada extremidade',value=c['brace_self_weight'],key=f'three_bar_weight_{revision}')
 st.caption('PP nodal é uma idealização: não representa flexão local da barra pelo próprio peso. Nas três travessas, 0.5/1/0.5 incide sobre vento e CP por área, incluindo peso da telha/revestimento; PP próprio do perfil de cada travessa fica integral.')
 if not c['brace_self_weight']:st.warning('PP das barras/cantoneiras foi excluído deste diagnóstico; ausência não significa dispensa normativa.')
 if d['load_mode']=='direct':
  if direct_PP_active(d):st.caption(direct_PP_text(d))
  else:st.caption('A carga central já combinada deve incluir seu PP. Informe abaixo a parcela PP já contida nela; não é uma segunda soma. Nos extremos usa-se 0.5×(q central−PP)+PP. PP das barras é adicional, com fator próprio explicitamente declarado.')
  for state,label in [('uls','ELU'),('sls','ELS')]:
   if not direct_PP_active(d):
    c['direct_pp_'+state+'_N_mm']=num('Parcela PP da travessa já contida no q vertical '+label,'three_pp_'+state,c['direct_pp_'+state+'_N_mm'],'kN/m')
   if c['brace_self_weight']:c['direct_brace_factor_'+state]=num('Fator do PP das barras — '+label,'three_bar_factor_'+state,c['direct_brace_factor_'+state])
 else:st.caption('Modo área: PP das travessas e das barras usa o coeficiente PP de cada linha da matriz do usuário. A matriz selecionada não é um gerador normativo universal.')
 c['origin']=txt('Origem / hipóteses do sistema de três travessas','three_origin',c['origin'])
 d['three_girt_model']=c
 return c


def diagram(data):
 c=configuration(data);L=data['L_mm'];gap=data['area_inputs']['spacing_m']*1000.;xs=[0.]+c['resolved_positions_mm']+[L];cols=len(xs)
 xy=[(80+740*x/L,70+150*row) for row in range(3) for x in xs]
 parts=['<svg xmlns="http://www.w3.org/2000/svg" role="img" aria-label="Esquema das três travessas e barras axiais" viewBox="0 0 900 440" style="width:100%;background:#f8fafc">']
 for name,a,b,color in topology(c['tie_count']):
  x,y=xy[a];xx,yy=xy[b];parts.append(f'<line x1="{x}" y1="{y}" x2="{xx}" y2="{yy}" stroke="'+('#2573cb' if color=='blue' else '#288252')+'" stroke-width="3"/>')
 parts.append('<text x="80" y="28" font-size="13">Superior/inferior: externas ½ + PP inteiro · Central: externas 1 + PP inteiro</text>')
 for row,label in enumerate(['Superior','Central','Inferior']):
  y=70+row*150;parts.append(f'<path d="M80 {y} H820" stroke="#c64045" stroke-width="5"/><text x="8" y="{y+5}" font-size="14">{label}</text>')
  for x in (80,820):parts.append(f'<path d="M{x} {y+2} l-10 17 h20 z" fill="white" stroke="#334155"/>')
 for i,(x,y) in enumerate(xy):
  label_y=y+32 if i%cols in (0,cols-1) else y+15
  label_x=x-16 if i%cols==0 else x+6
  parts.append(f'<circle cx="{x}" cy="{y}" r="4" fill="#25334a"/><text x="{label_x}" y="{label_y}" font-size="10">{i}</text>')
 parts.append(f'<text x="80" y="420" font-size="13">L = {html.escape(fmt(L))} mm · distância = {html.escape(fmt(gap))} mm · Y↑, X→; Z normal ao plano</text></svg>')
 return ''.join(parts)


def envelope_rows(model):
 out=[]
 for level,env in model.get('girt_envelopes',{}).items():
  row={'Travessa':LEVEL_LABEL[level],'N mínimo [kN]':env['N_N']['min']['N_N']/1000,'N máximo [kN]':env['N_N']['max']['N_N']/1000}
  for key,label,scale in [('My_strong_Nmm','|My forte| [kN·m]',1e6),('Mz_weak_Nmm','|Mz fraco| [kN·m]',1e6),('T_CG_Nmm','|T CG| [kN·m]',1e6),('uy_CG_mm','|uY CG| bruto [mm]',1),('uz_CG_mm','|uZ CG| bruto [mm]',1),('rx_rad','|torção| [rad]',1)]:row[label]=abs(env[key]['max_abs'][key])/scale
  out.append(row)
 return out


def render_result(st,result):
 from .model_domain import export_inputs as domain_export_inputs
 st.subheader('Sistema de três travessas — resultados elásticos condicionais')
 st.error('SEM CONCLUSÃO RESISTENTE OU ELS. Nenhum índice de aprovação foi calculado para o sistema 3D; os esforços não alimentam a rota isolada N=0.')
 st.caption(result['axis_convention']);st.caption(result['support_convention'])
 selected=0
 if result['status']=='not_solved':
  st.warning(result.get('reason','Modelo não resolvido.'))
  for m in result.get('missing',[]):st.write('• '+m)
  for case in result['cases']:
   if case['model']['status']!='conditional_elastic_diagnostic':st.error(case['combination']['id']+': NÃO RESOLVIDO — '+case['model'].get('reason','Gate numérico não satisfeito.'))
 if result['cases']:
  selected=st.selectbox('Combinação 3D para consultar',range(len(result['cases'])),format_func=lambda i:result['cases'][i]['combination']['id']+' — '+result['cases'][i]['combination']['limit_state'])
  case=result['cases'][selected];model=case['model'];st.caption(str(case['combination']['expression']))
  st.caption(result['load_distribution'])
  st.dataframe(display_frame([{'Travessa':LEVEL_LABEL[k],'qY [N/mm]':q['q_y_N_mm'],'qZ [N/mm]':q['q_z_N_mm'],'Torque distribuído CG [N]':q['distributed_torque_CG_N']} for k,q in zip(LEVEL_LABEL,case['loads'])]),hide_index=True,width='stretch')
  if model['status']=='conditional_elastic_diagnostic':
   st.markdown('**Extremos por componente — NÃO são uma interação concomitante**')
   st.dataframe(display_frame(envelope_rows(model)),hide_index=True,width='stretch')
   st.caption('O sinal e a seção de cada extremo, com todos os esforços concomitantes, permanecem no JSON. Torção Saint-Venant: empenamento/bimomento não representados. Flechas absolutas brutas, sem confronto com limite.')
   if model['primary_torsion_present']:st.warning('Há torção no modelo GJ. Para U/Ue aberto, esse diagnóstico não qualifica a resposta completa com empenamento; não usar como demanda resistente definitiva.')
   cols=len(model['inputs']['attachment_x_mm'])+2
   reactions=[]
   for node in model['nodes']:
    if node['id']%cols not in (0,cols-1):continue
    r=node['support_reactions'];reactions.append(dict(nó=node['id'],travessa=LEVEL_LABEL[list(LEVEL_LABEL)[node['id']//cols]],Fx_kN=r[0]/1000,Fy_kN=r[1]/1000,Fz_kN=r[2]/1000,Tx_kNm=r[3]/1e6,My_kNm=r[4]/1e6,Mz_kNm=r[5]/1e6))
   with st.expander('Reações nos seis apoios e forças das barras',expanded=True):
    st.dataframe(display_frame(reactions),hide_index=True,width='stretch')
    st.dataframe(display_frame([{'Barra':b['id'],'Perfil':b['material'].get('label',b['kind']),'N tração+ [kN]':b['axial_tension_N']/1000,'Estado':'Tração' if b['axial_state']=='tension' else 'Compressão — resistência NÃO verificada' if b['axial_state']=='compression' else 'Nulo','PP ponderado [N]':b['self_weight_N']} for b in model['bars']]),hide_index=True,width='stretch')
   with st.expander('Estados concomitantes por seção e lado',expanded=False):
    level=st.selectbox('Travessa para consultar',list(LEVEL_LABEL),format_func=LEVEL_LABEL.get)
    states=[s for e in model['beams'] if e['girt']==level for s in e['critical_sections']]
    st.dataframe(display_frame([{'x [mm]':s['x_mm'],'Lado':s['side'],'N [kN]':s['N_N']/1000,'Vy [kN]':s['Vy_N']/1000,'Vz [kN]':s['Vz_N']/1000,'My forte [kN·m]':s['My_strong_Nmm']/1e6,'Mz fraco [kN·m]':s['Mz_weak_Nmm']/1e6,'T CG [kN·m]':s['T_CG_Nmm']/1e6,'T SC [kN·m]':s['T_SC_Nmm']/1e6,'uY CG [mm]':s['uy_CG_mm'],'uZ CG [mm]':s['uz_CG_mm']} for s in states]),hide_index=True,width='stretch')
    st.caption('Nos nós internos, ambos os lados são mantidos: saltos por forças/momentos das barras não são ocultados. São extremos individuais e limites de elementos, não um máximo de interação resistente.')
   with st.expander('Equilíbrio e estabilidade numérica — não flambagem'):st.json({'residuals':model['residuals'],'stability_diagnostic':model['stability_diagnostic']})
  else:st.error(model.get('reason','Gate numérico não satisfeito; sem resposta liberada.'))
 with st.expander('Premissas, limites e fontes',expanded=True):
  for note in result['limitations']:st.write('• '+note)
  for src in result['sources']:st.markdown('['+src['title']+']('+src['url']+') — '+src['use'])
 from .three_girt_report import word
 c1,c2,c3=st.columns(3)
 with c1:st.download_button('Baixar memória diagnóstica 3D (Word)',word(result,selected),file_name='MC_tres_travessas_diagnostico.docx',mime='application/vnd.openxmlformats-officedocument.wordprocessingml.document')
 with c2:st.download_button('Baixar diagnóstico 3D (JSON)',json.dumps(result,ensure_ascii=False,indent=2),file_name='tres_travessas_diagnostico.json',mime='application/json')
 with c3:st.download_button('Baixar entradas (JSON)',json.dumps(domain_export_inputs(result['input_data']),ensure_ascii=False,indent=2),file_name='terca_entradas.json',mime='application/json')
 with st.expander('Rastreabilidade completa do diagnóstico 3D'):st.json(result)
