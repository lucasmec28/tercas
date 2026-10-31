"""Streamlit entry point. User inputs are untrusted; no global approval state."""
from tercas.presentation import fmt, display, display_records, measurement_text, DISPLAY_NOTE
import copy,json,math
import pandas as pd
import streamlit as st
from tercas.application import defaults,example,calculate,rows,fingerprint,VERSION
from tercas.drawing import svg
from tercas.report import word,batch_word
from tercas.catalogs import catalog_labels,STEEL_NAMES,material,critical_defaults,catalog_entry
from tercas.batch import calculate_batch,area_bundle,case_inputs
from tercas.load_combinations import COMBINATION_TYPES
from tercas.ux_inputs import CB_LABELS,cb_code,flange_segments,whole_span

def display_frame(records):
 # Styler changes visible text only: numeric sorting and column types survive.
 frame=pd.DataFrame(records)
 def formatter(key):
  return lambda value: '—' if value is None or (isinstance(value,float) and math.isnan(value)) else display_records([{key:value}])[0][key]
 return frame.style.format({key:formatter(key) for key in frame.columns})

def show_inclination(evidence):
 """Display concurrent effects; never interpret missing resistance as approval."""
 if not isinstance(evidence,dict):return
 if 'states' not in evidence:
  for state,item in evidence.items():
   if isinstance(item,dict):
    st.markdown('**'+str(state)+' — solicitações locais**');show_inclination(item)
  return
 st.caption(evidence.get('convention','Esforços simultâneos na mesma seção e combinação.'))
 st.warning(evidence.get('resistance_status','Resistência biaxial não avaliada; os esforços não constituem aprovação.'))
 if evidence.get('weak_axis_capacities'):
  caps=[]
  for sign,c in evidence['weak_axis_capacities'].items():
   caps.append({'Sentido':{'positive':'My positivo','negative':'My negativo'}[sign],'Estado':'Calculado com dados informados' if c.get('MRd_Nmm') else 'Dados pendentes','Me Anexo E [kN·m]':c.get('annex_e',{}).get('Me_Nmm',0)/1e6 if c.get('annex_e') else None,'MRd fraco [kN·m]':c.get('MRd_Nmm',0)/1e6 if c.get('MRd_Nmm') else None,'Origem / faltas':c.get('provenance',', '.join(c.get('missing',[])))})
  st.dataframe(display_frame(caps),hide_index=True,width='stretch')
 records=[]
 for state in evidence.get('states',[]):
  row={'x [mm]':state.get('x_mm'),'Lado da seção':{'left':'Esquerda','right':'Direita'}.get(state.get('side'),'—')}
  for axis,label in [('normal','Normal / eixo forte'),('parallel','Paralelo / eixo fraco')]:
   v=state.get(axis,{})
   for k,title,scale in [('M_Nmm','M [kN·m]',1e6),('V_N','V [kN]',1000),('Rleft_N','Reação esquerda [kN]',1000),('Rright_N','Reação direita [kN]',1000)]:
    if k in v:row[label+' — '+title]=v[k]/scale
  records.append(row)
 if records:st.dataframe(display_frame(records),hide_index=True,width='stretch')
 st.caption('Valores nas seções listadas; não são envelope biaxial nem resistência. P e q são considerados juntos na mesma combinação.')

st.set_page_config(page_title='LRO | Terças',page_icon='🏗️',layout='wide')
st.markdown('<style>.block-container{max-width:1200px} h1,h2,h3{color:#25334a} div.stButton>button[kind="primary"]{background:#d96516;border:0}</style>',unsafe_allow_html=True)
st.title('LRO | Terças')
with st.expander('Precisão dos números exibidos',expanded=False):st.caption(DISPLAY_NOTE)
st.caption(f'NBR 14762:2010 · {VERSION} · primeira emissão restrita')
st.info('Um vão, perfis U/Ue. Solicitações nos dois eixos; resistências desta emissão restritas às rotas disponíveis. A telha não é considerada como travamento. Resultados por verificação, sem aprovação global automática.')

if 'base' not in st.session_state:st.session_state.base=defaults()
if 'revision' not in st.session_state:st.session_state.revision=0

def load(d):
 st.session_state.base=copy.deepcopy(d);st.session_state.last_input=copy.deepcopy(d);st.session_state.revision+=1
 st.session_state.pop('result',None);st.session_state.pop('custom_steel_draft',None)

left,right=st.columns([2,1])
with right:
 if st.button('Carregar exemplo didático',help='Carrega dados sintéticos, explicitamente marcados. Não representa produto ou projeto validado.'):load(example());st.rerun()
with left:
 index=st.selectbox('Perfil de catálogo',range(len(catalog_labels())),format_func=lambda i:catalog_labels()[i],index=st.session_state.base['catalog_index'],key=f'catalog_{st.session_state.revision}')
 if index!=st.session_state.base['catalog_index']:
  changed=copy.deepcopy(st.session_state.get('last_input',st.session_state.base));fresh=defaults(index)
  for key in ['schema','catalog_index','properties','Ml_Nmm','Mdist_Nmm','critical_origin','property_origin']:changed[key]=fresh[key]
  changed.pop('weak_axis',None);changed.pop('weak_catalog',None)
  changed['synthetic']=False
  if changed.get('steel_name')!='Personalizado':changed['properties'].update(material(changed['steel_name'])['properties'])
  else:
   old=st.session_state.get('last_input',st.session_state.base)
   for key in ['fy_MPa','fu_MPa']:changed['properties'][key]=old['properties'][key]
  load(changed);st.rerun()
b=copy.deepcopy(st.session_state.base);r=st.session_state.revision
# Preserve values of widgets hidden when changing input mode.
last=st.session_state.get('last_input',b)
for key in ['load_mode','area_inputs','selected_types','ELS_down_denominator','ELS_up_denominator','q_uls','P_uls','x_uls','q_sls','P_sls','x_sls','actions_origin','ELS_limit_mm','ELS_origin']:
 b[key]=copy.deepcopy(last[key])
for key in ['weak_catalog','weak_axis','inclination','q_parallel_uls','q_parallel_sls','P_parallel_uls','P_parallel_sls']:
 if key in last:b[key]=copy.deepcopy(last[key])
d=copy.deepcopy(b)
if b.get('synthetic'):st.warning('EXEMPLO DIDÁTICO: propriedades complementares, críticos e contatos sintéticos. Substitua pelos dados do seu caso antes de usar resultados.')

def num(label,key,value,unit='',step=None):
 kw={'label':label+(f' [{unit}]' if unit else ''),'value':None if value is None else float(value),'key':f'{key}_{r}','format':'%.2f'}
 if step is not None:kw['step']=step
 out=st.number_input(**kw)
 if out is not None and out != 0 and abs(out)<0.005:st.caption('Valor não nulo: '+fmt(out)+' '+unit+'; precisão preservada.')
 return out

def txt(label,key,value):return st.text_input(label,value=str(value),key=f'{key}_{r}')

d['project']=txt('Identificação do estudo','project',b['project'])
c1,c2=st.columns(2)
with c1:d['L_mm']=num('Vão entre apoios','L',b['L_mm'],'mm')
with c2:d['steel_name']=st.selectbox('Tipo de aço',STEEL_NAMES,index=STEEL_NAMES.index(b.get('steel_name','ASTM A36')),key=f'steel_{r}')
if d['steel_name']=='Personalizado':
 custom=st.session_state.get('custom_steel_draft',dict(fy=b['properties']['fy_MPa'],fu=b['properties']['fu_MPa'],origin=b['property_origin']))
 c1,c2=st.columns(2)
 with c1:fy=num('fy personalizado','fy_custom',custom['fy'],'MPa')
 with c2:fu=num('fu personalizado','fu_custom',custom['fu'],'MPa')
 custom_origin=txt('Origem do aço personalizado','steel_origin',custom['origin'])
 st.session_state.custom_steel_draft=dict(fy=fy,fu=fu,origin=custom_origin)
 try:mat=material('Personalizado',{'fy_MPa':fy,'fu_MPa':fu,'origin':custom_origin})
 except ValueError as exc:mat=None;st.warning(str(exc));d['properties'].update(fy_MPa=fy,fu_MPa=fu)
else:mat=material(d['steel_name'])
if mat:
 d['properties'].update(mat['properties']);d['property_origin']=f"{mat['name']}: {mat['origin']}; {mat['physical_origin']}"
 st.caption(f"fy = {fmt(mat['properties']['fy_MPa'])} MPa · fu = {fmt(mat['properties']['fu_MPa'])} MPa. Conferir especificação do produto.")

with st.expander('Perfil, aço e origem dos dados',expanded=False):
 st.caption('209 perfis da planilha V03 fornecida por Lucas; fontes e linha de origem preservadas. Críticos tabulados de Pierin/DimPerfil quando disponíveis. A transcrição não é certificação do produto.')
 cols=st.columns(3)
 labels={'A_cm2':'Área [cm²]','mass_kg_m':'Massa linear [kg/m]','Ix_cm4':'Ix [cm⁴]','Wx_cm3':'Wx [cm³]','Iy_cm4':'Iy [cm⁴]','ri_mm':'Raio interno [mm]','J_mm4':'J [mm⁴]','Cw_mm6':'Cw [mm⁶]'}
 for i,(key,label) in enumerate(labels.items()):
  with cols[i%3]:d['properties'][key]=num(label,key,b['properties'][key])
 extra_origin=txt('Origem dos dados complementares / alterações','property_origin',b['property_origin'])
 d['property_origin']=(f"Aço {mat['name']}: {mat['origin']}; {mat['physical_origin']}; " if mat else '')+extra_origin
 st.caption(f"E = {fmt(d['properties']['E_MPa'])} MPa · G = {fmt(d['properties']['G_MPa'])} MPa — NBR 14762.")
 st.caption('Fonte: '+catalog_entry(index)['source_url']+'; linha '+str(catalog_entry(index)['source_workbook_row'])+' da planilha original.')
 st.caption('Conferir a convenção de Wx e das propriedades usadas em conjunto. Editar valores não comprova a correspondência física.')

st.subheader('Inclinação da cobertura')
ic=copy.deepcopy(b.get('inclination',{}))
c1,c2=st.columns(2)
with c1:
 unit_label=st.selectbox('Unidade de inclinação',['Graus','Porcentagem'],index=1 if ic.get('unit')=='percent' else 0,key=f'angle_unit_{r}')
with c2:
 new_unit='percent' if unit_label=='Porcentagem' else 'degrees'
 old_unit=st.session_state.get(f'inclination_previous_unit_{r}',ic.get('unit','degrees'))
 if new_unit!=old_unit:
  old=st.session_state.get(f'inclination_value_{r}',ic.get('value',0))
  if old is not None:
   converted=100*math.tan(math.radians(old)) if new_unit=='percent' else math.degrees(math.atan(old/100))
   st.session_state[f'inclination_value_{r}']=converted
 st.session_state[f'inclination_previous_unit_{r}']=new_unit
 ic['value']=num('Inclinação','inclination_value',ic.get('value',0),'%' if unit_label=='Porcentagem' else '°')
ic['unit']='percent' if unit_label=='Porcentagem' else 'degrees'
if ic.get('value') is not None:
 theta=math.atan(ic['value']/100) if ic['unit']=='percent' else math.radians(ic['value'])
 if abs(theta)<math.pi/2:st.caption(f'Ângulo equivalente: {fmt(math.degrees(theta))}° = {fmt(100*math.tan(theta))}%. Exibição arredondada; cálculo com precisão completa. Trocar a unidade mantém a inclinação física.')
st.caption('Alma perpendicular ao plano da cobertura. No modo por área, vento normal à cobertura; gravidade e peso próprio decompostos em normal e paralelo. Sem travamento pela telha.')
with st.expander('Bases de área e distância entre terças',expanded=False):
 basis_labels={'roof':'No plano da cobertura','horizontal':'Na projeção horizontal'}
 for key,label,default in [('spacing_basis','Distância entre terças medida','roof'),('permanent_basis','Área do carregamento permanente','roof'),('live_basis','Área da sobrecarga','horizontal'),('wind_basis','Área de referência do vento','roof')]:
  ic[key]=st.selectbox(label,list(basis_labels),format_func=lambda v:basis_labels[v],index=list(basis_labels).index(ic.get(key,default)),key=f'{key}_{r}')
 st.caption('Confira a base de cada valor recebido. O app converte a largura tributária entre projeção horizontal e plano da cobertura, sem duplicar o cosseno. Estas bases afetam somente o modo por área.')
d['inclination']=ic

st.subheader('Carregamentos')
mode=st.radio('Forma de entrada',['Ações já combinadas (ELU e ELS)','Cargas por área e combinações automáticas'],index=1 if b.get('load_mode')=='area' else 0,key=f'load_mode_{r}')
d['load_mode']='area' if mode.startswith('Cargas') else 'direct'
if d['load_mode']=='direct':
 st.subheader('Ações de uma combinação')
 st.caption('Ações já nos eixos locais: q e P principais são normais à cobertura; componentes paralelas são informadas abaixo. A inclinação não gira novamente estes valores. q positivo e P positivo atuam no mesmo sentido do esquema. q em kN/m equivale numericamente a N/mm. P é informado em kN. Inclua peso próprio nas ações; o app não o soma silenciosamente.')
 a,bcol=st.columns(2)
 with a:
  st.markdown('**ELU — valores já ponderados**')
  d['q_uls']=num('q ELU','q_uls',b['q_uls'],'kN/m');p=num('P ELU','P_uls',b['P_uls']/1000,'kN');d['P_uls']=None if p is None else p*1000;d['x_uls']=num('Posição de P ELU','x_uls',b['x_uls'],'mm')
 with bcol:
  st.markdown('**ELS — combinação de serviço**')
  d['q_sls']=num('q ELS','q_sls',b['q_sls'],'kN/m');p=num('P ELS','P_sls',b['P_sls']/1000,'kN');d['P_sls']=None if p is None else p*1000;d['x_sls']=num('Posição de P ELS','x_sls',b['x_sls'],'mm')
 with st.expander('Componentes paralelas à cobertura — ações já combinadas',expanded=False):
  st.caption('Zero quando não houver componente paralela. P paralela atua na mesma posição da P normal de cada estado-limite. Resistência biaxial não é aprovada sem resistências aplicáveis nos dois eixos.')
  c1,c2=st.columns(2)
  for state,col in [('uls',c1),('sls',c2)]:
   with col:
    label='ELU' if state=='uls' else 'ELS'
    key='q_parallel_'+state;d[key]=num('q paralelo '+label,key,b.get(key,0),'kN/m')
    key='P_parallel_'+state;pv=b.get(key,0);pv=num('P paralelo '+label,key,None if pv is None else pv/1000,'kN');d[key]=None if pv is None else pv*1000
 d['actions_origin']=txt('Identificação e origem das combinações','actions_origin',b['actions_origin'])
 
else:
 st.caption('Informe módulos positivos em kgf/m². Vento para cima recebe sinal negativo. PP vem da massa linear, sem campo adicional; CP não deve repetir PP.')
 area=copy.deepcopy(b['area_inputs']);cols=st.columns(2)
 labels=[('spacing_m','Distância entre terças','m'),('permanent_kgf_m2','Carregamento permanente','kgf/m²'),('live_kgf_m2','Sobrecarga','kgf/m²'),('wind_up_kgf_m2','Vento para cima','kgf/m²'),('wind_down_kgf_m2','Vento para baixo','kgf/m²')]
 for i,(key,label,unit) in enumerate(labels):
  with cols[i%2]:area[key]=num(label,key,area[key],unit)
 d['area_inputs']=area
 d['selected_types']=st.multiselect('Tipos de combinações consideradas',COMBINATION_TYPES,default=b['selected_types'],key=f'combo_types_{r}')
 st.caption('P = 1 kN de manutenção é incluída automaticamente nas famílias ELU normal e ELS rara selecionadas, apenas com permanentes; não se soma a SC ou vento. FLT móvel permanece parcial; na flecha normal, um limite superior conservador pode concluir o critério do modelo quando aplicável, sem calcular a flecha móvel exata.')
 st.caption(f"Massa linear selecionada: {fmt(d['properties']['mass_kg_m'])} kg/m. Matriz fixa fornecida por Lucas: 32 ELU normal, 8 ELS rara, 6 frequente e 2 quase permanente.")
 with st.expander('Casos e combinações que serão calculados'):
  try:
   preview=area_bundle(d)
   st.dataframe(display_frame([{'Caso':k,'q normal [kN/m]':v,'q paralelo [kN/m]':preview.get('case_vectors_N_mm',{}).get(k,{}).get('parallel',0)} for k,v in preview['case_q_N_mm'].items()]),hide_index=True)
   st.dataframe(display_frame([{'ID':c['id'],'Tipo':c['type'],'Expressão':c['expression'],'q normal [kN/m]':c['q_kN_m'],'q paralelo [kN/m]':c.get('q_vector',{}).get('parallel',0),'P normal [kN]':c.get('P_N',0)/1000,'P paralelo [kN]':c.get('P_vector',{}).get('parallel',0)/1000} for c in preview['combinations']]),hide_index=True)
  except (ValueError,TypeError,KeyError) as exc:st.warning(str(exc))

with st.expander('Estabilidade, críticos e trechos',expanded=True):
 st.caption('Ml e Mdist são críticos elásticos da mesma seção. Não são momentos resistentes. Sem dado suficiente, só a verificação afetada fica pendente.')
 c1,c2=st.columns(2)
 with c1:m=num('Ml — crítico local','Ml',None if b['Ml_Nmm'] is None else b['Ml_Nmm']/1e6,'kN·m');d['Ml_Nmm']=None if m is None else m*1e6
 with c2:m=num('Mdist — quando não dispensado','Mdist',None if b['Mdist_Nmm'] is None else b['Mdist_Nmm']/1e6,'kN·m');d['Mdist_Nmm']=None if m is None else m*1e6
 d['critical_origin']=txt('Origem dos críticos / método e seção','critical_origin',b['critical_origin'])
 selection=st.selectbox('Domínio da expressão de Me nesta emissão',['Não informado / outra situação','Eixo forte de simetria; sem torção primária ou efeito de altura neste modelo'],index=1 if b['route_domain'] else 0,key=f'domain_{r}')
 d['route_domain']=selection.startswith('Eixo')
 st.caption('Ly superior/inferior é o comprimento lateral associado à menor inércia no cálculo de FLT da flexão forte. Lz é torsional, não um comprimento da maior inércia. Esses comprimentos não criam apoios no diagrama de cargas.')
 st.caption('Esta seleção é uma hipótese do modelo, não uma verificação do caminho da torção. Ly e Lz são independentes; um tirante lateral não é automaticamente travamento torsional.')

 source_segments=flange_segments(st.session_state.get(f'last_segments_{r}',b['segments']))
 first=source_segments[0] if source_segments else {}
 source_whole=(len(source_segments)==1 and first.get('start_mm')==0 and first.get('end_mm')==st.session_state.get(f'last_span_{r}',b['L_mm']))
 custom=st.checkbox('Definir trechos específicos (avançado)',value=not source_whole,key=f'custom_segments_{r}')
 if not custom:
  # In the usual one-span case, section coordinates follow L automatically.
  # Only defaults following the whole span follow its change; edits persist.
  previous_span=st.session_state.get(f'last_span_{r}',b['L_mm'])
  new_span=d['L_mm']!=previous_span
  def length_value(key):
   v=first.get(key)
   return d['L_mm'] if v is None or (new_span and v==previous_span) else v
  if new_span:
   for widget,field in [('upper','Ly_top_effective_mm'),('lower','Ly_bottom_effective_mm'),('torsion','Lz_effective_mm')]:
    st.session_state[f'{widget}_{r}']=length_value(field)
   st.info('Vão alterado: comprimentos iguais ao vão anterior acompanham o novo vão; valores personalizados são preservados. Confira os travamentos.')
  c1,c2=st.columns(2)
  with c1:upper=num('Ly — mesa superior (menor inércia)','upper',length_value('Ly_top_effective_mm'),'mm')
  with c2:lower=num('Ly — mesa inferior (menor inércia)','lower',length_value('Ly_bottom_effective_mm'),'mm')
  cb_label=st.selectbox('Coeficiente Cb',list(CB_LABELS.values()),index=list(CB_LABELS).index(first.get('Cb_mode','one')),key=f'cb_{r}')
  st.caption('Momento positivo comprime a mesa superior; momento negativo comprime a inferior. O app escolhe o comprimento da mesa comprimida em cada caso e não considera a telha como travamento.')
  with st.expander('Vínculo torsional e origem dos comprimentos',expanded=False):
   torsion=num('Comprimento efetivo torsional Lz','torsion',length_value('Lz_effective_mm'),'mm')
   origin=txt('Origem / hipótese dos travamentos','restraint_origin',first.get('restraint_provenance') or 'Comprimentos efetivos informados; sem crédito de travamento da telha')
   st.caption('O valor inicial é o vão inteiro. Um travamento lateral de mesa não reduz automaticamente o comprimento torsional. Confira o vínculo adotado.')
  effective_cb=cb_label
  if cb_code(cb_label)=='quarter_formula' and (upper!=d['L_mm'] or lower!=d['L_mm']):
   st.warning('Cb = 1,0 adotado neste modo: os comprimentos efetivos não informam a posição física dos trechos. Para calcular Cb pelos momentos, defina os limites físicos em trechos específicos (avançado).')
   effective_cb='one'
  d['segments']=whole_span(d['L_mm'],upper,lower,torsion,effective_cb,origin)
  st.caption(f'Trecho de cálculo automático: 0 até {fmt(d["L_mm"])} mm, conforme o vão informado acima.')
 else:
  for seg in source_segments:seg['Cb_mode']=CB_LABELS[seg['Cb_mode']]
  df=pd.DataFrame(source_segments,columns=['start_mm','end_mm','Ly_top_effective_mm','Ly_bottom_effective_mm','Lz_effective_mm','Cb_mode','restraint_provenance'])
  edited=st.data_editor(df,num_rows='dynamic',hide_index=True,key=f'segments_{r}',column_config={'start_mm':st.column_config.NumberColumn('Início [mm]',format='%.2f'),'end_mm':st.column_config.NumberColumn('Fim [mm]',format='%.2f'),'Ly_top_effective_mm':st.column_config.NumberColumn('Mesa superior — comprimento efetivo [mm]',format='%.2f'),'Ly_bottom_effective_mm':st.column_config.NumberColumn('Mesa inferior — comprimento efetivo [mm]',format='%.2f'),'Lz_effective_mm':st.column_config.NumberColumn('Lz torsional [mm]',format='%.2f'),'restraint_provenance':'Origem / hipótese do vínculo','Cb_mode':st.column_config.SelectboxColumn('Cb',options=list(CB_LABELS.values()))},width='stretch')
  if any(0<abs(float(v))<0.005 for v in edited.select_dtypes(include='number').to_numpy().ravel()):st.caption('Há comprimento não nulo abaixo de 0,01 mm na tabela. O valor completo foi preservado; confira a entrada.')
  d['segments']=edited.astype(object).where(pd.notna(edited),None).to_dict('records')
  for seg in d['segments']:seg['Cb_mode']=cb_code(seg.get('Cb_mode') or 'one')
  st.caption('Início e fim são os limites físicos do diagrama usado no Cb; Ly e Lz são comprimentos efetivos e podem diferir desse intervalo por condição de vínculo. Trechos representam o diagrama usado no Cb; não criam apoios verticais nem comprovam travamentos. Uma inversão do momento não é um travamento.')

 st.session_state[f'last_segments_{r}']=copy.deepcopy(d['segments'])
 st.session_state[f'last_span_{r}']=d['L_mm']

with st.expander('Eixo fraco — dados existentes e críticos por sentido',expanded=False):
 st.caption('Wy, xg, x0 e r0 já estão na planilha. Área, Ix, Iy, J, Cw, E e G vêm do perfil/aço selecionados; o app calcula Nex e Nez, sem pedir estes números de novo. Lz usa o maior comprimento torsional dos trechos. Sem travamento da telha.')
 st.caption('Convenção: My positivo comprime a alma; My negativo comprime as bordas/lábios. Os eixos locais e o sentido da seção física devem corresponder a esta convenção. Cm = 1,0 em todas as combinações; não há redução automática.')
 raw=catalog_entry(index)['raw_source_values']
 st.dataframe(display_frame([{'Dado':k,'Valor tabelado':raw.get(k)} for k in ['Wy cm³','xg cm','x0 cm','r0 cm','Ml,y kNm']]),hide_index=True)
 wc=copy.deepcopy(b.get('weak_catalog',{}));gm=wc.get('mean_line',{})
 old_weak_span=st.session_state.get(f'weak_last_span_{r}',b['L_mm'])
 current_lx=st.session_state.get(f'weak_lx_{r}',wc.get('Lx_mm',d['L_mm']))
 if d['L_mm']!=old_weak_span and current_lx==old_weak_span:
  st.session_state[f'weak_lx_{r}']=d['L_mm'];wc['Lx_mm']=d['L_mm']
 st.session_state[f'weak_last_span_{r}']=d['L_mm']
 wc['Lx_mm']=num('Lx efetivo — instabilidade da flexão fraca','weak_lx',wc.get('Lx_mm',d['L_mm']),'mm')
 with st.expander('Convenção geométrica de linha média — somente para j do Anexo E',expanded=False):
  st.caption('A conversão das dimensões nominais do catálogo para am, bm e cm ainda não foi confirmada na fonte. Não são novos ensaios: são as dimensões de linha média do Anexo E. Não há valores presumidos. O app confere compatibilidade com xg, x0 e Iy da planilha; diferença acima de 3% bloqueia esta automação. Essa triagem não certifica a convenção.')
  vals={};cols=st.columns(3)
  for i,(key,label) in enumerate([('am_mm','am — altura na linha média'),('bm_mm','bm — largura na linha média'),('cm_mm','cm — lábio na linha média')]):
   with cols[i]:vals[key]=num(label,'weak_geom_'+key,gm.get(key,0. if key=='cm_mm' and catalog_entry(index)['family']=='U' else None),'mm')
  vals['origin']=txt('Origem / convenção das dimensões médias','weak_geometry_origin',gm.get('origin',''))
  wc['mean_line']=vals
 d['weak_catalog']=wc;d['weak_axis']={}
 from tercas.weak_catalog import critical_hypothesis
 provisional=critical_hypothesis(index)
 for sign,label in [('positive','My positivo — alma comprimida'),('negative','My negativo — bordas comprimidas')]:
  src=b.get('weak_axis',{}).get(sign,provisional[sign])
  st.markdown('**'+label+'**');out={};cols=st.columns(2)
  for i,(key,label2) in enumerate([('Ml_Nmm','Ml,y local'),('Mdist_Nmm','Mdist,y distorcional')]):
   with cols[i]:
    value=num(label2+' — '+label,'weak_'+sign+'_'+key,None if src.get(key) is None else src[key]/1e6,'kN·m');out[key]=None if value is None else value*1e6
  out['provisional_hypothesis']=src.get('provisional_hypothesis',False) or 'HIPÓTESE PROVISÓRIA' in src.get('provenance','').upper()
  out['plain_u_no_distortion']=catalog_entry(index)['family']=='U'
  if out['plain_u_no_distortion']:st.caption('U simples, sem painel na mesa tracionada: não aplicabilidade distorcional conforme §9.3. Não se usa dispensa da Tabela 14 forte no eixo fraco.')
  out['provenance']=txt('Origem dos críticos neste sentido — '+label,'weak_source_'+sign,src.get('provenance',''))
  d['weak_axis'][sign]=out
 st.caption('Hipótese provisória autorizada: o Ml,y tabulado preenche somente My positivo (alma comprimida), apoiado na comparação pyCUFSM, ainda a conferir com exemplos CBCA. Não é copiado no sentido oposto; Mdist,y não usa a tabela do eixo forte. A ausência de um crítico afeta só a rota correspondente.')

with st.expander('Introdução de P e limite de flecha',expanded=False):
 st.caption('Apoios e ligações não são dimensionados neste app. O cálculo da terça mantém as hipóteses de introdução das forças aplicáveis; não há aprovação automática do detalhe.')
 st.caption('Não é a posição da força. Deixe vazio quando desconhecido: a força pontual global continua sendo calculada. Não adote comprimento fictício.')
 d['patch_mm']=num('Contato físico de P — opcional, somente resistência local','patch',b['patch_mm'],'mm')
 d['patch_origin']=txt('Origem do contato de P','patch_origin',b['patch_origin'])
 st.caption('Anexo D nesta interface: força de compressão isolada e interna, aplicada à mesa. Próximo ao apoio ou outro detalhe: não avaliado, sem bloquear os cálculos globais.')
 if d['load_mode']=='direct':
  d['ELS_limit_mm']=num('Limite de flecha adotado','els_limit',b['ELS_limit_mm'],'mm')
  d['ELS_origin']=txt('Origem / aplicação do limite de flecha','els_origin',b['ELS_origin'])
 else:
  d['ELS_down_denominator']=num('Limite descendente L/','els_down',b['ELS_down_denominator'])
  d['ELS_up_denominator']=num('Limite ascendente L/','els_up',b['ELS_up_denominator'])
  st.caption('Limite escolhido por sentido de cada combinação ELS; conferir critério da aplicação.')

st.session_state['last_input']=copy.deepcopy(d)
try:
 drawing_data=copy.deepcopy(d)
 if d['load_mode']=='area':
  try:
   pv=area_bundle(d);govern=max(pv['combinations'],key=lambda c:abs(c['q_N_mm']))
   drawing_data.update(q_uls=govern['q_N_mm'],P_uls=govern.get('P_N',0.),x_uls=d['L_mm']/2)
   st.caption('Esquema: maior módulo de q entre as combinações selecionadas — '+govern['id'])
  except (ValueError,KeyError,TypeError):drawing_data.update(q_uls=0.,P_uls=0.)
 st.markdown(svg(drawing_data),unsafe_allow_html=True)
 token=fingerprint(d)
except (ValueError,TypeError,KeyError,ZeroDivisionError):token=None;st.caption('Complete geometria e ações para atualizar o esquema.')
if 'result' in st.session_state and st.session_state.result['input_fingerprint']!=token:
 st.session_state.pop('result');st.info('Entradas alteradas. Calcule novamente; os resultados e exportações anteriores foram retirados.')
if st.button('Calcular verificações disponíveis',type='primary'):
 st.session_state.pop('result',None)
 try:
  with st.spinner('Calculando o caso informado…'):st.session_state.result=calculate_batch(d) if d['load_mode']=='area' else calculate(d)
 except (ValueError,TypeError,KeyError,ZeroDivisionError) as exc:st.error('Não foi possível calcular: '+str(exc))
if 'result' in st.session_state:
 result=st.session_state.result
 st.subheader('Resultados por verificação')
 st.warning('Resultado parcial, sem aprovação global. “Atende” se refere somente ao critério e às entradas indicados.')
 batch=result.get('schema')=='tercas_batch_results_v1'
 if batch:
  for warning in dict.fromkeys(w for case in result['cases'] for w in case['warnings']):st.warning(warning)
  st.dataframe(display_frame(result['summary']),hide_index=True,width='stretch')
  st.caption('Máximos por verificação entre os casos calculados. Pendências em outras combinações permanecem visíveis; não há combinação global aprovada.')
  with st.expander('Resultados de cada combinação'):
   names=[f"{c['combination']['id']} — {c['combination']['type']}" for c in result['cases']]
   selected=st.selectbox('Combinação para consultar',range(len(names)),format_func=lambda i:names[i])
   item=result['cases'][selected];st.caption(measurement_text(item['combination']['expression'])+f"; q normal={fmt(item['combination']['q_kN_m'])} kN/m; P normal={fmt(item['combination'].get('P_N',0)/1000)} kN")
   st.dataframe(display_frame(item['rows']),hide_index=True,width='stretch')
   if item.get('evidence',{}).get('inclination'):show_inclination(item['evidence']['inclination'])
 else:
  for warning in result.get('coverage_warnings',[]):st.warning(warning)
  if result.get('numerical_warnings'):st.warning('A integração da flecha emitiu aviso numérico. A verificação ELS ficou pendente; demais resultados foram preservados.')
  st.dataframe(display_frame(rows(result)),hide_index=True,width='stretch')
  if result.get('inclination_evidence'):show_inclination(result['inclination_evidence'])
 c1,c2,c3=st.columns(3)
 with c1:st.download_button('Baixar memória parcial (Word)',batch_word(result) if batch else word(result),file_name='MC_terca_parcial.docx',mime='application/vnd.openxmlformats-officedocument.wordprocessingml.document')
 with c2:st.download_button('Baixar estudo e resultados (JSON)',json.dumps(result,ensure_ascii=False,indent=2),file_name='terca_estudo_resultados.json',mime='application/json')
 with c3:st.download_button('Baixar entradas (JSON)',json.dumps(d,ensure_ascii=False,indent=2),file_name='terca_entradas.json',mime='application/json')
 with st.expander('Memória numérica e rastreabilidade'):st.json(result)

with st.expander('Abrir entradas JSON',expanded=False):
 st.caption('Abra somente entradas exportadas por esta versão. O arquivo não executa código. Os resultados são sempre recalculados.')
 upload=st.file_uploader('Arquivo de entradas',type=['json'],key=f'import_{r}')
 if upload is not None and st.button('Aplicar entradas do arquivo'):
  try:
   if upload.size>200000:raise ValueError('Arquivo maior que 200 kB.')
   from tercas.application import build_spec
   new=json.loads(upload.getvalue())
   from tercas.inclination_adapter import configuration
   from tercas.inclination import number
   configuration(new)
   for field in ['q_parallel_uls','q_parallel_sls','P_parallel_uls','P_parallel_sls']:number(new.get(field,0),field)
   if new.get('load_mode')=='area':
    bundle=area_bundle(new);build_spec(case_inputs(new,bundle['combinations'][0]))
   else:build_spec(new)
   load(new);st.rerun()
  except (ValueError,TypeError,KeyError,UnicodeDecodeError) as exc:st.error('Arquivo não aplicado: '+str(exc))

st.caption('Método documentado na Rev07. Programa de domínio restrito: não dimensiona ligações, torção primária ou sistemas contínuos. Nenhum crédito de travamento da telha.')

