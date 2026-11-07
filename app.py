"""Streamlit entry point. User inputs are untrusted; no global approval state."""
from tercas.presentation import fmt, display, display_records, display_frame, measurement_text, DISPLAY_NOTE
import copy,json,math
import pandas as pd
import streamlit as st
from tercas.application import defaults,example,calculate,rows,fingerprint,VERSION
from tercas.drawing import svg
from tercas.member_application import is_girt
from tercas.three_girt_application import enabled as three_girt_enabled,SCHEMA as THREE_GIRT_SCHEMA
from tercas.drawing_cases import drawing_cases
from tercas.catalog_scan import scan_catalog,inputs_for_section
from tercas.report import word,batch_word
from tercas.catalogs import catalog_labels,STEEL_NAMES,material,critical_defaults,catalog_entry
from tercas.batch import calculate_batch,area_bundle,case_inputs
from tercas.load_combinations import COMBINATION_TYPES
from tercas.model_domain import TEXT as DOMAIN_TEXT,evidence as domain_evidence,export_inputs as domain_export_inputs,HISTORICAL as DOMAIN_HISTORICAL,historical_rows as domain_historical_rows,historical_inclination as domain_historical_inclination,VERSION as DOMAIN_VERSION,explicit_panel_conflict as domain_explicit_panel_conflict
from tercas.homogeneous_reference import FIELD as REFERENCE_FIELD, assess as assess_reference, activate as activate_reference
from tercas.homogeneous_reference_ui import loader as reference_loader, render as render_reference
from tercas.ue_reference import FIELD as UE_REFERENCE_FIELD, claims_reference as claims_ue_reference, assess as assess_ue_reference, activate as activate_ue_reference
from tercas.ue_reference_ui import loader as ue_reference_loader, render as render_ue_reference
from tercas.ue_family_reference import FIELD as UE_FAMILY_FIELD, claims_reference as claims_ue_family, assess as assess_ue_family, activate as activate_ue_family
from tercas.ue_catalog_reference import FIELD as UE_CATALOG_FIELD, EVIDENCE as UE_CATALOG_EVIDENCE, claims_reference as claims_ue_catalog
from tercas.ue_family_ui import loader as ue_family_loader, render as render_ue_family
from tercas.ux_inputs import CB_LABELS,cb_code,flange_segments,whole_span
from tercas.new_study_policy import for_new_study, initialize_session
from tercas.pierin_ue_registry_ui import render as render_new_pierin_ue_study
from tercas.point_contact_ui import render as render_point_contact, show_saved_results as show_point_contact_results

def show_elastic_wall(evidence):
 if not isinstance(evidence,dict):return
 for key,label in [('elastic_vertical','Flecha vertical fraca — estudo elástico bruto'),('elastic_tie_study','Tirantes verticais — estudo elástico bruto')]:
  if key in evidence:
   st.markdown('**'+label+'**');st.warning('Diagnóstico elástico bruto; não resistência nem aprovação. Sem crédito automático em FLT ou torção.');st.caption('Flecha livre e resposta condicional com molas são distintas. Conferir reações e eventual momento negativo; não substituir o vão por L/n.');st.json(evidence[key])

def show_inclination(evidence,girt=False):
 """Display concurrent effects; never interpret missing resistance as approval."""
 if not isinstance(evidence,dict):return
 if 'states' not in evidence:
  for state,item in evidence.items():
   if isinstance(item,dict):
    st.markdown('**'+str(state)+' — solicitações locais**');show_inclination(item,girt=girt)
  return
 st.caption(evidence.get('convention','Esforços simultâneos na mesma seção e combinação.'))
 st.warning(evidence.get('resistance_status','Resistência biaxial não avaliada; os esforços não constituem aprovação.'))
 if evidence.get('weak_axis_capacities'):
  caps=[]
  for sign,c in evidence['weak_axis_capacities'].items():
   caps.append({'Sentido':{'positive':'My positivo','negative':'My negativo'}[sign],'Estado':('Exploratório — hipótese inferida pendente' if c.get('conditional_assumption') else 'Calculado com dados informados') if c.get('MRd_Nmm') else 'Dados pendentes','Me Anexo E [kN·m]':c.get('annex_e',{}).get('Me_Nmm',0)/1e6 if c.get('annex_e') else None,'MRd fraco [kN·m]':c.get('MRd_Nmm',0)/1e6 if c.get('MRd_Nmm') else None,'Origem / faltas':c.get('provenance',', '.join(c.get('missing',[])))+' '+ ' '.join(c.get('automatic_inputs',{}).get('warnings',[]))})
  st.dataframe(display_frame(caps),hide_index=True,width='stretch')
 records=[]
 for state in evidence.get('states',[]):
  row={'Estado limite':state.get('position_limit','Posição fixa'),'x [mm]':state.get('x_mm'),'Lado da seção':{'left':'Esquerda','right':'Direita'}.get(state.get('side'),'—')}
  for axis,label in [('normal','Horizontal / eixo forte' if girt else 'Normal / eixo forte'),('parallel','Vertical / eixo fraco' if girt else 'Paralelo / eixo fraco')]:
   v=state.get(axis,{})
   for k,title,scale in [('M_Nmm','M [kN·m]',1e6),('V_N','V [kN]',1000),('Rleft_N','Reação esquerda [kN]',1000),('Rright_N','Reação direita [kN]',1000)]:
    if k in v:row[label+' — '+title]=v[k]/scale
  records.append(row)
 if records:st.dataframe(display_frame(records),hide_index=True,width='stretch')
 st.caption('Valores nas seções listadas; não são envelope biaxial nem resistência. P e q são considerados juntos na mesma combinação.')

def render_results(result,d):
 from tercas.study_completion import show_global
 show_global(st,result)
 from tercas.roof_top_nbr_ui import presentation_rows as roof_nbr_rows, presentation_inclination as roof_nbr_inclination
 from tercas.roof_top_load_ui import show_result as show_roof_top_load
 show_roof_top_load(st,result)
 from tercas.biaxial_component_ui import show as show_biaxial_component
 from tercas.flexural_components import presentation_rows as gross_component_rows,is_girt_result
 show_biaxial_component(st,result)
 from tercas.aa_component_ui import show as show_aa_component
 show_aa_component(st,result)
 from tercas.ue_catalog_ui import show as show_ue_catalog
 show_ue_catalog(st,result)
 from tercas.torsion_study_ui import show_result as show_torsion
 show_torsion(st,result)
 from tercas.aisi_torsion_ui import show as show_aisi_torsion
 show_aisi_torsion(st,result)
 from tercas.isolated_en_ui import show as show_isolated_EN
 show_isolated_EN(st,result)
 from tercas.torsion_material_ui import render as show_nominal_material
 result=show_nominal_material(st,result)
 if result.get('deflection_scope_evidence'):
  st.caption(result['deflection_scope_evidence']['text'])
 girt=is_girt(d)
 if 'model_domain_evidence' not in result:st.warning(DOMAIN_HISTORICAL)
 if result.get('schema')==THREE_GIRT_SCHEMA:
  from tercas.three_girt_ui import render_result as show_three_girt_result
  show_three_girt_result(st,result)
 else:
  st.subheader('Resultados por verificação')
  st.warning('Resultado parcial, sem aprovação global. “Atende” se refere somente ao critério e às entradas indicados.')
  if result.get('ue_family_reference_evidence'):
   record=result['ue_family_reference_evidence']
   st.caption('Fonte numérica ativa: '+record['reference_id']+'; propriedades e críticos próprios individuais.')
   st.warning('Família Ue100: D forte calculado, sem dispensa Tabela 14. D da alma é piso conservador discreto individual, não modo identificado.')
   st.caption(('A componente flexional biaxial e os complementos seccionais de torção têm somente o alcance explicitamente registrado; ELS físico completo e conclusão global permanecem separados. ' if ('gross_biaxial_component_evidence' in result or 'aa_web_component_evidence' in result) else 'ELS biaxial e conclusão global permanecem separados dos complementos seccionais de torção explicitamente registrados. ')+'Pierin somente corresponde à família nominal.')
  if result.get('ue_reference_evidence'):
   record=result['ue_reference_evidence']
   st.caption('Fonte numérica ativa: '+record['active_numeric_reference'])
   st.caption(record['nominal_documentary_reference'])
   st.warning(record['distortion_note'])
   st.caption(record['ELS_status'])
  batch=result.get('schema')=='tercas_batch_results_v1'
  if batch:
   for warning in dict.fromkeys(w for case in result['cases'] for w in case['warnings']):st.warning(warning)
   st.dataframe(display_frame(domain_historical_rows(result,roof_nbr_rows(result,gross_component_rows(result,result['summary'])))),hide_index=True,width='stretch')
   st.caption('Máximos por verificação entre os casos calculados. Pendências em outras combinações permanecem visíveis; não há combinação global aprovada.')
   with st.expander('Resultados de cada combinação'):
    names=[f"{c['combination']['id']} — {c['combination']['type']}" for c in result['cases']]
    selected=st.selectbox('Combinação para consultar',range(len(names)),format_func=lambda i:names[i])
    item=result['cases'][selected];st.caption(measurement_text(item['combination']['expression'])+f"; q normal={fmt(item['combination']['q_kN_m'])} kN/m; P normal={fmt(item['combination'].get('P_N',0)/1000)} kN")
    st.dataframe(display_frame(domain_historical_rows(result,roof_nbr_rows(result,gross_component_rows(result,item['rows']),item['combination']['id']))),hide_index=True,width='stretch')
    if item.get('evidence',{}).get('inclination'):show_inclination(domain_historical_inclination(result,roof_nbr_inclination(result,item['evidence']['inclination'],item['combination']['id'])),girt=girt)
    if girt and not is_girt_result(result):show_elastic_wall(item.get('evidence',{}))
  else:
   for warning in result.get('coverage_warnings',[])+result.get('critical_warnings',[]):st.warning(warning)
   if result.get('numerical_warnings'):st.warning('O integrador escalar anterior emitiu aviso numérico, preservado como diagnóstico. O estado da componente tensorial nova é informado separadamente.' if ('gross_biaxial_component_evidence' in result or 'aa_web_component_evidence' in result) else 'A integração da flecha emitiu aviso numérico. A verificação ELS ficou pendente; demais resultados foram preservados.')
   st.dataframe(display_frame(rows(result)),hide_index=True,width='stretch')
   if result.get('inclination_evidence'):show_inclination(domain_historical_inclination(result,roof_nbr_inclination(result,result['inclination_evidence'])),girt=girt)
   if girt and not is_girt_result(result):show_elastic_wall(result)
  show_point_contact_results(st,result)
  from tercas.support_web.ui import render as render_support_web
  render_support_web(st,result,context="isolated")
  c1,c2,c3=st.columns(3)
  with c1:st.download_button('Baixar memória parcial (Word)',batch_word(result) if batch else word(result),file_name='MC_terca_parcial.docx',mime='application/vnd.openxmlformats-officedocument.wordprocessingml.document')
  with c2:st.download_button('Baixar estudo e resultados (JSON)',json.dumps(result,ensure_ascii=False,indent=2),file_name='terca_estudo_resultados.json',mime='application/json')
  with c3:st.download_button('Baixar entradas (JSON)',json.dumps(copy.deepcopy(d) if (result.get('homogeneous_reference_evidence') or result.get('ue_reference_evidence') or result.get('ue_family_reference_evidence')) else domain_export_inputs(d),ensure_ascii=False,indent=2),file_name='terca_entradas.json',mime='application/json')
  with st.expander('Memória numérica e rastreabilidade'):
   if girt:st.json(result)
   else:st.caption('Consulta parcial de dados já salvos, sem novo cálculo. O arquivo “Baixar estudo e resultados (JSON)” conserva o lote completo, todas as evidências e a precisão original.')
   if batch and not girt:
    detail_index=st.selectbox('Combinação para abrir a memória numérica',range(len(result['cases'])),index=None,
     placeholder='Selecione uma combinação para exibir os dados salvos',
     format_func=lambda i:result['cases'][i]['combination']['id']+' — '+result['cases'][i]['combination']['type'],
     key='saved_numeric_detail_'+str(result.get('input_fingerprint','historical')))
    if detail_index is not None:
     selected_case=result['cases'][detail_index];cid=selected_case['combination']['id']
     detail={'view_scope':'Consulta parcial de uma combinação; não é um novo resultado nem substitui o JSON completo.',
      'source_input_fingerprint':result.get('input_fingerprint'),'selected_case':selected_case}
     torsion=result.get('torsion_evidence')
     if isinstance(torsion,dict):
      detail['torsion_saved_context']={k:v for k,v in torsion.items() if k!='records'}
      detail['torsion_selected_record']=next((r for r in torsion.get('records',[]) if r.get('combination_id')==cid),None)
     from tercas.aisi_torsion_ui import _saved as saved_aisi_component
     try:aisi=saved_aisi_component(result)
     except (ValueError,TypeError,KeyError) as exc:
      st.error('Registro do complemento AISI inválido; detalhe não reproduzido: '+str(exc));aisi=None
     if isinstance(aisi,dict):
      detail['aisi_saved_context']={k:v for k,v in aisi.items() if k!='records'}
      detail['aisi_selected_record']=next((r for r in aisi.get('records',[]) if r.get('combination_id')==cid),None)
      if detail['aisi_selected_record'] is None:st.caption('Não há registro AISI para esta combinação no arquivo salvo. Nenhum cálculo foi acrescentado; H4 não verifica ELS.')
     if result.get('aa_web_component_evidence') is not None:
      from tercas.aa_component_ui import _read as saved_aa_component
      aa,aa_error=saved_aa_component(result)
      if aa_error:st.error(aa_error)
      elif isinstance(aa,dict):
       detail['aa_saved_context']={k:v for k,v in aa.items() if k!='records'}
       detail['aa_selected_record']=aa.get('records',{}).get(cid)
     st.caption('Os contextos e seus identificadores pertencem à emissão completa original; somente os registros da combinação escolhida são exibidos abaixo. Ausência de registro permanece ausência, sem recompor ou requalificar o histórico.')
     st.json(detail,expanded=False)
   elif not girt and st.checkbox('Exibir memória numérica salva do caso direto',value=False,key='saved_numeric_direct_'+str(result.get('input_fingerprint','historical'))):
    st.json(result,expanded=False)


st.set_page_config(page_title='LRO | Terças',page_icon='🏗️',layout='wide')
st.markdown('<style>.block-container{max-width:1200px} h1,h2,h3{color:#25334a} div.stButton>button[kind="primary"]{background:#d96516;border:0}</style>',unsafe_allow_html=True)
st.title('LRO | Terças e travessas laterais')
with st.expander('Precisão dos números exibidos',expanded=False):st.caption(DISPLAY_NOTE)
st.caption(f'NBR 14762:2010 · {VERSION} · primeira emissão restrita')
from tercas.release_info import RELEASE_CAPTION
st.caption(RELEASE_CAPTION)
st.info('Um vão, perfis U/Ue. Solicitações nos dois eixos; resistências desta emissão restritas às rotas disponíveis. Resultados por verificação, sem aprovação global automática.')
st.caption(DOMAIN_TEXT)

initialize_session(st.session_state, defaults)
if 'revision' not in st.session_state:st.session_state.revision=0

# Session cache migration only: preserve inputs, widgets, drafts and histories.
from tercas.ui_cache_epoch import refresh as refresh_calculation_cache
if refresh_calculation_cache(st.session_state):
 st.info('Atualização do cálculo: resultados e comparação anteriores retirados. Entradas preservadas; calcule novamente quando desejar.')

# Isolated AISI research: before any project renderer can stop the page.
from tercas.aisi_research.panel import render as render_aisi_research
render_aisi_research(st)

def load(d):
 st.session_state.base=copy.deepcopy(d);st.session_state.last_input=copy.deepcopy(d);st.session_state.revision+=1
 st.session_state.pop('result',None);st.session_state.pop('custom_steel_draft',None);st.session_state.pop('catalog_scan_state',None)

def reject_json_constant(value):
 raise ValueError('Constante JSON não finita não permitida: '+value)

def render_input_import(revision):
 with st.expander('Abrir entradas JSON',expanded=False):
  st.caption('Abra somente entradas exportadas por esta versão. O arquivo não executa código. Resultados anteriores não são reaproveitados. Entradas manuais fora do editor comum são abertas para inspeção.')
  upload=st.file_uploader('Arquivo de entradas',type=['json'],key=f'import_{revision}')
  if upload is not None and st.button('Aplicar entradas do arquivo'):
   try:
    if upload.size>200000:raise ValueError('Arquivo maior que 200 kB.')
    from tercas.application import build_spec
    new=json.loads(upload.getvalue(),parse_constant=reject_json_constant)
    if isinstance(new,dict) and (REFERENCE_FIELD in new or claims_ue_reference(new) or claims_ue_family(new)):
     index=new.get('catalog_index')
     if isinstance(index,bool) or not isinstance(index,int) or not 0<=index<len(catalog_labels()):raise ValueError('Índice de perfil inválido.')
     load(new);st.rerun()
    from tercas.inclination_adapter import configuration
    from tercas.inclination import number
    configuration(new)
    for field in ['q_parallel_uls','q_parallel_sls','P_parallel_uls','P_parallel_sls']:number(new.get(field,0),field)
    if new.get('load_mode')=='area':
     bundle=area_bundle(new);build_spec(case_inputs(new,bundle['combinations'][0]))
    else:build_spec(new)
    if 'three_girt_model' in new:
     from tercas.three_girt_application import configuration as validate_three_girt_configuration
     validate_three_girt_configuration(new)
    load(new);st.rerun()
   except (ValueError,TypeError,KeyError,UnicodeDecodeError) as exc:st.error('Arquivo não aplicado: '+str(exc))

# The catalogue editor cannot preserve active explicit Annex E properties.
# In 3D they are inactive and already retained: only an actual material conflict
# can require inspection there. This is a UI limitation, not a backend guard.
MANUAL_WEAK_FIELDS={'W_mm3','Wc_mm3','Nex_N','Nez_N','r0_mm','j_mm','Cm','Cs'}
def has_manual_weak(data):
 cfg=data.get('weak_axis',{})
 return isinstance(cfg,dict) and any(isinstance(v,dict) and MANUAL_WEAK_FIELDS.intersection(v) for v in cfg.values())

def manual_inspection_reason(data):
 if claims_ue_family(data):
  state=assess_ue_family(data)
  if not state['active']:return 'a família própria Ue fora do contrato: '+'; '.join(state['reasons'] or ['ative explicitamente o vetor íntegro'])+'.'
 if claims_ue_reference(data):
  state=assess_ue_reference(data)
  if not state['active']:return 'a referência própria Ue fora do contrato: '+'; '.join(state['reasons'] or ['ative explicitamente o vetor íntegro'])+'.'
 if REFERENCE_FIELD in data:
  state=assess_reference(data)
  if not state['active']:return 'a referência própria fora do contrato congelado: '+'; '.join(state['reasons'])+'.'
 if not has_manual_weak(data):return None
 if not three_girt_enabled(data):return 'este contrato de propriedades manuais do eixo fraco ativo.'
 if data.get('steel_name')!='Personalizado':
  standard=material(data['steel_name'])['properties']
  conflicts=[k for k,v in standard.items() if data['properties'].get(k)!=v]
  if conflicts:return 'o material importado sem substituição pelo aço predefinido ('+', '.join(conflicts)+'). Os dados manuais do eixo fraco estão inativos no 3D e não são o motivo do bloqueio.'
 return None

def show_manual_inspection(preserved,reason):
 preserved=copy.deepcopy(preserved)
 st.session_state.last_input=copy.deepcopy(preserved)
 if 'result' in st.session_state:st.session_state['manual_result_history']=copy.deepcopy(st.session_state.result)
 if 'catalog_scan_state' in st.session_state:st.session_state['manual_catalog_history']=copy.deepcopy(st.session_state.catalog_scan_state)
 st.session_state.pop('result',None);st.session_state.pop('catalog_scan_state',None)
 st.warning('Entradas preservadas em modo de inspeção: esta interface não edita '+reason+' Cálculo e comparação estão desativados para evitar substituição silenciosa de dados.')
 st.caption('Limitação de edição/importação desta interface, não exigência normativa nem ausência de capacidade matemática do backend. Nenhum dado do arquivo foi substituído ou completado; E, G, origens e campos por sentido permanecem intactos.')
 st.warning('Preservar o arquivo não comprova sua coerência física, não valida a referência de Pierin e não aprova o elemento. Todas as hipóteses e limitações do estudo original permanecem.')
 st.caption('Para contrato de referência inválido, escolher outro perfil abre novas entradas padrão de catálogo. Para retornar ao editor comum, selecione outro perfil acima, carregue o exemplo didático ou abra outro JSON. Trocar de perfil descarta propriedades e críticos específicos desta seção; baixe o arquivo preservado antes de sair, se necessário.')
 state=assess_ue_family(preserved) if claims_ue_family(preserved) else assess_ue_reference(preserved) if claims_ue_reference(preserved) else assess_reference(preserved)
 if state['eligible'] and not state['active']:
  st.caption('Vetor integral reconhecido como referência própria '+state['reference_id']+'. A ativação preserva todos os campos existentes; não substitui nem normaliza o arquivo.')
  if st.button('Ativar esta referência para cálculo',key=f'ref_activate_{st.session_state.revision}'):
   load(activate_ue_family(preserved) if claims_ue_family(preserved) else activate_ue_reference(preserved) if claims_ue_reference(preserved) else activate_reference(preserved));st.rerun()
 try:inspection_fingerprint=fingerprint(preserved)
 except (ValueError,TypeError):inspection_fingerprint='indisponível para este objeto inválido'
 st.caption('Identificação SHA-256 das entradas: '+inspection_fingerprint)
 with st.expander('Entradas originais preservadas',expanded=False):st.json(preserved)
 st.download_button('Baixar entradas preservadas (JSON)',json.dumps(preserved,ensure_ascii=False,indent=2),file_name='terca_entradas_preservadas.json',mime='application/json')
 calc_col,scan_col=st.columns(2)
 try:inspection_3d=three_girt_enabled(preserved)
 except (ValueError,TypeError,KeyError):inspection_3d=False
 with calc_col:st.button('Calcular diagnóstico 3D' if inspection_3d else 'Calcular verificações disponíveis',type='primary',disabled=True)
 with scan_col:st.button('Calcular todas as seções do catálogo',disabled=True)
 ue_family_loader(st,st.session_state.revision,load)
 ue_reference_loader(st,st.session_state.revision,load)
 reference_loader(st,st.session_state.revision,load)
 render_input_import(st.session_state.revision)
 render_new_pierin_ue_study(st, defaults, for_new_study, load)
 st.stop()


left,right=st.columns([2,1])
with right:
 if st.button('Carregar exemplo didático',help='Carrega dados sintéticos, explicitamente marcados. Não representa produto ou projeto validado.'):load(for_new_study(example()));st.rerun()
with left:
 index=st.selectbox('Perfil de catálogo',range(len(catalog_labels())),format_func=lambda i:catalog_labels()[i],index=st.session_state.base['catalog_index'],key=f'catalog_{st.session_state.revision}')
 if index!=st.session_state.base['catalog_index']:
  prior=st.session_state.get('last_input',st.session_state.base)
  if (claims_ue_family(prior) and not assess_ue_family(prior)['eligible']) or (claims_ue_reference(prior) and not assess_ue_reference(prior)['eligible']) or (REFERENCE_FIELD in prior and not assess_reference(prior)['eligible']):
   load(for_new_study(defaults(index)));st.rerun()
  changed=copy.deepcopy(st.session_state.get('last_input',st.session_state.base));fresh=defaults(index)
  for key in ['schema','catalog_index','properties','Ml_Nmm','Mdist_Nmm','critical_origin','property_origin']:changed[key]=fresh[key]
  changed.pop('weak_axis',None)
  changed.pop(REFERENCE_FIELD,None)
  changed.pop('homogeneous_lengths',None)
  changed.pop('homogeneous_reference_evidence',None)
  changed.pop(UE_CATALOG_FIELD,None);changed.pop(UE_CATALOG_EVIDENCE,None)
  for field in (UE_REFERENCE_FIELD,'ue_model','ue_source_documents','active_numeric_reference','ue_reference_evidence',UE_FAMILY_FIELD,'ue_family_model','ue_family_sources','ue_family_reference_evidence','own_ue_isolated_application'):changed.pop(field,None)
  if 'three_girt_model' in changed:
   changed['three_girt_model'].update(sc_y_mm=None,sc_z_mm=0.,sc_origin='',connections_declared=False,load_line_declared=False)
  # Preserve project restraint length, not section-dependent mean-line data.
  old_wc=changed.get('weak_catalog',{})
  changed['weak_catalog']={k:copy.deepcopy(old_wc[k]) for k in ['Lx_mm'] if k in old_wc}
  # Changing a section does not turn didactic project inputs into real data.
  changed['synthetic']=changed.get('synthetic',False)
  if changed.get('steel_name')!='Personalizado':changed['properties'].update(material(changed['steel_name'])['properties'])
  else:
   old=copy.deepcopy(st.session_state.get('last_input',st.session_state.base))
   old.pop(UE_CATALOG_FIELD,None);old.pop(UE_CATALOG_EVIDENCE,None)
   changed=inputs_for_section(old,index)
  load(changed);st.rerun()
reference_data=st.session_state.get('last_input',st.session_state.base) if (REFERENCE_FIELD in st.session_state.base or claims_ue_reference(st.session_state.base) or claims_ue_family(st.session_state.base)) else st.session_state.base
if claims_ue_family(reference_data) and assess_ue_family(reference_data)['active']:
 reference_data=copy.deepcopy(reference_data)
 render_ue_family(st,reference_data,st.session_state.revision,load,render_results,render_input_import)
if claims_ue_reference(reference_data) and assess_ue_reference(reference_data)['active']:
 reference_data=copy.deepcopy(reference_data)
 render_ue_reference(st,reference_data,st.session_state.revision,load,render_results,render_input_import)
if assess_reference(reference_data)['active']:
 render_reference(st,reference_data,st.session_state.revision,load,render_results,render_input_import)
inspection_reason=manual_inspection_reason(reference_data)
if inspection_reason:show_manual_inspection(reference_data,inspection_reason)

b=copy.deepcopy(st.session_state.base);r=st.session_state.revision
# Preserve values of widgets hidden when changing input mode.
last=st.session_state.get('last_input',b)
for key in ['load_mode','area_inputs','selected_types','ELS_down_denominator','ELS_up_denominator','q_uls','P_uls','x_uls','q_sls','P_sls','x_sls','actions_origin','ELS_limit_mm','ELS_origin']:
 b[key]=copy.deepcopy(last[key])
for key in ['isolated_combined_service','isolated_en_ue_family_model','isolated_en_ue125_300_model','direct_load_basis','roof_top_load','point_contact','isolated_en_ue_catalog_model','isolated_en_stress_model','torsion_model','deflection_model','member_application','wall_els','wall_tie_study','three_girt_model','weak_catalog','weak_axis','model_domain','u_panel_condition','inclination','q_parallel_uls','q_parallel_sls','P_parallel_uls','P_parallel_sls']:
 if key in last:b[key]=copy.deepcopy(last[key])
d=copy.deepcopy(b)
try:
 domain=domain_evidence(d)
 if domain['conflict']:st.warning(domain['conflict'])
except ValueError as exc:st.error(str(exc));st.stop()
if b.get('synthetic'):st.warning('EXEMPLO DIDÁTICO: propriedades complementares, críticos e contatos sintéticos. Substitua pelos dados do seu caso antes de usar resultados.')

def num(label,key,value,unit='',step=None):
 kw={'label':label+(f' [{unit}]' if unit else ''),'value':None if value is None else float(value),'key':f'{key}_{r}','format':'%.2f'}
 if step is not None:kw['step']=step
 out=st.number_input(**kw)
 if out is not None and out != 0 and abs(out)<0.005:st.caption('Valor não nulo: '+fmt(out)+' '+unit+'; precisão preservada.')
 return out

def txt(label,key,value):return st.text_input(label,value=str(value),key=f'{key}_{r}')

d['project']=txt('Identificação do estudo','project',b['project'])
try:is_girt(b)
except (ValueError,TypeError) as exc:
 st.error('Aplicação inválida: '+str(exc));st.stop()
application_labels={'purlin':'Terça de cobertura','wall_girt':'Travessa lateral — boca para baixo'}
application=st.selectbox('Aplicação do elemento',list(application_labels),format_func=application_labels.get,index=list(application_labels).index(b.get('member_application','purlin')),key=f'member_application_{r}')
d['member_application']=application;girt=is_girt(d)
previous_application=st.session_state.get(f'previous_application_{r}',b.get('member_application','purlin'))
if application!=previous_application:
 st.warning('Aplicação alterada: confira a reinterpretação física das cargas locais, dos vínculos e dos critérios ELS. Valores armazenados foram preservados; nenhuma ação direta foi girada novamente.')
st.session_state[f'previous_application_{r}']=application
if girt:
 st.info('Travessa lateral U/Ue com boca para baixo. Gravidade/PP/permanente no eixo fraco vertical; vento no eixo forte horizontal. Sem crédito da telha ou de tirantes por padrão. Ligações e torção primária fora do escopo.')
 st.caption('Vista A→B: +paralelo para baixo; +normal horizontal para a esquerda. Mesa superior do referencial = mesa física direita; inferior = esquerda. Estes nomes de referência continuam identificando os dados de FLT.')

three_girt=False
if girt:
 three_girt=st.checkbox('Analisar sistema 3D de três travessas — diagnóstico sem resistência',value=b.get('three_girt_model',{}).get('enabled',False),key=f'three_enabled_{r}')
 if three_girt or 'three_girt_model' in b:
  d['three_girt_model']=copy.deepcopy(b.get('three_girt_model',{}));d['three_girt_model']['enabled']=three_girt
 if three_girt:st.warning('Os campos de resistência/FLT do vão isolado ficam armazenados, mas INATIVOS no sistema 3D. Esta seleção não libera resistência, torção com empenamento ou conclusão ELS.')

# Switching away from a 3D diagnostic reactivates the stored manual contract.
# Stop before any strength/material widget can rewrite it. Preserve the last
# complete 3D input snapshot and only the explicit application/activation edit.
if has_manual_weak(b) and three_girt_enabled(b) and not three_girt:
 switched=copy.deepcopy(last);switched['member_application']=application
 if 'three_girt_model' in d:switched['three_girt_model']=copy.deepcopy(d['three_girt_model'])
 load(switched);st.rerun()

c1,c2=st.columns(2)
with c1:d['L_mm']=num('Vão do modelo entre apoios' if girt else 'Vão entre apoios','L',b['L_mm'],'mm')
with c2:d['steel_name']=st.selectbox('Tipo de aço',STEEL_NAMES,index=STEEL_NAMES.index(b.get('steel_name','ASTM A36')),key=f'steel_{r}')
if d['steel_name']=='Personalizado':
 custom=st.session_state.get('custom_steel_draft',dict(fy=b['properties']['fy_MPa'],fu=b['properties']['fu_MPa'],origin=b.get('custom_steel_origin',b['property_origin'])))
 c1,c2=st.columns(2)
 with c1:fy=num('fy personalizado','fy_custom',custom['fy'],'MPa')
 with c2:fu=num('fu personalizado','fu_custom',custom['fu'],'MPa')
 custom_origin=txt('Origem do aço personalizado','steel_origin',custom['origin'])
 d['custom_steel_origin']=custom_origin
 st.session_state.custom_steel_draft=dict(fy=fy,fu=fu,origin=custom_origin)
 try:
  mat=material('Personalizado',{'fy_MPa':fy,'fu_MPa':fu,'origin':custom_origin})
  for key in ['E_MPa','G_MPa']:mat['properties'][key]=b['properties'][key]
  mat['physical_origin']='E e G preservados das entradas do aço personalizado; conferir origem e aplicabilidade'
  if mat['properties']['E_MPa']!=200000. or mat['properties']['G_MPa']!=77000.:st.warning('E/G personalizados diferem das constantes usuais da NBR 14762. Valores importados preservados, sem atribuí-los à norma; confira a origem e a aplicabilidade.')
 except ValueError as exc:mat=None;st.warning(str(exc));d['properties'].update(fy_MPa=fy,fu_MPa=fu)
else:
 mat=material(d['steel_name'])
 # This metadata belongs to the active custom material, not an exported draft.
 # In-session toggling still uses custom_steel_draft (fy/fu and origin together).
 d.pop('custom_steel_origin',None)
if mat:
 d['properties'].update(mat['properties']);d['property_origin']=f"{mat['name']}: {mat['origin']}; {mat['physical_origin']}"
 st.caption(f"fy = {fmt(mat['properties']['fy_MPa'])} MPa · fu = {fmt(mat['properties']['fu_MPa'])} MPa. Conferir especificação do produto.")

if not three_girt:
 st.subheader('Comprimentos efetivos e travamentos')
 st.caption('Travessa: flexão forte horizontal e fraca vertical. Ly das mesas físicas direita/esquerda entra na FLT forte; Lx na instabilidade fraca; Lz é torsional. L do modelo, L de referência ELS e comprimentos efetivos FLT são independentes; nenhum cria apoio automaticamente.' if girt else 'Eixos da seção: X horizontal (maior inércia), Y vertical (menor inércia). Ly das mesas entra na FLT da flexão em X; Lx entra na instabilidade da flexão em Y. Lz é torsional. Não são novos apoios verticais.')
 wc=copy.deepcopy(b.get('weak_catalog',{}))
 old_weak_span=st.session_state.get(f'weak_last_span_{r}',b['L_mm'])
 current_lx=st.session_state.get(f'weak_lx_{r}',wc.get('Lx_mm',d['L_mm']))
 if d['L_mm']!=old_weak_span and current_lx==old_weak_span:
  st.session_state[f'weak_lx_{r}']=d['L_mm'];wc['Lx_mm']=d['L_mm']
 st.session_state[f'weak_last_span_{r}']=d['L_mm']
 wc['Lx_mm']=num('Lx efetivo — instabilidade da flexão fraca','weak_lx',wc.get('Lx_mm',d['L_mm']),'mm')
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
  c1,c2,c3=st.columns(3)
  with c1:upper=num('Ly — mesa física direita (superior no referencial)' if girt else 'Ly — mesa superior (menor inércia)','upper',length_value('Ly_top_effective_mm'),'mm')
  with c2:lower=num('Ly — mesa física esquerda (inferior no referencial)' if girt else 'Ly — mesa inferior (menor inércia)','lower',length_value('Ly_bottom_effective_mm'),'mm')
  with c3:torsion=num('Comprimento efetivo torsional Lz','torsion',length_value('Lz_effective_mm'),'mm')
  cb_label=st.selectbox('Coeficiente Cb',list(CB_LABELS.values()),index=list(CB_LABELS).index(first.get('Cb_mode','one')),key=f'cb_{r}')
  st.caption('Travessa: Mx positivo comprime a mesa física direita (superior no referencial), negativo a esquerda (inferior). Nenhum travamento pela telha é presumido.' if girt else 'Momento positivo comprime a mesa superior; momento negativo comprime a inferior. O app escolhe o comprimento da mesa comprimida em cada caso e não considera a telha como travamento.')
  with st.expander('Vínculo torsional e origem dos comprimentos',expanded=False):
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
  edited=st.data_editor(df,num_rows='dynamic',hide_index=True,key=f'segments_{r}',column_config={'start_mm':st.column_config.NumberColumn('Início [mm]',format='%.2f'),'end_mm':st.column_config.NumberColumn('Fim [mm]',format='%.2f'),'Ly_top_effective_mm':st.column_config.NumberColumn('Mesa física direita (superior ref.) [mm]' if girt else 'Mesa superior — comprimento efetivo [mm]',format='%.2f'),'Ly_bottom_effective_mm':st.column_config.NumberColumn('Mesa física esquerda (inferior ref.) [mm]' if girt else 'Mesa inferior — comprimento efetivo [mm]',format='%.2f'),'Lz_effective_mm':st.column_config.NumberColumn('Lz torsional [mm]',format='%.2f'),'restraint_provenance':'Origem / hipótese do vínculo','Cb_mode':st.column_config.SelectboxColumn('Cb',options=list(CB_LABELS.values()))},width='stretch')
  d['segments']=edited.astype(object).where(pd.notna(edited),None).to_dict('records')
  for seg in d['segments']:seg['Cb_mode']=cb_code(seg.get('Cb_mode') or 'one')
  st.caption('Início e fim são os limites físicos do diagrama usado no Cb; Ly e Lz são comprimentos efetivos e podem diferir desse intervalo por condição de vínculo. Trechos representam o diagrama usado no Cb; não criam apoios verticais nem comprovam travamentos. Uma inversão do momento não é um travamento.')

 st.session_state[f'last_segments_{r}']=copy.deepcopy(d['segments'])
 st.session_state[f'last_span_{r}']=d['L_mm']

with st.expander('Perfil, aço e origem dos dados',expanded=False):
 st.caption('209 perfis da planilha V03 fornecida por Lucas; fontes e linha de origem preservadas. Críticos tabulados de Pierin/DimPerfil quando disponíveis. A transcrição não é certificação do produto.')
 cols=st.columns(3)
 labels={'A_cm2':'Área [cm²]','mass_kg_m':'Massa linear [kg/m]','Ix_cm4':'Ix [cm⁴]','Wx_cm3':'Wx [cm³]','Iy_cm4':'Iy [cm⁴]','ri_mm':'Raio interno [mm]','J_mm4':'J [mm⁴]','Cw_mm6':'Cw [mm⁶]'}
 for i,(key,label) in enumerate(labels.items()):
  with cols[i%3]:d['properties'][key]=num(label,key,b['properties'][key])
 extra_origin=txt('Origem dos dados complementares / alterações','property_origin',b['property_origin'])
 steel_prefix=f"Aço {mat['name']}: {mat['origin']}; {mat['physical_origin']}; " if mat else ''
 # Exported inputs already include this prefix: reopening must not duplicate it.
 d['property_origin']=extra_origin if extra_origin.startswith(steel_prefix) else steel_prefix+extra_origin
 # Legacy custom exports contain only the aggregate. Preserve that text intact;
 # do not guess its certificate/history boundary or wrap it in itself again.
 if mat and d['steel_name']=='Personalizado' and custom_origin==extra_origin and extra_origin.startswith('Aço Personalizado: '):d['property_origin']=extra_origin
 st.caption(f"E = {fmt(d['properties']['E_MPa'])} MPa · G = {fmt(d['properties']['G_MPa'])} MPa — propriedades físicas adotadas; conferir origem.")
 st.caption('Fonte: '+catalog_entry(index)['source_url']+'; linha '+str(catalog_entry(index)['source_workbook_row'])+' da planilha original.')
 st.caption('Conferir a convenção de Wx e das propriedades usadas em conjunto. Editar valores não comprova a correspondência física.')

if not girt:
 st.subheader('Inclinação da cobertura')
 st.caption('Convenção: seção vista do apoio A para B, boca à direita em 0°. Inclinação positiva: caimento para a boca; negativa: caimento oposto. A seção gira junto com a cobertura; não há espelhamento independente.')
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
else:
 st.warning('Entradas de cobertura preservadas, mas INATIVAS na travessa: inclinação '+display(b.get('inclination',{}))+'; SC de cobertura = '+display(b['area_inputs'].get('live_kgf_m2'))+' kgf/m². Não há SC usual de cobertura ou P de manutenção automáticos. Cargas especiais exigem combinação declarada no modo direto.')

st.subheader('Carregamentos')
mode=st.radio('Forma de entrada',['Ações já combinadas (ELU e ELS)','Cargas por área e combinações automáticas'],index=1 if b.get('load_mode')=='area' else 0,key=f'load_mode_{r}')
d['load_mode']='area' if mode.startswith('Cargas') else 'direct'
if d['load_mode']=='direct':
 st.subheader('Ações de uma combinação')
 from tercas.direct_self_weight import render as direct_PP_render,active as direct_PP_active
 direct_PP_render(st,d,f'direct_PP_{r}')
 if direct_PP_active(d):
  st.caption('Travessa: q/P normais são horizontais, eixo forte, positivos para a esquerda na vista A→B; paralelos são verticais, eixo fraco, positivos para baixo. q em kN/m equivale a N/mm; P em kN. Ações externas já locais e combinadas, sem nova rotação.' if girt else 'Terça: q/P principais são normais à cobertura, positivos no sentido do esquema; componentes paralelas são positivas para a boca do perfil na vista A→B. q em kN/m equivale a N/mm; P em kN. Ações externas já locais e combinadas, sem nova rotação.')
 if not direct_PP_active(d):
  st.caption('Travessa, modo direto: q/P normais são horizontais (eixo forte, positivo para a esquerda na vista A→B); paralelos são verticais (eixo fraco, positivo para baixo). Ações já locais e combinadas: não há rotação adicional nem PP automático. Inclua PP e cargas especiais na combinação declarada. kN/m equivale a N/mm; P em kN.' if girt else 'Ações já nos eixos locais: q e P principais são normais à cobertura; componentes paralelas são informadas abaixo. A inclinação não gira novamente estes valores. q positivo e P positivo atuam no mesmo sentido do esquema. q em kN/m equivale numericamente a N/mm. P é informado em kN. Inclua peso próprio nas ações; o app não o soma silenciosamente.')
 a,bcol=st.columns(2)
 with a:
  st.markdown('**ELU — valores já ponderados**')
  d['q_uls']=num('q horizontal ELU' if girt else 'q ELU','q_uls',b['q_uls'],'kN/m');p=num('P horizontal ELU' if girt else 'P ELU','P_uls',b['P_uls']/1000,'kN');d['P_uls']=None if p is None else p*1000;d['x_uls']=num('Posição de P ELU','x_uls',b['x_uls'],'mm')
 with bcol:
  st.markdown('**ELS — combinação de serviço**')
  d['q_sls']=num('q horizontal ELS' if girt else 'q ELS','q_sls',b['q_sls'],'kN/m');p=num('P horizontal ELS' if girt else 'P ELS','P_sls',b['P_sls']/1000,'kN');d['P_sls']=None if p is None else p*1000;d['x_sls']=num('Posição de P ELS','x_sls',b['x_sls'],'mm')
 with st.expander('Componentes verticais — eixo fraco, já combinadas' if girt else 'Componentes paralelas à cobertura — ações já combinadas',expanded=False):
  st.caption('Zero quando não houver componente paralela. P paralela atua na mesma posição da P normal de cada estado-limite. Resistência biaxial não é aprovada sem resistências aplicáveis nos dois eixos.')
  c1,c2=st.columns(2)
  for state,col in [('uls',c1),('sls',c2)]:
   with col:
    label='ELU' if state=='uls' else 'ELS'
    key='q_parallel_'+state;d[key]=num(('q vertical ' if girt else 'q paralelo ')+label,key,b.get(key,0),'kN/m')
    key='P_parallel_'+state;pv=b.get(key,0);pv=num(('P vertical ' if girt else 'P paralelo ')+label,key,None if pv is None else pv/1000,'kN');d[key]=None if pv is None else pv*1000
 d['actions_origin']=txt('Identificação e origem das combinações','actions_origin',b['actions_origin'])
 
else:
 st.caption('Travessa: módulos em kgf/m² na fachada e largura tributária pela distância entre travessas. Vento pressão positivo / sucção negativo no eixo forte horizontal; CP e PP verticais. CP inclui peso da telha/revestimento por área de influência; PP do perfil vem da massa linear uma única vez e não deve ser repetido em CP. Bases roof/horizontal da cobertura ficam inativas.' if girt else 'Informe módulos positivos em kgf/m². Vento para cima recebe sinal negativo. PP vem da massa linear, sem campo adicional; CP não deve repetir PP.')
 area=copy.deepcopy(b['area_inputs']);cols=st.columns(2)
 labels=[('spacing_m','Distância entre terças','m'),('permanent_kgf_m2','Carregamento permanente','kgf/m²'),('live_kgf_m2','Sobrecarga','kgf/m²'),('wind_up_kgf_m2','Vento para cima','kgf/m²'),('wind_down_kgf_m2','Vento para baixo','kgf/m²')]
 if girt:labels=[('spacing_m','Distância entre travessas','m'),('permanent_kgf_m2','Permanente vertical — telha/revestimento, sem PP do perfil','kgf/m²'),('wind_up_kgf_m2','Vento sucção — horizontal negativo','kgf/m²'),('wind_down_kgf_m2','Vento pressão — horizontal positivo','kgf/m²')]
 for i,(key,label,unit) in enumerate(labels):
  with cols[i%2]:area[key]=num(label,key,area[key],unit)
 d['area_inputs']=area
 d['selected_types']=st.multiselect('Tipos de combinações consideradas',COMBINATION_TYPES,default=b['selected_types'],key=f'combo_types_{r}')
 if not girt:st.caption('P = 1 kN de manutenção é incluída automaticamente nas famílias ELU normal e ELS rara selecionadas, apenas com permanentes; não se soma a SC ou vento. São calculadas duas posições: centro e limite junto ao apoio. Não há varredura intermediária; os resultados de interação e FLT cobrem essas posições, não um máximo contínuo.')
 if not girt:st.caption(f"Massa linear selecionada: {fmt(d['properties']['mass_kg_m'])} kg/m. Matriz fixa fornecida por Lucas: 32 ELU normal, 8 ELS rara, 6 frequente e 2 quase permanente.")
 with st.expander('Casos e combinações que serão calculados'):
  try:
   preview=area_bundle(d)
   st.dataframe(display_frame([{'Caso':k,'q normal [kN/m]':v,'q paralelo [kN/m]':preview.get('case_vectors_N_mm',{}).get(k,{}).get('parallel',0)} for k,v in preview['case_q_N_mm'].items()]),hide_index=True)
   st.dataframe(display_frame([{'ID':c['id'],'Tipo':c['type'],'Expressão':c['expression'],'q normal [kN/m]':c['q_kN_m'],'q paralelo [kN/m]':c.get('q_vector',{}).get('parallel',0),'P normal [kN]':c.get('P_N',0)/1000,'P paralelo [kN]':c.get('P_vector',{}).get('parallel',0)/1000} for c in preview['combinations']]),hide_index=True)
  except (ValueError,TypeError,KeyError) as exc:st.warning(str(exc))

from tercas.roof_top_load_ui import render_choice as render_roof_top_load
from tercas.roof_top_load import enabled as roof_top_load_enabled
if not three_girt:
 render_roof_top_load(st,d,f'roof_top_load_{r}')
 from tercas.isolated_en_ui import render_choice as render_EN_choice
 render_EN_choice(st,d,f'isolated_EN_{r}')

if three_girt:
 from tercas.three_girt_ui import render_configuration as three_girt_configuration_ui
 three_girt_configuration_ui(st,d,b,r,num,txt)
else:
 with st.expander('Estabilidade, críticos e trechos',expanded=True):
  st.caption('Ml e Mdist são críticos elásticos da mesma seção. Não são momentos resistentes. Sem dado suficiente, só a verificação afetada fica pendente.')
  c1,c2=st.columns(2)
  with c1:m=num('Ml — crítico local','Ml',None if b['Ml_Nmm'] is None else b['Ml_Nmm']/1e6,'kN·m');d['Ml_Nmm']=None if m is None else m*1e6
  with c2:m=num('Mdist — quando não dispensado','Mdist',None if b['Mdist_Nmm'] is None else b['Mdist_Nmm']/1e6,'kN·m');d['Mdist_Nmm']=None if m is None else m*1e6
  d['critical_origin']=txt('Origem dos críticos / método e seção','critical_origin',b['critical_origin'])
  from tercas.strong_pierin import qualify as qualify_pierin_U,use_label as pierin_U_use_label
  _,strong_ref=qualify_pierin_U(d)
  if strong_ref['status']=='tabulated_adopted_reference':
   st.markdown('**Pierin — referência oficial adotada para Mlx / Nl de U**')
   st.caption(f"Mlx = {fmt(strong_ref['Mlx_Nmm']/1e6)} kN·m; Nl = {fmt(strong_ref['Nl_N']/1000)} kN. Tabela 1, p{strong_ref['printed_page']} / PDF{strong_ref['PDF_page']}; linha nominal exata. Nl é somente documental: não há verificação axial implementada.")
   st.caption('Críticos elásticos, não resistências. Novas seleções U tabeladas usam Mlx Pierin; projetos importados mantêm sua entrada/fonte. Fonte: E=200000 MPa, apoio simples, cantos retos; G/ν e conversão exata para linha média não explicitados. As propriedades originais do catálogo são mantidas; equivalência física com INSTAB não demonstrada. Sem escala, interpolação ou fallback automático por E/G.')
   st.caption('Uso atual: '+pierin_U_use_label(strong_ref)+'. Ml informado acima é preservado; valor de referência não substitui silenciosamente entrada legada/manual.')
   if strong_ref.get('reason'):st.warning(strong_ref['reason'])
  elif strong_ref['status']=='not_tabulated':st.caption(strong_ref['reason']+' A rota Tabela 12 permanece quando válida.')
  if roof_top_load_enabled(d):
   # Hidden widget values are otherwise removed by Streamlit on the next run.
   domain_value=st.session_state.get(f'domain_{r}')
   d['route_domain']=(domain_value.startswith('Eixo') if isinstance(domain_value,str) else st.session_state.get(f'roof_legacy_domain_{r}',b['route_domain']))
   st.session_state[f'roof_legacy_domain_{r}']=d['route_domain']
   st.caption('Modelo de topo adotado acima: componente elástico separado, com altura da carga e PP no CG. A declaração legada de domínio CT é preservada, não ativada por esta escolha.')
  else:
   selection=st.selectbox('Domínio da expressão de Me nesta emissão',['Não informado / outra situação','Eixo forte de simetria; cargas no CT ou estabilizantes, sem torção primária'],index=1 if st.session_state.get(f'roof_legacy_domain_{r}',b['route_domain']) else 0,key=f'domain_{r}',help='CT é o centro de torção. A NBR 14762:2010 §9.8.2.2, p.48, permite usar a expressão de Me também para carga em posição estabilizante, sem aproveitar seu efeito favorável. Posição desestabilizante exige tratamento específico. A declaração deve valer para todas as ações, combinações e trechos calculados; a inversão do sentido da carga pode mudar o efeito da altura.')
   d['route_domain']=selection.startswith('Eixo')
   st.session_state[f'roof_legacy_domain_{r}']=d['route_domain']
   st.caption('Ly superior/inferior é o comprimento lateral associado à menor inércia no cálculo de FLT da flexão forte. Lz é torsional, não um comprimento da maior inércia. Esses comprimentos não criam apoios no diagrama de cargas.')
   st.caption('Sem torção primária significa sem torque aplicado por excentricidade das ações. Não exclui o giro do modo de FLT. Esta é uma hipótese do modelo, não uma verificação do caminho das forças nem resistência à torção. Ly e Lz são independentes; um tirante lateral não é automaticamente travamento torsional.')
   st.caption('Carga estabilizante: a altura de aplicação tende a restaurar a posição da barra quando ela gira. Carga desestabilizante: tende a ampliar o giro. Não se presume a posição pela inclinação do telhado, pelo sentido de q/P ou pela ausência de travamento da telha.')


 with st.expander('Eixo fraco — dados existentes e críticos por sentido',expanded=False):
  st.caption('Wy, xg, x0 e r0 já estão na planilha. Área, Ix, Iy, J, Cw, E e G vêm do perfil/aço selecionados; o app calcula Nex e Nez, sem pedir estes números de novo. Lz usa o maior comprimento torsional dos trechos. Sem travamento da telha.')
  st.caption('Convenção: My positivo comprime a alma; My negativo comprime as bordas/lábios. Os eixos locais e o sentido da seção física devem corresponder a esta convenção. Cm = 1,0 em todas as combinações; não há redução automática.')
  raw=catalog_entry(index)['raw_source_values']
  st.dataframe(display_frame([{'Dado':k,'Valor tabelado':raw.get(k)} for k in ['Wy cm³','xg cm','x0 cm','r0 cm','Ml,y kNm']]),hide_index=True)
  from tercas.weak_pierin import reference_for_inputs
  pierin=reference_for_inputs(d)
  st.markdown('**Pierin — referência oficial adotada no app para Ml,y**')
  if pierin['status']=='tabulated_adopted_reference':
   st.caption(f"Ml,y = {fmt(pierin['Mly_Nmm']/1e6)} kN·m; Tabela {pierin['table']}, p{pierin['printed_page']} / PDF{pierin['PDF_page']}. Geometria nominal exata. E=200000 MPa, apoios simples e cantos retos; G e ν da fonte não explicitados.")
   st.caption('Este é o valor tabelado oficial de referência, separado da atribuição por sentido. A fonte não explicita o lado comprimido. Não é resistência de cálculo, não libera ambos os sentidos e não fornece Mdist,y. Valores brutos da planilha permanecem preservados acima.')
   for reason in pierin['compatibility_reasons']:st.warning('Referência apenas documental nesta configuração: '+reason)
  else:st.caption(pierin['reason'])

  gm=wc.get('mean_line',{})
  with st.expander('Linha média do Anexo E — cálculo automático e origem',expanded=False):
   from tercas.weak_catalog import nominal_mean_line,geometry_mode
   auto_geom=nominal_mean_line(d)
   st.caption('Conversão conferida na Figura E.1 da NBR14762 e no Ex08 do CBCA. Ue: am=h−t, bm=bf−t, cm=D−t/2. U: am=h−t, bm=bf−t/2, cm=0. O raio ri permanece o tabelado; não é inferido destas dimensões.')
   st.caption(f"Linha média automática: am={fmt(auto_geom['am_mm'])} mm; bm={fmt(auto_geom['bm_mm'])} mm; cm={fmt(auto_geom['cm_mm'])} mm. Diferenças de Iy entre idealização de linha média e catálogo com cantos são informativas, não um limite normativo de3%.")
   explicit=st.checkbox('Usar dimensões médias explicitamente documentadas (avançado)',value=geometry_mode(wc)=='explicit',key=f'weak_explicit_{r}')
   wc['geometry_mode']='explicit' if explicit else 'catalog'
   if explicit:
    st.caption('Entradas legadas são preservadas, mas esta automação só aceita a conversão nominal comprovada. Outro modelo de seção exige propriedades próprias, não mistura automática com Iy do catálogo.')
    vals={};cols=st.columns(3)
    for i,(key,label) in enumerate([('am_mm','am — altura na linha média'),('bm_mm','bm — largura na linha média'),('cm_mm','cm — lábio na linha média')]):
     with cols[i]:vals[key]=num(label,'weak_geom_'+key,gm.get(key,auto_geom[key]),'mm')
    vals['origin']=txt('Origem / convenção das dimensões médias','weak_geometry_origin',gm.get('origin',''))
    wc['mean_line']=vals
   else:wc['mean_line']=auto_geom
  d['weak_catalog']=wc;d['weak_axis']={}
  from tercas.weak_catalog import critical_hypothesis
  from tercas.weak_axis import provisional_hypothesis
  provisional=critical_hypothesis(index)
  if claims_ue_catalog(d):
   provisional={sign:dict(Ml_Nmm=None,Mdist_Nmm=None,plain_u_no_distortion=False,provenance='Críticos próprios ainda não fornecidos para este contorno Ue.') for sign in ('positive','negative')}
  from tercas.weak_u_assumption import covered as u_covered,marked as u_marked,selected as u_selected,input_row as u_input_row,reasons as u_reasons,WARNING as U_WARNING
  u_src=copy.deepcopy(b.get('weak_axis',{}).get('positive',provisional['positive']))
  u_was_selected=u_selected(u_src);u_active=False;u_restored=None
  u_backup_key=f'u_pierin_manual_backup_{r}'
  if u_covered(index) or u_marked(u_src):
   st.caption('Opção em estudo, limitada a quatro geometrias com refinamento e modos revisados. É recorte de evidência, não limite normativo. A comparação 124/124 não confirma o sentido declarado pela fonte nem a resistência.')
   u_active=st.checkbox('Usar explicitamente a hipótese inferida U/alma — cálculo exploratório, pendente de confirmação',value=u_was_selected,key=f'u_pierin_optin_{r}',disabled=not u_covered(index) and not u_was_selected)
   if u_active:
    if not u_was_selected:
     st.session_state[u_backup_key]=copy.deepcopy(u_src if not u_marked(u_src) else provisional['positive'])
     u_src=u_input_row(index)
    st.warning(U_WARNING)
    st.caption('Seleção vinculada somente a esta seção e My positivo. A exportação registra a escolha; reabrir JSON mantém o aviso. Trocar perfil ou comparar todo o catálogo não transfere esta opção. Ao desligar, restaura-se o rascunho manual desta sessão; sem ele, os campos voltam vazios.')
    for reason in u_reasons(d,catalog_entry(index)['family'],'positive',u_src):st.warning('Hipótese não aplicável nesta configuração: '+reason)
   elif u_was_selected:
    u_restored=copy.deepcopy(st.session_state.pop(u_backup_key,provisional['positive']))
  elif catalog_entry(index)['family']=='U':
   st.caption('Hipótese inferida U/alma indisponível nesta proposta: fora das quatro geometrias com refinamento/modal revisado. Referência oficial permanece disponível, sem atribuição de sentido.')
  for sign,label in [('positive','My positivo — alma comprimida'),('negative','My negativo — bordas comprimidas')]:
   src=b.get('weak_axis',{}).get(sign,provisional[sign])
   if sign=='positive' and u_restored is not None:src=u_restored
   if sign=='positive' and u_active:
    st.markdown('**'+label+' — hipótese inferida selecionada**')
    st.caption('Ml,y da seleção [kN·m]: '+(fmt(u_src['Ml_Nmm']/1e6) if u_src.get('Ml_Nmm') is not None else 'ausente')+'; campo vinculado à referência, sem edição/escala nesta opção.')
    st.caption(u_src.get('provenance','Origem ausente'))
    st.caption('No domínio fixo sem ligação de mesa a painel, o U simples é dispensado de distorção em §9.3. A dispensa da Tabela 14 forte não é transferida ao eixo fraco. Declaração física incompatível permanece fora do domínio.')
    d['weak_axis'][sign]=copy.deepcopy(u_src)
    continue
   st.markdown('**'+label+'**');out={};cols=st.columns(2)
   for i,(key,label2) in enumerate([('Ml_Nmm','Ml,y local'),('Mdist_Nmm','Mdist,y distorcional')]):
    with cols[i]:
     value=num(label2+' — '+label,'weak_'+sign+'_'+key,None if src.get(key) is None else src[key]/1e6,'kN·m');out[key]=None if value is None else value*1e6
   inherited_hypothesis=provisional_hypothesis(src)
   replace_key=f'weak_replace_hypothesis_{sign}_{r}'
   replace_hypothesis=False
   if inherited_hypothesis or st.session_state.get(replace_key,False):
    replace_hypothesis=st.checkbox('Usar críticos informados com origem própria — '+label,value=False,key=replace_key)
    if replace_hypothesis:st.caption('Esta escolha só distingue a entrada manual da hipótese tabulada; não valida fisicamente os críticos. Informe valores compatíveis com seção, eixo, sentido e material, com sua própria origem.')
   out['plain_u_no_distortion']=catalog_entry(index)['family']=='U'
   if out['plain_u_no_distortion']:st.caption('U simples no domínio fixo sem ligação de mesa a painel: dispensa distorcional §9.3. Não se usa Tabela 14 forte no eixo fraco. Declaração física incompatível não é convertida silenciosamente.')
   out['provenance']=txt('Origem dos críticos neste sentido — '+label,'weak_source_'+sign,src.get('provenance',''))
   legacy_hypothesis='HIPÓTESE PROVISÓRIA' in out['provenance'].upper()
   out['provisional_hypothesis']=(inherited_hypothesis and not replace_hypothesis) or legacy_hypothesis
   if replace_hypothesis and legacy_hypothesis:st.warning('A origem ainda identifica a hipótese provisória. Substitua pela origem própria dos críticos; o selo e a restrição de compatibilidade permanecem enquanto este texto estiver presente.')
   d['weak_axis'][sign]=out
  st.caption('Ue: mantém-se a hipótese previamente autorizada de atribuição do Ml,y oficial a My positivo (alma comprimida), apoiada no comparador pyCUFSM e ainda a conferir; o valor da tabela não é uma hipótese, mas seu sentido aplicado é. U: os novos valores oficiais não recebem sentido automático; a opção exploratória exige escolha explícita e mantém a pendência de confirmação. Nenhum valor é copiado para ambos os sentidos; Mdist,y não usa a tabela forte. A ausência afeta só a rota correspondente.')

if not three_girt:
 if not girt:
  with st.expander('Limite de flecha',expanded=False):
   if d['load_mode']=='direct':
    d['ELS_limit_mm']=num('Limite de flecha adotado','els_limit',b['ELS_limit_mm'],'mm')
    d['ELS_origin']=txt('Origem / aplicação do limite de flecha','els_origin',b['ELS_origin'])
   else:
    d['ELS_down_denominator']=num('Limite descendente L/','els_down',b['ELS_down_denominator'])
    d['ELS_up_denominator']=num('Limite ascendente L/','els_up',b['ELS_up_denominator'])
    st.caption('Limite escolhido por sentido de cada combinação ELS; conferir critério da aplicação.')
 else:
  with st.expander('Critérios ELS da travessa e comprimentos de referência',expanded=True):
   st.caption('L/120 horizontal e L/180 vertical são escolhas históricas editáveis, não regra atual verificada. Informe a origem/aplicação. Lref vazio usa L do modelo; alterar Lref não cria apoio nem altera comprimentos FLT.')
   we=dict(normal_denominator=120.,vertical_denominator=180.,normal_reference_mm=None,vertical_reference_mm=None,origin='critério declarado pelo usuário');we.update(b.get('wall_els',{}))
   c1,c2=st.columns(2)
   with c1:
    we['normal_denominator']=num('Flecha horizontal forte — Lref/','wall_normal_denominator',we['normal_denominator'])
    we['normal_reference_mm']=num('Lref ELS horizontal (vazio = vão do modelo)','wall_normal_reference',we['normal_reference_mm'],'mm')
   with c2:
    we['vertical_denominator']=num('Flecha vertical fraca — Lref/','wall_vertical_denominator',we['vertical_denominator'])
    we['vertical_reference_mm']=num('Lref ELS vertical (vazio = vão do modelo)','wall_vertical_reference',we['vertical_reference_mm'],'mm')
   we['origin']=txt('Origem dos critérios ELS da travessa','wall_els_origin',we['origin']);d['wall_els']=we
  with st.expander('Estudo elástico bruto opcional de tirantes verticais',expanded=False):
   wt=dict(enabled=False,anchorage_confirmed=False,origin='',springs=[]);wt.update(b.get('wall_tie_study',{}))
   wt['enabled']=st.checkbox('Ativar estudo elástico bruto de molas verticais',value=wt['enabled'],key=f'wall_tie_enabled_{r}')
   st.warning('Diagnóstico elástico bruto, não resistência nem aprovação. Molas verticais ancoradas, tração-apenas, sem folga/pré-tensão. Não representam apoio rígido e não reduzem automaticamente Lz/FLT. Não use rigidez ou ancoragem sem origem.')
   if wt['enabled']:
    wt['anchorage_confirmed']=st.checkbox('Ancoragem externa explicitamente confirmada para este estudo',value=wt['anchorage_confirmed'],key=f'wall_tie_anchorage_{r}')
    wt['origin']=txt('Origem / hipótese do estudo dos tirantes','wall_tie_origin',wt['origin'])
    springs=pd.DataFrame(wt['springs'],columns=['x_mm','k_N_mm','origin'])
    edited_springs=st.data_editor(springs,num_rows='dynamic',hide_index=True,key=f'wall_springs_{r}',column_config={'x_mm':st.column_config.NumberColumn('Posição ao longo do vão [mm]'),'k_N_mm':st.column_config.NumberColumn('Rigidez vertical [N/mm]'),'origin':'Origem da rigidez / ancoragem'},width='stretch')
    wt['springs']=edited_springs.astype(object).where(pd.notna(edited_springs),None).to_dict('records')
   d['wall_tie_study']=wt

provenance_text=' '.join([str(d.get('project','')),str(d.get('patch_origin',''))]+[str(seg.get('restraint_provenance','')) for seg in d.get('segments',[])])
if any(tag in provenance_text.casefold() for tag in ['sintétic','sintetic','didático','didatico']):
 st.warning('Há referências a dados sintéticos/didáticos nas entradas ou origens. Foram preservadas; confira essas premissas antes de usar como dados de projeto.')
from tercas.deflection_scope import render_choice as render_deflection_choice
render_deflection_choice(st,d,f'deflection_model_{r}')
from tercas.isolated_service_ui import controls as render_combined_service
render_combined_service(st,d,f'isolated_combined_service_{r}')
render_point_contact(st,d,f'point_contact_{r}',disabled=three_girt)
from tercas.ue_catalog_ui import render_choice as render_ue_catalog_choice
render_ue_catalog_choice(st,d,f'ue_catalog_{r}',load)

st.session_state['last_input']=copy.deepcopy(d)
try:
 if three_girt:
  from tercas.three_girt_ui import diagram as three_girt_diagram
  st.markdown(three_girt_diagram(d),unsafe_allow_html=True)
  st.caption('Esquema das linhas de referência: braços excêntricos e deformada fora do plano não estão desenhados. Apoios impedem translações/torção, não rotações de flexão.')
 else:
  previews=drawing_cases(d)
  if d['load_mode']=='area':
   selected_preview=st.selectbox('Combinação mostrada no desenho',range(len(previews)),format_func=lambda i:previews[i][0])
   drawing_data=previews[selected_preview][1]
   st.caption('Prévia de uma combinação de travessa; vento horizontal e gravidade vertical. Sem SC/P de cobertura automáticos; não soma máximos.' if girt else 'Prévia de uma combinação, não soma dos máximos. Casos P aparecem primeiro; A posição indicada identifica o caso calculado; no apoio representa-se o limite x→0+.')
  else:drawing_data=previews[0][1]
  st.markdown(svg(drawing_data),unsafe_allow_html=True)
 token=fingerprint(d)
except (ValueError,TypeError,KeyError,ZeroDivisionError):token=None;st.caption('Complete geometria e ações para atualizar o esquema.')
if 'result' in st.session_state and st.session_state.result['input_fingerprint']!=token:
 st.session_state.pop('result');st.info('Entradas alteradas. Calcule novamente; os resultados e exportações anteriores foram retirados.')
calc_col,scan_col=st.columns(2)
with calc_col:calculate_clicked=st.button('Calcular diagnóstico 3D' if three_girt else 'Calcular verificações disponíveis',type='primary')
with scan_col:scan_clicked=st.button('Calcular todas as seções do catálogo',disabled=three_girt or claims_ue_catalog(d))
if claims_ue_catalog(d):st.caption('Comparação genérica do catálogo inativa nesta referência própria. Selecione outro Ue e aplique seu contorno explicitamente; fontes/capacidades não são transferidas por nome.')
if three_girt:st.caption('Comparação resistente do catálogo indisponível no sistema 3D: não há índices qualificados para ordenar aprovação. Trocar perfil exige redocumentar SC/linhas das conexões.')
if calculate_clicked:
 st.session_state.pop('result',None)
 try:
  with st.spinner('Calculando o caso informado…'):
   if three_girt:
    from tercas.three_girt_application import calculate as calculate_three_girts
    raw_result=calculate_three_girts(d)
   else:raw_result=calculate_batch(d) if d['load_mode']=='area' else calculate(d)
   from tercas.study_completion import complete_result
   st.session_state.result=complete_result(raw_result)
 except (ValueError,TypeError,KeyError,ArithmeticError) as exc:st.error('Não foi possível calcular: '+str(exc))
# Explicit snapshot; never scan on a normal input/profile edit.
if 'catalog_scan_state' in st.session_state and st.session_state.catalog_scan_state['fingerprint']!=token:
 st.session_state.pop('catalog_scan_state')
 st.info('Entradas alteradas: comparação anterior retirada. Inicie nova comparação quando desejar.')
# A conflicting pre-domain cache is historical, never resumed or re-qualified.
old_scan=st.session_state.get('catalog_scan_state')
if (old_scan and old_scan.get('model_domain_version')!=DOMAIN_VERSION
    and domain_explicit_panel_conflict(old_scan.get('inputs',{}))):
 st.session_state.catalog_scan_history=copy.deepcopy(old_scan)
 st.session_state.pop('catalog_scan_state')
if 'catalog_scan_history' in st.session_state:
 st.warning('Comparação histórica retirada dos resultados ativos: declaração física fora do domínio adotado. Nenhum perfil foi recalculado; o cache original foi preservado. Inicie nova comparação para avaliar as entradas atuais.')
 st.download_button('Baixar comparação histórica (JSON)',json.dumps(dict(historical_not_revalidated=True,original_state=st.session_state.catalog_scan_history),ensure_ascii=False,indent=2),file_name='comparacao_historica_nao_reavaliada.json',mime='application/json')
if scan_clicked:
 if token is None:st.error('Complete as entradas antes de comparar o catálogo.')
 else:
  st.session_state.catalog_scan_state=dict(model_domain_version=DOMAIN_VERSION,fingerprint=token,inputs=copy.deepcopy(d),rows=[],next_index=0,running=True,cancelled=False,elapsed_seconds=0.)

@st.fragment(run_every=0.5 if st.session_state.get('catalog_scan_state',{}).get('running') else None)
def catalog_comparison():
 state=st.session_state.get('catalog_scan_state')
 if not state:return
 total=len(catalog_labels())
 st.subheader('Comparação das seções — menor massa primeiro')
 st.caption('Utilização (%) = 100 × maior índice calculado, não porcentagem de aprovação. Pendências e hipóteses permanecem explícitas. No modo área, o peso próprio é recalculado para cada perfil. A comparação completa pode levar minutos.')
 if state['running'] and st.button('Cancelar comparação',key='cancel_catalog_scan'):
  state['running']=False;state['cancelled']=True
  st.rerun()
 if state['running']:
  # One section per fragment allows cooperative cancellation between sections.
  part=scan_catalog(state['inputs'],indices=[state['next_index']])
  state['rows'].extend(part['rows']);state['next_index']+=1
  state['elapsed_seconds']+=part['elapsed_seconds']
  state['running']=state['next_index']<total
  if not state['running']:st.rerun()
 done=state['next_index']
 st.progress(done/total,text=f'{done} de {total} perfis processados')
 if state['cancelled']:st.warning('Comparação interrompida: tabela parcial; perfis restantes não foram avaliados.')
 elif not state['running']:st.caption('Todos os perfis processados; dados insuficientes e verificações pendentes não foram ocultados.')
 rows_sorted=sorted(state['rows'],key=lambda r:(r['mass_kg_m'] if r['mass_kg_m'] is not None else float('inf'),r['profile'],r['catalog_index']))
 view=[{'Perfil':v['profile'],'Peso linear [kg/m]':v['mass_kg_m'],'Utilização máxima [%]':v['utilization_percent'],'Situação':v['status'],'Critério governante':v['governing_check'],'Combinação':v['governing_combination'],'Critérios calculados':v['evaluated_checks'],'Pendências':v['pending_checks']} for v in rows_sorted]
 if view:st.dataframe(display_frame(view),hide_index=True,width='stretch')
 with st.expander('Pendências e rastreabilidade da comparação'):
  st.caption('Ações externas diretas são mantidas; no novo contrato, o PP é recalculado para cada perfil. Entradas legadas preservam seus totais, sem PP adicional. Críticos manuais de outra seção não são transferidos. Nenhum resultado significa aprovação global.')
  for v in rows_sorted:
   if v['pending']:st.write(v['profile']+': '+'; '.join(v['pending']))
 st.download_button('Baixar comparação (JSON)',json.dumps(dict(schema='tercas_catalog_comparison_ui_v1',model_domain_version=state.get('model_domain_version'),input_fingerprint=state['fingerprint'],completed_count=done,requested_count=total,complete=done==total,cancelled=state['cancelled'],rows=rows_sorted,whole_member_approved=False),ensure_ascii=False,indent=2),file_name='comparacao_tercas.json',mime='application/json')
catalog_comparison()

if 'result' in st.session_state:render_results(st.session_state.result,d)

ue_family_loader(st,r,load)
ue_reference_loader(st,r,load)
reference_loader(st,r,load)
render_input_import(r)

st.caption('Método documentado na Rev07 e nos complementos identificados. Critérios resistentes e ELS parciais têm somente o alcance explicitamente exibido, inclusive no modelo 3D. Ligações não dimensionadas; introdução local depende do critério e detalhe registrados. Sem aprovação global nem crédito de travamento da telha.')


# Optional experimental laboratory, same page: do not trigger multipage widget cleanup.
with st.expander('Laboratório FSM experimental — separado do dimensionamento',expanded=False):
 st.caption('FSM experimental R01-20261101 — assinatura e modos, sem resistência automática')
 st.caption('Não altera entradas, catálogo ou resultados resistentes da terça. Sem transferência automática de críticos.')
 if not st.session_state.get('tercas_fsm_lab_open',False):
  if st.button('Abrir laboratório experimental',key='tercas_fsm_lab_activate'):
   st.session_state['tercas_fsm_lab_open']=True
 if st.session_state.get('tercas_fsm_lab_open',False):
  from experimental_fsm.app_integration.panel import render as render_fsm_laboratory
  render_fsm_laboratory(st,namespace='tercas_fsm_lab')


# Append creation controls after historical widgets; do not shift their order.
render_new_pierin_ue_study(st, defaults, for_new_study, load)
