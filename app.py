"""Streamlit entry point. User inputs are untrusted; no global approval state."""
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

st.set_page_config(page_title='LRO | Terças',page_icon='🏗️',layout='wide')
st.markdown('<style>.block-container{max-width:1200px} h1,h2,h3{color:#25334a} div.stButton>button[kind="primary"]{background:#d96516;border:0}</style>',unsafe_allow_html=True)
st.title('LRO | Terças')
st.caption(f'NBR 14762:2010 · {VERSION} · primeira emissão restrita')
st.info('Um vão, perfis U/Ue e flexão no eixo forte. A telha não é considerada como travamento. Resultados por verificação, sem aprovação global automática.')

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
d=copy.deepcopy(b)
if b.get('synthetic'):st.warning('EXEMPLO DIDÁTICO: propriedades complementares, críticos e contatos sintéticos. Substitua pelos dados do seu caso antes de usar resultados.')

def num(label,key,value,unit='',step=None):
 kw={'label':label+(f' [{unit}]' if unit else ''),'value':None if value is None else float(value),'key':f'{key}_{r}','format':'%.6f'}
 if step is not None:kw['step']=step
 return st.number_input(**kw)

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
 st.caption(f"fy = {mat['properties']['fy_MPa']:g} MPa · fu = {mat['properties']['fu_MPa']:g} MPa. Conferir especificação do produto.")

with st.expander('Perfil, aço e origem dos dados',expanded=False):
 st.caption('209 perfis da planilha V03 fornecida por Lucas; fontes e linha de origem preservadas. Críticos tabulados de Pierin/DimPerfil quando disponíveis. A transcrição não é certificação do produto.')
 cols=st.columns(3)
 labels={'A_cm2':'Área [cm²]','mass_kg_m':'Massa linear [kg/m]','Ix_cm4':'Ix [cm⁴]','Wx_cm3':'Wx [cm³]','Iy_cm4':'Iy [cm⁴]','ri_mm':'Raio interno [mm]','J_mm4':'J [mm⁴]','Cw_mm6':'Cw [mm⁶]'}
 for i,(key,label) in enumerate(labels.items()):
  with cols[i%3]:d['properties'][key]=num(label,key,b['properties'][key])
 extra_origin=txt('Origem dos dados complementares / alterações','property_origin',b['property_origin'])
 d['property_origin']=(f"Aço {mat['name']}: {mat['origin']}; {mat['physical_origin']}; " if mat else '')+extra_origin
 st.caption(f"E = {d['properties']['E_MPa']} MPa · G = {d['properties']['G_MPa']} MPa — NBR 14762.")
 st.caption('Fonte: '+catalog_entry(index)['source_url']+'; linha '+str(catalog_entry(index)['source_workbook_row'])+' da planilha original.')
 st.caption('Conferir a convenção de Wx e das propriedades usadas em conjunto. Editar valores não comprova a correspondência física.')

st.subheader('Carregamentos')
mode=st.radio('Forma de entrada',['Ações já combinadas (ELU e ELS)','Cargas por área e combinações automáticas'],index=1 if b.get('load_mode')=='area' else 0,key=f'load_mode_{r}')
d['load_mode']='area' if mode.startswith('Cargas') else 'direct'
if d['load_mode']=='direct':
 st.subheader('Ações de uma combinação')
 st.caption('q positivo e P positivo atuam no mesmo sentido do esquema. q em kN/m equivale numericamente a N/mm. P é informado em kN. Inclua peso próprio nas ações; o app não o soma silenciosamente.')
 a,bcol=st.columns(2)
 with a:
  st.markdown('**ELU — valores já ponderados**')
  d['q_uls']=num('q ELU','q_uls',b['q_uls'],'kN/m');p=num('P ELU','P_uls',b['P_uls']/1000,'kN');d['P_uls']=None if p is None else p*1000;d['x_uls']=num('Posição de P ELU','x_uls',b['x_uls'],'mm')
 with bcol:
  st.markdown('**ELS — combinação de serviço**')
  d['q_sls']=num('q ELS','q_sls',b['q_sls'],'kN/m');p=num('P ELS','P_sls',b['P_sls']/1000,'kN');d['P_sls']=None if p is None else p*1000;d['x_sls']=num('Posição de P ELS','x_sls',b['x_sls'],'mm')
 d['actions_origin']=txt('Identificação e origem das combinações','actions_origin',b['actions_origin'])
 
else:
 st.caption('Informe módulos positivos em kgf/m². Vento para cima recebe sinal negativo. PP vem da massa linear, sem campo adicional; CP não deve repetir PP.')
 area=copy.deepcopy(b['area_inputs']);cols=st.columns(2)
 labels=[('spacing_m','Distância entre terças','m'),('permanent_kgf_m2','Carregamento permanente','kgf/m²'),('live_kgf_m2','Sobrecarga','kgf/m²'),('wind_up_kgf_m2','Vento para cima','kgf/m²'),('wind_down_kgf_m2','Vento para baixo','kgf/m²')]
 for i,(key,label,unit) in enumerate(labels):
  with cols[i%2]:area[key]=num(label,key,area[key],unit)
 d['area_inputs']=area
 d['selected_types']=st.multiselect('Tipos de combinações consideradas',COMBINATION_TYPES,default=b['selected_types'],key=f'combo_types_{r}')
 st.caption(f"Massa linear selecionada: {d['properties']['mass_kg_m']} kg/m. Matriz fixa fornecida por Lucas: 32 ELU normal, 8 ELS rara, 6 frequente e 2 quase permanente.")
 with st.expander('Casos e combinações que serão calculados'):
  try:
   preview=area_bundle(d)
   st.dataframe(pd.DataFrame([{'Caso':k,'q [kN/m]':v} for k,v in preview['case_q_N_mm'].items()]),hide_index=True)
   st.dataframe(pd.DataFrame([{'ID':c['id'],'Tipo':c['type'],'Expressão':c['expression'],'q [kN/m]':c['q_kN_m']} for c in preview['combinations']]),hide_index=True)
  except (ValueError,TypeError,KeyError) as exc:st.warning(str(exc))

with st.expander('Estabilidade, críticos e trechos',expanded=True):
 st.caption('Ml e Mdist são críticos elásticos da mesma seção. Não são momentos resistentes. Sem dado suficiente, só a verificação afetada fica pendente.')
 c1,c2=st.columns(2)
 with c1:m=num('Ml — crítico local','Ml',None if b['Ml_Nmm'] is None else b['Ml_Nmm']/1e6,'kN·m');d['Ml_Nmm']=None if m is None else m*1e6
 with c2:m=num('Mdist — quando não dispensado','Mdist',None if b['Mdist_Nmm'] is None else b['Mdist_Nmm']/1e6,'kN·m');d['Mdist_Nmm']=None if m is None else m*1e6
 d['critical_origin']=txt('Origem dos críticos / método e seção','critical_origin',b['critical_origin'])
 selection=st.selectbox('Domínio da expressão de Me nesta emissão',['Não informado / outra situação','Eixo forte de simetria; sem torção primária ou efeito de altura neste modelo'],index=1 if b['route_domain'] else 0,key=f'domain_{r}')
 d['route_domain']=selection.startswith('Eixo')
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
  with c1:upper=num('Comprimento efetivo da mesa superior','upper',length_value('Ly_top_effective_mm'),'mm')
  with c2:lower=num('Comprimento efetivo da mesa inferior','lower',length_value('Ly_bottom_effective_mm'),'mm')
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
  st.caption(f'Trecho de cálculo automático: 0 até {d["L_mm"] if d["L_mm"] is not None else "—"} mm, conforme o vão informado acima.')
 else:
  for seg in source_segments:seg['Cb_mode']=CB_LABELS[seg['Cb_mode']]
  df=pd.DataFrame(source_segments,columns=['start_mm','end_mm','Ly_top_effective_mm','Ly_bottom_effective_mm','Lz_effective_mm','Cb_mode','restraint_provenance'])
  edited=st.data_editor(df,num_rows='dynamic',hide_index=True,key=f'segments_{r}',column_config={'start_mm':'Início [mm]','end_mm':'Fim [mm]','Ly_top_effective_mm':'Mesa superior — comprimento efetivo [mm]','Ly_bottom_effective_mm':'Mesa inferior — comprimento efetivo [mm]','Lz_effective_mm':'Lz torsional [mm]','restraint_provenance':'Origem / hipótese do vínculo','Cb_mode':st.column_config.SelectboxColumn('Cb',options=list(CB_LABELS.values()))},width='stretch')
  d['segments']=edited.astype(object).where(pd.notna(edited),None).to_dict('records')
  for seg in d['segments']:seg['Cb_mode']=cb_code(seg.get('Cb_mode') or 'one')
  st.caption('Início e fim são os limites físicos do diagrama usado no Cb; Ly e Lz são comprimentos efetivos e podem diferir desse intervalo por condição de vínculo. Trechos representam o diagrama usado no Cb; não criam apoios verticais nem comprovam travamentos. Uma inversão do momento não é um travamento.')

 st.session_state[f'last_segments_{r}']=copy.deepcopy(d['segments'])
 st.session_state[f'last_span_{r}']=d['L_mm']

with st.expander('Introdução de P e limite de flecha',expanded=False):
 st.caption('Apoios e ligações não são dimensionados neste app. O cálculo da terça mantém as hipóteses de introdução das forças aplicáveis; não há aprovação automática do detalhe.')
 d['patch_mm']=num('Comprimento longitudinal de contato de P','patch',b['patch_mm'],'mm')
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
   drawing_data.update(q_uls=govern['q_N_mm'],P_uls=0.)
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
  st.dataframe(pd.DataFrame(result['summary']),hide_index=True,width='stretch')
  st.caption('Máximos por verificação entre os casos calculados. Pendências em outras combinações permanecem visíveis; não há combinação global aprovada.')
  with st.expander('Resultados de cada combinação'):
   names=[f"{c['combination']['id']} — {c['combination']['type']}" for c in result['cases']]
   selected=st.selectbox('Combinação para consultar',range(len(names)),format_func=lambda i:names[i])
   item=result['cases'][selected];st.caption(item['combination']['expression']+f"; q={item['combination']['q_kN_m']:.6f} kN/m")
   st.dataframe(pd.DataFrame(item['rows']),hide_index=True,width='stretch')
 else:
  for warning in result.get('coverage_warnings',[]):st.warning(warning)
  if result.get('numerical_warnings'):st.warning('A integração da flecha emitiu aviso numérico. A verificação ELS ficou pendente; demais resultados foram preservados.')
  st.dataframe(pd.DataFrame(rows(result)),hide_index=True,width='stretch')
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
   if new.get('load_mode')=='area':
    bundle=area_bundle(new);build_spec(case_inputs(new,bundle['combinations'][0]))
   else:build_spec(new)
   load(new);st.rerun()
  except (ValueError,TypeError,KeyError,UnicodeDecodeError) as exc:st.error('Arquivo não aplicado: '+str(exc))

st.caption('Método documentado na Rev07. Programa de domínio restrito: não dimensiona ligações, torção primária ou sistemas contínuos. Nenhum crédito de travamento da telha.')

