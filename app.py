"""Streamlit entry point. User inputs are untrusted; no global approval state."""
import copy,json,math
import pandas as pd
import streamlit as st
from tercas.application import defaults,example,calculate,rows,fingerprint,VERSION
from tercas.drawing import svg
from tercas.report import word

st.set_page_config(page_title='LRO | Terças',page_icon='🏗️',layout='wide')
st.markdown('<style>.block-container{max-width:1200px} h1,h2,h3{color:#25334a} div.stButton>button[kind="primary"]{background:#d96516;border:0}</style>',unsafe_allow_html=True)
st.title('LRO | Terças')
st.caption(f'NBR 14762:2010 · {VERSION} · primeira emissão restrita')
st.info('Um vão, perfis U/Ue e flexão no eixo forte. A telha não é considerada como travamento. Resultados por verificação, sem aprovação global automática.')

if 'base' not in st.session_state:st.session_state.base=defaults()
if 'revision' not in st.session_state:st.session_state.revision=0

def load(d):
 st.session_state.base=copy.deepcopy(d);st.session_state.revision+=1
 st.session_state.pop('result',None)

left,right=st.columns([2,1])
with right:
 if st.button('Carregar exemplo didático',help='Carrega dados sintéticos, explicitamente marcados. Não representa produto ou projeto validado.'):load(example());st.rerun()
with left:
 index=st.selectbox('Perfil de catálogo',range(3),format_func=lambda i:['U 100 × 50 × 2,00 — Tuper','Ue 100 × 50 × 17 × 2,00 — Tuper','Ue 150 × 60 × 20 × 2,00 — Tuper'][i],index=st.session_state.base['catalog_index'],key=f'catalog_{st.session_state.revision}')
 if index!=st.session_state.base['catalog_index']:load(defaults(index));st.rerun()
b=st.session_state.base;r=st.session_state.revision;d=copy.deepcopy(b)
if b.get('synthetic'):st.warning('EXEMPLO DIDÁTICO: propriedades complementares, críticos e contatos sintéticos. Substitua pelos dados do seu caso antes de usar resultados.')

def num(label,key,value,unit='',step=None):
 kw={'label':label+(f' [{unit}]' if unit else ''),'value':None if value is None else float(value),'key':f'{key}_{r}','format':'%.6f'}
 if step is not None:kw['step']=step
 return st.number_input(**kw)

def txt(label,key,value):return st.text_input(label,value=str(value),key=f'{key}_{r}')

d['project']=txt('Identificação do estudo','project',b['project'])
c1,c2,c3=st.columns(3)
with c1:d['L_mm']=num('Vão entre apoios','L',b['L_mm'],'mm')
with c2:d['properties']['fy_MPa']=num('fy do aço — informar','fy',b['properties']['fy_MPa'],'MPa')
with c3:d['properties']['ri_mm']=num('Raio interno — informar','ri',b['properties']['ri_mm'],'mm')

with st.expander('Perfil, aço e origem dos dados',expanded=False):
 st.caption('Campos do catálogo conferidos: geometria, área, massa, Ix, Iy e Wx. O fabricante não fornece nesta tabela todos os dados necessários. Não copiamos valores ausentes da planilha.')
 cols=st.columns(3)
 labels={'A_cm2':'Área [cm²]','mass_kg_m':'Massa linear [kg/m]','Ix_cm4':'Ix [cm⁴]','Wx_cm3':'Wx [cm³]','Iy_cm4':'Iy [cm⁴]','E_MPa':'E [MPa]','G_MPa':'G [MPa]','fu_MPa':'fu [MPa]','J_mm4':'J [mm⁴]','Cw_mm6':'Cw [mm⁶]'}
 for i,(key,label) in enumerate(labels.items()):
  with cols[i%3]:d['properties'][key]=num(label,key,b['properties'][key])
 d['property_origin']=txt('Origem dos dados complementares / alterações','property_origin',b['property_origin'])
 st.markdown('[Catálogo Tuper — telhas e perfis](https://tuper-prd.s3.sa-east-1.amazonaws.com/wp-content/uploads/2021/08/11082537/Catalogo-Telhas-e-Perfis.pdf)')
 st.caption('Conferir a convenção de Wx e das propriedades usadas em conjunto. Editar valores não comprova a correspondência física.')

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

with st.expander('Estabilidade, críticos e trechos',expanded=True):
 st.caption('Ml e Mdist são críticos elásticos da mesma seção. Não são momentos resistentes. Sem dado suficiente, só a verificação afetada fica pendente.')
 c1,c2=st.columns(2)
 with c1:m=num('Ml — crítico local','Ml',None if b['Ml_Nmm'] is None else b['Ml_Nmm']/1e6,'kN·m');d['Ml_Nmm']=None if m is None else m*1e6
 with c2:m=num('Mdist — quando não dispensado','Mdist',None if b['Mdist_Nmm'] is None else b['Mdist_Nmm']/1e6,'kN·m');d['Mdist_Nmm']=None if m is None else m*1e6
 d['critical_origin']=txt('Origem dos críticos / método e seção','critical_origin',b['critical_origin'])
 selection=st.selectbox('Domínio da expressão de Me nesta emissão',['Não informado / outra situação','Eixo forte de simetria; sem torção primária ou efeito de altura neste modelo'],index=1 if b['route_domain'] else 0,key=f'domain_{r}')
 d['route_domain']=selection.startswith('Eixo')
 st.caption('Esta seleção é uma hipótese do modelo, não uma verificação do caminho da torção. Ly e Lz são independentes; um tirante lateral não é automaticamente travamento torsional.')
 df=pd.DataFrame(b['segments'],columns=['start_mm','end_mm','Ly_effective_mm','Lz_effective_mm','Cb_mode','restraint_provenance'])
 edited=st.data_editor(df,num_rows='dynamic',hide_index=True,key=f'segments_{r}',column_config={'start_mm':'Início [mm]','end_mm':'Fim [mm]','Ly_effective_mm':'Ly efetivo [mm]','Lz_effective_mm':'Lz efetivo [mm]','restraint_provenance':'Origem / hipótese do vínculo','Cb_mode':st.column_config.SelectboxColumn('Cb',options=['one','quarter_formula'])},width='stretch')
 d['segments']=edited.astype(object).where(pd.notna(edited),None).to_dict('records')
 st.caption('Cb: one = 1,0; quarter_formula = momentos nos quartos do próprio trecho. Os trechos não alteram a estática vertical do vão.')

with st.expander('Apoios, introdução de P e limite de flecha',expanded=False):
 c1,c2=st.columns(2)
 with c1:d['left_web']=st.selectbox('Apoio esquerdo',['Detalhe não informado','Alma ligada a viga/pilar (§9.5.1)'],index=int(b['left_web']),key=f'left_{r}').startswith('Alma')
 with c2:d['right_web']=st.selectbox('Apoio direito',['Detalhe não informado','Alma ligada a viga/pilar (§9.5.1)'],index=int(b['right_web']),key=f'right_{r}').startswith('Alma')
 d['support_origin']=txt('Origem do detalhe dos apoios','support_origin',b['support_origin'])
 st.caption('A exceção de enrijecedor não dimensiona a ligação. Outros detalhes ficam pendentes nesta emissão.')
 d['patch_mm']=num('Comprimento longitudinal de contato de P','patch',b['patch_mm'],'mm')
 d['patch_origin']=txt('Origem do contato de P','patch_origin',b['patch_origin'])
 st.caption('Anexo D nesta interface: força de compressão isolada e interna, aplicada à mesa. Próximo ao apoio ou outro detalhe: não avaliado, sem bloquear os cálculos globais.')
 d['ELS_limit_mm']=num('Limite de flecha adotado','els_limit',b['ELS_limit_mm'],'mm')
 d['ELS_origin']=txt('Origem / aplicação do limite de flecha','els_origin',b['ELS_origin'])

try:
 st.markdown(svg(d),unsafe_allow_html=True)
 token=fingerprint(d)
except (ValueError,TypeError,KeyError,ZeroDivisionError):token=None;st.caption('Complete geometria e ações para atualizar o esquema.')
if 'result' in st.session_state and st.session_state.result['input_fingerprint']!=token:
 st.session_state.pop('result');st.info('Entradas alteradas. Calcule novamente; os resultados e exportações anteriores foram retirados.')
if st.button('Calcular verificações disponíveis',type='primary'):
 st.session_state.pop('result',None)
 try:
  with st.spinner('Calculando o caso informado…'):st.session_state.result=calculate(d)
 except (ValueError,TypeError,KeyError,ZeroDivisionError) as exc:st.error('Não foi possível calcular: '+str(exc))
if 'result' in st.session_state:
 result=st.session_state.result
 st.subheader('Resultados por verificação')
 st.warning('Resultado parcial, sem aprovação global. “Atende” se refere somente ao critério e às entradas indicados.')
 for warning in result.get('coverage_warnings',[]):st.warning(warning)
 if result.get('numerical_warnings'):st.warning('A integração da flecha emitiu aviso numérico. A verificação ELS ficou pendente; demais resultados foram preservados.')
 st.dataframe(pd.DataFrame(rows(result)),hide_index=True,width='stretch')
 c1,c2,c3=st.columns(3)
 with c1:st.download_button('Baixar memória parcial (Word)',word(result),file_name='MC_terca_parcial.docx',mime='application/vnd.openxmlformats-officedocument.wordprocessingml.document')
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
   new=json.loads(upload.getvalue());build_spec(new);load(new);st.rerun()
  except (ValueError,TypeError,KeyError,UnicodeDecodeError) as exc:st.error('Arquivo não aplicado: '+str(exc))

st.caption('Método documentado na Rev07. Programa de domínio restrito: não dimensiona ligações, torção primária ou sistemas contínuos. Nenhum crédito de travamento da telha.')
