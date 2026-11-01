"""Optional isolated Streamlit panel; import render(st) explicitly only in a test app."""
import numpy as np
if __package__:
 from .adapter import run,ensure_current,export_json,mode_at,section_svg,NotEvaluated
else:
 from adapter import run,ensure_current,export_json,mode_at,section_svg,NotEvaluated

class ScopedUI:
 def __init__(self,st,namespace):self._st=st;self._namespace=namespace
 def __getattr__(self,name):
  if name=='columns':return lambda *a,**k:[ScopedUI(c,self._namespace) for c in self._st.columns(*a,**k)]
  target=getattr(self._st,name)
  if name in ('number_input','selectbox','button','download_button'):
   def call(label,*a,**k):
    k.setdefault('key',self._namespace+'::'+str(label));return target(label,*a,**k)
   return call
  return target

def render(st,namespace='fsm_experimental'):
 if not isinstance(namespace,str) or not namespace:raise ValueError('namespace obrigatório')
 st=ScopedUI(st,namespace)
 st.subheader('Laboratório experimental — faixas finitas U/Ue')
 st.warning('Estudo elástico, não dimensionamento: não preenche automaticamente críticos nem aprova resistência.')
 st.caption('Cantos retos, sem furos; seção de linha média; apoio simples nas extremidades do meia onda longitudinal. X horizontal e Y vertical, sem presumir qual inércia é maior.')
 with st.expander('Geometria e solicitação',expanded=True):
  c=st.columns(4);h=c[0].number_input('Alma externa h [mm]',value=200.,min_value=1.,format='%.2f');b=c[1].number_input('Mesa externa b [mm]',value=75.,min_value=1.,format='%.2f');lip=c[2].number_input('Enrijecedor externo [mm] — 0 para U',value=20.,min_value=0.,format='%.2f');t=c[3].number_input('Espessura [mm]',value=2.,min_value=.01,format='%.2f')
  c=st.columns(2);axis=c[0].selectbox('Eixo geométrico de flexão',['x','y']);sign=c[1].selectbox('Sinal do momento',[1,-1])
  with st.expander('Malha, material e domínio da assinatura'):
   E=st.number_input('E [MPa]',value=200000.,min_value=1.,format='%.2f');nu=st.number_input('Coeficiente de Poisson',value=.3,min_value=0.,max_value=.49,format='%.2f');n=st.selectbox('Refinamento transversal',[2,4,6],index=1);lmin=st.number_input('Meia onda longitudinal mínimo [mm]',value=10.,min_value=.01,format='%.2f');lmax=st.number_input('Meia onda longitudinal máximo [mm]',value=1000.,min_value=.02,format='%.2f');samples=st.selectbox('Pontos da assinatura',[21,41,61],index=0)
  submit=st.button('Calcular assinatura experimental')
 request={'geometry':{'h_mm':h,'b_mm':b,'lip_mm':lip,'t_mm':t},'E_MPa':E,'nu':nu,'axis':axis,'moment_sign':sign,'mesh_n':n,'halfwaves_mm':np.geomspace(lmin,lmax,samples).tolist()}
 key=namespace+'_result'
 if submit:
  st.session_state.pop(key,None)
  try:
   with st.spinner('Calculando assinatura amostral…'):st.session_state[key]=run(request)
  except (ValueError,ArithmeticError,NotEvaluated) as exc:st.error(str(exc))
 result=st.session_state.get(key)
 if result is None:return
 try:ensure_current(request,result)
 except ValueError as exc:st.warning(str(exc));return
 st.caption(result['mode_classification'])
 st.dataframe([{'Meia onda longitudinal [mm]':f"{r['halfwave_mm']:.2f}",'Fator elástico para momento [kN·m]':f"{r['first_positive_factor_kNm']:.2f}"} for r in result['curve']],hide_index=True)
 index=st.selectbox('Ponto para visualizar forma modal',range(len(result['curve'])),format_func=lambda i:f"{result['curve'][i]['halfwave_mm']:.2f} mm")
 try:
  mode=mode_at(request,result,index);st.markdown(section_svg(mode),unsafe_allow_html=True);st.caption(mode['warning'])
 except (ValueError,ArithmeticError,NotEvaluated) as exc:st.error(str(exc))
 with st.expander('Premissas e rastreabilidade'):
  st.write(result['limitations']);st.json({'input':result['input'],'request_sha256':result['request_sha256'],'implementation_sha256':result['implementation_sha256']})
 st.download_button('Exportar estudo experimental JSON',export_json(request,result),'fsm_experimental.json','application/json')

if __name__=='__main__':
 import streamlit as st
 st.set_page_config(page_title='Laboratório FSM — cópia isolada');render(st)
